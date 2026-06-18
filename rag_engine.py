import chromadb
import a
import json
import os
import sqlite3

from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI
from sentence_transformers import SentenceTransformer

import systemprompts
from whatifmapping import whatif_mapping

load_dotenv()

# API and vector DB clients
or_client = OpenAI(
    api_key=os.getenv('OPEN_ROUTER'),
    base_url='https://openrouter.ai/api/v1'
)
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
chromadb_client = chromadb.PersistentClient(path='./vector_db')
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Collections
chroma_collection_matchup = chromadb_client.get_or_create_collection('custom_matchup_llm')
chroma_collection_fantasy = chromadb_client.get_or_create_collection('fantasyXI_llm')
chroma_collection_whatif = chromadb_client.get_or_create_collection('what_if_llm')
chroma_collection_teamgraph = chromadb_client.get_or_create_collection('team_llm')


def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_data (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id  TEXT    NOT NULL,
            user_id    INTEGER NOT NULL,
            question   TEXT    NOT NULL,
            response   TEXT    NOT NULL,
            pipeline   TEXT    NOT NULL DEFAULT 'custom',
            created_at TEXT    DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

init_db()


def store(chunks, user_id):
    if not chunks:
        return 'no data is provided'

    user_id_str = str(user_id)
    batch_size = 500
    prepared_batches = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        ids = [str(c['id']) for c in batch]
        documents = [c['text'] for c in batch]
        metadata = [{'user_id': user_id_str, 'pipeline': 'custom'} for _ in batch]
        embeddings = embedder.encode(documents).tolist()
        prepared_batches.append((ids, documents, embeddings, metadata))

    existing = chroma_collection_matchup.get(where={'user_id': user_id_str})
    if existing['ids']:
        chroma_collection_matchup.delete(ids=existing['ids'])

    for ids, documents, embeddings, metadata in prepared_batches:
        chroma_collection_matchup.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadata
        )
    return 'Custom match-up data embeded success-fully'


def store_fantasy(chunks, teamA, teamB, user_scope):
    if not chunks:
        return "no data is provided"

    team_key = "_vs_".join([teamA.strip(), teamB.strip()])
    user_scope_str = str(user_scope)
    batch_size = 500
    prepared_batches = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        ids = [str(f['id']) for f in batch]
        documents = [f['text'] for f in batch]
        metadatas = [{"pipeline": "fantasy", "team_key": team_key, "user_scope": user_scope_str} for _ in batch]
        embeddings = embedder.encode(documents).tolist()
        prepared_batches.append((ids, documents, embeddings, metadatas))

    existing = chroma_collection_fantasy.get(where={"$and": [{"team_key": team_key}, {"user_scope": user_scope_str}]})
    if existing['ids']:
        chroma_collection_fantasy.delete(ids=existing['ids'])

    for ids, documents, embeddings, metadatas in prepared_batches:
        chroma_collection_fantasy.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings
        )

    return f"Data embedded for {team_key}"


def get_content(question, collection, filter):
    data_in_collection = collection.count()
    if data_in_collection == 0:
        return "Nothing is stored in the CHROMA DB"
   
    question_embedding = embedder.encode(question).tolist()
    result = collection.query(
        where= filter,
        query_embeddings= question_embedding,
        n_results= 5
    )
    raw_documents = result.get('documents', [])
    docs = raw_documents[0] if raw_documents else []
    context = ""
    for doc in docs:
        if len(context) + len(doc) > 12000:
            break
        context += doc + "\n----\n"
    return context if context else "No relevent data found for the query"

def extract_total_tokens(response_obj):
    usage = getattr(response_obj, 'usage', None)
    if usage is None:
        return 0
    total = getattr(usage, 'total_tokens', None)
    if total is None and isinstance(usage, dict):
        total = usage.get('total_tokens', 0)
    try:
        return int(total or 0)
    except Exception:
        return 0

def get_llm_response(question, user_id, thread_id, system_prompt, content, pipeline, max_output_tokens=400, plan_policy=""):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT question, response
        from chat_data
        where user_id = ? AND thread_id = ? AND pipeline = ?
        ORDER BY created_at DESC
        LIMIT 4
        """, (user_id, thread_id, pipeline)
    )
    row = cursor.fetchall()

    # â”€â”€ Content is injected into the system prompt once, not per user turn â”€â”€
    system_with_context = (
        f"{system_prompt}\n\n"
        f"=== PLAN RESPONSE POLICY ===\n"
        f"{plan_policy}\n"
        f"=== END PLAN RESPONSE POLICY ===\n\n"
        f"=== MATCH DATA (use this to answer all questions in this session) ===\n"
        f"{content}\n"
        f"=== END OF MATCH DATA ==="
    )

    message = [{'role': 'system', 'content': system_with_context}]

    # Chat history: plain questions and answers â€” no content repetition
    for question_text, response_text in reversed(row):
        message.append({'role': 'user',      'content': question_text})
        message.append({'role': 'assistant', 'content': response_text})

    # Current turn: just the question
    message.append({'role': 'user', 'content': question})

    response = groq_client.chat.completions.create(
        model=os.getenv('AI_MODEL'),
        messages=message,
        temperature=0,
        max_tokens=max_output_tokens
    )
    answer = response.choices[0].message.content
    tokens_used = extract_total_tokens(response)

    cursor.execute(
        """
        INSERT INTO chat_data (thread_id, user_id, question, response, pipeline) VALUES (?,?,?,?,?)
        """, (thread_id, user_id, question, answer, pipeline)
    )
    conn.commit()
    conn.close()
    return answer, tokens_used


def ask(question, thread, user_id, system_prompt, max_output_tokens=400, plan_policy=""):
    user_id_str = str(user_id)
    content = get_content(
        question = question,
        collection = chroma_collection_matchup,
        filter = {'user_id': user_id_str}
    )
    return get_llm_response(
        question= question,
        user_id= user_id_str,
        thread_id= thread,
        system_prompt = system_prompt,
        content= content,
        pipeline= 'custom',
        max_output_tokens=max_output_tokens,
        plan_policy=plan_policy
    )

def ask_fantasy(question, user_id, thread_id, system_propmt, teamA, teamB, user_scope, max_output_tokens=400, plan_policy=""):
    team_key = "_vs_".join([teamA.strip(), teamB.strip()])
    user_id_str = str(user_id)
    user_scope_str = str(user_scope)
    content = get_content(
        question= question,
        collection= chroma_collection_fantasy,
        filter= {"$and": [{"team_key": team_key}, {"user_scope": user_scope_str}]}
    )
    return get_llm_response(
        question= question,
        user_id= user_id_str,
        thread_id= thread_id,
        system_prompt = system_propmt,
        content= content,
        pipeline= 'fantasy',
        max_output_tokens=max_output_tokens,
        plan_policy=plan_policy
    )

MY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "extract_weather_date_query",
            "description": (
                "Extracts a full date from a user's query related to weather conditions "
                "and returns it in normalized ISO format (YYYY-MM-DD). "
                "Example: '20 April 2024' → '2024-04-20'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": (
                            "Normalized date in ISO format: YYYY-MM-DD. "
                            "Month must always be numeric (01–12). "
                            "Day must always be two-digit format (01–31). "
                            "Example outputs: '2024-04-20', '2008-02-18'."
                        ),
                        "pattern": "^(2008|2009|201[0-9]|202[0-5])-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"
                    }
                },
                "required": ["date"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "whatif_player_was_bowler_or_batter",
            'description': (
                "Scenerio where the given player is asked if the player played as the bowler in its"
                'You only need the player_name, what the will will be'
                'eg:- "What if RG Sharma Played a opening Bowler." or "Would YS Chahal be a good bowler if he primarily was a batsmen "'
                'you will get the all the values of tha person regarding that field, if you want the player to be a batsmen and the bowler you will get all the related data.'
            ),
            "parameters": {
                "type": 'object',
                'properties': {
                    'player_name': {
                        'type': 'string',
                        'description': (
                             "Full player name as commonly known. "
                            "e.g. 'V Kohli', 'MS Dhoni', 'Rohit Sharma or RG Sharma'. "
                            "Even if they have a full name such as Ravendra Jadeja always convert it into initials with the data as - Virat Kohli must always be V Kohli"
                        )
                    },
                    'player_role':{
                        'type': 'string',
                        'description': (
                            "This is the new role that they are to be assigned to"
                            "What if V Kohli was a bowler - bowler is the new role that they have been assigned to."
                            "role must be just 'batter' or 'bowler'."
                        )
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_player_from_match",
            "description": (
                "Removes a player from a specific IPL match and returns recalculated "
                "team stats without that player's contributions. "
                "Use this when user asks 'what if [player] didn't play', "
                "'what if [player] was absent', 'remove [player] from match', etc. "
                "You ONLY need player_name + season + any ONE of: match_id (ordinal/numeric) OR team OR opponent. "
                "Never hallucinate values â€” leave fields empty if not stated by the user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "player_name": {
                        "type": "string",
                        "description": (
                            "Full player name as commonly known. "
                            "e.g. 'V Kohli', 'MS Dhoni', 'Rohit Sharma or RG Sharma'. "
                            "Even if they have a full name such as Ravendra Jadeja always convert it into initials - Virat Kohli must always be V Kohli"
                        )
                    },
                    "season": {
                        "type": "string",
                        "description": (
                            "IPL season year. e.g. '2025', '2024'. "
                            "If user says 'this year' or 'latest IPL', use '2025'."
                        )
                    },
                    "match_id": {
                        "type": "string",
                        "description": (
                            "The match identifier. Can be any of: "
                            "(a) Ordinal label â€” '74th', '1st', '33rd' when user says 'Nth match of IPL'. "
                            "(b) Numeric ID â€” a raw integer match ID. "
                            "(c) Playoff label â€” 'Final', 'Qualifier 1', 'Eliminator', 'Qualifier 2'. "
                            "Leave EMPTY if user mentions no specific match."
                        )
                    },
                    "team": {
                        "type": "string",
                        "description": "The player's team in this match. Leave EMPTY if not stated."
                    },
                    "opponent": {
                        "type": "string",
                        "description": "The opposing team. Leave EMPTY if not stated."
                    }
                },
                "required": ["player_name", "season"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "hypothetical_scenario_whatif",
            "description": (
                "Handles hypothetical IPL scenarios: partial_contribution, swap_players, "
                "change_team, change_position. Use when user says things like "
                "'what if Kohli batted only 10 balls', 'swap Bumrah and Chahal', "
                "'what if Kohli played for CSK', 'what if Dhoni opened the batting'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_type": {
                        "type": "string",
                        "description": (
                            "One of: 'partial_contribution', 'swap_players', "
                            "'change_team', 'change_position'."
                        )
                    },
                    "player_1": {
                        "type": "string",
                        "description": (
                            "Full name of the primary player. "
                            "Expand initials where unambiguous: 'V Kohli' â†’ 'Virat Kohli'."
                        )
                    },
                    "player_2": {
                        "type": "string",
                        "description": (
                            "Full name of the second player. "
                            "Only required for 'swap_players' scenario. Leave EMPTY otherwise."
                        )
                    },
                    "target_team": {
                        "type": "string",
                        "description": (
                            "The team the player belongs to OR is moving to, depending on scenario. "
                            "Use full official team names (same as remove_player_from_match). "
                            "Leave EMPTY if not stated â€” will be auto-resolved from match mapping."
                        )
                    },
                    "season": {
                        "type": "string",
                        "description": (
                            "IPL season year. e.g. '2025', '2024'. "
                            "If user says 'this year' or 'latest IPL', use '2025'."
                        )
                    },
                    "match_context": {
                        "type": "string",
                        "description": (
                            "The match identifier â€” same rules as match_id in remove_player_from_match. "
                            "Can be: ordinal ('74th'), playoff label ('Final', 'Qualifier 1'), "
                            "numeric ID ('1473511'), or opponent reference ('vs CSK'). "
                            "Leave EMPTY if user mentions no specific match."
                        )
                    },
                    "constraint": {
                        "type": "string",
                        "description": (
                            "The specific constraint or limit in the hypothetical. "
                            "Only for 'partial_contribution' scenarios. "
                            "e.g. 'bowled only 1 over', 'batted only 10 balls', "
                            "'scored only 5 runs', 'got out for a duck', 'bowled only 2 overs'. "
                            "Extract this verbatim from the user's question."
                        )
                    }
                },
                "required": ["scenario_type", "player_1", "season"]
            }
        }
    }
]

def whatif_store(chunks, user_scope, thread_id):
    if not chunks:
        return "nothing in the what-if"
    batch_size = 500
    prepared_batches = []
    user_scope_str = str(user_scope)
    thread_id_str = str(thread_id)
    where_filter = {"$and": [{"user_scope": user_scope_str}, {"thread_id": thread_id_str}]}
    existing = chroma_collection_whatif.get(where=where_filter)
    if existing['ids']:
        chroma_collection_whatif.delete(ids=existing['ids'])

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        ids = [str(c['id']) for c in batch]
        documents = [c['text'] for c in batch]
        embeddings = embedder.encode(documents).tolist()
        metadatas = [{"pipeline": "whatif", "user_scope": user_scope_str, "thread_id": thread_id_str} for _ in batch]
        prepared_batches.append((ids, documents, embeddings, metadatas))

    
    for ids, documents, embeddings, metadatas in prepared_batches:
        chroma_collection_whatif.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
    
    return "what-if data embedded successfully"

def is_empty(val):
    return val is None or str(val).strip() == ""


def resolve_match(season, match_id, mapping):
    if is_empty(season) or is_empty(match_id):
        return None

    season_data = mapping.get(str(season), {})
    match_id_str = str(match_id)

    if match_id_str in season_data:
        return season_data[match_id_str]

    for match in season_data.values():
        if match.get("id") == match_id:
            return match

    return None


def _fetch_and_store_match(season, first_team, second_team, match_id, user_scope, thread_id, delete_player=None):

    raw_match_docs = a.whatif_matchup(
        season=season,
        first_team=first_team,
        second_team=second_team,
        match_id=match_id,
        delete_player=delete_player
    )
    return whatif_store(raw_match_docs, user_scope=user_scope, thread_id=thread_id)

def execute_tool(fn_name, fn_args, pipeline, user_scope, thread_id):
 
    if fn_name == "remove_player_from_match":
        season = fn_args.get("season")
        first_team = fn_args.get("team")
        second_team = fn_args.get("opponent")
        match_id = fn_args.get("match_id")
        delete_player = fn_args.get("player_name")
        

        mapping = whatif_mapping()
        match_data = resolve_match(season, match_id, mapping)

        if match_data:
            match_id = match_data.get("id")
            if is_empty(first_team):
                first_team = match_data.get("batting")
            if is_empty(second_team):
                second_team = match_data.get("bowling")
 
        if is_empty(season) or is_empty(first_team) or is_empty(match_id) or is_empty(delete_player):
            return {
                "error": "Missing required fields (even after mapping)",
                "resolved": {
                    "season": season,
                    "team": first_team,
                    "opponent": second_team,
                    "match_id": match_id,
                    "player_name": delete_player
                }
            }

        return _fetch_and_store_match(
            season=season,
            first_team=first_team,
            second_team=second_team,
            match_id=match_id,
            user_scope=user_scope,
            thread_id=thread_id,
            delete_player=delete_player
        )
 
    if fn_name == "hypothetical_scenario_whatif":
        season        = fn_args.get("season")
        scenario_type = fn_args.get("scenario_type")
        player_1      = fn_args.get("player_1")
        player_2      = fn_args.get("player_2")
        target_team   = fn_args.get("target_team")
        match_context = fn_args.get("match_context")
        constraint    = fn_args.get("constraint")
 
        mapping = whatif_mapping()
        match_data = resolve_match(season, match_context, mapping)
 
        payload = {
            "scenario_type": scenario_type,
            "player_1": player_1,
            "player_2": player_2,
            "target_team": target_team,
            "season": season,
            "constraint": constraint,
        }

        if match_data:
            match_id_numeric = match_data.get("id")
            batting_team     = match_data.get("batting")
            bowling_team     = match_data.get("bowling")
 
            payload["match_id"]     = match_id_numeric
            payload["batting_team"] = batting_team
            payload["bowling_team"] = bowling_team
 
            try:
                _fetch_and_store_match(
                    season=season,
                    first_team=batting_team,
                    second_team=bowling_team,
                    match_id=match_id_numeric,
                    user_scope=user_scope,
                    thread_id=thread_id,
                    delete_player=None
                )
                payload["match_stats_loaded"] = True
            except Exception as e:
                payload["match_stats_loaded"] = False
                payload["fetch_error"] = str(e)
        else:
            payload["match_resolved"] = False
            payload["note"] = (
                "No specific match found in mapping for the given season/match_context. "
                "The LLM should answer this hypothetical analytically from cricket knowledge."
            )
        return {
            'status': 'ok',
            'scenario': payload
        }
 
    if fn_name == "whatif_player_was_bowler_or_batter":
        player = fn_args.get('player_name')
        role   = fn_args.get('player_role')

        if role == 'bowler':
            teamname = ""
            bowler_data = a.bowler_pipeline(player, teamname, role, pipeline)
            return whatif_store(bowler_data, user_scope=user_scope, thread_id=thread_id)
        
        elif role == 'batter':
            team = ""
            batting = a.batter_index(player, team, role)
            return whatif_store(batting, user_scope=user_scope, thread_id=thread_id)
    
    if fn_name == "extract_weather_date_query":
        date = fn_args.get("date")
        match_data= a.whatif_weather(date=date)
        whatif_store(match_data, user_scope=user_scope, thread_id=thread_id)
        return 'OK DONE'    

    return {"error": f"Unknown tool: {fn_name}"}

   




def whatif_llm(question, user_id, thread_id, pipeline, user_scope, max_output_tokens=400, plan_policy=""):
    pipeline = pipeline
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT question, response
        from chat_data
        where user_id = ? AND thread_id = ? AND pipeline = ?
        ORDER BY created_at DESC
        LIMIT 4
        """, (user_id, thread_id, pipeline)
    )

    row = cursor.fetchall()
    messages = [
        {
            "role": "system",
            "content": (
                f"{systemprompts.systemPrompts.whatif_prompt}\n\n"
                f"=== PLAN RESPONSE POLICY ===\n"
                f"{plan_policy}\n"
                f"=== END PLAN RESPONSE POLICY ==="
            )
        }
    ]

    for question_text, response_text in reversed(row):
        messages.append({'role': 'user',      'content': question_text})
        messages.append({'role': 'assistant', 'content': response_text})

    messages.append({"role": "user", "content": question})

    response = groq_client.chat.completions.create(
        model=os.getenv("AI_MODEL"),
        messages=messages,
        tools=MY_TOOLS,
        tool_choice="auto",
        temperature=0,
        max_tokens=max_output_tokens
    )
    initial_tokens = extract_total_tokens(response)

    message = response.choices[0].message


    if message.tool_calls:
        tool_call = message.tool_calls[0]
        fn_name   = tool_call.function.name
        fn_args   = json.loads(tool_call.function.arguments)

        result    = execute_tool(fn_name, fn_args, pipeline, user_scope, thread_id)


        question_query = embedder.encode(question).tolist()
        
        rag_context = chroma_collection_whatif.query(
            query_embeddings=[question_query],
            where={"$and": [{"user_scope": str(user_scope)}, {"thread_id": str(thread_id)}]},
            n_results=60,
        )

        rag_context = rag_context.get('documents', [])
        doc = rag_context[0] if rag_context else []
        rag_context = ""
        for raw in doc:
            if len(rag_context) + len(raw) > 15000:
                break
            rag_context += raw + "\n\n"
        
        messages.append(message)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result) + "\n\n<====== MATCH DATA ======>\n\n" + rag_context + "<=======END OF MATCH DATA ======>"
        })

        final_response = groq_client.chat.completions.create(
            model=os.getenv("AI_MODEL"),
            messages=messages,
            max_tokens=max_output_tokens
        )
        final_tokens = extract_total_tokens(final_response)

        answer = final_response.choices[0].message.content
        cursor.execute(
            """
            INSERT INTO chat_data (thread_id, user_id, question, response, pipeline) VALUES (?,?,?,?,?)
            """, (thread_id, user_id, question, answer, pipeline)
        )
        conn.commit()
        conn.close()
        return answer, (initial_tokens + final_tokens)
    
    answer = message.content
    cursor.execute(
        """
        INSERT INTO chat_data (thread_id, user_id, question, response, pipeline) VALUES (?,?,?,?,?)
        """, (thread_id, user_id, question, answer, pipeline)
    )
    conn.commit()
    conn.close()
    return answer, initial_tokens



def team_store(chunks, user_scope, namespace):
    chunk_size = 5
    user_scope_str = str(user_scope)
    namespace_str = str(namespace)

    where_filter = {"$and": [{"user_scope": user_scope_str}, {"namespace": namespace_str}]}
    existing = chroma_collection_teamgraph.get(where=where_filter)
    if existing['ids']:
        chroma_collection_teamgraph.delete(ids=existing['ids'])

    for i in range(0, len(chunks), chunk_size):
        batch = chunks[i:i+chunk_size]
        ids = [str(c['id']) for c in batch]
        documents = [str(t['text']) for t in batch]
        embeddings = embedder.encode(documents).tolist()

        metadatas = [{"pipeline": "team_summary", "user_scope": user_scope_str, "namespace": namespace_str} for _ in batch]
        chroma_collection_teamgraph.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
    return 'data embedded successfully'

def get_answer(question, user_scope, namespace):
    question_embedding = embedder.encode(question).tolist()
    result = chroma_collection_teamgraph.query(
        query_embeddings= [question_embedding],
        where={"$and": [{"user_scope": str(user_scope)}, {"namespace": str(namespace)}]},
        n_results=10
    )

    doc = result.get('documents', [])
    raw = doc[0] if doc else []
    content = ''
    for docs in raw:
        if len(content) + len(docs) > 12000:
            break
        content += docs + '\n\n'
    return content




# will do for the both bowler and batsmen stats
def get_team(content, question):
    messages = [
        {
            'role': 'system',
            'content': f"{systemprompts.systemPrompts.image_llm}\n\n=== MATCH DATA ===\n{content}\n=== END OF MATCH DATA ==="
        },
        {
            'role': 'user',
            'content': question 
        }
    ]

    response = or_client.chat.completions.create(
        model= os.getenv("IMAGE_MODEL"),
        messages= messages,
        temperature=0
    )

    answer = response.choices[0].message.content
    return answer

def ask_team(question, user_scope, namespace):
    get_result = get_answer(question, user_scope, namespace)
    return get_team(get_result, question)


def ask_team_stream(question, user_scope, namespace):
    content = get_answer(question, user_scope, namespace)
    messages = [
        {
            'role': 'system',
            'content': f"{systemprompts.systemPrompts.image_llm}\n\n=== MATCH DATA ===\n{content}\n=== END OF MATCH DATA ==="
        },
        {
            'role': 'user',
            'content': question
        }
    ]

    try:
        stream = or_client.chat.completions.create(
            model=os.getenv("IMAGE_MODEL"),
            messages=messages,
            temperature=0,
            stream=True
        )

        for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except Exception:
                delta = None
            if delta:
                yield delta
    except Exception:
        # Fallback for providers/models that do not support streaming.
        yield get_team(content, question)
