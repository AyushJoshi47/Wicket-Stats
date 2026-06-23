import datetime
import difflib
import io
import hashlib
import hmac
import json
import os
import random
import re
import smtplib
import sqlite3
import urllib.parse
import urllib.request
import uuid
import base64
from email.mime.text import MIMEText
from functools import wraps
import image_mapping
import matplotlib
import numpy as np
import pandas as pd
import polars as pl
import rag_engine
import razorpay
import systemprompts
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, render_template, request, session, stream_with_context, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

matplotlib.use('Agg')  # must be before any other matplotlib import
import matplotlib.pyplot as plt



app = Flask(__name__)


def _validate_parquet_file(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing required parquet file: {path}")

    with open(path, "rb") as f:
        head = f.read(64)
        try:
            f.seek(-4, os.SEEK_END)
            footer = f.read(4)
        except OSError:
            footer = b""

    # Git LFS pointer files are plain text and are a common deployment trap.
    if head.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise RuntimeError(
            f"{path} is a Git LFS pointer file, not real parquet data. "
            "Install git-lfs on the server, run `git lfs install`, `git lfs pull`, "
            "then restart the app."
        )

    # A parquet file must end with the magic bytes "PAR1".
    if footer != b"PAR1":
        raise RuntimeError(
            f"{path} looks invalid/corrupted (missing parquet footer PAR1). "
            "Re-copy the file from a known good source and restart."
        )


def _read_pd_parquet(path):
    _validate_parquet_file(path)
    return pd.read_parquet(path)


def _read_pl_parquet(path):
    _validate_parquet_file(path)
    return pl.read_parquet(path)


def limit_key_user_or_ip():
    user_id = session.get('user_id')
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_remote_address()}"


def limit_key_email_or_ip():
    payload = request.get_json(silent=True) or {}
    email = (
        request.form.get('email')
        or payload.get('email')
        or ''
    ).strip().lower()
    ip = get_remote_address()
    return f"{ip}:{email or 'no-email'}"


limiter = Limiter(
    app=app,
    key_func=limit_key_user_or_ip,
    storage_uri="memory://",
    default_limits=[]
)


def json_safe(value):
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.floating, float)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if value is None:
        return None
    # pandas NA / NaT safe handling
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def _figure_to_data_url(fig, *, dpi=300):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight')
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('ascii')
    return f"data:image/png;base64,{encoded}"


def get_user_scope():
    user_id = session.get('user_id')
    if user_id:
        return f"user:{user_id}"
    anon_scope = session.get('anon_scope_id')
    if not anon_scope:
        anon_scope = uuid.uuid4().hex
        session['anon_scope_id'] = anon_scope
    return f"anon:{anon_scope}"

# ----------------------------- DATA LOADING / GLOBAL DATAFRAMES -----------------------------
pl.Config.set_float_precision(2)
pd.set_option('display.max_rows', None)
pd.set_option('display.precision', 3)
df = _read_pd_parquet('IPL.parquet')
df_new = _read_pd_parquet('IPL.parquet')
df_new = df_new[df_new['season'].isin(['2024', '2025'])]
df_2026 = _read_pd_parquet('2026.parquet')




dataframe = _read_pl_parquet('IPL.parquet')
df1 = _read_pd_parquet('2026.parquet')

df_2026['batting_team'] = df_2026['batting_team'].replace({
    'RCB': 'Royal Challengers Bangalore',
    'DC':  'Delhi Capitals',
    'PBKS': 'Punjab Kings',
    'MI':  'Mumbai Indians',
    'CSK': 'Chennai Super Kings',
    'KKR': 'Kolkata Knight Riders',
    'RR':  'Rajasthan Royals',
    'SRH': 'Sunrisers Hyderabad',
    'LSG': 'Lucknow Super Giants',
    'GT':  'Gujarat Titans',

})
df_2026['bowling_team'] = df_2026['bowling_team'].replace(
    {
    'RCB': 'Royal Challengers Bangalore',
    'DC':  'Delhi Capitals',
    'PBKS': 'Punjab Kings',
    'MI':  'Mumbai Indians',
    'CSK': 'Chennai Super Kings',
    'KKR': 'Kolkata Knight Riders',
    'RR':  'Rajasthan Royals',
    'SRH': 'Sunrisers Hyderabad',
    'LSG': 'Lucknow Super Giants',
    'GT':  'Gujarat Titans',
}
)

df['date'] = pd.to_datetime(df['date'])

load_dotenv()
app.secret_key = os.getenv('SECRET_KEY')  # required for session storage
SECRET_KEY = app.secret_key
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# ----------------------------- PLAN / BILLING CONFIG -----------------------------
PLAN_QUOTA = {
    'Basic': 5000,
    'Plus': 7000,
    'Premium': 12000
}
PLAN_REFILL = {
    'Basic': 500,
    'Plus': 1000,
    'Premium': 1200
}
PLAN_MAX_OUTPUT_TOKENS = {
    'Basic': 400,
    'Plus': 700,
    'Premium': 1200
}
REFILL_INTERVAL_HOURS = 6
PLAN_CHANGE_COOLDOWN_HOURS = 24
PLAN_PRICES = {
    'Basic': 0,
    'Plus': 49900,
    'Premium': 99900
}


# ----------------------------- PAYMENT + OTP HELPERS -----------------------------
def get_razorpay_creds():
    key_id = (os.getenv('RAZOR_PAY_KEY') or os.getenv('RAZORPAY_KEY_ID') or '').strip()
    key_secret = (os.getenv('RAZOR_PAY_SECRET') or os.getenv('RAZORPAY_KEY_SECRET') or '').strip()
    return key_id, key_secret


def get_razorpay_client():
    key_id, key_secret = get_razorpay_creds()
    if not key_id or not key_secret:
        return None, key_id, key_secret
    return razorpay.Client(auth=(key_id, key_secret)), key_id, key_secret


def validate_latest_email_otp(cursor, email, user_otp):
    otp_row = cursor.execute(
        "SELECT otp, created_at FROM otp_codes WHERE email = ? ORDER BY created_at DESC LIMIT 1",
        (email,)
    ).fetchone()
    if not otp_row:
        return False, 'No OTP found for this email'

    db_otp, created_at = otp_row
    if str(db_otp).strip() != str(user_otp).strip():
        return False, 'Invalid OTP'

    try:
        otp_time = datetime.datetime.fromisoformat(created_at)
    except Exception:
        return False, 'OTP data is invalid. Please request a new OTP.'

    if datetime.datetime.utcnow() - otp_time > datetime.timedelta(minutes=5):
        return False, 'OTP expired'

    return True, None

OTP_EXPIRY_SECONDS = 5 * 60

def get_otp_remaining_seconds(created_at):
    try:
        otp_time = datetime.datetime.fromisoformat(created_at)
    except Exception:
        return 0
    elapsed = (datetime.datetime.utcnow() - otp_time).total_seconds()
    remaining = OTP_EXPIRY_SECONDS - int(elapsed)
    return max(0, remaining)

def get_latest_otp_status(cursor, email):
    row = cursor.execute(
        "SELECT otp, created_at FROM otp_codes WHERE email = ? ORDER BY created_at DESC LIMIT 1",
        (email,)
    ).fetchone()
    if not row:
        return False, 0
    _, created_at = row
    remaining = get_otp_remaining_seconds(created_at)
    return remaining > 0, remaining

def create_and_store_email_otp(cursor, email):
    otp = f"{random.randint(100000, 999999)}"
    cursor.execute("DELETE FROM otp_codes WHERE email = ?", (email,))
    cursor.execute(
        "INSERT INTO otp_codes (email, otp) VALUES (?, ?)",
        (email, otp)
    )
    return otp

def send_otp_mail(email, otp):
    msg = MIMEText(f"Your OTP is: {otp}")
    msg['Subject'] = 'OTP Verification'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = email
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

def is_email_verified_for_signup(email):
    verified_email = (session.get('otp_verified_email') or '').strip().lower()
    return bool(verified_email) and verified_email == (email or '').strip().lower()

def _name_key(name):
    return re.sub(r'[^a-z0-9]+', '', str(name or '').strip().lower())

def resolve_player_headshot_id(player_name):
    # Single source of truth: image_mapping.batter_map().
    full_map = image_mapping.batter_map()

    if player_name in full_map:
        return full_map[player_name]

    target = _name_key(player_name)
    if not target:
        return None

    for k, v in full_map.items():
        if _name_key(k) == target:
            return v
    return None

def resolve_player_image_url(player_name):
    headshot_id = resolve_player_headshot_id(player_name)
    if str(headshot_id).isdigit():
        return f"https://documents.iplt20.com/ipl/IPLHeadshot2026/{headshot_id}.png"
    return "https://documents.iplt20.com/ipl/assets/images/Default-Men.png"

def normalize_plan(plan_value):
    plan_raw = (plan_value or '').strip().lower()
    if plan_raw == 'plus':
        return 'Plus'
    if plan_raw == 'premium':
        return 'Premium'
    return 'Basic'

def get_plan_quota(plan_value):
    return PLAN_QUOTA.get(normalize_plan(plan_value), PLAN_QUOTA['Basic'])

def get_plan_refill(plan_value):
    return PLAN_REFILL.get(normalize_plan(plan_value), PLAN_REFILL['Basic'])

def get_plan_output_limit(plan_value):
    return PLAN_MAX_OUTPUT_TOKENS.get(normalize_plan(plan_value), PLAN_MAX_OUTPUT_TOKENS['Basic'])


def _parse_db_timestamp(value):
    raw = str(value or '').strip()
    if not raw:
        return None

    # Handles both ISO strings and sqlite CURRENT_TIMESTAMP format.
    for parser in (
        lambda s: datetime.datetime.fromisoformat(s.replace('Z', '+00:00')),
        lambda s: datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S"),
    ):
        try:
            parsed = parser(raw)
            if parsed.tzinfo is not None:
                return parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return parsed
        except Exception:
            continue
    return None


def _plan_change_cooldown(cursor, user_id):
    row = cursor.execute(
        """
        SELECT new_plan, changed_at
        FROM plan_change_history
        WHERE user_id = ?
        ORDER BY datetime(changed_at) DESC, id DESC
        LIMIT 1
        """,
        (user_id,)
    ).fetchone()
    if not row:
        return 0, None

    changed_at = _parse_db_timestamp(row[1])
    if not changed_at:
        return 0, normalize_plan(row[0])

    cooldown = datetime.timedelta(hours=PLAN_CHANGE_COOLDOWN_HOURS)
    remaining = cooldown - (datetime.datetime.utcnow() - changed_at)
    remaining_seconds = max(0, int(remaining.total_seconds()))
    return remaining_seconds, normalize_plan(row[0])


def _format_wait_time(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600 + 59) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{max(1, minutes)}m"

def plan_response_policy(plan_value):
    plan = normalize_plan(plan_value)
    if plan == 'Premium':
        return (
            "Plan tier is Premium. Provide high-depth analysis with richer tactical detail, "
            "scenario comparisons, and actionable recommendations."
        )
    if plan == 'Plus':
        return (
            "Plan tier is Plus. Provide medium-depth analysis with concise reasoning and "
            "clear supporting points."
        )
    return (
        "Plan tier is Basic. Provide concise, focused answers with essential insights only. "
        "Avoid overly long responses."
    )

def fantasy_plan_policy(plan_value):
    plan = normalize_plan(plan_value)
    if plan == 'Premium':
        return (
            "FANTASY PLAN FORMAT (Premium): This tier MUST return exactly 3 teams.\n"
            "- Team 1 label MUST be 'Safe/Balanced'.\n"
            "- Team 2 label MUST be 'Aggressive/High-Variance'.\n"
            "- Team 3 label MUST be 'Differential/Contrarian'.\n"
            "- For each team include exactly 11 players, each with Team + Role (WK/BAT/AR/BOWL).\n"
            "- For each team include both Captain (C) and Vice-Captain (VC).\n"
            "- Add concise reasons and keep selections grounded in provided match data.\n"
            "- Even if user asks for one lineup, still return all 3 premium teams."
        )
    if plan == 'Plus':
        return (
            "FANTASY PLAN FORMAT (Plus): Return exactly 1 computed XI.\n"
            "- Include exactly 11 players with Team + Role (WK/BAT/AR/BOWL).\n"
            "- Include both Captain (C) and Vice-Captain (VC).\n"
            "- Do NOT include premium strategy labels (no Balanced/Aggressive/Differential sections).\n"
            "- Keep output concise and practical."
        )
    return (
        "FANTASY PLAN FORMAT (Basic): Return exactly 1 simple XI with a friendly heading.\n"
        "- Start with a short heading like: 'Here is your custom made XI team'.\n"
        "- Output exactly 11 player names with team names only.\n"
        "- Do NOT include Captain or Vice-Captain.\n"
        "- Add 1 short friendly note that users can choose any picks and make their own combination."
    )

def whatif_plan_policy(plan_value):
    plan = normalize_plan(plan_value)
    if plan == 'Premium':
        return (
            "WHAT-IF PLAN FORMAT (Premium): Detailed analyst output.\n"
            "- Include scenario summary, assumptions, key impact factors, and final outcome.\n"
            "- Use structured markdown sections with short bullets.\n"
            "- Include concise tactical recommendations at the end.\n"
            "- If user message is casual (e.g., hi/hello/thanks), respond warmly and briefly without forcing simulation."
        )
    if plan == 'Plus':
        return (
            "WHAT-IF PLAN FORMAT (Plus): Medium detail output.\n"
            "- Include what changed, expected impact, and final likely outcome.\n"
            "- Keep response compact and easy to scan.\n"
            "- If user message is casual (e.g., hi/hello/thanks), respond briefly and naturally."
        )
    return (
        "WHAT-IF PLAN FORMAT (Basic): Short output only.\n"
        "- Give a concise direct answer in 2-4 lines.\n"
        "- No long breakdowns unless user explicitly asks.\n"
        "- If user message is casual (e.g., hi/hello/thanks), reply with a short friendly greeting."
    )

def ensure_token_quota_row(conn, cursor, user_id, user_plan):
    normalized_plan = normalize_plan(user_plan)
    existing = cursor.execute(
        "SELECT user_id FROM token_quota WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    if existing:
        return
    cursor.execute(
        """
        INSERT INTO token_quota (user_id, plan, tokens_remaining, last_refill)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, normalized_plan, get_plan_quota(normalized_plan), datetime.datetime.utcnow().isoformat())
    )
    conn.commit()

def apply_refill_for_user(conn, cursor, user_id):
    row = cursor.execute(
        "SELECT tokens_remaining, plan, last_refill FROM token_quota WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    if not row:
        return None

    tokens_remaining, plan, last_refill = row
    plan = normalize_plan(plan)
    now = datetime.datetime.utcnow()

    try:
        last_refill_dt = datetime.datetime.fromisoformat(last_refill)
    except Exception:
        last_refill_dt = now

    interval_seconds = REFILL_INTERVAL_HOURS * 3600
    elapsed_seconds = (now - last_refill_dt).total_seconds()
    completed_intervals = int(max(0, elapsed_seconds // interval_seconds))

    if completed_intervals > 0:
        refill_amount = get_plan_refill(plan) * completed_intervals
        quota_cap = get_plan_quota(plan)
        tokens_remaining = min(quota_cap, int(tokens_remaining) + refill_amount)
        new_last_refill = last_refill_dt + datetime.timedelta(seconds=completed_intervals * interval_seconds)
        cursor.execute(
            """
            UPDATE token_quota
            SET tokens_remaining = ?, last_refill = ?
            WHERE user_id = ?
            """,
            (tokens_remaining, new_last_refill.isoformat(), user_id)
        )
        conn.commit()
        return (tokens_remaining, plan, new_last_refill.isoformat())

    return (int(tokens_remaining), plan, last_refill)

def get_token_status_for_user(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    user_plan_row = cursor.execute(
        "SELECT plan FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    user_plan = normalize_plan(user_plan_row[0] if user_plan_row else 'Basic')
    ensure_token_quota_row(conn, cursor, user_id, user_plan)

    quota_row = cursor.execute(
        "SELECT tokens_remaining, plan, last_refill FROM token_quota WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    if not quota_row:
        conn.close()
        return {'tokens_remaining': 0, 'plan': user_plan, 'next_refill': None}

    quota_tokens, quota_plan, _ = quota_row
    quota_plan = normalize_plan(quota_plan)
    if quota_plan != user_plan:
        updated_tokens = min(get_plan_quota(user_plan), int(quota_tokens))
        cursor.execute(
            "UPDATE token_quota SET plan = ?, tokens_remaining = ? WHERE user_id = ?",
            (user_plan, updated_tokens, user_id)
        )
        conn.commit()

    updated = apply_refill_for_user(conn, cursor, user_id)
    tokens_remaining, plan, last_refill = updated
    last_refill_dt = datetime.datetime.fromisoformat(last_refill)
    next_refill_dt = last_refill_dt + datetime.timedelta(hours=REFILL_INTERVAL_HOURS)

    conn.close()
    return {
        'tokens_remaining': int(tokens_remaining),
        'plan': normalize_plan(plan),
        'next_refill': next_refill_dt.isoformat()
    }

def consume_tokens(user_id, tokens_used):
    tokens_used = max(0, int(tokens_used or 0))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    user_plan_row = cursor.execute(
        "SELECT plan FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    user_plan = normalize_plan(user_plan_row[0] if user_plan_row else 'Basic')
    ensure_token_quota_row(conn, cursor, user_id, user_plan)
    apply_refill_for_user(conn, cursor, user_id)
    cursor.execute(
        """
        UPDATE token_quota
        SET tokens_remaining = MAX(0, tokens_remaining - ?)
        WHERE user_id = ?
        """,
        (tokens_used, user_id)
    )
    conn.commit()
    conn.close()
    return get_token_status_for_user(user_id)

def log_user_activity(user_id, activity_type, title, thread_id=None, reference_id=None, payload=None):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO user_recent_activities (user_id, activity_type, title, thread_id, reference_id, payload)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            activity_type,
            title,
            thread_id,
            reference_id,
            json.dumps(payload or {})
        )
    )
    conn.commit()
    conn.close()

def require_tokens(estimated_cost=100):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

            user_id = session['user_id']
            status = get_token_status_for_user(user_id)
            if status['tokens_remaining'] < estimated_cost:
                return jsonify({
                    'status': 'error',
                    'error_code': 'INSUFFICIENT_TOKENS',
                    'message': f"Not enough tokens. You have {status['tokens_remaining']} left.",
                    'tokens_remaining': status['tokens_remaining'],
                    'plan': status['plan'],
                    'next_refill': status['next_refill']
                }), 402
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ----------------------------- DATABASE BOOTSTRAP -----------------------------
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            plan TEXT,
            password TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );''')
       

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teamname (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team TEXT,
            user_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );''')
        
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            otp TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS token_quota (
            user_id INTEGER PRIMARY KEY,
            plan TEXT NOT NULL DEFAULT 'Basic',
            tokens_remaining INTEGER NOT NULL,
            last_refill TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_recent_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            title TEXT NOT NULL,
            thread_id TEXT,
            reference_id INTEGER,
            payload TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );''')
    cursor.execute('''
       CREATE TABLE IF NOT EXISTS custom_matchups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,               
    matchup_name TEXT NOT NULL,
    teamA TEXT NOT NULL,
    teamB TEXT NOT NULL,
    teamA_players TEXT NOT NULL,   
    teamB_players TEXT,            
    metrics TEXT,
    teamA_bat_stats TEXT,
    teamA_bat_total TEXT,          
    teamA_bowl_stats TEXT,
    teamA_bowl_total TEXT,
    teamB_bat_stats TEXT,
    teamB_bat_total TEXT,
    teamB_bowl_stats TEXT,
    teamB_bowl_total TEXT,
    teamScores TEXT,
    winner TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plan_change_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            old_plan TEXT NOT NULL,
            new_plan TEXT NOT NULL,
            changed_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS billing_refs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            flow TEXT NOT NULL,
            razorpay_order_id TEXT NOT NULL,
            razorpay_payment_id TEXT NOT NULL,
            razorpay_signature TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE (razorpay_order_id, razorpay_payment_id)
        );
    ''')

    cursor.execute('''
        INSERT INTO token_quota (user_id, plan, tokens_remaining, last_refill)
        SELECT
            u.id,
            CASE lower(COALESCE(u.plan, 'basic'))
                WHEN 'plus' THEN 'Plus'
                WHEN 'premium' THEN 'Premium'
                ELSE 'Basic'
            END AS normalized_plan,
            CASE lower(COALESCE(u.plan, 'basic'))
                WHEN 'plus' THEN 7000
                WHEN 'premium' THEN 12000
                ELSE 5000
            END AS initial_tokens,
            CURRENT_TIMESTAMP
        FROM users u
        LEFT JOIN token_quota t ON t.user_id = u.id
        WHERE t.user_id IS NULL
    ''')
    
    conn.commit()
    conn.close()

init_db()




replacements = {
    'Royal Challengers Bengaluru': 'Royal Challengers Bangalore',
    'Delhi Daredevils': 'Delhi Capitals',
    'Punjab Kings': 'Kings XI Punjab',
}

replacement = {
    "2007/08": "2008",
    "2009/10": "2010", 
    "2020/21": "2020"
}

dataframe = dataframe.with_columns(
    pl.col(['batting_team', 'bowling_team']).replace(replacements)
)

dataframe = dataframe.with_columns(
    pl.col("season").replace(replacement)
)
df_new['batting_team'] = df_new['batting_team'].replace({
    'Royal Challengers Bengaluru': 'Royal Challengers Bangalore',
    'Delhi Daredevils':            'Delhi Capitals',
    'Punjab Kings':                'Kings XI Punjab',
})
df_new['bowling_team'] = df_new['bowling_team'].replace({
    'Royal Challengers Bengaluru': 'Royal Challengers Bangalore',
    'Delhi Daredevils':            'Delhi Capitals',
    'Punjab Kings':                'Kings XI Punjab',
})
df_new['season'] = (
    df_new['season']
    .replace({'2007/08': '2008', '2009/10': '2010', '2020/21': '2020'})
    .astype(str)
)
# Dedicated 2024-2025 slice for Top Scorer predictor.
# Keep separate from df_new, which is reused later for broader historical merges.
df_recent_2425 = df_new.copy()


# ===== Normalize team names here =====
df['batting_team'] = df['batting_team'].replace({'Royal Challengers Bengaluru': 'Royal Challengers Bangalore'})
df['bowling_team'] = df['bowling_team'].replace({'Royal Challengers Bengaluru': 'Royal Challengers Bangalore'})
df['match_won_by'] = df['match_won_by'].replace({'Royal Challengers Bengaluru': 'Royal Challengers Bangalore'})
df['toss_winner'] = df['toss_winner'].replace({'Royal Challengers Bengaluru': 'Royal Challengers Bangalore'})
# =====================================
df['batting_team'] = df['batting_team'].replace({'Delhi Daredevils': 'Delhi Capitals'})
df['bowling_team'] = df['bowling_team'].replace({'Delhi Daredevils': 'Delhi Capitals'})
df['match_won_by'] = df['match_won_by'].replace({'Delhi Daredevils': 'Delhi Capitals'})
df['toss_winner'] = df['toss_winner'].replace({'Delhi Daredevils': 'Delhi Capitals'})
# =====================================
df['batting_team'] = df['batting_team'].replace({'Punjab Kings': 'Kings XI Punjab'})
df['bowling_team'] = df['bowling_team'].replace({'Punjab Kings': 'Kings XI Punjab'})
df['match_won_by'] = df['match_won_by'].replace({'Punjab Kings': 'Kings XI Punjab'})
df['toss_winner'] = df['toss_winner'].replace({'Punjab Kings': 'Kings XI Punjab'})
# =====================================
df['season'] = df['season'].replace({'2007/08': '2008'})
df['season'] = df['season'].replace({'2009/10': '2010'})
df['season'] = df['season'].replace({'2020/21': '2020'})    

# Updated on 2026-06-14 12:00:33 +05:30: unified historical (<=2025) + 2026 merge helpers for index/compare/teamgraph endpoints.
def _season_start_year(val, fallback_date=None):
    text = str(val) if val is not None else ""
    m = re.search(r"(19|20)\d{2}", text)
    if m:
        return int(m.group(0))
    if pd.notna(fallback_date):
        return int(pd.to_datetime(fallback_date).year)
    return None

def _safe_int_series(series, default=0):
    return pd.to_numeric(series, errors='coerce').fillna(default).astype(int)

def _safe_float_series(series, default=0.0):
    return pd.to_numeric(series, errors='coerce').fillna(default).astype(float)

def _normalize_2026_for_combined(raw_2026_df):
    d = raw_2026_df.copy()
    d['date'] = pd.to_datetime(d['date'], errors='coerce')
    d['season'] = '2026'
    d['match_id'] = d['match_no'].astype(str)
    d['batting_team'] = d['batting_team'].replace({
        'RCB': 'Royal Challengers Bangalore',
        'DC': 'Delhi Capitals',
        'PBKS': 'Kings XI Punjab',
        'MI': 'Mumbai Indians',
        'CSK': 'Chennai Super Kings',
        'KKR': 'Kolkata Knight Riders',
        'RR': 'Rajasthan Royals',
        'SRH': 'Sunrisers Hyderabad',
        'LSG': 'Lucknow Super Giants',
        'GT': 'Gujarat Titans',
    })
    d['bowling_team'] = d['bowling_team'].replace({
        'RCB': 'Royal Challengers Bangalore',
        'DC': 'Delhi Capitals',
        'PBKS': 'Kings XI Punjab',
        'MI': 'Mumbai Indians',
        'CSK': 'Chennai Super Kings',
        'KKR': 'Kolkata Knight Riders',
        'RR': 'Rajasthan Royals',
        'SRH': 'Sunrisers Hyderabad',
        'LSG': 'Lucknow Super Giants',
        'GT': 'Gujarat Titans',
    })

    d['runs_batter'] = _safe_int_series(d.get('runs_of_bat', 0), 0)
    d['runs_extras'] = _safe_int_series(d.get('extras', 0), 0)
    d['runs_total'] = d['runs_batter'] + d['runs_extras']
    d['runs_bowler'] = d['runs_total']

    wides = _safe_float_series(d.get('wide', 0), 0.0)
    no_balls = _safe_float_series(d.get('noballs', 0), 0.0) if 'noballs' in d.columns else 0
    legal_ball = ((wides == 0) & (no_balls == 0)).astype(int)
    d['balls_faced'] = legal_ball
    d['valid_ball'] = legal_ball

    d['batter'] = d.get('striker')
    d['non_striker'] = None
    d['player_out'] = d.get('player_dismissed')
    d['wicket_kind'] = d.get('wicket_type')
    d['fielders'] = d.get('fielder')
    d['ball_no'] = d.get('over')
    d['over'] = _safe_float_series(d.get('over', 0), 0.0)
    d['_row_order'] = range(len(d))

    over_as_text = d['over'].astype(str)
    ball_part = over_as_text.str.split('.').str[-1]
    ball_part = pd.to_numeric(ball_part, errors='coerce').fillna(0).astype(int)
    d['ball'] = ball_part

    non_bowler_wickets = {
        'run out', 'retired hurt', 'retired out', 'obstructing the field',
        'hit wicket', 'retired'
    }
    wk = d['wicket_kind'].fillna('').astype(str).str.strip().str.lower()
    d['bowler_wicket'] = ((wk != '') & (~wk.isin(non_bowler_wickets))).astype(int)
    d['_team_wicket_event'] = ((wk != '') & (wk != 'retired hurt')).astype(int)

    # Build cumulative innings scoreboard fields consumed by history APIs.
    d = d.sort_values(['match_id', 'innings', '_row_order']).copy()
    d['team_runs'] = d.groupby(['match_id', 'innings'])['runs_total'].cumsum().astype(int)
    d['team_wicket'] = d.groupby(['match_id', 'innings'])['_team_wicket_event'].cumsum().astype(int)

    innings_totals = (
        d.groupby(['match_id', 'batting_team'], as_index=False)['runs_total']
        .sum()
        .sort_values(['match_id', 'runs_total'], ascending=[True, False])
    )

    winners = []
    for match_id, grp in innings_totals.groupby('match_id'):
        if grp.empty:
            winners.append((match_id, 'Unknown'))
            continue
        top_score = grp.iloc[0]['runs_total']
        top_rows = grp[grp['runs_total'] == top_score]
        winner = 'Unknown' if len(top_rows) != 1 else top_rows.iloc[0]['batting_team']
        winners.append((match_id, winner))
    winner_df = pd.DataFrame(winners, columns=['match_id', 'match_won_by'])
    d = d.merge(winner_df, on='match_id', how='left')
    d['match_won_by'] = d['match_won_by'].fillna('Unknown')
    d['toss_winner'] = None
    d['toss_decision'] = None
    d['innings'] = _safe_int_series(d.get('innings', 0), 0)
    d = d.drop(columns=['_row_order', '_team_wicket_event'], errors='ignore')
    return d

TEAM_ALIASES = {
    'Royal Challengers Bangalore': {'Royal Challengers Bangalore', 'Royal Challengers Bengaluru'},
    'Kings XI Punjab': {'Kings XI Punjab', 'Punjab Kings'},
    'Delhi Capitals': {'Delhi Capitals', 'Delhi Daredevils'},
}
TEAM_ALIAS_LOOKUP = {}
for canonical_name, alias_set in TEAM_ALIASES.items():
    for alias in alias_set:
        TEAM_ALIAS_LOOKUP[alias.strip().lower()] = set(alias_set)

def get_team_aliases(team_name):
    key = str(team_name or '').strip().lower()
    if not key:
        return set()
    return TEAM_ALIAS_LOOKUP.get(key, {str(team_name).strip()})

df_hist = df.copy()
df_hist['season_year'] = df_hist.apply(lambda r: _season_start_year(r.get('season'), r.get('date')), axis=1)
df_hist = df_hist[df_hist['season_year'].fillna(0).astype(int) <= 2025].copy()

df_new = df_hist.copy()
df_2026_combined = _normalize_2026_for_combined(df_2026)

_all_cols = sorted(set(df_hist.columns).union(set(df_2026_combined.columns)))
df_all = pd.concat(
    [df_hist.reindex(columns=_all_cols), df_2026_combined.reindex(columns=_all_cols)],
    ignore_index=True
)


def _build_player_name_lookup():
    lookup = {}
    for col in ['batter', 'bowler', 'non_striker', 'player_out']:
        if col not in df_all.columns:
            continue
        series = df_all[col].dropna().astype(str)
        for raw in series:
            name = raw.strip()
            if not name:
                continue
            key = _name_key(name)
            if not key:
                continue
            lookup.setdefault(key, name)
    return lookup


PLAYER_NAME_LOOKUP = _build_player_name_lookup()


def resolve_player_name(player_name):
    raw = str(player_name or '').strip()
    if not raw:
        return raw
    key = _name_key(raw)
    if key in PLAYER_NAME_LOOKUP:
        return PLAYER_NAME_LOOKUP[key]

    # Typo-tolerant fallback (e.g., "Viraat Kohli" -> "Virat Kohli")
    closest = difflib.get_close_matches(key, PLAYER_NAME_LOOKUP.keys(), n=1, cutoff=0.88)
    if closest:
        return PLAYER_NAME_LOOKUP[closest[0]]
    return raw

# Build a typed Polars view only for bowler pipeline fields.
# This avoids Arrow conversion failures from unrelated mixed-type object columns in df_all.
_bowler_view_cols = ['match_id', 'season', 'bowler', 'bowling_team', 'bowler_wicket', 'balls_faced', 'runs_bowler', 'over']
_bowler_view = df_all.reindex(columns=_bowler_view_cols).copy()
_bowler_view['match_id'] = _bowler_view['match_id'].astype(str)
_bowler_view['season'] = _bowler_view['season'].astype(str)
_bowler_view['bowler'] = _bowler_view['bowler'].fillna('').astype(str)
_bowler_view['bowling_team'] = _bowler_view['bowling_team'].fillna('').astype(str)
_bowler_view['bowler_wicket'] = pd.to_numeric(_bowler_view['bowler_wicket'], errors='coerce').fillna(0).astype(int)
_bowler_view['balls_faced'] = pd.to_numeric(_bowler_view['balls_faced'], errors='coerce').fillna(0).astype(int)
_bowler_view['runs_bowler'] = pd.to_numeric(_bowler_view['runs_bowler'], errors='coerce').fillna(0).astype(float)
_bowler_view['over'] = pd.to_numeric(_bowler_view['over'], errors='coerce').fillna(0).astype(float)
dataframe_all = pl.from_pandas(_bowler_view)

# -------- Match history dataset (pandas only) --------
HISTORY_COLUMNS = [
    'match_id', 'season', 'date', 'innings', 'batting_team', 'bowling_team',
    'team_runs', 'team_wicket', 'match_won_by', 'win_outcome', 'toss_winner',
    'toss_decision', 'venue', 'city', 'event_name', 'player_of_match', 'umpire',
    'stage', 'match_type', 'result_type', 'method', 'batter', 'bowler',
    'runs_batter', 'runs_total', 'runs_extras', 'runs_bowler', 'valid_ball',
    'extra_type', 'wicket_kind', 'player_out', 'fielders', 'ball_no', 'over',
    'bowler_wicket', 'overs'
]
history_df = df_all.reindex(columns=HISTORY_COLUMNS).copy()
history_df['season'] = history_df['season'].astype(str)
history_df['date'] = pd.to_datetime(history_df['date'], errors='coerce')

history_match_meta = history_df[
    [
        'match_id', 'season', 'date', 'match_won_by', 'win_outcome', 'toss_winner',
        'toss_decision', 'venue', 'city', 'event_name', 'player_of_match', 'umpire',
        'stage', 'match_type', 'result_type', 'method'
    ]
].drop_duplicates(subset=['match_id']).copy()

history_innings_scores = (
    history_df
    .groupby(['match_id', 'season', 'innings', 'batting_team'], as_index=False)
    .agg(score=('team_runs', 'max'), wickets=('team_wicket', 'max'))
)

history_season_cards = (
    history_match_meta
    .groupby('season', as_index=False)
    .agg(matches=('match_id', 'nunique'))
)
history_season_winners = (
    history_match_meta
    .sort_values(['season', 'date', 'match_id'])
    .groupby('season', as_index=False)
    .tail(1)[['season', 'match_won_by']]
    .rename(columns={'match_won_by': 'season_winner'})
)
history_season_cards = history_season_cards.merge(history_season_winners, on='season', how='left')
history_season_cards['season_sort'] = pd.to_numeric(history_season_cards['season'], errors='coerce')
history_season_cards = history_season_cards.sort_values('season_sort').drop(columns=['season_sort'])

def _format_overs(balls):
    balls = int(balls or 0)
    return f"{balls // 6}.{balls % 6}"

def _contains_extra(series, token):
    pattern = rf'(^|,\s*){token}($|,\s*)'
    return series.fillna('').str.lower().str.contains(pattern, regex=True)

def _dismissal_text(row):
    kind = str(row.get('wicket_kind', '') or '').strip().lower()
    bowler = str(row.get('bowler', '') or '').strip()
    fielders = str(row.get('fielders', '') or '').strip()

    if kind == 'not out':
        return 'not out'
    if kind == 'caught and bowled':
        return f"c & b {bowler}" if bowler else 'caught and bowled'
    if kind == 'caught':
        if fielders and bowler:
            return f"c {fielders} b {bowler}"
        if bowler:
            return f"c b {bowler}"
        return 'caught'
    if kind == 'bowled':
        return f"b {bowler}" if bowler else 'bowled'
    if kind == 'lbw':
        return f"lbw b {bowler}" if bowler else 'lbw'
    if kind == 'stumped':
        if fielders and bowler:
            return f"st {fielders} b {bowler}"
        return 'stumped'
    if kind == 'run out':
        return f"run out ({fielders})" if fielders and fielders.lower() != 'none' else 'run out'
    if kind:
        return kind
    return 'out'

def _build_innings_scorecard(innings_df, target_runs=None):
    innings_df = innings_df.copy().sort_values('ball_no')
    batting_team = innings_df['batting_team'].iloc[0] if not innings_df.empty else None
    bowling_team = innings_df['bowling_team'].iloc[0] if not innings_df.empty else None
    max_overs = int(innings_df['overs'].dropna().iloc[0]) if innings_df['overs'].notna().any() else 20

    batter_order = (
        innings_df.groupby('batter', as_index=False)['ball_no']
        .min()
        .sort_values('ball_no')
        .reset_index(drop=True)
    )

    batter_stats = innings_df.groupby('batter', as_index=False).agg(
        runs=('runs_batter', 'sum'),
        fours=('runs_batter', lambda x: int((x == 4).sum())),
        sixes=('runs_batter', lambda x: int((x == 6).sum()))
    )
    batter_stats = batter_order[['batter']].merge(batter_stats, on='batter', how='left')

    wide_mask = _contains_extra(innings_df['extra_type'], 'wides')
    faced_mask = ~wide_mask
    balls_faced = (
        innings_df[faced_mask]
        .groupby('batter', as_index=False)
        .size()
        .rename(columns={'size': 'balls'})
    )
    batter_stats = batter_stats.merge(balls_faced, on='batter', how='left')
    batter_stats['balls'] = batter_stats['balls'].fillna(0).astype(int)
    batter_stats['sr'] = batter_stats.apply(
        lambda r: round((r['runs'] * 100.0 / r['balls']), 2) if r['balls'] > 0 else 0.0,
        axis=1
    )

    dismissals = innings_df[innings_df['player_out'].notna()].copy()
    dismissals = dismissals[dismissals['player_out'].astype(str).str.strip() != '']
    dismissals = dismissals.sort_values('ball_no').drop_duplicates(subset=['player_out'], keep='first')
    dismissal_map = {
        str(row['player_out']): _dismissal_text(row)
        for _, row in dismissals.iterrows()
    }

    batting_rows = []
    for _, row in batter_stats.iterrows():
        batter_name = str(row['batter'])
        dismissal = dismissal_map.get(batter_name, 'not out')
        batting_rows.append({
            'batter': batter_name,
            'dismissal': dismissal,
            'r': int(row['runs']),
            'b': int(row['balls']),
            'm': '-',
            '4s': int(row['fours']),
            '6s': int(row['sixes']),
            'sr': float(row['sr'])
        })

    wicket_events = innings_df[innings_df['player_out'].notna()].sort_values('ball_no')
    fall_of_wickets = []
    wicket_no = 0
    for _, row in wicket_events.iterrows():
        player_out = str(row.get('player_out', '') or '').strip()
        if not player_out:
            continue
        wicket_no += 1
        runs_at_wicket = int(row['team_runs']) if pd.notna(row['team_runs']) else 0
        ball_marker = str(row['ball_no']) if pd.notna(row['ball_no']) else '-'
        fall_of_wickets.append(f"{wicket_no}-{runs_at_wicket} ({player_out}, {ball_marker} ov)")

    legal_balls = int((innings_df['valid_ball'].fillna(0).astype(int) == 1).sum())
    total_runs = int(innings_df['team_runs'].max()) if innings_df['team_runs'].notna().any() else 0
    total_wkts = int(innings_df['team_wicket'].max()) if innings_df['team_wicket'].notna().any() else 0
    rr = round(total_runs / (legal_balls / 6), 2) if legal_balls else 0.0

    no_ball_mask = _contains_extra(innings_df['extra_type'], 'noballs')
    bye_mask = _contains_extra(innings_df['extra_type'], 'byes') & ~_contains_extra(innings_df['extra_type'], 'legbyes')
    legbye_mask = _contains_extra(innings_df['extra_type'], 'legbyes')
    penalty_mask = _contains_extra(innings_df['extra_type'], 'penalty')

    extras = {
        'w': int(innings_df.loc[wide_mask, 'runs_extras'].fillna(0).sum()),
        'nb': int(innings_df.loc[no_ball_mask, 'runs_extras'].fillna(0).sum()),
        'b': int(innings_df.loc[bye_mask, 'runs_extras'].fillna(0).sum()),
        'lb': int(innings_df.loc[legbye_mask, 'runs_extras'].fillna(0).sum()),
        'p': int(innings_df.loc[penalty_mask, 'runs_extras'].fillna(0).sum())
    }
    extras['total'] = int(sum(extras.values()))

    bowling_group = innings_df.groupby('bowler', as_index=False).agg(
        legal_balls=('valid_ball', lambda x: int((x.fillna(0).astype(int) == 1).sum())),
        runs=('runs_bowler', lambda x: int(x.fillna(0).sum())),
        wickets=('bowler_wicket', lambda x: int(x.fillna(0).sum())),
        dots=('runs_total', lambda x: int((x.fillna(0) == 0).sum()))
    )

    bowling_group = bowling_group.merge(
        innings_df[wide_mask].groupby('bowler', as_index=False)['runs_extras'].sum().rename(columns={'runs_extras': 'wd'}),
        on='bowler',
        how='left'
    ).merge(
        innings_df[no_ball_mask].groupby('bowler', as_index=False)['runs_extras'].sum().rename(columns={'runs_extras': 'nb'}),
        on='bowler',
        how='left'
    )

    bowling_group['wd'] = bowling_group['wd'].fillna(0).astype(int)
    bowling_group['nb'] = bowling_group['nb'].fillna(0).astype(int)

    over_runs = innings_df.groupby(['bowler', 'over'], as_index=False).agg(
        over_runs=('runs_bowler', lambda x: int(x.fillna(0).sum())),
        legal_balls=('valid_ball', lambda x: int((x.fillna(0).astype(int) == 1).sum()))
    )
    maiden_map = (
        over_runs[(over_runs['over_runs'] == 0) & (over_runs['legal_balls'] >= 6)]
        .groupby('bowler')
        .size()
        .to_dict()
    )

    bowling_rows = []
    for _, row in bowling_group.iterrows():
        balls = int(row['legal_balls'])
        runs = int(row['runs'])
        econ = round(runs / (balls / 6), 2) if balls else 0.0
        bowling_rows.append({
            'bowler': str(row['bowler']),
            'o': _format_overs(balls),
            'm': int(maiden_map.get(row['bowler'], 0)),
            'r': runs,
            'w': int(row['wickets']),
            'econ': float(econ),
            '0s': int(row['dots']),
            'wd': int(row['wd']),
            'nb': int(row['nb'])
        })

    return {
        'batting_team': batting_team,
        'bowling_team': bowling_team,
        'header': (
            f"{batting_team} (T: {target_runs} runs from {max_overs} ovs)"
            if target_runs is not None
            else f"{batting_team} ({max_overs} ovs maximum)"
        ),
        'batting': batting_rows,
        'bowling': bowling_rows,
        'extras': extras,
        'total': {
            'runs': total_runs,
            'wickets': total_wkts,
            'overs': _format_overs(legal_balls),
            'run_rate': rr
        },
        'fall_of_wickets': fall_of_wickets
    }


# ----------------------------- PAGE ROUTES (TEMPLATES) -----------------------------
@app.route('/')
def index():
    teams = df['batting_team'].unique().tolist()
    logged_in = 'user_id' in session  # True if user is logged in
    return render_template('index.html', teams=teams, logged_in=logged_in)

@app.route("/whatif")
def whatif():
    return render_template('whatif.html')

@app.route('/team_graph')
def team_graph():
    return render_template('teamgraph.html')

@app.route('/newindex')
def newindex():
    return render_template('new_index.html')

@app.route('/player_index1')
def player_index1():
    return render_template('player_index.html')

@app.route('/fantasy')
def fantasy():
    return render_template('fantasy.html')

@app.route('/bowlerindex')
def bowlerindex():
    return render_template('bowler_index.html')

@app.route('/player_comparison')
def player_comparison():
    return render_template('comparison.html')

@app.route('/new_comparison')
def new_comparison():
    return render_template('new_comparison.html')

@app.route('/new_teamgraph')
def new_teamgraph():
    return render_template('new_teamgraph.html')

@app.route('/top_scorer_page')
def top_scorer_page():
    return render_template('top_score.html')

@app.route('/predict_winner_page')
def predict_winner_page():
    # Updated on 2026-06-14 13:46:10 +05:30: restrict predictor inputs to the same 10 active teams used in Top Scorer page.
    teams = [
        "Chennai Super Kings",
        "Delhi Capitals",
        "Gujarat Titans",
        "Kolkata Knight Riders",
        "Lucknow Super Giants",
        "Mumbai Indians",
        "Kings XI Punjab",
        "Rajasthan Royals",
        "Royal Challengers Bangalore",
        "Sunrisers Hyderabad",
    ]
    logged_in = 'user_id' in session
    return render_template('predict_winner.html', teams=teams, logged_in=logged_in)
 
@app.route('/history')
def history():
    logged_in = 'user_id' in session
    return render_template('history.html', logged_in=logged_in)

# ----------------------------- HISTORY APIs -----------------------------
@app.route('/api/history/seasons', methods=['GET'])
def history_seasons():
    seasons = [
        {
            'season': str(row['season']),
            'matches': int(row['matches']),
            'season_winner': str(row['season_winner']) if pd.notna(row['season_winner']) else None
        }
        for _, row in history_season_cards.iterrows()
    ]
    return jsonify({'status': 'success', 'seasons': seasons})

@app.route('/api/history/matches', methods=['GET'])
def history_matches():
    season = str(request.args.get('season', '')).strip()
    if not season:
        return jsonify({'status': 'error', 'message': 'season is required'}), 400

    season_meta = history_match_meta[history_match_meta['season'] == season].copy()
    if season_meta.empty:
        return jsonify({'status': 'success', 'season': season, 'matches': []})

    season_scores = history_innings_scores[history_innings_scores['season'] == season].copy()
    season_meta = season_meta.sort_values(['date', 'match_id'])

    matches = []
    for _, meta_row in season_meta.iterrows():
        match_id = meta_row['match_id']
        innings_rows = season_scores[season_scores['match_id'] == match_id].sort_values('innings')
        if innings_rows.empty:
            continue

        innings_payload = []
        for _, score_row in innings_rows.iterrows():
            innings_payload.append({
                'innings': int(score_row['innings']) if pd.notna(score_row['innings']) else None,
                'team': str(score_row['batting_team']),
                'runs': int(score_row['score']) if pd.notna(score_row['score']) else 0,
                'wickets': int(score_row['wickets']) if pd.notna(score_row['wickets']) else 0
            })

        team1 = innings_payload[0] if len(innings_payload) > 0 else None
        team2 = innings_payload[1] if len(innings_payload) > 1 else None

        matches.append({
            'match_id': int(match_id) if pd.notna(match_id) else None,
            'season': season,
            'date': meta_row['date'].strftime('%Y-%m-%d') if pd.notna(meta_row['date']) else None,
            'winner': str(meta_row['match_won_by']) if pd.notna(meta_row['match_won_by']) else None,
            'result': str(meta_row['win_outcome']) if pd.notna(meta_row['win_outcome']) else None,
            'toss_winner': str(meta_row['toss_winner']) if pd.notna(meta_row['toss_winner']) else None,
            'toss_decision': str(meta_row['toss_decision']) if pd.notna(meta_row['toss_decision']) else None,
            'venue': str(meta_row['venue']) if pd.notna(meta_row['venue']) else None,
            'city': str(meta_row['city']) if pd.notna(meta_row['city']) else None,
            'team1': team1,
            'team2': team2,
            'innings_scores': innings_payload
        })

    return jsonify({'status': 'success', 'season': season, 'matches': matches})

@app.route('/api/history/match-scorecard', methods=['GET'])
def history_match_scorecard():
    match_id_raw = str(request.args.get('match_id', '')).strip()
    if not match_id_raw:
        return jsonify({'status': 'error', 'message': 'match_id is required'}), 400

    try:
        match_id = int(match_id_raw)
    except ValueError:
        return jsonify({'status': 'error', 'message': 'match_id must be an integer'}), 400

    match_df = history_df[history_df['match_id'] == match_id].copy()
    if match_df.empty:
        return jsonify({'status': 'error', 'message': 'match not found'}), 404

    match_df = match_df.sort_values(['innings', 'ball_no'])
    meta = history_match_meta[history_match_meta['match_id'] == match_id].head(1)
    if meta.empty:
        return jsonify({'status': 'error', 'message': 'match metadata unavailable'}), 404
    meta_row = meta.iloc[0]

    def _pick_meta_value(field_name):
        series = match_df[field_name] if field_name in match_df.columns else pd.Series(dtype=object)
        for value in series:
            if pd.isna(value):
                continue
            text = str(value).strip()
            if not text or text.lower() in {'nan', 'none', 'null'}:
                continue
            return text
        fallback = meta_row[field_name] if field_name in meta_row.index else None
        if pd.notna(fallback):
            text = str(fallback).strip()
            if text and text.lower() not in {'nan', 'none', 'null'}:
                return text
        return None

    def _clean_display(text):
        if text is None:
            return None
        t = str(text).strip()
        if not t or t.lower() in {'nan', 'none', 'null', 'n/a', 'na', 'unknown'}:
            return None
        return t

    def _derive_result_type(result_margin):
        margin = _clean_display(result_margin)
        if not margin:
            return None
        lower = margin.lower()
        if 'wicket' in lower:
            return 'By Wickets'
        if 'run' in lower:
            return 'By Runs'
        if 'tie' in lower:
            return 'Tie'
        if 'no result' in lower or 'abandon' in lower:
            return 'No Result'
        return 'Win'

    innings_payload = []
    innings_values = sorted([int(x) for x in match_df['innings'].dropna().unique().tolist()])
    first_innings_total = None
    for inn in innings_values:
        innings_df = match_df[match_df['innings'] == inn].copy()
        scorecard = _build_innings_scorecard(
            innings_df,
            target_runs=(first_innings_total + 1 if inn == 2 and first_innings_total is not None else None)
        )
        if inn == 1:
            first_innings_total = scorecard['total']['runs']
        scorecard['innings'] = inn
        innings_payload.append(scorecard)

    season = str(meta_row['season'])
    season_final = (
        history_match_meta[history_match_meta['season'] == season]
        .sort_values(['date', 'match_id'])
        .tail(1)
    )
    season_winner = None
    if not season_final.empty and pd.notna(season_final.iloc[0]['match_won_by']):
        season_winner = str(season_final.iloc[0]['match_won_by'])

    winner = _clean_display(_pick_meta_value('match_won_by'))
    win_outcome = _clean_display(_pick_meta_value('win_outcome'))
    toss_winner = _clean_display(_pick_meta_value('toss_winner'))
    toss_decision = _clean_display(_pick_meta_value('toss_decision'))
    venue = _clean_display(_pick_meta_value('venue'))
    city = _clean_display(_pick_meta_value('city'))
    event_name = _clean_display(_pick_meta_value('event_name'))
    player_of_match = _clean_display(_pick_meta_value('player_of_match'))
    match_type = _clean_display(_pick_meta_value('match_type'))
    stage = _clean_display(_pick_meta_value('stage'))
    result_type = _clean_display(_pick_meta_value('result_type'))
    method = _clean_display(_pick_meta_value('method'))

    # Build a cleaner ground string without duplicate city text.
    ground = venue or 'N/A'
    if venue and city and city.lower() not in venue.lower():
        ground = f"{venue}, {city}"

    # Derive consistent result text for details panel.
    if winner and win_outcome:
        result_summary = f"{winner} won by {win_outcome}"
    elif winner:
        result_summary = f"{winner} won"
    elif win_outcome:
        result_summary = win_outcome
    else:
        result_summary = 'N/A'

    final_match_id = int(season_final.iloc[0]['match_id']) if not season_final.empty and pd.notna(season_final.iloc[0]['match_id']) else None
    if not stage:
        stage = 'Final' if final_match_id == match_id else 'League Stage'
    if not result_type:
        result_type = _derive_result_type(win_outcome) or 'N/A'
    if not method:
        method = 'Normal'

    umpires = [
        str(x) for x in match_df['umpire'].dropna().unique().tolist()
        if str(x).strip() and str(x).strip().lower() != 'none'
    ]
    details = {
        'ground': ground,
        'toss': f"{toss_winner}, elected to {toss_decision} first" if toss_winner else 'N/A',
        'series': event_name or 'Indian Premier League',
        'season': season,
        'result': result_summary,
        'player_of_the_match': player_of_match or 'N/A',
        'series_result': (
            f"{season_winner} won the {season} Indian Premier League"
            if season_winner else 'N/A'
        ),
        'match_days': (
            f"{meta_row['date'].strftime('%d %B %Y')} - {match_type.lower()}"
            if pd.notna(meta_row['date']) and match_type else 'N/A'
        ),
        'stage': stage,
        'umpires': ', '.join(umpires) if umpires else 'N/A',
        'result_type': result_type,
        'method': method
    }

    return jsonify({
        'status': 'success',
        'match_id': match_id,
        'season': season,
        'winner': winner,
        'result': win_outcome,
        'innings': innings_payload,
        'match_details': details
    })


# ----------------------------- MATCHUP / PREDICTION HELPERS -----------------------------
def get_h2h_match(team1, team2):
      h2h = df[
        ((df['batting_team'] == team1) & (df['bowling_team'] == team2)) |
        ((df['batting_team'] == team2) & (df['bowling_team'] == team1))
    ]
      return h2h
def get_h2h_matches(team1, team2):
    h2h = df_recent_2425[
        (
            ((df_recent_2425['batting_team'] == team1) & (df_recent_2425['bowling_team'] == team2)) |
            ((df_recent_2425['batting_team'] == team2) & (df_recent_2425['bowling_team'] == team1))
        )
    ]
    return h2h



def get_h2h_matches_2026(team1, team2):
    h2h = df_2026[
        (
            ((df_2026['batting_team'] == team1) & (df_2026['bowling_team'] == team2)) |
            ((df_2026['batting_team'] == team2) & (df_2026['bowling_team'] == team1))
        )
    ]
    return h2h

@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()
    team1 = data['team1']
    team2 = data['team2']

    # Blend scores: 35% historical (<=2025) + 65% 2026
    HIST_WEIGHT = 0.35
    CURR_WEIGHT = 0.65
    WEIGHTS = {
        'wins': 0.40,
        'avg_runs': 0.20,
        'powerplay': 0.15,
        'death': 0.15,
        'toss_win': 0.10,
    }

    def safe_ratio(a, b):
        total = a + b
        if total == 0:
            return 0.5, 0.5
        return a / total, b / total

    def _best_venue(venue_counts):
        if venue_counts is None or venue_counts.empty:
            return None, 0
        return str(venue_counts.idxmax()), int(venue_counts.max())

    def _pick_extreme(hist_val, hist_winner, cur_val, cur_winner, pick='max'):
        if pick == 'max':
            if cur_val > hist_val:
                return int(cur_val), cur_winner
            return int(hist_val), hist_winner
        if hist_val == 0 and cur_val == 0:
            return 0, None
        vals = [(hist_val, hist_winner), (cur_val, cur_winner)]
        vals = [x for x in vals if x[0] > 0]
        if not vals:
            return 0, None
        low = min(vals, key=lambda x: x[0])
        return int(low[0]), low[1]

    def _metrics_from_h2h(h2h, t1, t2):
        if h2h is None or h2h.empty:
            return {
                'total_matches': 0,
                'team1_runs': 0.0,
                'team2_runs': 0.0,
                'team1_average_runs': 0.0,
                'team2_average_runs': 0.0,
                'team1_wins': 0,
                'team2_wins': 0,
                'team1_toss_wins': 0,
                'team1toss_matchwon': 0,
                'team1toss_field': 0,
                'team1toss_bat': 0,
                'team2_toss_wins': 0,
                'team2toss_matchwon': 0,
                'team2toss_field': 0,
                'team2toss_bat': 0,
                'team1_venue_counts': pd.Series(dtype='int64'),
                'team2_venue_counts': pd.Series(dtype='int64'),
                't1_high': 0,
                't1_high_winner': None,
                't1_low': 0,
                't1_low_winner': None,
                't2_high': 0,
                't2_high_winner': None,
                't2_low': 0,
                't2_low_winner': None,
                'team1_pp_avg': 0.0,
                'team2_pp_avg': 0.0,
                'team1_death_avg': 0.0,
                'team2_death_avg': 0.0,
                'team1_score': 50.0,
                'team2_score': 50.0,
            }

        total_matches = int(h2h['match_id'].nunique())

        team1_runs = float(
            h2h[h2h['batting_team'] == t1].groupby('match_id')['runs_total'].sum().sum()
        )
        team2_runs = float(
            h2h[h2h['batting_team'] == t2].groupby('match_id')['runs_total'].sum().sum()
        )
        team1_average_runs = team1_runs / total_matches if total_matches else 0.0
        team2_average_runs = team2_runs / total_matches if total_matches else 0.0

        match_results = h2h[['match_id', 'match_won_by']].drop_duplicates()
        team1_wins = int(match_results[match_results['match_won_by'] == t1].shape[0])
        team2_wins = int(match_results[match_results['match_won_by'] == t2].shape[0])

        toss_df = h2h[['match_id', 'match_won_by', 'toss_decision', 'toss_winner']].drop_duplicates()

        def toss_stats(team):
            toss_wins = toss_df[toss_df['toss_winner'] == team]
            total = int(toss_wins.shape[0])
            match_won = int(toss_wins[toss_wins['match_won_by'] == team].shape[0])
            won_field = int(
                toss_wins[
                    (toss_wins['match_won_by'] == team)
                    & (toss_wins['toss_decision'] == 'field')
                ].shape[0]
            )
            won_bat = int(
                toss_wins[
                    (toss_wins['match_won_by'] == team)
                    & (toss_wins['toss_decision'] == 'bat')
                ].shape[0]
            )
            return total, match_won, won_field, won_bat

        team1_toss_wins, team1toss_matchwon, team1toss_field, team1toss_bat = toss_stats(t1)
        team2_toss_wins, team2toss_matchwon, team2toss_field, team2toss_bat = toss_stats(t2)

        venue_df = h2h[['match_id', 'match_won_by', 'venue']].drop_duplicates()
        team1_venue_counts = venue_df[venue_df['match_won_by'] == t1]['venue'].value_counts()
        team2_venue_counts = venue_df[venue_df['match_won_by'] == t2]['venue'].value_counts()

        match_scores = h2h.groupby(['match_id', 'batting_team'])['runs_total'].sum().reset_index()
        t1_scores = match_scores[match_scores['batting_team'] == t1]
        t2_scores = match_scores[match_scores['batting_team'] == t2]

        def score_info(scores_df):
            if scores_df.empty:
                return 0, None, 0, None
            hi_id = scores_df.loc[scores_df['runs_total'].idxmax(), 'match_id']
            lo_id = scores_df.loc[scores_df['runs_total'].idxmin(), 'match_id']
            hi_won = h2h[h2h['match_id'] == hi_id]['match_won_by'].iloc[0]
            lo_won = h2h[h2h['match_id'] == lo_id]['match_won_by'].iloc[0]
            return int(scores_df['runs_total'].max()), hi_won, int(scores_df['runs_total'].min()), lo_won

        t1_high, t1_high_winner, t1_low, t1_low_winner = score_info(t1_scores)
        t2_high, t2_high_winner, t2_low, t2_low_winner = score_info(t2_scores)

        pp = h2h[h2h['over'] <= 6]
        team1_pp_avg = float(
            pp[pp['batting_team'] == t1].groupby('match_id')['runs_total'].sum().mean() or 0.0
        )
        team2_pp_avg = float(
            pp[pp['batting_team'] == t2].groupby('match_id')['runs_total'].sum().mean() or 0.0
        )

        death = h2h[h2h['over'] >= 15]
        team1_death_avg = float(
            death[death['batting_team'] == t1].groupby('match_id')['runs_total'].sum().mean() or 0.0
        )
        team2_death_avg = float(
            death[death['batting_team'] == t2].groupby('match_id')['runs_total'].sum().mean() or 0.0
        )

        r_wins = safe_ratio(team1_wins, team2_wins)
        r_avg = safe_ratio(team1_average_runs, team2_average_runs)
        r_pp = safe_ratio(team1_pp_avg, team2_pp_avg)
        r_death = safe_ratio(team1_death_avg, team2_death_avg)
        r_toss_win = safe_ratio(team1toss_matchwon, team2toss_matchwon)

        team1_score = round(
            r_wins[0] * WEIGHTS['wins'] * 100
            + r_avg[0] * WEIGHTS['avg_runs'] * 100
            + r_pp[0] * WEIGHTS['powerplay'] * 100
            + r_death[0] * WEIGHTS['death'] * 100
            + r_toss_win[0] * WEIGHTS['toss_win'] * 100,
            2,
        )
        team2_score = round(100 - team1_score, 2)

        return {
            'total_matches': total_matches,
            'team1_runs': team1_runs,
            'team2_runs': team2_runs,
            'team1_average_runs': team1_average_runs,
            'team2_average_runs': team2_average_runs,
            'team1_wins': team1_wins,
            'team2_wins': team2_wins,
            'team1_toss_wins': team1_toss_wins,
            'team1toss_matchwon': team1toss_matchwon,
            'team1toss_field': team1toss_field,
            'team1toss_bat': team1toss_bat,
            'team2_toss_wins': team2_toss_wins,
            'team2toss_matchwon': team2toss_matchwon,
            'team2toss_field': team2toss_field,
            'team2toss_bat': team2toss_bat,
            'team1_venue_counts': team1_venue_counts,
            'team2_venue_counts': team2_venue_counts,
            't1_high': t1_high,
            't1_high_winner': t1_high_winner,
            't1_low': t1_low,
            't1_low_winner': t1_low_winner,
            't2_high': t2_high,
            't2_high_winner': t2_high_winner,
            't2_low': t2_low,
            't2_low_winner': t2_low_winner,
            'team1_pp_avg': team1_pp_avg,
            'team2_pp_avg': team2_pp_avg,
            'team1_death_avg': team1_death_avg,
            'team2_death_avg': team2_death_avg,
            'team1_score': team1_score,
            'team2_score': team2_score,
        }

    h2h_hist = df_hist[
        ((df_hist['batting_team'] == team1) & (df_hist['bowling_team'] == team2))
        | ((df_hist['batting_team'] == team2) & (df_hist['bowling_team'] == team1))
    ]
    h2h_2026 = df_2026_combined[
        ((df_2026_combined['batting_team'] == team1) & (df_2026_combined['bowling_team'] == team2))
        | ((df_2026_combined['batting_team'] == team2) & (df_2026_combined['bowling_team'] == team1))
    ]

    hist = _metrics_from_h2h(h2h_hist, team1, team2)
    curr = _metrics_from_h2h(h2h_2026, team1, team2)

    total_matches = int(hist['total_matches'] + curr['total_matches'])
    team1_runs = hist['team1_runs'] + curr['team1_runs']
    team2_runs = hist['team2_runs'] + curr['team2_runs']
    team1_average_runs = team1_runs / total_matches if total_matches else 0.0
    team2_average_runs = team2_runs / total_matches if total_matches else 0.0

    team1_wins = int(hist['team1_wins'] + curr['team1_wins'])
    team2_wins = int(hist['team2_wins'] + curr['team2_wins'])

    team1_toss_wins = int(hist['team1_toss_wins'] + curr['team1_toss_wins'])
    team1toss_matchwon = int(hist['team1toss_matchwon'] + curr['team1toss_matchwon'])
    team1toss_field = int(hist['team1toss_field'] + curr['team1toss_field'])
    team1toss_bat = int(hist['team1toss_bat'] + curr['team1toss_bat'])

    team2_toss_wins = int(hist['team2_toss_wins'] + curr['team2_toss_wins'])
    team2toss_matchwon = int(hist['team2toss_matchwon'] + curr['team2toss_matchwon'])
    team2toss_field = int(hist['team2toss_field'] + curr['team2toss_field'])
    team2toss_bat = int(hist['team2toss_bat'] + curr['team2toss_bat'])

    team1_venue_counts = hist['team1_venue_counts'].add(curr['team1_venue_counts'], fill_value=0)
    team2_venue_counts = hist['team2_venue_counts'].add(curr['team2_venue_counts'], fill_value=0)
    top_venue_team1, top_venue_count_team1 = _best_venue(team1_venue_counts)
    top_venue_team2, top_venue_count_team2 = _best_venue(team2_venue_counts)

    t1_high, t1_high_winner = _pick_extreme(
        hist['t1_high'], hist['t1_high_winner'], curr['t1_high'], curr['t1_high_winner'], pick='max'
    )
    t1_low, t1_low_winner = _pick_extreme(
        hist['t1_low'], hist['t1_low_winner'], curr['t1_low'], curr['t1_low_winner'], pick='min'
    )
    t2_high, t2_high_winner = _pick_extreme(
        hist['t2_high'], hist['t2_high_winner'], curr['t2_high'], curr['t2_high_winner'], pick='max'
    )
    t2_low, t2_low_winner = _pick_extreme(
        hist['t2_low'], hist['t2_low_winner'], curr['t2_low'], curr['t2_low_winner'], pick='min'
    )

    team1_pp_avg = (
        (hist['team1_pp_avg'] * hist['total_matches']) + (curr['team1_pp_avg'] * curr['total_matches'])
    ) / total_matches if total_matches else 0.0
    team2_pp_avg = (
        (hist['team2_pp_avg'] * hist['total_matches']) + (curr['team2_pp_avg'] * curr['total_matches'])
    ) / total_matches if total_matches else 0.0
    team1_death_avg = (
        (hist['team1_death_avg'] * hist['total_matches']) + (curr['team1_death_avg'] * curr['total_matches'])
    ) / total_matches if total_matches else 0.0
    team2_death_avg = (
        (hist['team2_death_avg'] * hist['total_matches']) + (curr['team2_death_avg'] * curr['total_matches'])
    ) / total_matches if total_matches else 0.0

    if hist['total_matches'] == 0 and curr['total_matches'] > 0:
        eff_hist_w, eff_curr_w = 0.0, 1.0
    elif curr['total_matches'] == 0 and hist['total_matches'] > 0:
        eff_hist_w, eff_curr_w = 1.0, 0.0
    elif curr['total_matches'] == 0 and hist['total_matches'] == 0:
        eff_hist_w, eff_curr_w = 0.5, 0.5
    else:
        eff_hist_w, eff_curr_w = HIST_WEIGHT, CURR_WEIGHT

    team1_score = round((hist['team1_score'] * eff_hist_w) + (curr['team1_score'] * eff_curr_w), 2)
    team1_score = max(0.0, min(100.0, team1_score))
    team2_score = round(100 - team1_score, 2)
    predicted_winner = team1 if team1_score > team2_score else team2
    confidence = round(abs(team1_score - team2_score), 2)

    return jsonify({
        "team1": team1,
        "team2": team2,
        "total_matches": int(total_matches),
        "total_team1_runs": int(team1_runs),
        "total_team2_runs": int(team2_runs),
        "team1_average_runs": round(team1_average_runs, 2),
        "team2_average_runs": round(team2_average_runs, 2),
        "team1_wins": team1_wins,
        "team2_wins": team2_wins,
        "team1_toss_wins": team1_toss_wins,
        "team1_toss_match_won": team1toss_matchwon,
        "team1_toss_won_field": team1toss_field,
        "team1_toss_won_bat": team1toss_bat,
        "team2_toss_wins": team2_toss_wins,
        "team2_toss_match_won": team2toss_matchwon,
        "team2_toss_won_field": team2toss_field,
        "team2_toss_won_bat": team2toss_bat,
        "team1_top_venue": top_venue_team1,
        "team1_top_venue_wins": top_venue_count_team1,
        "team2_top_venue": top_venue_team2,
        "team2_top_venue_wins": top_venue_count_team2,
        "team1_highest_score": t1_high,
        "team1_highest_score_won_by": t1_high_winner,
        "team1_lowest_score": t1_low,
        "team1_lowest_score_won_by": t1_low_winner,
        "team2_highest_score": t2_high,
        "team2_highest_score_won_by": t2_high_winner,
        "team2_lowest_score": t2_low,
        "team2_lowest_score_won_by": t2_low_winner,
        "team1_powerplay_avg": round(float(team1_pp_avg), 2),
        "team2_powerplay_avg": round(float(team2_pp_avg), 2),
        "team1_death_avg": round(float(team1_death_avg), 2),
        "team2_death_avg": round(float(team2_death_avg), 2),
        "team1_prediction_score": team1_score,
        "team2_prediction_score": team2_score,
        "predicted_winner": predicted_winner,
        "confidence_gap": confidence,
    })
@app.route('/top_scorer', methods=['POST'])
def top_scorer():
    data  = request.json
    team1 = data.get('team1')
    team2 = data.get('team2')


 
    #  2024/25 data 
    h2h_2025 = get_h2h_matches(team1, team2)   # uses df_recent_2425 (2024+2025 only)
 
    batter_scores =  h2h_2025.groupby(["match_id", "date", "batter", "batting_team"], as_index=False).agg(
            runs_total=('runs_total', 'sum'),
            balls_faced=('valid_ball', 'sum')
    )
       
        
    
 
    overall_totals =batter_scores.groupby(['batter', 'batting_team'], as_index=False).agg(
            runs_total = ('runs_total', "sum"),
            balls_faced= ('balls_faced', 'sum'),
            match_id = ('match_id', 'nunique')
        )
        
    
 
    highest_score = (
        batter_scores
        .groupby(['batter', 'batting_team'])['runs_total']
        .max()
        .reset_index()
    )
 
    max_runs_old = overall_totals['runs_total'].max()
    max_peak_old = highest_score['runs_total'].max()
 
    overall_totals['total_norm'] = overall_totals['runs_total'] / max_runs_old if max_runs_old else 0
    highest_score['peak_norm']   = highest_score['runs_total']  / max_peak_old if max_peak_old else 0
 
    prediction_df = pd.merge(overall_totals, highest_score,
                             on=['batter', 'batting_team'],
                             suffixes=('_total', '_peak'))
    prediction_df['predicted_score'] = (
        70 * prediction_df['total_norm'] + 30 * prediction_df['peak_norm']
    )
    prediction_top_scorer = prediction_df[['batter', 'batting_team', 'predicted_score']]
 
    #  2026 data 
    h2h_2026 = get_h2h_matches_2026(team1, team2)
 
    batter_scores_2026 = h2h_2026.groupby(["match_no", "date", "striker", "batting_team"], as_index=False).agg(
        runs_of_bat=('runs_of_bat', 'sum'),
        extras=('extras', 'sum'),
        wide=('wide', 'sum'),
        ball=('over', 'nunique')
    )

    batter_scores_2026['total_runs'] = (
        batter_scores_2026['runs_of_bat'] +
        batter_scores_2026['extras'] +
        batter_scores_2026['wide']
    )
 
    overall_totals_2026 = (
    batter_scores_2026
    .groupby(['striker', 'batting_team'], as_index=False)
    .agg(
        total_runs=('total_runs', 'sum'),
        balls=('ball', 'sum'),
        match_no=('match_no', 'nunique')
    )
    )
 
    highest_score_2026 = (
        batter_scores_2026
        .groupby(['striker', 'batting_team'])['total_runs']
        .max()
        .reset_index()
    )
 
    max_runs_new = overall_totals_2026['total_runs'].max()
    max_peak_new = highest_score_2026['total_runs'].max()
 
    overall_totals_2026['total_norm'] = (
        overall_totals_2026['total_runs'] / max_runs_new if max_runs_new else 0
    )
    highest_score_2026['peak_norm'] = (
        highest_score_2026['total_runs'] / max_peak_new if max_peak_new else 0
    )
 
    prediction_df_2026 = pd.merge(overall_totals_2026, highest_score_2026,
                                  on=['striker', 'batting_team'],
                                  suffixes=('_total', '_peak'))
    prediction_df_2026['predicted_score'] = (
        70 * prediction_df_2026['total_norm'] + 30 * prediction_df_2026['peak_norm']
    )
    prediction_df_2026 = prediction_df_2026.rename(columns={'striker': 'batter'})
    prediction_top_scorer_2026 = prediction_df_2026[['batter', 'batting_team', 'predicted_score']]
 
    #  FIX: OUTER JOIN so players in only one season are kept 
    overall_score = pd.merge(
        prediction_top_scorer,
        prediction_top_scorer_2026,
        on=['batter', 'batting_team'],
        how='outer',                        #  was inner (default), dropping players
        suffixes=('_old', '_new')
    )
    # Fill NaN scores (player appeared in only one dataset)
    overall_score['predicted_score_old'] = overall_score['predicted_score_old'].fillna(0)
    overall_score['predicted_score_new'] = overall_score['predicted_score_new'].fillna(0)
 
    overall_score['final_prediction'] = (
        0.5 * overall_score['predicted_score_old'] +
        0.5 * overall_score['predicted_score_new']
    )
    overall_score = (
        overall_score
        .sort_values('final_prediction', ascending=False)
        .reset_index(drop=True)
    )
 
    top_scorer_details = []
 
    for idx, row in overall_score.head(7).iterrows():
        batter      = row['batter']
        bat_team    = row['batting_team']
 
        #  Peak score 
        peak_old_row = highest_score[
            (highest_score['batter'] == batter) &
            (highest_score['batting_team'] == bat_team)
        ]
        peak_new_row = highest_score_2026[
            (highest_score_2026['striker'] == batter) &
            (highest_score_2026['batting_team'] == bat_team)
        ]
        peak_old_val = peak_old_row['runs_total'].iloc[0]  if not peak_old_row.empty else 0
        peak_new_val = peak_new_row['total_runs'].iloc[0]  if not peak_new_row.empty else 0
        best_peak    = max(peak_old_val, peak_new_val)
 
        #  Totals 
        total_old_row = overall_totals[
            (overall_totals['batter'] == batter) &
            (overall_totals['batting_team'] == bat_team)
        ]
        total_new_row = overall_totals_2026[
            (overall_totals_2026['striker'] == batter) &
            (overall_totals_2026['batting_team'] == bat_team)
        ]
 
        matches_old = int(total_old_row['match_id'].sum())   if not total_old_row.empty else 0
        matches_new = int(total_new_row['match_no'].sum())   if not total_new_row.empty else 0
        total_matches = matches_old + matches_new
 
        runs_old  = int(total_old_row['runs_total'].iloc[0])  if not total_old_row.empty else 0
        balls_old = int(total_old_row['balls_faced'].iloc[0]) if not total_old_row.empty else 0
        runs_new  = int(total_new_row['total_runs'].iloc[0])  if not total_new_row.empty else 0
        balls_new = int(total_new_row['balls'].iloc[0])       if not total_new_row.empty else 0
 
        total_runs  = runs_old  + runs_new
        total_balls = balls_old + balls_new
 
        strike_rate   = (total_runs / total_balls) * 100 if total_balls > 0 else 0
        avg_per_match = total_runs / max(1, total_matches)
 
        
        image_url = resolve_player_image_url(batter)

        top_scorer_details.append({
            "batter":           batter,
            "batting_team":     bat_team,
            "final_prediction": float(row['final_prediction']),
            "total_runs":       total_runs,
            "highest_runs":     int(best_peak),
            "strike_rate":      round(strike_rate, 2),
            "avg_per_match":    round(avg_per_match, 2),
            "matches":          total_matches,
            "image_url":        image_url
        })
 
    return jsonify({
        'team1': team1,
        'team2': team2,
        'detailed_top_scorers': top_scorer_details
    })
 

def batter_index(batter, team, role, include_summary=True):
    batter = resolve_player_name(batter)
    batter_norm = (batter or "").strip().lower()
    team_aliases = get_team_aliases(team)

    df_bat = df_all[df_all['batter'].astype(str).str.strip().str.lower() == batter_norm]

    if team_aliases:
        alias_lc = {t.lower() for t in team_aliases}
        df_bat = df_bat[df_bat['batting_team'].astype(str).str.strip().str.lower().isin(alias_lc)]

    if df_bat.empty:
        return {
            "total_seasons": 0,
            "best_season": {'season': None},
            "best_average": {'avg_runs': 0},
            "peak_consistency": None,
            "player_stats_one": pd.DataFrame(columns=['season', 'matches_played', 'total_runs', 'avg_runs', 'std_runs', 'sixes', 'fours', 'consistency']),
            "six": 0,
            "fours": 0,
            "wicket_kind": "No dismissal data available.",
            "matches_played": 0,
            "matches_lost": 0,
            "playerstats": '',
            'batter_llm': ""
        }
    
    df1 = df_bat.drop_duplicates(subset='match_id')

    match_batter = df_bat.groupby(['match_id', 'season'])['runs_batter'].sum().reset_index()


    matches_played = df_bat.groupby('season')['match_id'].nunique()

    if team_aliases:
        matches_won = df1[df1['match_won_by'].isin(team_aliases)]
    else:
        matches_won = pd.DataFrame(columns=df1.columns)
    matches_won = len(matches_won)

    no_result = len(df1[df1['match_won_by'].fillna('Unknown') == 'Unknown'])

    if team_aliases:
        matches_lost = df1[~df1['match_won_by'].isin(team_aliases) & (df1['match_won_by'].fillna('Unknown') != 'Unknown')]
        matches_lost = len(matches_lost)
    else:
        matches_lost = int(max(len(df1) - no_result - matches_won, 0))


    sixes = df_bat.groupby(['season']).apply(
        lambda x: (x['runs_batter'] == 6).sum()
    ).reset_index(name='Total_Sixes')


    six = df_bat[df_bat['runs_batter'] == 6]
    six = len(six)

    fours = df_bat[df_bat['runs_batter'] == 4]
    fours = len(fours)

    value = df_bat[df_bat['player_out'] == batter]

    wicket_kind = value['wicket_kind'].value_counts().sort_values(ascending=False)
    if wicket_kind.empty:
        wicket_kind = "No dismissal data available."
    else:
        wicket_kind = f"Most common mode of dismissal: {wicket_kind.index[0]} ({wicket_kind.iloc[0]} times)."


    player_stats = match_batter.groupby('season').agg(
        matches_played=('match_id', 'count'),
        total_runs=('runs_batter', 'sum'),
        avg_runs=('runs_batter', 'mean'),
        std_runs=('runs_batter', 'std')
    ).reset_index()

    matches_played_all = df_bat.groupby('season')['match_id'].nunique().sum().item()

    
    boundaries = df_bat.groupby('season').agg(
    sixes=('runs_batter', lambda x: (x == 6).sum()),
    fours=('runs_batter', lambda x: (x == 4).sum())
    ).reset_index()

    player_stats = player_stats.merge(boundaries, on='season', how='left')

    player_stats['consistency'] = player_stats.apply(
        lambda x: x['avg_runs'] / x['std_runs'] if x['std_runs'] and not pd.isna(x['std_runs']) else x['avg_runs'], axis=1
    )
    player_stats_sorted = player_stats.sort_values(by='season', ascending=True).reset_index(drop=True)
    player_stats_one = player_stats.sort_values(by='season', ascending=False).reset_index(drop=True)

    player_stats_sorted = player_stats.sort_values(by='consistency', ascending=False).reset_index(drop=True)

    best_season = player_stats.sort_values(by='total_runs', ascending=False).iloc[0]
    best_average = player_stats.sort_values(by='avg_runs', ascending=False).iloc[0]

    total_seasons = player_stats['season'].nunique()
    peak_consistency = player_stats_sorted['season'].iloc[0]

    player_stats_sorted1 = player_stats.sort_values(by='season')
    fig, ax1 = plt.subplots(figsize=(12, 7))

    ax1.plot(player_stats_sorted1['season'],
            player_stats_sorted1['total_runs'],
            marker='o', linewidth=2,
            color='#1f77b4',
            label='Total Runs')

    best_season_year = best_season['season']
    best_runs = best_season['total_runs']

    ax1.scatter(best_season_year, best_runs,
                color="#FF0000", s=200, marker='*',
                zorder=15, label='Best Season')

    ax1.set_xlabel('Season', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Total Runs', fontsize=12, fontweight='bold')

    ax1.set_ylim(0, 
        player_stats_sorted1['total_runs'].max()
    * 1.2)

    ax2 = ax1.twinx()

    ax2.plot(player_stats_sorted1['season'],
            player_stats_sorted1['avg_runs'],
            marker='s', linestyle='--',
            color='#ff7f0e',
            label='Average Runs')

    ax2.plot(sixes['season'],
            sixes['Total_Sixes'],
            marker='x', linestyle='-.',
            color='#d62728',
            label='Sixes')

    ax2.set_ylabel('Average Runs / Sixes', fontsize=12, fontweight='bold')

    ax2.set_ylim(0, max(
        player_stats_sorted1['avg_runs'].max(),
        sixes['Total_Sixes'].max()
    ) * 1.2)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()

    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    for x,y in zip(sixes['season'], sixes['Total_Sixes']):
        ax2.annotate(
            str(y),
            (x,y),
            textcoords= 'offset points',
            xytext=(0,8),
            ha='center',
            fontsize=10,
            fontweight='bold',
            color='black'
        )

    plt.title(f'{batter} Performance Across Seasons', fontsize=16, fontweight='bold')
    plt.tight_layout(pad=1.5)

    ax1.grid(True, linestyle='--', linewidth=0.8, alpha=0.5, color='black')

    ax2.grid(True, linestyle=':', linewidth=0.6, alpha=0.3, color='black')
    plt_image = _figure_to_data_url(plt.gcf(), dpi=300)
    plt.close()
    batting_data = []

    for row in player_stats_one.to_dict(orient='records'):
        text = f"""
                Player: {batter}
                Season: {row['season']}
                Matches Played: {row['matches_played']}
                Total Runs: {row['total_runs']}
                Average Runs: {row['avg_runs']}
                Sixes: {row['sixes']}
                Fours: {row['fours']}
                Consistency: {row['consistency']}
                """
        batting_data.append({
            'id': f"{batter.replace(' ', '_')}_{row['season']}",
            'text': text.strip()
        })
    question = f"""
               Geneate me a summary on the given data for the Batter: {batter}, across all seasons the batter have played and give me an overview of the batter performance
               over all the season's while also summarise what the batter's strength's and short-cummings are, with proper evaluation on how he can can improve.
                """
    batting = ""
    if include_summary:
        user_scope = get_user_scope()
        namespace = f"batter:{batter.strip().lower()}:{(team or 'all').strip().lower()}"
        rag_engine.team_store(batting_data, user_scope=user_scope, namespace=namespace)
        batting = rag_engine.ask_team(question, user_scope=user_scope, namespace=namespace)

    if role == 'batter':
        return batting_data

    return {
    "total_seasons": total_seasons,
    "best_season": best_season,
    "best_average": best_average,
    "peak_consistency": peak_consistency,
    "player_stats_one": player_stats_one,
    "six": six,
    "fours": fours,
    "wicket_kind": wicket_kind,
    "matches_played": matches_played_all,
    "matches_lost": matches_lost,
    "playerstats": plt_image,
    'batter_llm': batting
}


def _build_batter_summary_chunks(player_name, season_rows):
    chunks = []
    for row in season_rows or []:
        chunks.append({
            "id": f"{str(player_name).replace(' ', '_')}_{row.get('season', 'na')}",
            "text": (
                f"Player: {player_name}\n"
                f"Season: {row.get('season', 'NA')}\n"
                f"Matches Played: {row.get('matches_played', 0)}\n"
                f"Total Runs: {row.get('total_runs', 0)}\n"
                f"Average Runs: {row.get('avg_runs', 0)}\n"
                f"Sixes: {row.get('sixes', 0)}\n"
                f"Fours: {row.get('fours', 0)}\n"
                f"Consistency: {row.get('consistency', 0)}"
            )
        })
    return chunks


def _build_bowler_summary_chunks(player_name, season_rows):
    chunks = []
    for row in season_rows or []:
        chunks.append({
            "id": f"{str(player_name).replace(' ', '_')}_{row.get('season', 'na')}",
            "text": (
                f"Bowler: {player_name}\n"
                f"Season: {row.get('season', 'NA')}\n"
                f"Matches: {row.get('Matches', 0)}\n"
                f"Wickets: {row.get('Total_Wickets', 0)}\n"
                f"Overs: {row.get('Total_Overs', 0)}\n"
                f"Runs Conceded: {row.get('Total_Runs', 0)}\n"
                f"Economy: {row.get('Seasonal_Economy', 0)}\n"
                f"Average: {row.get('Seasonal_Average', 0)}\n"
                f"Strike Rate: {row.get('Seasonal_Strike_Rate', 0)}"
            )
        })
    return chunks


def _build_team_summary_chunks(team_name, season_rows):
    chunks = []
    for idx, row in enumerate(season_rows or []):
        chunks.append({
            "id": f"{str(team_name).replace(' ', '_')}_{row.get('season', 'na')}_{idx}",
            "text": (
                f"Season: {row.get('season', 'NA')}\n"
                f"Team: {team_name}\n"
                f"Matches: {row.get('matches_played', 0)}\n"
                f"Wins: {row.get('wins', 0)}\n"
                f"Losses: {row.get('losses', 0)}\n"
                f"No Result: {row.get('no_result', 0)}\n"
                f"Runs Scored: {row.get('runs_scored', 0)}\n"
                f"Fours: {row.get('fours', 0)}\n"
                f"Sixes: {row.get('sixes', 0)}\n"
                f"Wickets Taken: {row.get('wickets_taken', 0)}\n"
                f"Top Batter: {row.get('top_batter', 'NA')} ({row.get('top_batter_runs', 0)})\n"
                f"Top Bowler: {row.get('top_bowler', 'NA')} ({row.get('top_bowler_wickets', 0)})"
            )
        })
    return chunks


def _stream_team_summary(question, chunks, namespace):
    if not chunks:
        yield "No data available for summary."
        return
    user_scope = get_user_scope()
    rag_engine.team_store(chunks, user_scope=user_scope, namespace=namespace)
    for token in rag_engine.ask_team_stream(question, user_scope=user_scope, namespace=namespace):
        if token:
            yield token

@app.route('/player_index', methods=['POST'])
def player_index():
    data = request.get_json() 

    team = data.get('team')
    batter = resolve_player_name(data.get('player'))

    # TATA IPL 2025 Player Headshot ID Map
    # Base URL: https://documents.iplt20.com{ID}.png


    image_url = resolve_player_image_url(batter)
    role = ""

    bat_index = batter_index(batter, team, role, include_summary=False)
    best_season_val = bat_index.get("best_season", {}).get("season")
    best_avg_val = bat_index.get("best_average", {}).get("avg_runs")
    peak_consistency_val = bat_index.get("peak_consistency")
    season_stats_rows = bat_index["player_stats_one"].to_dict(orient='records')
    
    best_season_payload = str(best_season_val).strip() if pd.notna(best_season_val) else None
    peak_consistency_payload = str(peak_consistency_val).strip() if pd.notna(peak_consistency_val) else None

    return jsonify({
    "player": batter,
    "image_url": image_url,
    "player_plot": bat_index['playerstats'],
    "team": team,
    "total_seasons_played": int(bat_index["total_seasons"]),
    "best_season_by_runs": best_season_payload,
    "highest_average": round(float(best_avg_val), 2) if pd.notna(best_avg_val) else None,
    "peak_consistency": peak_consistency_payload,
    "season_stats": season_stats_rows,
    "total_sixes": bat_index["six"],
    "total_fours": bat_index["fours"],
    "dismissible": bat_index["wicket_kind"],
    "matches_played": bat_index["matches_played"],
    "matches_lost": int(bat_index["matches_lost"]),
    'batting_data': "",
    'summary_input_rows': season_stats_rows
})


@app.route('/player_index/summary_stream', methods=['POST'])
def player_index_summary_stream():
    payload = request.get_json(silent=True) or {}
    batter = resolve_player_name((payload.get('player') or "").strip())
    team = (payload.get('team') or "").strip()
    rows = payload.get('season_stats') or []
    if not batter:
        return Response("Please provide a batter name.", mimetype='text/plain')

    scope_text = f"for team {team}" if team else "across all teams"
    question = f"""
               Geneate me a summary on the given data for the Batter: {batter}, {scope_text}, across all seasons the batter have played and give me an overview of the batter performance
               over all the season's while also summarise what the batter's strength's and short-cummings are, with proper evaluation on how he can can improve.
                """
    chunks = _build_batter_summary_chunks(batter, rows)
    namespace = f"player_summary:{batter.strip().lower()}:{(team or 'all').strip().lower()}"

    return Response(
        stream_with_context(_stream_team_summary(question, chunks, namespace)),
        mimetype='text/plain'
    )

# ----------------------------- AUTH / ACCOUNT ROUTES -----------------------------
@app.route('/send-otp', methods=['POST'])
@limiter.limit("3 per minute", key_func=limit_key_email_or_ip)
@limiter.limit("10 per hour", key_func=limit_key_email_or_ip)
def send_otp():
    email = (request.form.get('email') or '').strip().lower()
    if not email:
        return jsonify({'message': 'Email required'}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    existing_user = cursor.execute(
        'SELECT id FROM users WHERE LOWER(email) = ?',
        (email,)
    ).fetchone()
    if existing_user:
        conn.close()
        return jsonify({'message': 'Email already registered. Please sign in.'}), 400

    session.pop('otp_verified_email', None)
    otp = create_and_store_email_otp(cursor, email)
    conn.commit()
    conn.close()

    try:
        send_otp_mail(email, otp)
        return jsonify({'message': 'OTP sent successfully', 'expires_in': OTP_EXPIRY_SECONDS})
    except Exception:
        return jsonify({'message': 'Failed to send OTP'}), 500

@app.route('/verify-otp', methods=['POST'])
@limiter.limit("10 per 5 minutes", key_func=limit_key_email_or_ip)
def verify_otp():
    payload = request.get_json(silent=True) or {}
    email = (
        request.form.get('email')
        or payload.get('email')
        or ''
    ).strip()
    user_otp = (
        request.form.get('otp')
        or payload.get('otp')
        or ''
    ).strip()

    if not email or not user_otp:
        return jsonify({'status': 'error', 'message': 'Email and OTP are required'}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    is_valid, error_message = validate_latest_email_otp(cursor, email, user_otp)
    conn.close()

    if not is_valid:
        return jsonify({'status': 'error', 'message': error_message}), 400

    # OTP verification is the primary email-verification step in signup flow.
    session['otp_verified_email'] = email.strip().lower()
    return jsonify({'status': 'success', 'message': 'OTP verified successfully'})

@app.route('/otp-status', methods=['GET'])
def otp_status():
    email = (request.args.get('email') or '').strip().lower()
    if not email:
        return jsonify({'status': 'error', 'message': 'Email required'}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    is_active, remaining = get_latest_otp_status(cursor, email)
    conn.close()

    return jsonify({
        'status': 'success',
        'has_active_otp': is_active,
        'remaining_seconds': remaining
    })

@app.route('/forgot-password/send-otp', methods=['POST'])
@limiter.limit("3 per minute", key_func=limit_key_email_or_ip)
@limiter.limit("10 per hour", key_func=limit_key_email_or_ip)
def forgot_password_send_otp():
    email = (request.form.get('email') or '').strip().lower()
    if not email:
        return jsonify({'status': 'error', 'message': 'Email required'}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    user = cursor.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'status': 'error', 'message': 'No account found for this email'}), 404

    session.pop('forgot_password_verified_email', None)
    otp = create_and_store_email_otp(cursor, email)
    conn.commit()
    conn.close()

    try:
        send_otp_mail(email, otp)
        return jsonify({'status': 'success', 'message': 'OTP sent successfully', 'expires_in': OTP_EXPIRY_SECONDS})
    except Exception:
        return jsonify({'status': 'error', 'message': 'Failed to send OTP'}), 500

@app.route('/forgot-password/verify-otp', methods=['POST'])
@limiter.limit("10 per 5 minutes", key_func=limit_key_email_or_ip)
def forgot_password_verify_otp():
    email = (
        request.form.get('email')
        or (request.get_json(silent=True) or {}).get('email')
        or ''
    ).strip().lower()
    user_otp = (
        request.form.get('otp')
        or (request.get_json(silent=True) or {}).get('otp')
        or ''
    ).strip()

    if not email or not user_otp:
        return jsonify({'status': 'error', 'message': 'Email and OTP are required'}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    user = cursor.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'status': 'error', 'message': 'No account found for this email'}), 404

    is_valid, error_message = validate_latest_email_otp(cursor, email, user_otp)
    conn.close()
    if not is_valid:
        return jsonify({'status': 'error', 'message': error_message}), 400

    session['forgot_password_verified_email'] = email
    return jsonify({'status': 'success', 'message': 'OTP verified successfully'})

@app.route('/forgot-password/reset', methods=['POST'])
@limiter.limit("5 per 15 minutes", key_func=limit_key_email_or_ip)
def forgot_password_reset():
    email = (request.form.get('email') or '').strip().lower()
    new_password = (request.form.get('new_password') or '').strip()
    confirm_password = (request.form.get('confirm_password') or '').strip()

    if not all([email, new_password, confirm_password]):
        return jsonify({'status': 'error', 'message': 'All fields are required'}), 400
    if new_password != confirm_password:
        return jsonify({'status': 'error', 'message': 'Passwords do not match'}), 400
    if session.get('forgot_password_verified_email') != email:
        return jsonify({'status': 'error', 'message': 'Please verify OTP first'}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    user = cursor.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'status': 'error', 'message': 'No account found for this email'}), 404

    hashed_password = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_password, email))
    cursor.execute("DELETE FROM otp_codes WHERE email = ?", (email,))
    conn.commit()
    conn.close()

    session.pop('forgot_password_verified_email', None)
    return jsonify({'status': 'success', 'message': 'Password changed successfully'})


@app.route('/register/create-order', methods=['POST'])
@limiter.limit("5 per 10 minutes", key_func=limit_key_email_or_ip)
def create_register_order():
    data = request.json or {}
    name = str(data.get('name', '')).strip()
    email = str(data.get('email', '')).strip()
    password = str(data.get('password', '')).strip()
    plan = normalize_plan(str(data.get('plan', '')).strip())
    allowed_plans = {'Basic', 'Plus', 'Premium'}

    if not all([name, email, password]):
        return jsonify({'status': 'error', 'message': 'All fields are required'}), 400
    if plan not in allowed_plans:
        return jsonify({'status': 'error', 'message': 'Invalid plan selected'}), 400
    if not is_email_verified_for_signup(email):
        return jsonify({'status': 'error', 'message': 'Please verify your email OTP first'}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({'status': 'error', 'message': 'Email already registered'}), 400

    conn.close()

    amount = PLAN_PRICES.get(plan, 0)
    if amount <= 0:
        return jsonify({
            'status': 'success',
            'requires_payment': False,
            'order_id': '',
            'amount': 0,
            'currency': 'INR',
            'plan': plan
        })

    client, key_id, _ = get_razorpay_client()
    if not client:
        return jsonify({'status': 'error', 'message': 'Razorpay keys are missing in environment'}), 500

    order = client.order.create({
        'amount': amount,
        'currency': 'INR',
        'notes': {
            'email': email,
            'plan': plan,
            'flow': 'register'
        }
    })
    return jsonify({
        'status': 'success',
        'requires_payment': True,
        'order_id': order['id'],
        'amount': amount,
        'currency': 'INR',
        'key_id': key_id,
        'plan': plan
    })


@app.route('/register', methods=['POST'])
@limiter.limit("5 per 10 minutes", key_func=limit_key_email_or_ip)
def register():
    name = request.form.get('name')
    email = request.form.get('email')
    plan = normalize_plan(request.form.get('plan'))
    password = request.form.get('password')
    razorpay_order_id = request.form.get('razorpay_order_id', '').strip()
    razorpay_payment_id = request.form.get('razorpay_payment_id', '').strip()
    razorpay_signature = request.form.get('razorpay_signature', '').strip()

    if not all([name, email, password]):
        return jsonify({'message': 'All fields required'}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if not is_email_verified_for_signup(email):
        conn.close()
        return jsonify({'message': 'Please verify your email OTP first'}), 400

    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({'message': 'Email already registered'}), 400

    if PLAN_PRICES.get(plan, 0) > 0:
        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            conn.close()
            return jsonify({'message': 'Payment details are required for selected plan'}), 400

        _, _, key_secret = get_razorpay_client()
        if not key_secret:
            conn.close()
            return jsonify({'message': 'Razorpay keys are missing in environment'}), 500

        message = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
        expected = hmac.new(key_secret.encode(), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, razorpay_signature):
            conn.close()
            return jsonify({'message': 'Payment verification failed'}), 400

    hashed_password = generate_password_hash(password)
    cursor.execute(
        "INSERT INTO users (name, email, plan, password) VALUES (?, ?, ?, ?)",
        (name, email, plan, hashed_password)
    )
    conn.commit()

    user_id = cursor.lastrowid
    ensure_token_quota_row(conn, cursor, user_id, plan)
    if PLAN_PRICES.get(plan, 0) > 0:
        cursor.execute(
            """
            INSERT OR IGNORE INTO billing_refs
            (user_id, flow, razorpay_order_id, razorpay_payment_id, razorpay_signature)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, 'register', razorpay_order_id, razorpay_payment_id, razorpay_signature)
        )
    session['user_id'] = user_id
    session['email'] = email

    cursor.execute("DELETE FROM otp_codes WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    session.pop('otp_verified_email', None)
# Flask
    return jsonify({'status': 'success', 'redirect': url_for('dashboard')})


@app.route('/login', methods=['POST'])
@limiter.limit("10 per minute", key_func=limit_key_email_or_ip)
@limiter.limit("30 per hour", key_func=limit_key_email_or_ip)
def login():
    email = request.form.get('email')
    password = request.form.get('password')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    user = cursor.execute(
        'SELECT id, name, email, plan, password FROM users WHERE email = ?',
        (email,)
    ).fetchone()

    if user and check_password_hash(user[4], password):
        session['user_id'] = user[0]
        session['email'] = user[2]
        ensure_token_quota_row(conn, cursor, user[0], user[3])
        conn.close()
        return jsonify({'status': 'success', 'redirect': url_for('dashboard')})

    conn.close()
    return jsonify({'status': 'error', 'message': 'Invalid email or password'}), 401


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ----------------------------- DASHBOARD + ACCOUNT STATUS -----------------------------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    user = cursor.execute(
        'SELECT name, email, plan, created_at FROM users WHERE id = ?',
        (user_id,)
    ).fetchone()
    conn.close()

    if user:
        user = (user[0], user[1], normalize_plan(user[2]), user[3])

    return render_template('dashboard.html', user=user)

@app.route('/api/auth-status', methods=['GET'])
def auth_status():
    return jsonify({
        'status': 'success',
        'logged_in': 'user_id' in session
    })

@app.route('/api/token-status', methods=['GET'])
def token_status():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    try:
        status = get_token_status_for_user(session['user_id'])
        return jsonify({
            'status': 'success',
            'tokens_remaining': status['tokens_remaining'],
            'plan': status['plan'],
            'next_refill': status['next_refill']
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Unable to load token status: {str(e)}'
        }), 500

@app.route('/dashboard/recent-activities', methods=['GET'])
def recent_activities():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    user_id = session['user_id']
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        # Self-heal for older DBs / running instances where migration wasn't applied yet.
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS user_recent_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,
                title TEXT NOT NULL,
                thread_id TEXT,
                reference_id INTEGER,
                payload TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            '''
        )
        conn.commit()

        rows = cursor.execute(
            """
            SELECT id, activity_type, title, thread_id, reference_id, payload, created_at
            FROM user_recent_activities
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 25
            """,
            (user_id,)
        ).fetchall()
        conn.close()

        activities = []
        for row in rows:
            payload = {}
            if row[5]:
                try:
                    payload = json.loads(row[5])
                except Exception:
                    payload = {}
            activities.append({
                'id': row[0],
                'activity_type': row[1],
                'title': row[2],
                'thread_id': row[3],
                'reference_id': row[4],
                'payload': payload,
                'created_at': row[6]
            })

        return jsonify({'status': 'success', 'activities': activities})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Unable to load activities: {str(e)}'}), 500

@app.route('/dashboard/fantasy/session/<thread_id>', methods=['GET'])
def fantasy_session(thread_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    user_id = session['user_id']
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        chat_row = cursor.execute(
            """
            SELECT question, response, created_at
            FROM chat_data
            WHERE user_id = ? AND thread_id = ? AND pipeline = 'fantasy'
            ORDER BY id DESC
            LIMIT 1
            """,
            (str(user_id), thread_id)
        ).fetchone()

        if not chat_row:
            conn.close()
            return jsonify({'status': 'error', 'message': 'No saved fantasy session found'}), 404

        team1 = None
        team2 = None
        try:
            activity_row = cursor.execute(
                """
                SELECT payload
                FROM user_recent_activities
                WHERE user_id = ? AND activity_type = 'fantasy_team' AND thread_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id, thread_id)
            ).fetchone()
            if activity_row and activity_row[0]:
                payload = json.loads(activity_row[0])
                team1 = payload.get('team1')
                team2 = payload.get('team2')
        except Exception:
            pass

        conn.close()
        return jsonify({
            'status': 'success',
            'thread_id': thread_id,
            'question': chat_row[0],
            'answer': chat_row[1],
            'created_at': chat_row[2],
            'team1': team1,
            'team2': team2
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Unable to load fantasy session: {str(e)}'}), 500

@app.route('/dashboard/whatif/session/<thread_id>', methods=['GET'])
def whatif_session(thread_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    user_id = session['user_id']
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        chat_row = cursor.execute(
            """
            SELECT question, response, created_at
            FROM chat_data
            WHERE user_id = ? AND thread_id = ? AND pipeline LIKE 'whatif_%'
            ORDER BY id DESC
            LIMIT 1
            """,
            (str(user_id), thread_id)
        ).fetchone()

        if not chat_row:
            conn.close()
            return jsonify({'status': 'error', 'message': 'No saved what-if session found'}), 404

        payload = {}
        try:
            activity_row = cursor.execute(
                """
                SELECT payload
                FROM user_recent_activities
                WHERE user_id = ? AND activity_type = 'whatif_chat' AND thread_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id, thread_id)
            ).fetchone()
            if activity_row and activity_row[0]:
                payload = json.loads(activity_row[0])
        except Exception:
            payload = {}

        conn.close()
        return jsonify({
            'status': 'success',
            'thread_id': thread_id,
            'question': chat_row[0],
            'answer': chat_row[1],
            'created_at': chat_row[2],
            'payload': payload
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Unable to load what-if session: {str(e)}'}), 500

# ----------------------------- PLAN UPGRADE / BILLING ROUTES -----------------------------
@app.route('/dashboard/upgrade-plan/create-order', methods=['POST'])
@limiter.limit("10 per 10 minutes", key_func=limit_key_user_or_ip)
def create_razorpay_order():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    user_id = session['user_id']
    new_plan = normalize_plan((request.json or {}).get('plan', '').strip())
    allowed_plans = {'Basic', 'Plus', 'Premium'}

    if new_plan not in allowed_plans:
        return jsonify({'status': 'error', 'message': 'Invalid plan'}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    user_row = cursor.execute(
        'SELECT plan FROM users WHERE id = ?',
        (user_id,)
    ).fetchone()

    if not user_row:
        conn.close()
        return jsonify({'status': 'error', 'message': 'User not found'}), 404

    current_plan = normalize_plan(user_row[0])
    if current_plan == new_plan:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Already on this plan'}), 400

    remaining_seconds, last_plan = _plan_change_cooldown(cursor, user_id)
    if remaining_seconds > 0:
        conn.close()
        return jsonify({
            'status': 'error',
            'message': (
                f"Plan can be changed once every {PLAN_CHANGE_COOLDOWN_HOURS} hours. "
                f"Last plan: {last_plan}. Try again in {_format_wait_time(remaining_seconds)}."
            ),
            'retry_after_seconds': remaining_seconds
        }), 429
    conn.close()

    amount = PLAN_PRICES.get(new_plan, 0)
    if amount <= 0:
        return jsonify({
            'status': 'success',
            'requires_payment': False,
            'order_id': '',
            'amount': 0,
            'currency': 'INR',
            'key_id': '',
            'plan': new_plan
        })

    client, key_id, _ = get_razorpay_client()
    if not client:
        return jsonify({'status': 'error', 'message': 'Razorpay keys are missing in environment'}), 500

    order = client.order.create({
        'amount': amount,
        'currency': 'INR',
        'notes': {
            'user_id': str(user_id),
            'plan': new_plan
        }
    })
    return jsonify({
        'status': 'success',
        'requires_payment': True,
        'order_id': order['id'],
        'amount': amount,
        'currency': 'INR',
        'key_id': key_id,
        'plan': new_plan
    })


@app.route('/dashboard/upgrade-plan/verify-payment', methods=['POST'])
@limiter.limit("10 per 10 minutes", key_func=limit_key_user_or_ip)
def verify_razorpay_payment():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    user_id = session['user_id']
    data = request.json or {}
    razorpay_order_id = str(data.get('razorpay_order_id', '')).strip()
    razorpay_payment_id = str(data.get('razorpay_payment_id', '')).strip()
    razorpay_signature = str(data.get('razorpay_signature', '')).strip()
    new_plan = normalize_plan(data.get('plan', ''))
    allowed_plans = {'Basic', 'Plus', 'Premium'}

    if new_plan not in allowed_plans:
        return jsonify({'status': 'error', 'message': 'Invalid plan'}), 400

    if PLAN_PRICES.get(new_plan, 0) > 0:
        _, _, key_secret = get_razorpay_client()
        if not key_secret:
            return jsonify({'status': 'error', 'message': 'Razorpay keys are missing in environment'}), 500
        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            return jsonify({'status': 'error', 'message': 'Missing payment details'}), 400

        message = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
        expected = hmac.new(key_secret.encode(), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, razorpay_signature):
            return jsonify({'status': 'error', 'message': 'Payment verification failed'}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    old_plan_row = cursor.execute(
        'SELECT plan FROM users WHERE id = ?',
        (user_id,)
    ).fetchone()
    if not old_plan_row:
        conn.close()
        return jsonify({'status': 'error', 'message': 'User not found'}), 404

    old_plan = normalize_plan(old_plan_row[0] if old_plan_row else 'Basic')
    if old_plan == new_plan:
        conn.close()
        status = get_token_status_for_user(user_id)
        return jsonify({
            'status': 'success',
            'message': f'Plan is already {new_plan}',
            'plan': status['plan'],
            'tokens_remaining': status['tokens_remaining'],
            'next_refill': status['next_refill']
        })

    remaining_seconds, last_plan = _plan_change_cooldown(cursor, user_id)
    if remaining_seconds > 0:
        conn.close()
        return jsonify({
            'status': 'error',
            'message': (
                f"Plan can be changed once every {PLAN_CHANGE_COOLDOWN_HOURS} hours. "
                f"Last plan: {last_plan}. Try again in {_format_wait_time(remaining_seconds)}."
            ),
            'retry_after_seconds': remaining_seconds
        }), 429

    if PLAN_PRICES.get(new_plan, 0) > 0:
        cursor.execute(
            """
            INSERT OR IGNORE INTO billing_refs
            (user_id, flow, razorpay_order_id, razorpay_payment_id, razorpay_signature)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, 'upgrade', razorpay_order_id, razorpay_payment_id, razorpay_signature)
        )

    cursor.execute(
        'UPDATE users SET plan = ? WHERE id = ?',
        (new_plan, user_id)
    )
    quota_cap = get_plan_quota(new_plan)
    cursor.execute(
        """
        INSERT INTO token_quota (user_id, plan, tokens_remaining, last_refill)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            plan = excluded.plan,
            tokens_remaining = excluded.tokens_remaining,
            last_refill = excluded.last_refill
        """,
        (user_id, new_plan, quota_cap, datetime.datetime.utcnow().isoformat())
    )
    cursor.execute(
        'INSERT INTO plan_change_history (user_id, old_plan, new_plan) VALUES (?, ?, ?)',
        (user_id, old_plan or 'Basic', new_plan)
    )
    conn.commit()
    conn.close()
    status = get_token_status_for_user(user_id)
    return jsonify({
        'status': 'success',
        'message': f'Upgraded to {new_plan} successfully',
        'plan': status['plan'],
        'tokens_remaining': status['tokens_remaining'],
        'next_refill': status['next_refill']
    })

def get_batting_stats(df, players):
    df_bat = df[df['batter'].isin(players)].copy()
    
    if df_bat.empty:
        return None

    df_bat['is_six'] = (df_bat['runs_batter'] == 6)
    df_bat['is_four'] = (df_bat['runs_batter'] == 4)

    player_stats = df_bat.groupby('batter').apply(
        lambda x: pd.Series({
            'Matches'    : x['match_id'].nunique(),
            'Runs'       : x['runs_batter'].sum(),
            'Balls'      : x['balls_faced'].sum(),
            'Average'    : x['runs_batter'].sum() / x['match_id'].nunique(),
            'StrikeRate': (x['runs_batter'].sum() / x['balls_faced'].sum() * 100),
            'Fours'      : x['is_four'].sum(),
            'Sixes'      : x['is_six'].sum()
        }), include_groups=False
    ).reset_index()

    total_matches = df_bat['match_id'].nunique()
    total_runs = df_bat['runs_batter'].sum()
    total_balls = df_bat['balls_faced'].sum()

    total_stats = pd.DataFrame({
        'Matches': [total_matches],
        "Total Runs": [total_runs],
        "Total Balls": [total_balls],
        "Team Avg Score": [player_stats['Average'].sum()],
        "Team SR": [(total_runs / total_balls * 100) if total_balls > 0 else 0],
        "Total Fours": [df_bat['is_four'].sum()],
        "Total Sixes": [df_bat['is_six'].sum()]
    })
    player_stats_bat = player_stats.to_dict(orient="records")
    total_stats_bat = total_stats.to_dict(orient="records")

    return {
        'player_stats': player_stats_bat,
        'total_stats' : total_stats_bat,
        "total_runs"  : total_runs,
        "strike_rate" : total_stats["Team SR"].iloc[0],
        "avg_runs"    : total_stats["Team Avg Score"].iloc[0],
        "fours"       : total_stats["Total Fours"].iloc[0],
        "sixes"       : total_stats["Total Sixes"].iloc[0]
    }

def get_bowling_stats(df, players):
    df_bowl = df[df['bowler'].isin(players)].copy()

    if df_bowl.empty:
        return None

    def bowler_row(x):
        wickets = x['bowler_wicket'].sum()
        runs    = x['runs_bowler'].sum()
        total_overs = x.groupby('match_id')['over'].nunique().sum()
        total_balls = x.groupby(['match_id', 'over'])['ball'].nunique().sum()

        return pd.Series({
            'Wickets' : wickets,
            'Runs'    : runs,
            'Overs'   : total_overs,
            'Balls'   : total_balls,
            'Economy' : (runs / total_overs) if total_overs > 0 else 0,
            'Avg'     : (runs / wickets) if wickets > 0 else 0,
            'SR'      : (total_balls / wickets) if wickets > 0 else 0,
        })

    player_bowl_stats = df_bowl.groupby('bowler').apply(
        bowler_row, include_groups=False
    ).reset_index()

    t_wickets = player_bowl_stats['Wickets'].sum()
    t_runs    = player_bowl_stats['Runs'].sum()
    t_overs   = player_bowl_stats['Overs'].sum()
    t_balls   = player_bowl_stats['Balls'].sum()

    total_stats = pd.DataFrame({
        'Total Wickets'   : [t_wickets],
        'Total Runs'      : [t_runs],
        'Total Overs'     : [t_overs],
        'Total Balls'     : [t_balls],
        'Team Economy'    : [(t_runs / t_overs) if t_overs > 0 else 0],
        'Team Average'    : [(t_runs / t_wickets) if t_wickets > 0 else 0],
        'Team Strike Rate': [(t_balls / t_wickets) if t_wickets > 0 else 0]
    })

    player_bowl_stats = player_bowl_stats.to_dict(orient="records")
    total_bowl_stats = total_stats.to_dict(orient="records")

    return {
        "player_bowl_stats": player_bowl_stats,
        'total_bowl_stats': total_bowl_stats,
        "total_wickets" : total_stats['Total Wickets'].iloc[0],
        "economy"       : total_stats['Team Economy'].iloc[0],
        "bowl_avg"      : total_stats['Team Average'].iloc[0],
        "strike_rate"   : total_stats['Team Strike Rate'].iloc[0]
    }

def build_team(df, teamname, xiplayers):
    team_name = teamname    
    players = xiplayers
    
    bat_stats  = get_batting_stats(df, players)
    bowl_stats = get_bowling_stats(df, players)
    if not bat_stats or not bowl_stats:
        return None

    return {
        "name"    : team_name,
        "players" : players,
        "batting" : bat_stats,
        "bowling" : bowl_stats
    }



def calculate_score(team):
    bat  = team['batting']
    bowl = team['bowling']

    bat_score = (
        bat['avg_runs'] * 3.0 +
        bat['strike_rate'] * 25.0 +
        bat['sixes'] * 5.0
    )

    bowl_score = (
        (15 - bowl['economy']) * 25.0 +
        (30 - bowl['strike_rate']) * 15.0 +
        bowl['total_wickets'] * 1.0
    )

    total_score = bat_score + bowl_score
    return total_score, bat_score, bowl_score

def decide_winner(team1, team2, matchup, teamA_players, teamB_players):
    score1, bat1, bowl1 = calculate_score(team1)
    score2, bat2, bowl2 = calculate_score(team2)

    metrics = ['Average Runs(bat)', 'Strike Rate', 'Fours', 'Sixes',
               'Wickets', 'Bowler Economy', 'Bowling Average', 'Bowler Strike Rate']

    answer = pd.DataFrame({
        "Metric": metrics,
        "Team1": [
            team1['batting']['avg_runs'],
            team1['batting']['strike_rate'],
            team1['batting']['fours'],
            team1['batting']['sixes'],
            team1['bowling']['total_wickets'],
            team1['bowling']['economy'],
            team1['bowling']['bowl_avg'],
            team1['bowling']['strike_rate']
        ],
        "Team2": [
            team2['batting']['avg_runs'],
            team2['batting']['strike_rate'],
            team2['batting']['fours'],
            team2['batting']['sixes'],
            team2['bowling']['total_wickets'],
            team2['bowling']['economy'],
            team2['bowling']['bowl_avg'],
            team2['bowling']['strike_rate']
        ]
    })
    result_teams = {
                                         team1['name']: {"bat1": float(bat1), "bowl1": float(bowl1), "total1": float(score1)},
                                         team2['name']: {"bat2": float(bat2), "bowl2": float(bowl2), "total2": float(score2)}
                                     }

    winner = team1['name'] if score1 > score2 else team2['name'] if score2 > score1 else "Tie"
    user_id = session['user_id']

    conn= sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute(
    'INSERT INTO custom_matchups(user_id, matchup_name, teamA, teamB, teamA_players, teamB_players, metrics, teamA_bat_stats,teamA_bat_total, teamA_bowl_stats, teamA_Bowl_total, teamB_bat_stats,teamB_bat_total, teamB_bowl_stats, teamB_bowl_total, teamScores, winner) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'  ,    
        (
            user_id,
            matchup, 
            str(team1['name']), 
            str(team2['name']), 
            json.dumps(teamA_players), 
            json.dumps(teamB_players), 
            json.dumps(answer.to_dict(orient="records")), 
            json.dumps(team1['batting']['player_stats']), 
            json.dumps(team1['batting']['total_stats']), 
            json.dumps(team1['bowling']['player_bowl_stats']), 
            json.dumps(team1['bowling']['total_bowl_stats']),
            json.dumps(team2['batting']['player_stats']), 
            json.dumps(team2['batting']['total_stats']),
            json.dumps(team2['bowling']['player_bowl_stats']),
            json.dumps(team2['bowling']['total_bowl_stats']), 
            json.dumps(result_teams),
            winner
        )  
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    log_user_activity(
        user_id=user_id,
        activity_type='custom_matchup',
        title=f"{team1['name']} vs {team2['name']}",
        reference_id=new_id,
        payload={
            'teamA': team1['name'],
            'teamB': team2['name'],
            'winner': winner,
            'matchup_name': matchup
        }
    )

    return jsonify(
        {
            "Status": "ok",
            "matchup_id": new_id,
            "redirect": url_for('get_matchup_by_id', matchup_id=new_id)
        }
    )

@app.route('/dashboard/customteam/latest', methods=['GET'])
def get_latest_matchup():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM custom_matchups
                WHERE user_id = ?
                ORDER BY id DESC LIMIT 1
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({"error": "No matchups found"}), 404
            return get_matchup_by_id(row[0])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/dashboard/customteam/all', methods=['GET'])
def get_all_matchups():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, matchup_name, teamA, teamB, created_at
                FROM custom_matchups
                WHERE user_id = ?
                ORDER BY id DESC
            """, (user_id,))
            rows = cursor.fetchall()
            matchups = [
                {"id": r[0], "matchup_name": r[1], "teamA": r[2], "teamB": r[3], "created_at": r[4]}
                for r in rows
            ]
            return jsonify({"matchups": matchups})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/dashboard/customteam/<int:matchup_id>', methods=['GET'])
def get_matchup_by_id(matchup_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM custom_matchups
                WHERE id = ? AND user_id = ?
            """, (matchup_id, user_id))
            row = cursor.fetchone()
            if not row:
                return jsonify({"error": "Not found"}), 404

            columns = [col[0] for col in cursor.description]
            result = dict(zip(columns, row))

            for field in ['teamA_players', 'teamB_players', 'metrics',
                          'teamA_bat_stats', 'teamA_bat_total',
                          'teamA_bowl_stats', 'teamA_bowl_total',
                          'teamB_bat_stats', 'teamB_bat_total',
                          'teamB_bowl_stats', 'teamB_bowl_total', 'teamScores']:
                if result.get(field):
                    result[field] = json.loads(result[field])

            return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/customteam', methods=['POST'])
def customteam():

    data = request.get_json()

    matchup_name = data.get('matchup')

    teamA = data.get('teamA_players')
    teamB = data.get('teamB_players')

    teamA_name = data.get('teamA_name', 'Team A')
    teamB_name = data.get('teamB_name', 'Team B')

    team1_stats = build_team(df, teamA_name, teamA)
    team2_stats = build_team(df, teamB_name, teamB)

    if team1_stats and team2_stats:
        return decide_winner(team1_stats, team2_stats, matchup_name, teamA, teamB)
    else:
        return jsonify({"error": "Could not build both teams. Check player names."}), 400


# ----------------------------- LLM CHAT ROUTES -----------------------------
@app.route('/llm_chat', methods=['POST'])
@limiter.limit("20 per minute", key_func=limit_key_user_or_ip)
def llm_chat():
    user_id = session.get('user_id')
    data = request.get_json() or {}
    matchup_id = data.get('matchup_id')

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if matchup_id:
        cursor.execute("""
            SELECT id, matchup_name, teamA, teamB, teamA_players, teamB_players, metrics,
                   teamA_bat_stats, teamA_bat_total, teamA_bowl_stats, teamA_bowl_total,
                   teamB_bat_stats, teamB_bat_total, teamB_bowl_stats, teamB_bowl_total,
                   teamScores, winner
            FROM custom_matchups
            WHERE user_id = ? AND id = ?
        """, (user_id, matchup_id))
    else:
        cursor.execute("""
            SELECT id, matchup_name, teamA, teamB, teamA_players, teamB_players, metrics,
                   teamA_bat_stats, teamA_bat_total, teamA_bowl_stats, teamA_bowl_total,
                   teamB_bat_stats, teamB_bat_total, teamB_bowl_stats, teamB_bowl_total,
                   teamScores, winner
            FROM custom_matchups
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
        """, (user_id,))

    rows = cursor.fetchall()
    conn.close()
    chunks = []

    for row in rows:
        row_id       = row['id']
        matchup_name = row['matchup_name']
        teamA        = row['teamA']
        teamB        = row['teamB']
        winner       = row['winner']

        # FIX 2: parse every JSON field before use
        def p(field):
            raw = row[field]
            if not raw:
                return []
            try:
                return json.loads(raw)
            except Exception:
                return []

        tA_bat_players  = p('teamA_bat_stats')   # list of player dicts
        tA_bat_total    = p('teamA_bat_total')    # list with one summary dict
        tA_bowl_players = p('teamA_bowl_stats')
        tA_bowl_total   = p('teamA_bowl_total')
        tB_bat_players  = p('teamB_bat_stats')
        tB_bat_total    = p('teamB_bat_total')
        tB_bowl_players = p('teamB_bowl_stats')
        tB_bowl_total   = p('teamB_bowl_total')
        metrics_list    = p('metrics')
        scores          = p('teamScores')
        teamA_players   = p('teamA_players')
        teamB_players   = p('teamB_players')
        #

        # CHUNK 1: matchup summary
        tA_summary = tA_bat_total[0]  if tA_bat_total  else {}
        tB_summary = tB_bat_total[0]  if tB_bat_total  else {}
        tA_bowl_s  = tA_bowl_total[0] if tA_bowl_total else {}
        tB_bowl_s  = tB_bowl_total[0] if tB_bowl_total else {}

        # Build readable roster strings from the player lists
        tA_roster = ", ".join(teamA_players) if teamA_players else "N/A"
        tB_roster = ", ".join(teamB_players) if teamB_players else "N/A"

        chunks.append({
            "id": f"{row_id}_summary",
            "text": f"""
Matchup: {matchup_name}
{teamA} vs {teamB}
Winner: {winner}

{teamA} Players: {tA_roster}
{teamB} Players: {tB_roster}

{teamA} batting - Total Runs: {tA_summary.get('Total Runs', 'N/A')},
  Team Avg Score: {tA_summary.get('Team Avg Score', 'N/A')},
  Strike Rate: {tA_summary.get('Team SR', 'N/A')},
  Fours: {tA_summary.get('Total Fours', 'N/A')},
  Sixes: {tA_summary.get('Total Sixes', 'N/A')}

{teamB} batting - Total Runs: {tB_summary.get('Total Runs', 'N/A')},
  Team Avg Score: {tB_summary.get('Team Avg Score', 'N/A')},
  Strike Rate: {tB_summary.get('Team SR', 'N/A')},
  Fours: {tB_summary.get('Total Fours', 'N/A')},
  Sixes: {tB_summary.get('Total Sixes', 'N/A')}

{teamA} bowling - Wickets: {tA_bowl_s.get('Total Wickets', 'N/A')},
  Economy: {tA_bowl_s.get('Team Economy', 'N/A')},
  Avg: {tA_bowl_s.get('Team Average', 'N/A')},
  Strike Rate: {tA_bowl_s.get('Team Strike Rate', 'N/A')}

{teamB} bowling - Wickets: {tB_bowl_s.get('Total Wickets', 'N/A')},
  Economy: {tB_bowl_s.get('Team Economy', 'N/A')},
  Avg: {tB_bowl_s.get('Team Average', 'N/A')},
  Strike Rate: {tB_bowl_s.get('Team Strike Rate', 'N/A')}
""".strip()
        })

        # CHUNK 2: metrics comparison
        metrics_lines = "\n".join(
            f"  {m.get('Metric', '')}: {teamA} = {m.get('Team1', 'N/A')}, "
            f"{teamB} = {m.get('Team2', 'N/A')}"
            for m in metrics_list
        )
        chunks.append({
            "id": f"{row_id}_metrics",
            "text": f"""
Head-to-head metrics for matchup '{matchup_name}' ({teamA} vs {teamB}):
{metrics_lines}
Winner: {winner}
""".strip()
        })

        # CHUNK 3: per-player batting - Team A
        for player in tA_bat_players:
            name = player.get('batter', 'Unknown')
            chunks.append({
                "id": f"{row_id}_bat_A_{name.replace(' ', '_')}",
                "text": f"""
Batting stats for {name} (Team: {teamA}, Matchup: {matchup_name}):
  Matches: {player.get('Matches', 'N/A')}
  Runs: {player.get('Runs', 'N/A')}
  Balls: {player.get('Balls', 'N/A')}
  Average: {player.get('Average', 'N/A')}
  Strike Rate: {player.get('StrikeRate', 'N/A')}
  Fours: {player.get('Fours', 'N/A')}
  Sixes: {player.get('Sixes', 'N/A')}
""".strip()
            })

        # CHUNK 4: per-player batting - Team B
        for player in tB_bat_players:
            name = player.get('batter', 'Unknown')
            chunks.append({
                "id": f"{row_id}_bat_B_{name.replace(' ', '_')}",
                "text": f"""
Batting stats for {name} (Team: {teamB}, Matchup: {matchup_name}):
  Matches: {player.get('Matches', 'N/A')}
  Runs: {player.get('Runs', 'N/A')}
  Balls: {player.get('Balls', 'N/A')}
  Average: {player.get('Average', 'N/A')}
  Strike Rate: {player.get('StrikeRate', 'N/A')}
  Fours: {player.get('Fours', 'N/A')}
  Sixes: {player.get('Sixes', 'N/A')}
""".strip()
            })

        # CHUNK 5: per-player bowling - Team A
        for player in tA_bowl_players:
            name = player.get('bowler', 'Unknown')
            chunks.append({
                "id": f"{row_id}_bowl_A_{name.replace(' ', '_')}",
                "text": f"""
Bowling stats for {name} (Team: {teamA}, Matchup: {matchup_name}):
  Wickets: {player.get('Wickets', 'N/A')}
  Runs: {player.get('Runs', 'N/A')}
  Overs: {player.get('Overs', 'N/A')}
  Economy: {player.get('Economy', 'N/A')}
  Bowling Average: {player.get('Avg', 'N/A')}
  Strike Rate: {player.get('SR', 'N/A')}
""".strip()
            })

        # CHUNK 6: per-player bowling - Team B
        for player in tB_bowl_players:
            name = player.get('bowler', 'Unknown')
            chunks.append({
                "id": f"{row_id}_bowl_B_{name.replace(' ', '_')}",
                "text": f"""
Bowling stats for {name} (Team: {teamB}, Matchup: {matchup_name}):
  Wickets: {player.get('Wickets', 'N/A')}
  Runs: {player.get('Runs', 'N/A')}
  Overs: {player.get('Overs', 'N/A')}
  Economy: {player.get('Economy', 'N/A')}
  Bowling Average: {player.get('Avg', 'N/A')}
  Strike Rate: {player.get('SR', 'N/A')}
""".strip()
            })

    data_response = rag_engine.store(chunks, user_id)
    return data_response

@app.route('/get_llm', methods=['POST'])
@limiter.limit("20 per minute", key_func=limit_key_user_or_ip)
@require_tokens(estimated_cost=120)
def get_llm():
    user_id = session.get('user_id')
    data = request.get_json()
    question = data.get('question')
    thread = data.get('thread_id')
    system_prompt = systemprompts.systemPrompts.custom_matchup_prompt
    if not question:
        return {"status": "error",
                "message": "No question provided."
                }, 400

    status = get_token_status_for_user(user_id)
    answer, tokens_used = rag_engine.ask(
        question,
        thread,
        user_id,
        system_prompt,
        max_output_tokens=get_plan_output_limit(status['plan']),
        plan_policy=plan_response_policy(status['plan'])
    )
    updated = consume_tokens(user_id, tokens_used)
    return jsonify({"status": "success",
                    "answer": answer,
                    "tokens_used": int(tokens_used),
                    "tokens_remaining": updated['tokens_remaining'],
                    "plan": updated['plan'],
                    "next_refill": updated['next_refill']})

def comp_player(player):
    player1 = resolve_player_name(player)
    df_compare_bat = df_all[df_all['batter'] == player1]

    player1_matches = df_all[
        (df_all['batter'] == player1) |
        (df_all['bowler'] == player1) |
        (df_all['non_striker'] == player1)
    ]
    player1_total_matches_played = player1_matches['match_id'].nunique()
    player1_innings = (
        df_compare_bat[df_compare_bat['innings'] <= 2]
        .groupby('match_id')['balls_faced']
        .sum()
    )
    player1_innings = (player1_innings > 0).sum()
    player1_total_runs = df_compare_bat['runs_batter'].sum()
    player1_total_balls_faced = df_compare_bat['balls_faced'].sum()
    player1_highest_score = df_compare_bat.groupby(['match_id', 'innings'])['runs_batter'].sum().max()
    player1_bat_average = player1_total_runs / player1_innings if player1_innings else 0
    player1_strike_rate = (player1_total_runs / player1_total_balls_faced * 100) if player1_total_balls_faced else 0
    player1_runs_per_innings = df_compare_bat.groupby(['match_id', 'innings'])['runs_batter'].sum()
    total_100 = (player1_runs_per_innings >= 100).sum()
    total_50 = ((player1_runs_per_innings >= 50) & (player1_runs_per_innings < 100)).sum()
    player1_total_sixes = (df_compare_bat['runs_batter'] == 6).sum()
    player1_total_fours = (df_compare_bat['runs_batter'] == 4).sum()


    df_compare_bowl = df_all[df_all['bowler'] == player1]
    player1_bowl_stats = df_compare_bowl[['match_id', 'innings']].drop_duplicates().shape[0]
    player1_runs_bowl = df_compare_bowl['runs_bowler'].sum()
    player1_total_bowl_balls = df_compare_bowl.groupby(['match_id', 'over'])['ball'].nunique().sum()
    player1_total_bowl_overs = df_compare_bowl.groupby('match_id')['over'].nunique().sum()
    player1_wickets = df_compare_bowl['bowler_wicket'].sum()
    player1_bowl_eco  = player1_runs_bowl / player1_total_bowl_overs if player1_total_bowl_overs else 0
    player1_bowl_avg = player1_runs_bowl / player1_wickets if player1_wickets else 0
    player1_bowl_strike_rate = player1_total_bowl_balls / player1_wickets if player1_wickets else 0
    player1_4_wicket_haul = df_compare_bowl.groupby(['match_id', 'innings'])['bowler_wicket'].sum()
    four_wkt_haul = player1_4_wicket_haul == 4
    four_wkt_haul=four_wkt_haul[four_wkt_haul].count()
    player1_5_wicket_haul = df_compare_bowl.groupby(['match_id', 'innings'])['bowler_wicket'].sum()
    five_wkt_haul = player1_5_wicket_haul == 5
    five_wkt_haul=five_wkt_haul[five_wkt_haul].count()


    catches = df_all[(df_all['wicket_kind'] == 'caught') & (df_all['fielders'] == player1)].shape[0]
    stumping = df_all[(df_all['wicket_kind'] == 'stumped') & (df_all['fielders'] == player1)].shape[0]
    runout = df_all[
    (df_all['wicket_kind'] == 'run out') &
    (df_all['fielders'].notna()) &
    (df_all['fielders'].str.contains(player1, case=False))
    ].shape[0]

    stats = {
        'player_name': player1,
        'batting': {
            'total_matches_played': player1_total_matches_played,
            'total_innings': player1_innings,
            'total_runs': player1_total_runs,
            'total_balls_faced': player1_total_balls_faced,
            'highest_score': player1_highest_score,
            'batting_average': player1_bat_average,
            'strike_rate': player1_strike_rate,
            'total_100s': total_100,
            'total_50s': total_50,
            'total_sixes': player1_total_sixes,
            'total_fours': player1_total_fours
        },
        'bowling': {
            'bowling_innings': player1_bowl_stats,
            'total_runs_conceded': player1_runs_bowl,
            'total_balls_bowled': player1_total_bowl_balls,
            'total_overs': player1_total_bowl_overs,
            'wickets': player1_wickets,
            'bowling_economy': player1_bowl_eco,
            'bowling_average': player1_bowl_avg,
            'bowling_strike_rate': player1_bowl_strike_rate,
            'four_wicket_haul': four_wkt_haul,
            'five_wicket_haul': five_wkt_haul
        },
        'fielding':{
            'catches': catches,
            'stumpings': stumping,
            'runout': runout
        }
    }
    def convert(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return round(float(obj), 2)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return obj

    def deep_convert(d):
        if isinstance(d, dict):
            return {k: deep_convert(v) for k, v in d.items()}
        return convert(d)
    return deep_convert(stats)

# ----------------------------- FEATURE ROUTES: COMPARISON / FANTASY / WHAT-IF -----------------------------
@app.route('/comparison', methods=['POST'])
def player_compare():
    data = request.json
    p1 = resolve_player_name(data.get('player1'))
    p2 = resolve_player_name(data.get('player2'))
    user1 = comp_player(p1)
    user2 = comp_player(p2)

    image_url1 = resolve_player_image_url(p1)
    image_url2 = resolve_player_image_url(p2)


    index = ['Total Matches Played', 'Batting Innings', 'Total Runs', 'Total Balls Faced', 'Highest Score', 'Batting Average', 'Strike Rate', 'Centuries(100)', 'Half-centuries(50)', 'Fours', 'Sixes', 'Bowling Innings', 'Runs Conceded', 'Balls Bowled', 'Total Overs', 'Wickets', 'Bowling Economy', 'Bowling Average', 'Bowling Strike Rate', '4 Wicket Haul', '5 Wicket Haul', 'Catches', 'Stumpings', 'Runout']    
    Data = pd.DataFrame(
        {
            user1['player_name']: [
                user1['batting']['total_matches_played'],
                user1['batting']['total_innings'],
                user1['batting']['total_runs'],
                user1['batting']['total_balls_faced'],
                user1['batting']['highest_score'],
                user1['batting']['batting_average'],
                user1['batting']['strike_rate'],
                user1['batting']['total_100s'],
                user1['batting']['total_50s'],
                user1['batting']['total_fours'],
                user1['batting']['total_sixes'],
                user1['bowling']['bowling_innings'],
                user1['bowling']['total_runs_conceded'],
                user1['bowling']['total_balls_bowled'],
                user1['bowling']['total_overs'],
                user1['bowling']['wickets'],
                user1['bowling']['bowling_economy'],
                user1['bowling']['bowling_average'],
                user1['bowling']['bowling_strike_rate'],
                user1['bowling']['four_wicket_haul'],
                user1['bowling']['five_wicket_haul'],
                user1['fielding']['catches'],
                user1['fielding']['stumpings'],
                user1['fielding']['runout']
            ],

            user2['player_name']: [
                user2['batting']['total_matches_played'],
                user2['batting']['total_innings'],
                user2['batting']['total_runs'],
                user2['batting']['total_balls_faced'],
                user2['batting']['highest_score'],
                user2['batting']['batting_average'],
                user2['batting']['strike_rate'],
                user2['batting']['total_100s'],
                user2['batting']['total_50s'],
                user2['batting']['total_fours'],
                user2['batting']['total_sixes'],
                user2['bowling']['bowling_innings'],
                user2['bowling']['total_runs_conceded'],
                user2['bowling']['total_balls_bowled'],
                user2['bowling']['total_overs'],
                user2['bowling']['wickets'],
                user2['bowling']['bowling_economy'],
                user2['bowling']['bowling_average'],
                user2['bowling']['bowling_strike_rate'],
                user2['bowling']['four_wicket_haul'],
                user2['bowling']['five_wicket_haul'],
                user2['fielding']['catches'],
                user2['fielding']['stumpings'],
                user2['fielding']['runout']
            ]
        },
        index=index
    )

    return jsonify({'user1': user1, 'user2': user2, 'image_url': image_url1, 'image_url1': image_url2})

@app.route('/fantasy-matchup', methods=['POST'])
def fantasy_matchup():
    data = request.get_json(force=True)
    team1 = data.get('team1')
    team2 = data.get('team2')
    df22 = pl.read_parquet('2026.parquet')
    pl.Config.set_tbl_rows(-1)
    pl.Config.set_tbl_cols(-1)

    replacements = {
        'RCB': 'Royal Challengers Bangalore',
        'DC': 'Delhi Capitals',
        'PBKS': 'Kings XI Punjab',
        'SRH': 'Sunrisers Hyderabad',
        'CSK': 'Chennai Super Kings',
        'GT': 'Gujarat Titans',
        'RR': 'Rajasthan Royals',
        'LSG': 'Lucknow Super Giants',
        'KKR': 'Kolkata Knight Riders',
        'MI': 'Mumbai Indians'
    }
    df22 = df22.with_columns(pl.col('batting_team', 'bowling_team').replace(replacements))

    firstteam = team1
    secondteam = team2

    df_filtered22 = df22.filter(
        (pl.col("batting_team").is_in([firstteam, secondteam])) |
        (pl.col("bowling_team").is_in([firstteam, secondteam]))
    )


    # -----------------------------
    # Batter stats
    # -----------------------------
    batter_overall = (
        df_filtered22.group_by('striker')
        .agg([
            pl.sum('runs_of_bat').alias('total_runs'),
            pl.n_unique('match_no').alias('matches_played'),
            (pl.sum('runs_of_bat') / pl.n_unique('over') * 100).alias('overall_strike_rate'),
        ])
    ).sort('total_runs', descending=True)

    batter_vs_opponent = (
        df_filtered22.group_by(['striker', 'bowling_team'])
        .agg([
            pl.sum('runs_of_bat').alias('runs_vs_opponent'),
            pl.n_unique('match_no').alias('matches_vs_opponent'),
            (pl.sum('runs_of_bat') / pl.n_unique('over') * 100).alias('strike_rate_vs_opponent'),
        ])
    ).sort(['striker', 'bowling_team'])

    batter_summary = batter_vs_opponent.join(batter_overall, on='striker', how='left')


    # -----------------------------
    # Bowler stats
    # -----------------------------
    bowler_overall = (
        df_filtered22.group_by('bowler')
        .agg([
            pl.sum('runs_of_bat').alias('runs_conceded'),
            pl.n_unique('match_no').alias('matches_played'),
            (pl.col('wicket_type') != '').sum().alias('wickets_taken'),
            (pl.n_unique('over') / 6).alias('total_overs'),
            (pl.sum('runs_of_bat') / pl.n_unique('over')).alias('economy')
        ])
    ).sort('wickets_taken', descending=True)

    bowler_vs_opponent = (
        df_filtered22.group_by(['bowler', 'batting_team'])
        .agg([
            pl.sum('runs_of_bat').alias('runs_vs_opponent'),
            pl.n_unique('match_no').alias('matches_vs_opponent'),
            (pl.col('wicket_type') != '').sum().alias('wickets_vs_opponent'),
            (pl.n_unique('over') / 6).alias('overs_vs_opponent'),
            (pl.sum('runs_of_bat') / pl.n_unique('over')).alias('economy_vs_opponent')
        ])
    ).sort(['bowler', 'batting_team'])

    bowler_summary = bowler_vs_opponent.join(bowler_overall, on='bowler', how='left')



    dream_team = []

    matches = df_filtered22['match_no'].unique().to_list()

    for match in matches:
        match_df = df_filtered22.filter(pl.col('match_no') == match)
        date = match_df['date'][0]
        venue = match_df['venue'][0]

        text_content = f"Match Number: {match}\nDate: {date}\nVenue: {venue}\n\n"

        for team in [firstteam, secondteam]:
            opponent = secondteam if team == firstteam else firstteam
            text_content += f"Team: {team}\n"

            # --- Batting ---
            text_content += "  Batting:\n"
            team_batters = match_df.filter(pl.col('batting_team') == team)['striker'].unique().to_list()
        
            for batter in team_batters:
                overall_row = batter_overall.filter(pl.col('striker') == batter)
                # All vs-opponent records for this batter, not just tonight's opponent
                vs_rows = batter_vs_opponent.filter(pl.col('striker') == batter)

                if overall_row.height == 0:
                    continue

                o = overall_row.row(0, named=True)
                text_content += f"    - {batter}:\n"
                text_content += f"        Overall: {o['total_runs']} runs across {o['matches_played']} matches, Strike Rate: {o['overall_strike_rate']:.2f}\n"

                if vs_rows.height > 0:
                    text_content += f"        vs Opponents:\n"
                    for v in vs_rows.iter_rows(named=True):
                        text_content += (
                            f"            vs {v['bowling_team']}: {v['runs_vs_opponent']} runs across "
                            f"{v['matches_vs_opponent']} matches, Strike Rate: {v['strike_rate_vs_opponent']:.2f}\n"
                        )
                else:
                    text_content += f"        vs Opponents: No previous data\n"

            # --- Bowling ---
            text_content += "  Bowling:\n"
            team_bowlers = match_df.filter(pl.col('bowling_team') == team)['bowler'].unique().to_list()

            for bowler in team_bowlers:
                overall_row = bowler_overall.filter(pl.col('bowler') == bowler)
                # All vs-opponent records for this bowler
                vs_rows = bowler_vs_opponent.filter(pl.col('bowler') == bowler)

                if overall_row.height == 0:
                    continue

                o = overall_row.row(0, named=True)
                text_content += f"    - {bowler}:\n"
                text_content += (
                    f"        Overall: {o['wickets_taken']} wickets, {o['runs_conceded']} runs conceded "
                    f"across {o['matches_played']} matches, Economy: {o['economy']:.2f}\n"
                )

                if vs_rows.height > 0:
                    text_content += f"        vs Opponents:\n"
                    for v in vs_rows.iter_rows(named=True):
                        text_content += (
                            f"            vs {v['batting_team']}: {v['wickets_vs_opponent']} wickets, {v['runs_vs_opponent']} runs conceded "
                            f"across {v['matches_vs_opponent']} matches, "
                            f"Overs: {v['overs_vs_opponent']:.1f}, Economy: {v['economy_vs_opponent']:.2f}\n"
                        )
                else:
                    text_content += f"        vs Opponents: No previous data\n"

            text_content += "\n"

        dream_team.append({
            'id': f"Match Number: {match}",
            'text': text_content.strip()
        })

    user_scope = get_user_scope()
    to_embedding = rag_engine.store_fantasy(dream_team, team1, team2, user_scope=user_scope)
    return to_embedding

@app.route('/fantasy-chat', methods=['POST'])
@limiter.limit("20 per minute", key_func=limit_key_user_or_ip)
@require_tokens(estimated_cost=120)
def fantasy_chat():
    data = request.get_json()
    firstteam = data.get('firstteam')
    secondteam = data.get('secondteam')
    user_id = session.get('user_id')
    user_scope = get_user_scope()
    thread_id = data.get('threadId') or data.get('threadIde') or f"fantasy-{np.random.randint(100000, 999999)}"
    question = f"Create me a XI Player Fantasy MatchUp with the top Players for {firstteam} vs {secondteam}"
    system_prompt = systemprompts.systemPrompts.fantasy_xi_prompt
    status = get_token_status_for_user(user_id)
    fanatsyXI, tokens_used = rag_engine.ask_fantasy(
        question,
        user_id,
        thread_id,
        system_prompt,
        firstteam,
        secondteam,
        user_scope,
        max_output_tokens=get_plan_output_limit(status['plan']),
        plan_policy=fantasy_plan_policy(status['plan'])
    )
    updated = consume_tokens(user_id, tokens_used)
    log_user_activity(
        user_id=user_id,
        activity_type='fantasy_team',
        title=f"{firstteam} vs {secondteam}",
        thread_id=thread_id,
        payload={
            'team1': firstteam,
            'team2': secondteam,
            'ai_response': fanatsyXI,
            'ai_response_partial': fanatsyXI,
            'is_complete': True
        }
    )
    return jsonify({"status": "success",
                    "answer": fanatsyXI,
                    "tokens_used": int(tokens_used),
                    "tokens_remaining": updated['tokens_remaining'],
                    "plan": updated['plan'],
                    "next_refill": updated['next_refill'],
                    "thread_id": thread_id})


def whatif_matchup(season, first_team, second_team, match_id, delete_player):
    inp = str(season)
    first = first_team
    second = second_team

    matchid = str(match_id)

    df = pl.read_parquet('IPL.parquet')

    pl.Config.set_tbl_rows(-1)

    replacements = {
        'Royal Challengers Bengaluru': 'Royal Challengers Bangalore',
        'Delhi Daredevils': 'Delhi Capitals',
        'Punjab Kings': 'Kings XI Punjab',
    }

    replacement = {
        "2007/08": "2008",
        "2009/10": "2010",
        "2020/21": "2020"
    }

    df = df.with_columns(
        pl.col(['batting_team', 'bowling_team']).replace(replacements)
    )
    df = df.with_columns(
        pl.col("season").replace(replacement)
    )
    # Cast match_id column to String so is_in comparison is always str vs str
    df = df.with_columns(
        pl.col("match_id").cast(pl.Utf8)
    )

    df = df.filter(pl.col('season') == inp)

    df = df.filter(
        pl.col('batting_team').is_in([first, second]) &
        pl.col('bowling_team').is_in([first, second])
    )

    df = df.filter(
        ~pl.col('batting_team').is_in(['Kochi Tuskers Kerala', 'Pune Warriors']) &
        ~pl.col('bowling_team').is_in(['Kochi Tuskers Kerala', 'Pune Warriors'])
    )

    df = df.filter(
        pl.col('match_id').is_in([matchid])
    )

    batsmen_played = df.group_by(['match_id', 'batter', 'batting_team', 'bowler', 'bowling_team']).agg(
        [
            pl.sum('runs_batter').alias('Runs Scored in a match'),
            pl.sum('runs_extras').alias('Extra Runs'),
            pl.sum('balls_faced').alias('Balls Played'),
            pl.sum('runs_bowler').alias('Bowler Runs'),
            pl.sum('bowler_wicket').alias('bowler wickets')
        ]
    ).sort(['batting_team', 'bowling_team'])


    batting_runs = batsmen_played.group_by(['batter', 'batting_team']).agg(
        [
            pl.sum('Runs Scored in a match').alias('runs_scored'),
            pl.sum('Extra Runs').alias('Extra Runs'),
            pl.sum('Balls Played').alias('Balls Faced')
        ]
    ).sort('batting_team')

    bowling_runs = batsmen_played.group_by(['bowler', 'bowling_team']).agg(
        [
            (pl.sum('Runs Scored in a match') + pl.sum('Extra Runs')).alias('Runs Given'),
            pl.sum('Balls Played').alias('Balls Delivered'),
            pl.sum('bowler wickets').alias('Wickets Taken')
        ]
    ).sort(['bowling_team', 'Wickets Taken'], descending=[False, True])

    team_totals = batsmen_played.group_by(['batting_team']).agg(
        [
            (pl.sum('Runs Scored in a match') + pl.sum('Extra Runs')).alias('Total Runs'),
            pl.sum('Balls Played').alias('Total Balls'),
            pl.sum('bowler wickets').alias('Total Wickets')
        ]
    ).sort('batting_team')


    del_player = delete_player

    df = df.filter(
        (pl.col("batter") != del_player) &
        (pl.col("bowler") != del_player)
    )

    V = []

    for row in df.iter_rows(named=True):
        V.append({
            "match_id": row["match_id"],
            "batter": row["batter"],
            "bowler": row["bowler"],
            "batting_team": row["batting_team"],
            "bowling_team": row["bowling_team"],
            "runs_scored": row["runs_batter"],
            "extras": row["runs_extras"],
            "balls": row["balls_faced"],
            "bowler_runs": row["runs_bowler"],
            "wickets": row["bowler_wicket"]
        })


    original_df = batsmen_played

    original_batters = original_df.group_by(['batter', 'batting_team']).agg([
        pl.sum('Runs Scored in a match').alias('runs_scored'),
        pl.sum('Balls Played').alias('balls_faced'),
        pl.sum('Extra Runs').alias('extras')
    ]).sort('batting_team')

    original_bowlers = original_df.group_by(['bowler', 'bowling_team']).agg([
        (pl.sum('Runs Scored in a match') + pl.sum('Extra Runs')).alias('runs_given'),
        pl.sum('Balls Played').alias('balls_delivered'),
        pl.sum('bowler wickets').alias('wickets_taken')
    ]).sort(['bowling_team', 'wickets_taken'], descending=[False, True])

    original_teams = original_df.group_by(['batting_team']).agg([
        (pl.sum('Runs Scored in a match') + pl.sum('Extra Runs')).alias('total_runs'),
        pl.sum('Balls Played').alias('total_balls'),
        pl.sum('bowler wickets').alias('total_wickets_lost')
    ]).sort('batting_team')

    whatif_batters = df.group_by(['batter', 'batting_team']).agg([
        pl.sum('runs_batter').alias('runs_scored'),
        pl.sum('balls_faced').alias('balls_faced'),
        pl.sum('runs_extras').alias('extras')
    ]).sort('batting_team')

    whatif_bowlers = df.group_by(['bowler', 'bowling_team']).agg([
        (pl.sum('runs_batter') + pl.sum('runs_extras')).alias('runs_given'),
        pl.sum('balls_faced').alias('balls_delivered'),
        pl.sum('bowler_wicket').alias('wickets_taken')
    ]).sort('bowling_team')

    whatif_teams = df.group_by(['batting_team']).agg([
        (pl.sum('runs_batter') + pl.sum('runs_extras')).alias('total_runs'),
        pl.sum('balls_faced').alias('total_balls'),
        pl.sum('bowler_wicket').alias('total_wickets_lost')
    ]).sort('batting_team')

    original_lines = []
    original_lines.append(f"=== ORIGINAL MATCH DATA (with all players including {del_player}) ===")

    original_lines.append("\n-- Batting --")
    for row in original_batters.iter_rows(named=True):
        original_lines.append(
            f"{row['batter']} ({row['batting_team']}): {row['runs_scored']} runs off {row['balls_faced']} balls, extras {row['extras']}."
        )

    original_lines.append("\n-- Bowling --")
    for row in original_bowlers.iter_rows(named=True):
        original_lines.append(
            f"{row['bowler']} ({row['bowling_team']}): gave {row['runs_given']} runs in {row['balls_delivered']} balls, took {row['wickets_taken']} wicket(s)."
        )

    original_lines.append("\n-- Team Totals --")
    for row in original_teams.iter_rows(named=True):
        original_lines.append(
            f"{row['batting_team']}: {row['total_runs']} runs in {row['total_balls']} balls, lost {row['total_wickets_lost']} wicket(s)."
        )

    whatif_lines = []
    whatif_lines.append(f"\n=== WHAT-IF DATA (with {del_player} removed) ===")

    whatif_lines.append("\n-- Batting --")
    for row in whatif_batters.iter_rows(named=True):
        whatif_lines.append(
            f"{row['batter']} ({row['batting_team']}): {row['runs_scored']} runs off {row['balls_faced']} balls, extras {row['extras']}."
        )

    whatif_lines.append("\n-- Bowling --")
    for row in whatif_bowlers.iter_rows(named=True):
        whatif_lines.append(
            f"{row['bowler']} ({row['bowling_team']}): gave {row['runs_given']} runs in {row['balls_delivered']} balls, took {row['wickets_taken']} wicket(s)."
        )

    whatif_lines.append("\n-- Team Totals --")
    for row in whatif_teams.iter_rows(named=True):
        whatif_lines.append(
            f"{row['batting_team']}: {row['total_runs']} runs in {row['total_balls']} balls, lost {row['total_wickets_lost']} wicket(s)."
        )

    combined_text = (
        f"Match ID: {matchid} | Season: {inp} | {first} vs {second}\n\n"
        + "\n".join(original_lines)
        + "\n"
        + "\n".join(whatif_lines)
    )

    whatif_match = [
        {
            "id": str(matchid),
            "text": combined_text
        }
    ]

    return whatif_match

@app.route('/query', methods=['POST'])
@limiter.limit("20 per minute", key_func=limit_key_user_or_ip)
@require_tokens(estimated_cost=150)
def give_query():
    data = request.get_json()
    query = data.get('query')
    thread_id = data.get('thread_id') or f"whatif-thread-{np.random.randint(100000, 999999)}"
    pipeline = f"whatif_{thread_id}"
    user_id = session.get('user_id')
    user_scope = get_user_scope()
    status = get_token_status_for_user(user_id)
    answer, tokens_used = rag_engine.whatif_llm(
        query,
        user_id,
        thread_id,
        pipeline,
        user_scope,
        max_output_tokens=get_plan_output_limit(status['plan']),
        plan_policy=whatif_plan_policy(status['plan'])
    )
    updated = consume_tokens(user_id, tokens_used)
    log_user_activity(
        user_id=user_id,
        activity_type='whatif_chat',
        title=query[:100],
        thread_id=thread_id,
        payload={'query': query}
    )
    return jsonify({
        "answer": answer,
        "tokens_used": int(tokens_used),
        "tokens_remaining": updated['tokens_remaining'],
        "plan": updated['plan'],
        "next_refill": updated['next_refill'],
        "thread_id": thread_id
    })

def bowler_pipeline(bowl, bowl_team, role, pipeline, include_summary=True):
    bowl = resolve_player_name(bowl)
    bowl_norm = (bowl or "").strip().lower()
    team_aliases = get_team_aliases(bowl_team)

    df = dataframe_all.filter(pl.col('bowler').cast(pl.Utf8).str.to_lowercase() == bowl_norm)
    if team_aliases:
        df = df.filter(pl.col('bowling_team').is_in(list(team_aliases)))

    value = df.group_by(['match_id', 'season', 'bowler', 'bowling_team']).agg([
        pl.sum('bowler_wicket').alias('Wickets Taken'),
        pl.sum('balls_faced').alias('balls bowled'),
        (pl.sum('balls_faced') / 6).alias('overs faced'),
        pl.sum('runs_bowler').alias('Total runs'),
        (pl.sum('runs_bowler') / (pl.sum('balls_faced') / 6)).alias('Economy'),
        (pl.sum('runs_bowler') / pl.sum('bowler_wicket')).alias("Average"),
        (pl.sum('balls_faced') / pl.sum('bowler_wicket')).alias('Strike Rate')
    ])

    total = value.group_by(['season', 'bowler', 'bowling_team']).agg([
        pl.n_unique('match_id').alias('Matches'),
        pl.sum('Wickets Taken').alias('Total_Wickets'),
        pl.sum('overs faced').alias('Total_Overs'),
        pl.sum('Total runs').alias('Total_Runs'),
        pl.mean('Economy').alias('Seasonal_Economy'),
        (pl.sum('Total runs') / pl.sum('Wickets Taken')).alias('Seasonal_Average'),
        (pl.sum('balls bowled') / pl.sum('Wickets Taken')).alias('Seasonal_Strike_Rate')
    ]).sort('season')

    if total.is_empty():
        empty_summary = "No bowling records found for the selected filters."
        if role == 'bowler':
            return []
        return {
            'stats_image': '',
            'total': [],
            'high_wkt': {},
            'best_avg': {},
            'best_eco': {},
            'best_sr': {},
            'bowler_data': empty_summary
        }

    season_df = total.to_pandas()
    season_df = season_df.replace([np.inf, -np.inf], np.nan)

    best_wickets = season_df.loc[season_df['Total_Wickets'].idxmax(), ['season', 'Total_Wickets']]

    avg_df = season_df[season_df['Seasonal_Average'].notna()]
    eco_df = season_df[season_df['Seasonal_Economy'].notna()]
    sr_df = season_df[season_df['Seasonal_Strike_Rate'].notna()]

    best_avg = avg_df.loc[avg_df['Seasonal_Average'].idxmin(), ['season', 'Seasonal_Average']] if not avg_df.empty else pd.Series(dtype='object')
    best_eco = eco_df.loc[eco_df['Seasonal_Economy'].idxmin(), ['season', 'Seasonal_Economy']] if not eco_df.empty else pd.Series(dtype='object')
    best_sr  = sr_df.loc[sr_df['Seasonal_Strike_Rate'].idxmin(), ['season', 'Seasonal_Strike_Rate']] if not sr_df.empty else pd.Series(dtype='object')

    labels = season_df['season'].astype(str) + '\n(' + season_df['Matches'].astype(str) + ' matches)'

    fig, ax1 = plt.subplots(figsize=(14, 7))
    
    ax1.plot(season_df['season'], season_df['Total_Wickets'],
             color='#1f77b4', marker='8', linewidth=2, label='Total Wickets')   
    ax1.scatter(best_wickets['season'], best_wickets['Total_Wickets'],
                color='red', s=100, zorder=5, label='Best Season')

    ax2 = ax1.twinx()
    ax2.plot(season_df['season'], season_df['Seasonal_Economy'],
             color='#ff7f0e', marker='s', linestyle='--', linewidth=2, label='Economy')
    ax2.plot(season_df['season'], season_df['Seasonal_Average'],
             color='#d62728', marker='^', linestyle='-.', linewidth=2, label='Bowling Average')
    ax2.plot(season_df['season'], season_df['Seasonal_Strike_Rate'],
             color='#2ca02c', marker='D', linestyle=':', linewidth=2, label='Strike Rate')

    ax1.set_xlabel('Season & Matches Played', fontsize=12)
    ax1.set_ylabel('Wickets', fontsize=12)

    ax2.set_ylabel('Economy / Average / Strike Rate', fontsize=12)

    ax1.set_xticks(season_df['season'])
    ax1.set_xticklabels(labels, rotation=20)
    ax1.grid(True, linestyle='--', color='black', alpha=0.4)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

    plt.title(f"{bowl} - {'All Seasons' if not bowl_team else bowl_team}", fontsize=16, fontweight='bold')
    plt.tight_layout(pad=1.5)
    stats_image_data_url = _figure_to_data_url(fig, dpi=300)
    plt.close(fig)

   
    if not include_summary and role != 'bowler':
        return ({
            'stats_image': stats_image_data_url,
            'total':     season_df.where(pd.notna(season_df), None).to_dict(orient='records'),
            'high_wkt':  best_wickets.to_dict(),
            'best_avg':  best_avg.to_dict() if not best_avg.empty else {},
            'best_eco':  best_eco.to_dict() if not best_eco.empty else {},
            'best_sr':   best_sr.to_dict() if not best_sr.empty else {},
            'bowler_data': ""
        })

    bowler_data = []
    rows = season_df.where(pd.notna(season_df), None).to_dict(orient='records')

    def _fmt_num(v, digits=2):
        try:
            n = float(v)
            if not np.isfinite(n):
                return "NA"
            return f"{n:.{digits}f}"
        except Exception:
            return "NA"

    for row in rows:
        text = (
            f"Bowler {row.get('bowler')} from {row.get('bowling_team')} in season {row.get('season')} "
            f"played {row.get('Matches')} matches, took {row.get('Total_Wickets')} wickets, "
            f"bowled {_fmt_num(row.get('Total_Overs'), 1)} overs, conceded {row.get('Total_Runs')} runs. "
            f"Economy: {_fmt_num(row.get('Seasonal_Economy'), 2)}, "
            f"Average: {_fmt_num(row.get('Seasonal_Average'), 2)}, "
            f"Strike Rate: {_fmt_num(row.get('Seasonal_Strike_Rate'), 2)}."
        )

        bowler_data.append({
            "id": f"{pipeline}_{row.get('bowler')}_{row.get('season')}",
            "text": text
        })

    if role == 'bowler':
        return bowler_data

    question = f"""
               Geneate me a summary on the given data for the Bowler: {bowl}, across all seasons the bowler have played and give me an overview of the bowler performance
               over all the season's while also summarise what the bowlers's strength's and short-cummings are, with proper evaluation on how he can can improve.
                """
    if include_summary:
        user_scope = get_user_scope()
        namespace = f"bowler:{bowl.strip().lower()}:{(bowl_team or 'all').strip().lower()}"
        rag_engine.team_store(bowler_data, user_scope=user_scope, namespace=namespace)
        bowler_data = rag_engine.ask_team(question, user_scope=user_scope, namespace=namespace)
    else:
        bowler_data = ""
    
    return ({
        'stats_image': stats_image_data_url,
        'total':     season_df.where(pd.notna(season_df), None).to_dict(orient='records'),
        'high_wkt':  best_wickets.to_dict(),
        'best_avg':  best_avg.to_dict() if not best_avg.empty else {},
        'best_eco':  best_eco.to_dict() if not best_eco.empty else {},
        'best_sr':   best_sr.to_dict() if not best_sr.empty else {},
        'bowler_data': bowler_data
    })

# ----------------------------- FEATURE ROUTES: BOWLER / TEAMGRAPH -----------------------------
@app.route('/bowler_index', methods=['POST'])
def bowler_index():
    data = request.get_json()
    bowl_team = data.get('bowl_team')
    bowl = resolve_player_name(data.get('bowl_player'))
    role = ""
    pipeline = ""
    image_url = resolve_player_image_url(bowl)

    bowler_stats = bowler_pipeline(bowl, bowl_team, role, pipeline, include_summary=False)

    payload = json_safe({
        'stats_image': bowler_stats['stats_image'],
        'total': bowler_stats['total'],
        'high_wkt': bowler_stats['high_wkt'],
        'best_avg': bowler_stats['best_avg'],
        'best_eco': bowler_stats['best_eco'],
        'best_sr': bowler_stats['best_sr'],
        'image_url': image_url,
        'bowler_data': "",
        'summary_input_rows': bowler_stats['total']
    })
    return Response(
        json.dumps(payload, allow_nan=False),
        mimetype='application/json'
    )


@app.route('/bowler_index/summary_stream', methods=['POST'])
def bowler_index_summary_stream():
    payload = request.get_json(silent=True) or {}
    bowl = resolve_player_name((payload.get('bowl_player') or "").strip())
    bowl_team = (payload.get('bowl_team') or "").strip()
    rows = payload.get('season_stats') or []
    if not bowl:
        return Response("Please provide a bowler name.", mimetype='text/plain')

    scope_text = f"for team {bowl_team}" if bowl_team else "across all teams"
    question = f"""
               Geneate me a summary on the given data for the Bowler: {bowl}, {scope_text}, across all seasons the bowler have played and give me an overview of the bowler performance
               over all the season's while also summarise what the bowlers's strength's and short-cummings are, with proper evaluation on how he can can improve.
                """
    chunks = _build_bowler_summary_chunks(bowl, rows)
    namespace = f"bowler_summary:{bowl.strip().lower()}:{(bowl_team or 'all').strip().lower()}"

    return Response(
        stream_with_context(_stream_team_summary(question, chunks, namespace)),
        mimetype='text/plain'
    )

@app.route('/teamgraph', methods=['POST'])
def teamgraph():
    # Updated on 2026-06-14 12:00:33 +05:30: season table + top batter/bowler metrics using merged 2008-2025 and 2026 data.
    data = request.get_json(silent=True) or {}
    team = (data.get('teamname') or '').strip()
    if not team:
        return jsonify({"error": "No team provided"}), 400

    team_aliases = get_team_aliases(team)
    team_rows = df_all[
        df_all['batting_team'].isin(team_aliases) |
        df_all['bowling_team'].isin(team_aliases)
    ].copy()
    if team_rows.empty:
        return jsonify({"error": "No data found for selected team"}), 404

    team_rows['season_num'] = team_rows.apply(
        lambda r: _season_start_year(r.get('season'), r.get('date')),
        axis=1
    )
    team_rows = team_rows[team_rows['season_num'].notna()].copy()
    team_rows['season_num'] = team_rows['season_num'].astype(int)

    match_meta = team_rows[
        ['match_id', 'season_num', 'date', 'batting_team', 'bowling_team', 'match_won_by']
    ].drop_duplicates(subset='match_id')

    batting_rows = team_rows[team_rows['batting_team'].isin(team_aliases)].copy()
    bowling_rows = team_rows[team_rows['bowling_team'].isin(team_aliases)].copy()

    wins_by_season = (
        match_meta[match_meta['match_won_by'].isin(team_aliases)]
        .groupby('season_num', as_index=False)
        .agg(wins=('match_id', 'nunique'))
    )
    no_result_by_season = (
        match_meta[match_meta['match_won_by'].fillna('Unknown').eq('Unknown')]
        .groupby('season_num', as_index=False)
        .agg(no_result=('match_id', 'nunique'))
    )
    matches_by_season = (
        match_meta.groupby('season_num', as_index=False)
        .agg(matches_played=('match_id', 'nunique'))
    )
    runs_by_season = (
        batting_rows.groupby('season_num', as_index=False)
        .agg(runs_scored=('runs_total', 'sum'))
    )
    fours_sixes_by_season = (
        batting_rows.groupby('season_num', as_index=False)
        .agg(
            fours=('runs_batter', lambda s: int((s == 4).sum())),
            sixes=('runs_batter', lambda s: int((s == 6).sum()))
        )
    )
    wickets_by_season = (
        bowling_rows.groupby('season_num', as_index=False)
        .agg(wickets_taken=('bowler_wicket', 'sum'))
    )

    season_table = matches_by_season.merge(wins_by_season, on='season_num', how='left')
    season_table = season_table.merge(no_result_by_season, on='season_num', how='left')
    season_table = season_table.merge(runs_by_season, on='season_num', how='left')
    season_table = season_table.merge(fours_sixes_by_season, on='season_num', how='left')
    season_table = season_table.merge(wickets_by_season, on='season_num', how='left')
    season_table = season_table.fillna(0)
    season_table['losses'] = (
        season_table['matches_played'] - season_table['wins'] - season_table['no_result']
    ).clip(lower=0)

    top_batter_df = (
        batting_rows.groupby(['season_num', 'batter'], as_index=False)['runs_batter'].sum()
        .sort_values(['season_num', 'runs_batter'], ascending=[True, False])
        .drop_duplicates(subset=['season_num'])
        .rename(columns={'batter': 'top_batter', 'runs_batter': 'top_batter_runs'})
    )
    top_bowler_df = (
        bowling_rows.groupby(['season_num', 'bowler'], as_index=False)['bowler_wicket'].sum()
        .sort_values(['season_num', 'bowler_wicket'], ascending=[True, False])
        .drop_duplicates(subset=['season_num'])
        .rename(columns={'bowler': 'top_bowler', 'bowler_wicket': 'top_bowler_wickets'})
    )
    season_table = season_table.merge(top_batter_df, on='season_num', how='left')
    season_table = season_table.merge(top_bowler_df, on='season_num', how='left')
    season_table[['top_batter', 'top_bowler']] = season_table[['top_batter', 'top_bowler']].fillna('N/A')
    season_table[['top_batter_runs', 'top_bowler_wickets']] = season_table[['top_batter_runs', 'top_bowler_wickets']].fillna(0)

    season_table = season_table.sort_values('season_num').rename(columns={'season_num': 'season'})
    for col in ['matches_played', 'wins', 'losses', 'no_result', 'runs_scored', 'fours', 'sixes', 'wickets_taken', 'top_batter_runs', 'top_bowler_wickets']:
        season_table[col] = season_table[col].astype(int)

    # Updated on 2026-06-14 12:35:14 +05:30: Title seasons computed from all-team finals, not team-filtered matches.
    all_match_meta = df_all[['match_id', 'season', 'date', 'stage', 'match_won_by']].drop_duplicates(subset='match_id').copy()
    all_match_meta['season_num'] = all_match_meta.apply(
        lambda r: _season_start_year(r.get('season'), r.get('date')),
        axis=1
    )
    all_match_meta = all_match_meta[all_match_meta['season_num'].notna()].copy()
    all_match_meta['season_num'] = all_match_meta['season_num'].astype(int)
    all_match_meta['date'] = pd.to_datetime(all_match_meta['date'], errors='coerce')
    all_match_meta['stage_lc'] = all_match_meta['stage'].astype(str).str.lower()

    # Updated on 2026-06-14 12:54:00 +05:30: avoid groupby-apply index quirks that can drop season_num on some pandas versions.
    sorted_meta = all_match_meta.sort_values(['season_num', 'date'])
    season_finals = (
        sorted_meta[sorted_meta['stage_lc'].str.contains('final', na=False)]
        .drop_duplicates(subset='season_num', keep='last')
    )
    all_seasons = set(sorted_meta['season_num'].dropna().astype(int).tolist())
    final_seasons = set(season_finals['season_num'].dropna().astype(int).tolist())
    missing_seasons = all_seasons - final_seasons
    fallback_rows = (
        sorted_meta[sorted_meta['season_num'].isin(missing_seasons)]
        .drop_duplicates(subset='season_num', keep='last')
    )
    season_final_rows = pd.concat([season_finals, fallback_rows], ignore_index=True)
    season_final_rows = season_final_rows[season_final_rows['season_num'].notna()].copy()
    season_final_rows['season_num'] = season_final_rows['season_num'].astype(int)
    titles = (
        season_final_rows[season_final_rows['match_won_by'].isin(team_aliases)]['season_num']
        .astype(int)
        .sort_values()
        .tolist()
    )

    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax1.plot(season_table['season'], season_table['wins'], color="#175FAD", marker='s', linestyle='-', label='Matches Won Per Season')
    ax1.plot(season_table['season'], season_table['wickets_taken'], color="#F52A18", marker='o', linewidth=2, linestyle='--', label='Wickets Taken Per Season')

    ax2 = ax1.twinx()
    ax2.plot(season_table['season'], season_table['runs_scored'], color="#0D7901", marker='D', linestyle='-.', linewidth=2, label='Runs Scored Per Season')
    ax2.set_ylabel('Total Runs Made Per Season', fontsize=12, fontweight='bold')

    title_wins = season_table[season_table['season'].isin(titles)]
    if not title_wins.empty:
        ax1.scatter(
            title_wins['season'],
            title_wins['wins'],
            marker='*',
            zorder=5,
            label='Season Winner',
            color="#CF9400",
            s=400
        )

    for x, y in zip(season_table['season'], season_table['wins']):
        ax1.annotate(str(int(y)), (x, y), textcoords="offset points", xytext=(0, 8), ha='center', fontsize=10, fontweight='bold', color='black')

    line1, label1 = ax1.get_legend_handles_labels()
    line2, label2 = ax2.get_legend_handles_labels()
    ax1.legend(line1 + line2, label1 + label2, loc='upper left')
    ax1.set_title(f"'{team}' - Performance Across Seasons", fontsize=16, fontweight='bold')
    ax1.set_xlabel("Season", fontsize=12, fontweight='bold')
    ax1.set_ylabel("Total Matches Won / Total Wickets Taken", fontweight='bold', fontsize=12)
    ax1.grid(True, linestyle='--', color='black', alpha=0.5)

    plt.tight_layout(pad=1.5)
    team_graph_data_url = _figure_to_data_url(fig, dpi=300)
    plt.close(fig)

    payload = {
        'Total_matches': int(match_meta['match_id'].nunique()),
        'Total_won': int(season_table['wins'].sum()),
        'Total_lost': int(season_table['losses'].sum()),
        'Total_null': int(season_table['no_result'].sum()),
        'Total_runs': int(season_table['runs_scored'].sum()),
        'Total_wickets': int(season_table['wickets_taken'].sum()),
        'Team_graph': team_graph_data_url,
        'Total_wins': [int(x) for x in titles],
        'Title_count': int(len(titles)),
        'image_summary': "",
        'season_table': season_table.to_dict(orient='records'),
        'summary_input_rows': season_table.to_dict(orient='records')
    }
    return jsonify(json_safe(payload))


@app.route('/teamgraph/summary_stream', methods=['POST'])
def teamgraph_summary_stream():
    payload = request.get_json(silent=True) or {}
    team = (payload.get('teamname') or "").strip()
    rows = payload.get('season_stats') or []
    if not team:
        return Response("Please provide a team name.", mimetype='text/plain')

    question = f"""
               Geneate me a summary on the given data for the team: {team}, across all seasons the team have played and give me an overview of the team performance
               over all the season's while also summarise what the team's strength's and short-cummings are, with proper evaluation on how they can improve.
                """
    chunks = _build_team_summary_chunks(team, rows)
    namespace = f"team_summary:{team.strip().lower()}"

    return Response(
        stream_with_context(_stream_team_summary(question, chunks, namespace)),
        mimetype='text/plain'
    )

def whatif_weather(date):

    df_filtered = df[df['date'] == date]

    grp = df_filtered.groupby(
        ['match_id', 'season', 'batting_team', 'bowling_team', 'batter', 'bowler']
    )[['runs_total', 'balls_faced']].sum().reset_index()

    grp1 = df_filtered.groupby(
        ['match_id', 'season', 'batting_team', 'bowling_team', 'bowler', 'batter']
    )['bowler_wicket'].sum().reset_index()

    merged = pd.merge(
        grp,
        grp1,
        on=['match_id', 'season', 'batting_team', 'bowling_team', 'batter', 'bowler'],
        how='left'
    )

    match_data = []

    for _, row in merged.iterrows():
        text = (
            f"{row['batter']} from {row['batting_team']} scored "
            f"{row['runs_total']} against {row['bowler']} "
            f"in {row['balls_faced']} balls."
        )

        if row['bowler_wicket'] > 0:
            text += f" He was dismissed by {row['bowler']}."

        match_data.append({
           "id": f"{row['match_id']}_{row['batter']}_{row['bowler']}",
            "text": text
        })

    venue = df_filtered['venue'].unique().tolist()
    location = ",".join(venue)

    API_KEY = os.getenv('WEATHER_API')
    unit_group = "metric"

    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{urllib.parse.quote_plus(location)}/{date}?unitGroup={unit_group}&key={API_KEY}&contentType=json"

    try:
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                raise Exception(f"Error! Status code: {response.status}")

            weather_data = json.loads(response.read().decode('utf-8'))
            day = weather_data['days'][0]
            conditions = day.get('conditions', 'unknown')
            weather_sentence = (
                f"Weather for {weather_data['resolvedAddress']} on {day['datetime']} "
                f"is  {conditions} with a temperature of {day['temp']}C."
            )

    except Exception as e:
        return str(e)

    for item in match_data:
        item["text"] += f" Weather on match day: {weather_sentence}"
    return match_data

if __name__ == '__main__':
    app.run(debug=True)


