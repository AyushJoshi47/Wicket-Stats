# WicketStats: Streaming Retry + Razorpay + Plan System (Explained)

## 1. What was changed in AI summary streaming

### Problem before
- The UI showed summary text with a fake JS typing effect after backend finished full generation.
- Users waited for the full model response before seeing summary text.
- If streaming/generation got slow, there was no clear retry path.

### New behavior
- Stats/cards/table/graph are returned first from:
  - `/player_index`
  - `/bowler_index`
  - `/teamgraph`
- AI summary now streams separately from:
  - `/player_index/summary_stream`
  - `/bowler_index/summary_stream`
  - `/teamgraph/summary_stream`
- Frontend consumes `response.body.getReader()` chunks and appends text live.

### Cancellation on new search
- Each page now tracks one active summary stream with `AbortController`.
- On new search/click, old stream is aborted immediately.
- Result: no mixed summaries from old and new requests.

### Timeout + retry
- Each summary stream has a timeout window (`SUMMARY_STREAM_TIMEOUT_MS = 45000`).
- If timeout or stream failure occurs:
  - A clear message is shown.
  - A `Retry` button appears.
- Retry reuses the last payload (player/team + season rows) and starts a fresh stream.

## 2. Bowler 500 error fix

### Error
- `ValueError: attempt to get argmax of an empty sequence`
- Happened in `bowler_pipeline()` when filtered data was empty and code called `idxmax()/idxmin()`.

### Fix
- Added guard for empty aggregated data (`total.is_empty()`).
- Returns safe empty payload instead of crashing:
  - empty `total`
  - empty best stat dicts
  - empty `stats_image`
- Route `/bowler_index` now responds gracefully even for missing/invalid filter combinations.

## 3. Razorpay payment flow

### Config
- Razorpay keys are read from env:
  - `RAZOR_PAY_KEY` or `RAZORPAY_KEY_ID`
  - `RAZOR_PAY_SECRET` or `RAZORPAY_KEY_SECRET`
- Plan pricing (`PLAN_PRICES`):
  - `Basic = 0`
  - `Plus = 49900` (paise)
  - `Premium = 99900` (paise)

### Registration payment flow
1. Frontend calls `POST /register/create-order` with `name, email, password, otp, plan`.
2. Backend validates OTP and duplicate email.
3. If plan is paid:
   - Creates Razorpay order and returns `order_id`, `amount`, `key_id`.
4. Frontend completes Razorpay checkout.
5. Frontend submits `POST /register` with form fields + `razorpay_order_id`, `razorpay_payment_id`, `razorpay_signature`.
6. Backend verifies signature using HMAC SHA256 (`order_id|payment_id` with key secret).
7. On success:
   - Creates user
   - Sets session
   - Initializes token quota row
   - Deletes OTP entry

### Upgrade payment flow (dashboard)
1. Frontend calls `POST /dashboard/upgrade-plan/create-order` with target `plan`.
2. Backend validates user + current plan.
3. If target plan is paid, creates Razorpay order and returns order info.
4. Frontend completes checkout and calls `POST /dashboard/upgrade-plan/verify-payment`.
5. Backend verifies signature and updates:
   - `users.plan`
   - `token_quota.plan`
   - `token_quota.tokens_remaining` (raised to plan cap logic)
   - `token_quota.last_refill`
   - inserts audit row in `plan_change_history`

## 4. How plan changes affect AI behavior

### Plan normalization
- `normalize_plan()` maps input to `Basic/Plus/Premium`.

### Token quota and refill
- Quota/refill are plan-based:
  - `PLAN_QUOTA`
  - `PLAN_REFILL`
  - refill interval: every `REFILL_INTERVAL_HOURS = 6`
- `get_token_status_for_user()`:
  - syncs quota plan with `users.plan`
  - applies elapsed refills
  - returns `tokens_remaining`, `plan`, `next_refill`
- `consume_tokens()` deducts after responses.

### Response depth limits
- `PLAN_MAX_OUTPUT_TOKENS` controls max generation length per plan.
- Plan-aware policy strings shape output style:
  - `plan_response_policy()` (general)
  - `fantasy_plan_policy()`
  - `whatif_plan_policy()`

## 5. New endpoints introduced for streaming

- `POST /player_index/summary_stream`
  - input: `player`, `season_stats`
  - output: streamed plain text summary

- `POST /bowler_index/summary_stream`
  - input: `bowl_player`, `season_stats`
  - output: streamed plain text summary

- `POST /teamgraph/summary_stream`
  - input: `teamname`, `season_stats`
  - output: streamed plain text summary

## 6. Frontend files updated

- `templates/player_index.html`
- `templates/bowler_index.html`
- `templates/teamgraph.html`

All three now have:
- cancel-on-new-search stream handling,
- timeout detection,
- retry button rendering,
- live chunk append from backend stream.

## 7. New upgrade: team-scoped summary and graph consistency fixes

### Issue identified
- In Player/Bowler index, two modes exist:
  - Career mode (player only)
  - Vs Team mode (player + team)
- But users could still see same-looking graph/summary between modes due to:
  - graph image caching in browser,
  - summary prompt not explicitly carrying selected team scope,
  - strict team/name match behavior.

### Fixes added
- **Player graph cache-bust**
  - Frontend now appends timestamp query param to `player_plot` image URL.
  - Prevents stale image reuse across career/team searches.

- **Team-aware summary prompts**
  - `player_index_summary_stream` now accepts `team` and injects scope text:
    - `for team <name>` or `across all teams`
  - `bowler_index_summary_stream` now accepts `bowl_team` and injects scope text similarly.
  - Frontend sends selected team in stream payload for retry and first request.

- **Normalized filtering**
  - Player and bowler filters now compare case-insensitively with trim normalization.
  - Team filters for both are also normalized the same way.

### Expected result
- Career and team-mode now produce distinct stats context more reliably.
- Graph refreshes correctly after each search (no stale cached plot).
- AI summary is explicitly aligned with selected team scope when team is provided.
