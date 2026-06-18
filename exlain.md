# WicketStats Internal Working Guide (Complete Technical Explanation)

## Read This First
This document is a complete internal explanation of the current WicketStats codebase, written in the exact order requested:

1. Data and analytics stack first: Pandas, Polars, NumPy, Matplotlib, and data engineering pipeline.
2. RAG, AI chatbot, and analytics flow next (highest priority section).
3. LLM execution layer after that.
4. Token system, plans, and consumption/refill lifecycle after LLM.
5. Frontend integration and end-to-end UI plus API handshake at the end.

The content is intentionally detailed and long-form so it can serve as a serious internal architecture chapter for training/project documentation.

---

## Part 1: Data and Analytics Core (Pandas, Polars, NumPy, Matplotlib)

## 1.1 Why this stack exists in this project
WicketStats is a Flask web product, but the quality of every route depends on data correctness and data speed. Because the app serves many analytics routes, it uses a mixed data stack rather than a single library:

- Pandas is used for broad preprocessing, flexible joins, groupby operations, time parsing, and route-friendly dict/json conversion.
- Polars is used where columnar speed and memory behavior are useful for computational endpoints.
- NumPy is used for numeric safety, finite checks, random IDs, and value normalization.
- Matplotlib is used for deterministic server-side graph rendering.

In this app, analytics is not a side feature. It is the foundation behind player index, bowler index, team graph, fantasy, what-if, compare, and prediction routes.

## 1.2 Dataset loading and first-stage initialization
At startup, `a.py` loads historical and current data from Parquet files:

- `IPL.parquet` as the main historical core.
- `2026.parquet` as the live-extension season dataset.

Relevant code-level behavior:

- `df = pd.read_parquet('IPL.parquet')`
- `df_2026 = pd.read_parquet('2026.parquet')`
- `dataframe = pl.read_parquet('IPL.parquet')`

Important consequences:

- The app keeps both pandas and polars representations in memory.
- It performs immediate data standardization before route logic starts.
- This avoids repeated read costs on each request.

## 1.3 Team-name normalization across seasons
A major analytics problem in IPL datasets is naming drift over years. Same franchise appears with multiple names or abbreviations.

The code normalizes this at load time for both historical and 2026 streams. Examples:

- `Royal Challengers Bengaluru` converted to `Royal Challengers Bangalore`.
- `Delhi Daredevils` converted to `Delhi Capitals`.
- `Punjab Kings` converted to `Kings XI Punjab`.
- 2026 abbreviations (`RCB`, `DC`, `PBKS`, etc.) expanded to full names.

Why this is critical:

- Groupby counts and joins break if team names are not canonical.
- Win/loss/titles logic can be wrong if aliases are not unified.
- Frontend dropdown values must map 1:1 with backend identity.

## 1.4 Season normalization and temporal coherence
Historical season labels are not always plain years, for example `2007/08`, `2009/10`, `2020/21`. The app normalizes to start-year style.

Core helper:

- `_season_start_year(val, fallback_date=None)` extracts numeric year from label text; falls back to parsed date when needed.

This function is reused where season ordering is required, especially in merged historical plus 2026 logic.

## 1.5 Pandas-safe numeric conversion strategy
The app includes explicit safety helpers to prevent mixed-type failures:

- `_safe_int_series(series, default=0)`
- `_safe_float_series(series, default=0.0)`

Both use `pd.to_numeric(..., errors='coerce')` then fill and cast. This matters because cricket feeds often have object columns with mixed strings and numbers.

Practical impact:

- Avoids conversion exceptions during aggregate pipelines.
- Keeps plots and API responses stable.
- Prevents invalid JSON numeric values.

## 1.6 2026 transformation into a historical-compatible schema
The most important data engineering block is `_normalize_2026_for_combined(raw_2026_df)`.

This function transforms 2026 schema to match the historical schema used by all legacy logic. It computes and maps:

- `season = '2026'`
- `match_id` from `match_no`
- `runs_batter`, `runs_extras`, `runs_total`, `runs_bowler`
- legal ball indicators using wide/no-ball checks
- wicket fields (`player_out`, `wicket_kind`, `fielders`)
- bowler wicket logic excluding non-bowler dismissal types
- winner inference from innings totals when direct winner field is absent

It also injects missing placeholders:

- `toss_winner = None`
- `toss_decision = None`

Why this is architecturally strong:

- Old analytics functions can keep working on one merged frame.
- You avoid writing duplicate route logic for 2026-only schema.
- Maintenance cost remains lower as new seasons arrive.

## 1.7 Building unified all-season frame (`df_all`)
After normalization:

1. Historical frame is restricted to `<= 2025` using season-year extraction.
2. 2026 normalized frame is aligned to same column universe.
3. Both are concatenated into `df_all`.

This `df_all` is the base for many endpoints, including compare, team graph, and mixed analytics.

## 1.8 Why a typed Polars view is built separately
A known failure mode appears when converting full mixed-object pandas frames directly into Polars/Arrow. To prevent this, the app creates a typed subset view:

- `_bowler_view_cols` includes only required columns.
- Every column is explicitly cast (string/int/float).
- `dataframe_all = pl.from_pandas(_bowler_view)`

This is a practical production fix:

- Avoid ArrowInvalid type errors from unrelated object columns.
- Keep bowler computations fast in Polars.
- Isolate performance paths from noisy text columns.

## 1.9 Pandas in route analytics: where and why
Pandas is still the dominant route-side operator because:

- It handles custom groupby lambda logic with rich compatibility.
- It integrates naturally with Flask JSON conversion (`to_dict`).
- Many operations depend on easy row-level manipulation.

Heavy pandas use appears in:

- player compare route
- team graph seasonal tables
- prediction route aggregate stats
- history scorecard shaping

## 1.10 Polars in route analytics: where and why
Polars appears in compute-focused areas like fantasy and bowler-related summaries.

Why Polars is used here:

- Fast grouped aggregations over match-level ball data.
- Cleaner column expressions in chained pipelines.
- Better performance for repeated summary assembly.

This mixed strategy is intentional. The app does not force one tool for all jobs.

## 1.11 NumPy usage in this project
NumPy is used for:

- JSON safety conversion for numpy scalar types.
- finite-check protection (`np.isfinite`) before serialization.
- lightweight random generation for fallback thread IDs.

This avoids common API bugs:

- NaN and Inf values breaking JSON clients.
- numpy numeric objects failing plain `json.dumps` expectations.

## 1.12 Matplotlib rendering strategy
Matplotlib is configured with non-GUI backend:

- `matplotlib.use('Agg')`

That is required for server environments and Flask workers.

Typical graph lifecycle in routes:

1. Build figure and axes.
2. Plot lines/scatter/annotations.
3. Save to static image path.
4. Close figure (`plt.close(fig)`) to avoid memory leaks.
5. Return image path in API payload.

Example outputs:

- `static/images/team.png` for team graph route.
- player and bowler graph images generated similarly.

## 1.13 Team Graph analytics internals (deep breakdown)
`/teamgraph` is one of the best examples of multi-step analytics engineering:

- Input team name.
- Alias expansion via `get_team_aliases`.
- Filter merged dataset by batting/bowling membership.
- Build `season_num` for robust ordering.
- Construct season metrics:
  - matches played
  - wins
  - no result
  - losses (derived)
  - runs scored
  - fours
  - sixes
  - wickets taken
- Compute top batter and top bowler per season.
- Compute title seasons using final-match logic from all matches, not only filtered rows.
- Plot three dimensions on dual axes.
- Return aggregate cards plus full season table.

This route is both analytics endpoint and explainability endpoint because it returns table data plus visual timeline.

## 1.14 Player and Bowler index analytics internals
Player and bowler routes split into two phases:

Phase A: numerical analytics payload

- `/player_index` and `/bowler_index` return charts, best-season metrics, and season rows.
- They intentionally skip immediate LLM summary generation for responsiveness.

Phase B: summary streaming

- Frontend calls `/player_index/summary_stream` or `/bowler_index/summary_stream` separately.
- Uses already returned season rows as compact summary context.

This architecture separates deterministic math from probabilistic language generation.

## 1.15 Prediction route data logic
`/predict` computes matchup-level stats for two teams. It includes:

- toss impact
- venue behavior
- score boundaries
- powerplay/death averages
- prediction score split
- confidence gap

Output is structured JSON, later transformed into cards in frontend.

## 1.16 History route data engineering
History module extracts scorecard-friendly slices from historical frame:

- season cards
- match lists by season
- detailed innings scorecard reconstruction

It uses helper functions for display cleaning and derived labels so raw data becomes UI-ready.

## 1.17 Why this data stack is the core strength of the project
The strongest technical quality in this project is that analytics routes are not just wrappers over static data. They perform:

- schema harmonization
- alias normalization
- typed conversion protection
- multi-season aggregation
- view-oriented serialization

This is why the product can support many analytical surfaces without duplicating business logic in every endpoint.

---

## Part 2: RAG, AI Chatbot, and Analytics Intelligence Layer (Priority Section)

## 2.1 RAG architecture in this codebase
The RAG engine is implemented in `rag_engine.py` and is deeply coupled with analytics outputs from `a.py`.

Core RAG stack:

- Vector DB: ChromaDB persistent client (`./vector_db`)
- Embedder: SentenceTransformer `all-MiniLM-L6-v2`
- LLM providers:
  - Groq client for chat completions in several flows
  - OpenRouter/OpenAI-compatible client for team summary and streaming

Collections used:

- `custom_matchup_llm`
- `fantasyXI_llm`
- `what_if_llm`
- `team_llm`

Each collection is pipeline-scoped so contexts do not leak across features.

## 2.2 Why multiple collections are used
A single shared vector store would contaminate relevance because query semantics differ by module.

Example:

- fantasy asks for XI lineup recommendations.
- what-if asks hypothetical structural changes.
- team summary asks season trend synthesis.

Separate collections preserve query precision and reduce accidental context bleed.

## 2.3 Chunk design strategy
RAG quality depends on chunk quality more than model size. This project builds chunks from computed analytics, not from raw database dumps.

Chunk examples:

- matchup summary chunk
- metric comparison chunk
- per-player batting chunks
- per-player bowling chunks
- season-wise player/team summary chunks

Benefits:

- LLM receives high-signal context.
- Retrieval is smaller and relevant.
- Faster and lower token cost vs full raw feed.

## 2.4 Embedding and store lifecycle
Common flow in store functions:

1. Prepare chunks with deterministic IDs and text.
2. Encode with sentence transformer.
3. Delete existing pipeline-specific records (for replace semantics).
4. Insert fresh embeddings/documents/metadata.

Functions implementing this pattern:

- `store(...)` for custom matchup
- `store_fantasy(...)`
- `whatif_store(...)`
- `team_store(...)`

## 2.5 Retrieval strategy and context window capping
`get_content(...)` and related functions perform query embedding and top-k retrieval.

Then they cap total context length manually (for example near 12000 chars, what-if near 15000) to avoid extreme prompt bloat.

This is critical because:

- retrieval can return verbose documents.
- model context must stay bounded.
- long contexts degrade latency and often answer quality.

## 2.6 Team summary RAG flow (streaming analytics narrative)
Team, player, and bowler summaries now use a dedicated streaming path:

- build compact season summary rows in API response.
- send rows to summary stream endpoint.
- convert rows into mini text chunks.
- upsert to `team_llm` collection.
- query relevant chunks.
- stream LLM tokens back progressively.

Relevant functions:

- `_build_batter_summary_chunks`
- `_build_bowler_summary_chunks`
- `_build_team_summary_chunks`
- `_stream_team_summary`
- `rag_engine.ask_team_stream`

This gives quick first paint for cards while LLM summary arrives incrementally.

## 2.7 Custom matchup RAG flow
For custom team matchup analytics:

- `/llm_chat` fetches latest or selected matchup from SQLite.
- Parses stored JSON fields.
- Builds multi-part chunks (summary, metrics, players).
- Stores in `custom_matchup_llm` with user metadata.

Then `/get_llm` queries this store through `rag_engine.ask(...)`.

This makes the chatbot answer based on user-generated matchup state, not generic cricket text.

## 2.8 Fantasy RAG flow
Fantasy flow has two endpoints:

- `/fantasy-matchup` computes team-vs-team context and stores as fantasy chunks.
- `/fantasy-chat` asks the model for XI recommendations from that context.

The stored fantasy chunks include:

- match context
- batter overall and vs-opponent records
- bowler overall and vs-opponent records

This gives the model structured comparative evidence for selection output.

## 2.9 What-if tool-assisted RAG flow
What-if is the most advanced chatbot flow in current code.

Core mechanism:

- LLM first decides a tool call (`tool_choice='auto'`) from `MY_TOOLS` schema.
- App executes tool via `execute_tool(...)`.
- Tool may trigger fresh analytical recomputation from `a.py`.
- Result and retrieved context are fed back to model.
- Final response is generated with enriched scenario data.

Supported tool intents include:

- remove player from match
- hypothetical scenario transforms
- role reassignment (batter or bowler)
- weather-date extraction and impact path

This is function-calling orchestration plus retrieval, not plain question-answer chat.

## 2.10 Why this RAG design is strong
The core advantage is analytics-first RAG:

- deterministic stats are computed in Python first.
- chunks represent computed facts.
- LLM handles interpretation and narrative.

This avoids the common failure of asking LLM to infer statistics from raw noisy records directly.

## 2.11 Current RAG constraints and real-world caveats
Important practical points in this codebase:

- `rag_engine.py` imports `a.py`, creating tight coupling.
- what-if mapping has season-specific assumptions hardcoded.
- collection replacement behavior may override previous contextual sessions in some flows.
- team summary collection is globally reused for player/bowler/team summary stream route context.

These are manageable but should be known for scaling refactors.

## 2.12 Suggested hardening roadmap for RAG layer
Future improvements that align with current architecture:

- Add collection namespaces per user/session for team summary stream.
- Add retrieval score threshold filtering.
- Add chunk deduplication by hash.
- Add structured JSON responses for machine-checkable outputs.
- Decouple `rag_engine` from direct `a.py` import into service interfaces.

---

## Part 3: LLM Execution Layer

## 3.1 Model clients and providers used
Current file shows two distinct model clients:

- Groq client: `groq_client.chat.completions.create(...)`
- OpenRouter-compatible client via OpenAI SDK wrapper: `or_client.chat.completions.create(...)`

Environment-driven model selection:

- `AI_MODEL` for Groq paths
- `IMAGE_MODEL` for team summary style path

## 3.2 Prompt composition strategy
The app uses system prompts from `systemprompts` module and appends policy plus context.

In `get_llm_response(...)`, system message includes:

- base system prompt
- plan response policy block
- match data context block

Then chat history and current user question are appended.

This design keeps context stable per session while allowing small incremental turns.

## 3.3 Chat memory strategy
Short memory window from SQLite `chat_data` table:

- fetches last 4 question-response pairs by user, thread, pipeline
- appends as conversation turns before current question

This balances continuity with token control.

## 3.4 Token accounting from provider usage
`extract_total_tokens(...)` reads usage metadata from response object and normalizes to integer.

Token usage then flows into plan consumption logic (`consume_tokens`).

## 3.5 Standard LLM flow (`get_llm`)
Sequence:

1. Validate question and thread.
2. Resolve user plan and output limit.
3. Retrieve RAG context and call LLM.
4. Persist answer in `chat_data`.
5. Consume used tokens.
6. Return answer plus updated token state.

## 3.6 Fantasy LLM flow
Fantasy uses plan-specific format policy:

- Basic: simple XI style
- Plus: one computed XI with C and VC
- Premium: three strategy variants

This is implemented through policy string injection, not multiple hardcoded formatter functions.

## 3.7 What-if two-stage LLM flow
What-if can run two completion calls:

Call 1:

- ask with tool schema
- detect tool call and arguments

Execution stage:

- run tool in Python
- optionally fetch/store fresh data
- build additional RAG context

Call 2:

- feed tool result and context
- generate final analytical answer

Token usage accumulates both calls.

## 3.8 Team summary streaming flow
`ask_team_stream(...)` uses provider stream mode and yields token deltas.

Fallback logic:

- if stream fails or provider does not support stream for selected model, fallback to non-stream complete answer.

This prevents empty UI even in unstable provider conditions.

## 3.9 LLM response style governance
The project uses plan policies to modulate:

- response depth
- structure
- brevity
- tactical detail

This is a good architecture decision because output control is centralized by plan instead of route-specific scattered prompt rules.

## 3.10 LLM operational risks and controls
Current controls present:

- temperature mostly set to 0 for determinism.
- context length capping before LLM call.
- explicit route-level token gating.

Risks still relevant:

- prompt drift if data chunks are inconsistent.
- stale vector store if chunk update lifecycle fails.
- provider outages affecting stream endpoints.

---

## Part 4: Token System, Plans, and Consumption Lifecycle

## 4.1 Why token system exists
Token system turns analytics and AI routes into a usable SaaS model with fairness and cost control.

Without token controls, one heavy user could consume disproportionate model usage and degrade service economics.

## 4.2 Plan model defined in code
Plan constants in `a.py`:

- `Basic`, `Plus`, `Premium`
- `PLAN_QUOTA`
- `PLAN_REFILL`
- `PLAN_MAX_OUTPUT_TOKENS`
- `REFILL_INTERVAL_HOURS = 6`

Pricing mapping in paise:

- Basic: 0
- Plus: 49900
- Premium: 99900

## 4.3 Plan normalization contract
`normalize_plan(...)` ensures casing/input variants resolve to canonical names.

This prevents logic forks caused by inconsistent plan strings from forms or DB rows.

## 4.4 Quota-row provisioning
`ensure_token_quota_row(...)` creates missing quota state at first need.

Properties stored:

- user_id
- plan
- tokens_remaining
- last_refill timestamp

This makes token status resilient even if a user row exists before quota row.

## 4.5 Refill algorithm details
`apply_refill_for_user(...)`:

1. Reads current tokens and last refill timestamp.
2. Calculates elapsed seconds.
3. Computes completed refill intervals.
4. Adds refill amount per completed interval.
5. Caps by plan quota maximum.
6. Advances `last_refill` to exact boundary.

This is robust against delayed calls and app downtime gaps.

## 4.6 Status synchronization logic
`get_token_status_for_user(...)` also syncs quota plan with `users.plan` if mismatch exists.

Reason:

- after plan upgrades, token table must reflect new plan and cap logic.

## 4.7 Consumption logic
`consume_tokens(user_id, tokens_used)`:

- normalizes token value
- reads latest status
- deducts with floor at 0
- updates DB
- returns updated state

## 4.8 Route protection contract
`@require_tokens(estimated_cost=...)` decorator enforces pre-check before expensive route logic.

If insufficient:

- returns HTTP 402 with structured payload:
  - status
  - error code
  - message
  - tokens remaining
  - plan
  - next refill

This allows frontend to show upgrade/refill guidance instantly.

## 4.9 Plan-aware output-depth control
`get_plan_output_limit(...)` is used to pass max output tokens into LLM calls.

This means plan impacts not only count of requests but depth per response.

## 4.10 Policy-based output shaping
Policies:

- `plan_response_policy`
- `fantasy_plan_policy`
- `whatif_plan_policy`

These are injected into prompt. Plan therefore impacts tone, detail level, structure, and recommendation style.

## 4.11 Payment and token linkage
Plan upgrade endpoints update both user plan and token quota metadata.

Key flows:

- register-time paid plan order creation
- dashboard-time upgrade order creation
- payment verification with HMAC
- quota realignment and plan history write

This ensures payment success has deterministic backend state transition.

## 4.12 Audit and activity tracking
`log_user_activity(...)` writes significant actions to `user_recent_activities`.

This supports dashboard activity feed and potential operational tracing.

---

## Part 5: Frontend Integration and Full-Stack Handshake

## 5.1 Frontend architecture style
The app uses Flask-rendered templates with JavaScript-enhanced interactivity.

Main templates include:

- `index.html`
- `top_score.html`
- `predict_winner.html`
- `history.html`
- `player_index.html`
- `bowler_index.html`
- `teamgraph.html`
- `comparison.html`
- `fantasy.html`
- `whatif.html`
- `dashboard.html`

## 5.2 Navigation and entry-point routing
`render_template(...)` routes are defined in `a.py` for each major module. This keeps URL to page mapping explicit and centralized.

Examples:

- `/` -> `index.html`
- `/top_scorer_page` -> `top_score.html`
- `/predict_winner_page` -> `predict_winner.html`
- `/history` -> `history.html`
- `/player_index1` -> `player_index.html`
- `/bowlerindex` -> `bowler_index.html`
- `/team_graph` -> `teamgraph.html`

## 5.3 API-first UI interactions
Most pages follow a two-step JS pattern:

1. POST to analytics endpoint for deterministic data.
2. POST to summary stream endpoint for AI narrative.

This architecture gives fast cards and charts without waiting for LLM completion.

## 5.4 Streaming UX implementation
Summary stream pages use:

- fetch stream reader (`response.body.getReader()` pattern)
- append chunks live into UI text area
- timeout handling
- retry with cached payload
- cancellation via `AbortController` when new search starts

This prevents stale mixed responses and improves perceived responsiveness.

## 5.5 Data-driven dropdown and autocomplete behavior
The project uses embedded full-name list in:

- `static/full_names_data.js`

It includes master player names for client-side suggestion and validation workflows.

Current design advantage:

- prevents invalid manual entry for long name lists
- keeps autocomplete local without extra API roundtrip

## 5.6 Team and player media integration
Static media in `static/images` includes team logos and generated plot targets.

Dynamic image URLs are also generated from IPL headshot patterns for known players using mapping file.

## 5.7 Predict winner frontend reshaping intent
The `/predict` endpoint sends rich key-value JSON. Frontend should map this payload into grouped cards and bento sections rather than raw key dump.

This has already been directionally implemented in current work and should remain schema-driven for maintainability.

## 5.8 History page frontend complexity
History page is not a simple list. It contains:

- season cards
- match cards
- full scorecard expansion
- metadata blocks

This makes it one of the most style-sensitive pages, especially for navbar and hero consistency.

## 5.9 Cross-page style consistency engineering
Recent updates introduced a shared navbar sizing profile for non-dashboard pages and synchronized hero typography.

The practical pattern used:

- final override block near end of `<style>` with `!important` for deterministic precedence.

This is useful in a codebase where templates contain legacy and newer style blocks together.

## 5.10 Frontend-backend contract examples
Player index contract:

- Backend returns:
  - stats numbers
  - season rows
  - image path
  - summary input rows
- Frontend renders cards and chart, then streams summary.

Bowler index contract is parallel to player index.

Team graph contract includes:

- snapshot cards
- season table
- plot image
- title seasons

## 5.11 Error and fallback behavior
Many endpoints return meaningful status and messages for:

- missing parameters
- no data scenarios
- token insufficiency
- stream fallback

Frontend should always map these states to clear user messages instead of silent failures.

---

## Part 6: Module-by-Module Internal Map

## 6.1 `a.py` module map
`a.py` is the orchestration core. It includes:

- app boot and environment loading
- data loading and normalization
- DB schema initialization
- auth and session routes
- payment routes
- token policy and consumption
- analytics routes
- streaming summary routes

It is a monolithic but operationally coherent control module.

## 6.2 `rag_engine.py` module map
`rag_engine.py` handles:

- vector DB and embedding clients
- chunk storage and retrieval
- chat history and LLM execution wrappers
- what-if tool function orchestration
- team summary streaming interface

It is effectively the AI service layer for the Flask app.

## 6.3 `systemprompts` role
Prompt templates are externalized, which is good because:

- prompt editing does not require route rewrites
- plan-policy overlay remains modular
- prompt tuning can be done per pipeline

## 6.4 `image_mapping` role
Provides player lookup IDs used to construct headshot URLs.

Useful because it keeps route code free from large hardcoded ID maps.

## 6.5 Templates and static assets
Templates are route views and JS interaction points.

Static layer provides:

- generated graph output targets
- logos and visuals
- embedded name datasets for client validation

---

## Part 7: Execution Walkthroughs (End-to-End)

## 7.1 Player index full lifecycle

1. User enters batter and optional team.
2. Frontend POST `/player_index`.
3. Backend computes deterministic stats and chart path.
4. Frontend renders summary cards and table immediately.
5. Frontend POST `/player_index/summary_stream` with season rows.
6. Backend builds chunks, stores in `team_llm`, retrieves, streams response.
7. Frontend appends summary tokens progressively.

## 7.2 Bowler index full lifecycle

1. User enters bowler and optional team.
2. Frontend POST `/bowler_index`.
3. Backend runs bowler pipeline and returns stats payload.
4. Frontend renders cards/table/plot.
5. Frontend starts stream via `/bowler_index/summary_stream`.
6. Backend uses chunked seasonal context and streams summary.

## 7.3 Team graph full lifecycle

1. User selects a team.
2. Frontend POST `/teamgraph`.
3. Backend computes season table, totals, titles, and graph image.
4. Frontend renders snapshot cards, season table, and graph.
5. Frontend streams AI summary via `/teamgraph/summary_stream`.

## 7.4 Custom matchup chat lifecycle

1. User builds custom teams and stats.
2. `/llm_chat` builds and embeds matchup chunks into custom collection.
3. User asks question through `/get_llm`.
4. RAG retrieves relevant chunks plus thread history.
5. LLM answers with plan-conditioned output.
6. Token usage deducted and returned.

## 7.5 Fantasy lifecycle

1. User picks two teams.
2. `/fantasy-matchup` computes and stores fantasy context.
3. `/fantasy-chat` asks for XI generation.
4. LLM returns plan-specific structure.
5. Tokens consumed.

## 7.6 What-if lifecycle

1. User asks hypothetical scenario.
2. `whatif_llm` tool-calls as needed.
3. Tool executes stats recomputation path.
4. New context is embedded and queried.
5. Final LLM response generated and stored.
6. Combined token usage deducted.

---

## Part 8: Data Model and Tables (Practical View)

## 8.1 Key tables created and used
From `init_db()` and related flows:

- `users`
- `otp_codes`
- `token_quota`
- `plan_change_history`
- `user_recent_activities`
- `custom_matchups`
- `chat_data` (created in `rag_engine.py` init)

## 8.2 Why SQLite still works here
For current project scope, SQLite is acceptable because:

- local deployment simplicity
- direct Python driver availability
- low operational overhead

For high-concurrency production, migration to managed Postgres would be the next step.

---

## Part 9: Quality, Testing, and Stability Notes

## 9.1 Strong points in current implementation

- Typed conversion guard for mixed dataframe issues.
- Clear separation between numeric payload and LLM summary generation.
- Plan-aware depth and token enforcement.
- Tool-calling what-if architecture.
- End-to-end payment verification before plan mutation.

## 9.2 Known architectural debt

- `a.py` is large and should be split into service modules.
- `rag_engine` imports `a.py`, increasing coupling.
- Some pipelines rely on static file outputs (`static/images/...`) which can race under concurrency.
- Multiple style blocks in templates can create CSS precedence conflicts.

## 9.3 Refactor-ready module split suggestion
Suggested folders:

- `services/data_pipeline.py`
- `services/token_service.py`
- `services/payment_service.py`
- `services/rag_service.py`
- `routes/analytics.py`
- `routes/auth.py`
- `routes/dashboard.py`

This would preserve behavior while increasing maintainability.

---

## Part 10: Final Internal Summary (What actually makes this project strong)

If this project is evaluated for internal technical depth, your strongest differentiator is not only UI or route count. It is the combined architecture:

- Real data engineering to merge historical and new-season schemas.
- Multi-library analytics pipeline where each tool is used for a specific reason.
- Retrieval-augmented AI grounded in computed cricket context.
- Tool-calling what-if system that can trigger data recomputation.
- Plan-aware output shaping and token economics tied to payment verification.
- Frontend that uses stream-based progressive rendering for high-latency AI content.

This is exactly the profile of a serious full-stack analytics plus AI product prototype.

---

## Appendix A: Quick Reference by Concern

### A.1 Data concerns
Use:

- `_normalize_2026_for_combined`
- `_safe_int_series`
- `_safe_float_series`
- `get_team_aliases`

### A.2 AI summary concerns
Use:

- `/player_index/summary_stream`
- `/bowler_index/summary_stream`
- `/teamgraph/summary_stream`
- `rag_engine.ask_team_stream`

### A.3 Chatbot concerns
Use:

- `/llm_chat` and `/get_llm`
- `/fantasy-matchup` and `/fantasy-chat`
- what-if tool chain via `whatif_llm`

### A.4 Token concerns
Use:

- `get_token_status_for_user`
- `consume_tokens`
- `require_tokens`

### A.5 Plan and payment concerns
Use:

- `/register/create-order`
- `/register`
- `/dashboard/upgrade-plan/create-order`
- `/dashboard/upgrade-plan/verify-payment`

---

## Appendix B: Suggested Viva/Interview Narrative Using This File

When presenting this project verbally, the strongest order is:

1. Start with data harmonization challenge across IPL historical plus 2026 schema.
2. Explain why mixed Pandas plus Polars plus NumPy plus Matplotlib is intentional.
3. Explain two-phase endpoint architecture: deterministic stats first, LLM narrative second.
4. Explain RAG collection design and what-if tool calling.
5. Explain plan-aware token and payment-verified upgrade lifecycle.
6. End with frontend streaming UX and reliability controls.

This sequence demonstrates engineering maturity, not only feature implementation.

---

## Document Completion Note
This file is now a complete internal working explanation and can be used as the long-form module chapter for project documentation.
