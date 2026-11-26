# Reacher Backend

FastAPI backend for Reacher: it finds people and companies to reach out to and personalizes results using the user's résumé.

This README holds the **development plan for improving search results**, so the context survives between work sessions. Update the status table as phases land.

## Status

| Phase | What | Status |
|---|---|---|
| 0 | Eval harness and baseline | **Done.** Harness in `eval/`; baseline = `eval/results/20261124-203206-rejudged.json` (see "Phase 0 baseline" below) |
| 1 | Search layer (SearXNG + Brave comparison), real page content | **Next** |
| 1b | LLM provider switch (`llm_invoke`, Groq gpt-oss-120b for deployment) | Not started. Do before Phase 2 |
| 2 | Grounded extraction and verification | Not started |
| 3 | Transparent ranking | Not started |
| 3.5 | Encrypt sensitive fields | Not started |
| 4 | User memory | Not started |
| 5 | Speed and robustness | Not started |

**Who builds what:** each step is tagged **[You]** (the developer writes it), **[Claude]** (Claude writes it) or **[Pair]** (designed together first).

## Handoff notes (for whoever picks this up next)

**Where things stand (2026-11-24):** Phase 0 is done. Next is Phase 1, starting with the SearXNG Docker setup **[Claude]** and `search_client.py` **[You]**.

**Working agreement:**
- The developer wants to **understand the design and write parts of the code**. Explain the design first, and give example code with explanations for **[You]** and **[Pair]** steps.
- The developer **runs eval and test commands themselves**. Give the exact command (PowerShell, run from `Backend/` with `.\venv\Scripts\python.exe`) instead of running long or LLM-heavy jobs. Each pipeline query makes several Claude CLI calls.
- **Search:**
  - No paid search API as the default. Brave's free tier is only a comparison.
  - Never solve CAPTCHAs or get around bot detection. Detect blocks and switch sources.

**Machine gotchas:**
- **C: is almost always full (0 MB).** The Claude CLI writes temp files there. Before running anything that calls the LLM, set this in the same terminal:
  `$env:TEMP = "D:\Reacher\Backend\eval\cache\tmp"; $env:TMP = $env:TEMP`
- **Docker Desktop stores images on C:** by default. Free about 300 MB there, or move its disk image to D: (Settings → Resources → Disk image location), before pulling SearXNG.
- **`pytest` isn't installed** in the venv: pip needs space on C:. Run the tests with plain Python:
  `.\venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'eval'); import test_metrics as a, test_scoring as b; n=[(m,x) for m in (a,b) for x in dir(m) if x.startswith('test_')]; [getattr(m,x)() for m,x in n]; print('passed', len(n), 'tests')"`
- **Windows PowerShell 5.1 strips double quotes** inside `python -c "…"`. Use single quotes inside, or a script file.
- **DuckDuckGo blocks this machine's IP** as of 2026-11-24 (connections time out). The old pipeline can't run until that lifts.

---

## Why: problems with the current pipeline

The current flow (`/processQuery` in `app.py` → `pipeline.find_leads` / `find_companies` → `planner.py` + `scraper.py`) has structural weaknesses:

- **Thin evidence.** The planner LLM writes 2–4 DuckDuckGo HTML URLs. The scraper keeps about 3,000 characters per results page, so the synthesizer mostly sees **search snippets**, not the pages behind them. Link following builds broken URLs from DuckDuckGo's relative `/l/?uddg=` redirects (`scraper.py`).
- **Silent failures.** A CAPTCHA or block page longer than 500 bytes counts as a success and goes into synthesis. Fetch errors are dropped without a trace.
- **No grounding.** Nothing checks that a lead's name appears on its `source_url`, and the prompt invites guessed emails. Leads are never deduplicated, and ranking is whatever order the LLM returns.
- **No personalization beyond the résumé.** Every query is stateless: no chat history, no record of preferences, no memory of leads already shown. The structured `resume_profile` only shapes the search plan; ranking reads the raw résumé text instead.
- **No way to measure.** There's no eval of result quality, so any change is guesswork.

## What makes Reacher different

Search itself isn't the novel part. Google, SerpAPI and SearXNG all return links, so the search source is swappable plumbing. Reacher's value is what happens after search:

- turning a goal into **verified people**, each with evidence from a real page;
- ranking by **warm paths relative to this user** (shared school, employers, tech stack, events), with the reason shown;
- **memory and the outreach loop**, so results improve with use;
- **sources beyond LinkedIn:** team pages, conference speakers, GitHub contributors, papers, blogs, alumni pages.

The niche is personalized, explainable warm-path discovery for individuals (students, job seekers), not bulk sales prospecting, where Apollo and Clay win on data volume.

## Decisions

- **Constraints (2026-11-24):** the app will be **deployed and released**, and **nothing paid** can be used, in development or production. Every component must work on free tiers, and its free-tier limits must be planned for.
- **LLM in production:** the Claude Code CLI runs on a personal subscription, so it's for **local development and the eval judge only**. The deployed app uses a free-tier, OpenAI-compatible API (first choice: **Groq, `openai/gpt-oss-120b`**), chosen with `LLM_PROVIDER`. See Phase 1b.
- **Search:** self-hosted **SearXNG**, a metasearch engine that queries several engines and returns JSON. It sits behind a swappable `search_client.py`, and the **Brave Search API free tier** is compared with it in the eval. Search providers are never scraped past a block: the fetcher detects blocks and skips that source.
- **Memory:** **visible and editable** by the user ("What Reacher knows about you" panel).
- **Privacy:** sensitive free-text fields are **encrypted app-side** with a per-user key, so deleting a user's data really deletes it.

## Target pipeline

```
query + chat history + user context (profile + memory)
  → plan        (1 LLM call: mode + 3–6 search queries; replaces the separate classifier call)
  → search      (SearXNG / Brave JSON, several engines)
  → fetch pages (top results, trafilatura text, block detection, Mongo page cache)
  → extract     (LLM per page batch: leads + evidence quote)
  → verify      (code: name in page text, source URL was fetched, email only if literally on the page)
  → dedupe and merge (code: normalized name + company, merged sources)
  → rank        (code: feature score from profile + memory + evidence; LLM writes "why" for the top results only)
  → respond, then update memory in the background
```

---

## Phase 0: Eval harness and baseline (do first)

Build this before changing anything, so every later phase can show whether it helped.

- **[Pair]** `eval/queries.json`: about 25 queries in three groups (people, companies, alumni-style such as "SWE engineers from UMD at Meta"). Add one or two fixed test profiles in `eval/profiles/`.
- **[Claude]** `eval/run_eval.py` calls `pipeline.find_leads` / `find_companies` directly and records for each query:
  - **Grounding rate:** the share of leads whose name appears in the fetched text of their `source_url`.
  - **Relevance:** an LLM judge scores each lead 0–2 against the query and test profile using a fixed rubric.
  - Number of leads, duplicate rate, latency, and failed or blocked fetches.

  Results go to `eval/results/<timestamp>.json`, with a short table printed for comparing two runs.
- **[Pair]** Optional gold set: for 3–5 queries, list real people who should appear. That measures recall.
- **[You]** Spot-check about 20 judge scores by hand, to know whether the LLM judge can be trusted.
- Run it once on today's pipeline. **That's the baseline.**
- **How to use it:** a quick subset of about 5 queries while developing, and the full set at the end of each phase. Run versions back to back, because the web and LLM output both drift, and trust only large or consistent differences.

**Running it** (from `Backend/`, with the backend venv):

| Command | What it does |
|---|---|
| `python eval/run_eval.py --quick --label dev` | The 5-query dev subset |
| `python eval/run_eval.py --label baseline` | The full set, saved as `eval/results/<time>-baseline.json` |
| `python eval/run_eval.py --ids p01,c01 --no-judge` | Specific queries, without the LLM judge |
| `python eval/run_eval.py --repeat 2` | Each query twice, to see run-to-run noise |
| `python eval/run_eval.py --quick --profiles both` | Each profiled query with **and** without its profile, plus a personalization report |
| `python eval/run_eval.py --profiles none` | Every query without a profile |
| `python eval/run_eval.py --rejudge eval/results/<file>.json` | Re-score a saved run with the current judge and metrics. No pipeline and no searching, so it's safe while a search engine is blocking |
| `python eval/run_eval.py --rejudge eval/results/<file>-rejudged.json --no-judge` | Recompute metrics only, keeping the saved judge scores. No LLM calls at all |
| `python eval/inspect_run.py eval/results/<file>.json` | What happened in each query: pages, blocks, the model's own summary, every lead |
| `python eval/inspect_run.py eval/results/<file>.json --id p01` | One query in full: fetched URLs, sources, judge reasons |

Runs pause 5 seconds between queries (`--delay`) and stop after 3 queries in a row where every search page was blocked (`--stop-after-blocked`). Today's pipeline searches DuckDuckGo's HTML page, which rate-limits after about 100+ searches in a few minutes and then serves a CAPTCHA with HTTP 202. **Don't run the full set right after another run.**

**How to read a run:**
1. **Check blocking first.** Look at "Queries where every page was blocked" and the `NOTE` line if the run stopped early. A blocked run measures the search engine, not your change, so re-run it later rather than comparing it.
2. **Then evidence:** leads per query, queries with 0 leads, grounded rate and unreadable sources.
3. **Then usefulness:** prefer **useful leads per query** over any mean. A mean falls whenever an answer adds a few weak leads after strong ones.
   - **The judge gives two scores per lead.**
     - **Request match (0–3):**
       - **3** = exactly the requested role at the right company.
       - **2** = a closely adjacent individual-contributor role in the same function, e.g. "AI Developer Technology Engineer" for ML engineers.
       - **1** = right company, but a different function or seniority (managers and directors, unless the request asks for leaders), a former employee, or vague.
       - **0** = wrong.
     - **User fit (0–2):** a warm path for this test user (shared school, employer, stack or events).
     - Fictional or joke entries are flagged **fabricated** and get 0 on both.
   - **Useful** = not fabricated, and either request match ≥ 2, or request match 1 with user fit 2.
   - **Verified useful** = useful *and* the name was found on its source page. **This is the headline number.**
   - **Order quality (nDCG):** 1.0 when the best leads come first. Each lead is worth 2^(request match + user fit) − 1, so a strong lead counts far more than a weak one. Exact matches should sit above adjacent roles, and adjacent roles above managers. nDCG stays high when most leads are strong, so a drop of 0.02–0.03 is meaningful. Phase 3 ranking should raise this.
   - **Personalization** shows up as user fit and useful leads going up with the profile.
   - **Source types** show where leads come from: company/team pages, blogs, conference pages, code, papers, news, directories, or **LinkedIn / data brokers / social**, which can't be checked. "Source is checkable" is the share that can be.
4. **Then open `inspect_run.py`** on any query that looks odd. The model's summary often says exactly what went wrong.
| `python eval/run_eval.py --compare eval/results/A.json eval/results/B.json` | A side-by-side table of two runs |

Files in `eval/`:
- `queries.json`: the query set. `quick` marks the dev subset, `gold` lists names that should appear, and `profile` names a test profile.
- `profiles/`: synthetic test users.
- `metrics.py`: name matching, email-on-page and block detection. Tested by `test_metrics.py`.
- `run_eval.py`: the runner.
- `results/`: saved runs.
- `cache/`: the grounding page cache, kept for 24 hours and git-ignored.

Queries go straight to `find_leads` / `find_companies` using the `mode` in `queries.json`, so the classifier isn't part of the eval.

**Measuring personalization (`--profiles both`):**
- Without the profile, the pipeline gets no résumé or profile at all.
- The judge **always** scores against the query's test profile, even for the no-profile run, so both runs answer the same question: how useful is this to this user?
- The report shows the average relevance gain and how many queries got better, worse or stayed about the same, then lists each query.
- It roughly doubles run time, because every profiled query runs twice.

### Phase 0 baseline (recorded 2026-11-24)

The old pipeline was run with `--quick --profiles both`, then re-scored with the final judge (`--rejudge`). The result file is `eval/results/20261124-203206-rejudged.json`. Only 5 of the 10 runs had real search results: DuckDuckGo started blocking partway through, from p09 without a profile onwards.

| Metric | Value |
|---|---|
| Verified useful leads per query | **0.90** (people queries 1.50; company and alumni queries 0) |
| Useful leads per query | 1.50 |
| Verified useful, with vs without profile | 1.60 vs 0.20 (only 2 query pairs, so a hint, not proof) |
| Source actually fetched by the pipeline | **0%**: every lead comes from a search snippet |
| Source is checkable (not LinkedIn, broker or social) | 77% |
| Fabricated leads | 1 ("Erlich Bachman", from a joke RocketReach profile) |
| Order quality (nDCG) | about 0.97 (p01 with profile: 0.971) |
| Latency | about 22 seconds per query |

**Findings that shape Phase 1:**
- **The pipeline never reads a real page.** It fetches DuckDuckGo results pages only. Its link following builds broken URLs: `//duckduckgo.com/l/?uddg=…` is turned into `https://duckduckgo.com//duckduckgo.com/l/…`, and the real URL inside `uddg=` is never decoded.
- **DuckDuckGo rate-limits the HTML endpoint** after about 100+ searches in about 10 minutes. It first serves a CAPTCHA with HTTP 202 ("bots use DuckDuckGo too"), which the old scraper treats as success. After that it **drops connections from the IP entirely**: as of 2026-11-24, duckduckgo.com connections time out from the dev machine.
- **Re-run on 2026-11-25** (`eval/results/20261125-042229-baseline.json`): DuckDuckGo had unblocked overnight, but **blocked again after only 2 queries** (about 16 requests). The early-stop worked, and 5 of 10 runs completed. Once an IP has been flagged, its tolerance is much lower. Also:
  - **The broken follow links hit duckduckgo.com too,** so every query sends about 8 requests to DuckDuckGo, not 4.
  - **Run-to-run variance is large.** p01 with the profile went from 7 useful leads to 2, because this time the model added managers, a recruiter and a product manager. **Don't trust single-pair personalization numbers;** use `--repeat` and more queries.
  - **Open product question:** for a job-seeking student, a recruiter can be a valuable contact even when the request says "ML engineers". The judge currently scores that as a mismatch.
- **LinkedIn and data brokers** (RocketReach, ZoomInfo) block every automated fetch, so leads citing them can't be verified. Some broker profiles are jokes.
- The old scraper sends a **fake Chrome User-Agent**. Wikipedia returns 403 to generic programmatic User-Agents and asks bots to identify themselves.

## Phase 1: Search layer and real page content

**Additions from the Phase 0 findings:**
- **Turn off the `duckduckgo` engine in SearXNG** while the dev machine's IP is blocked. Use Brave, Mojeek, Wikipedia, Bing and other engines. Keep the engine list in `settings.yml`, so it's easy to change back.
- **Fetch politely:**
  - Use an honest, descriptive User-Agent such as `ReacherBot/0.1 (+<project or contact URL>)` instead of pretending to be Chrome.
  - Check `robots.txt` before fetching a page.
  - Limit concurrency per domain and pause between searches; no bursts of parallel searches.
  - Skip any site that refuses. Never work around a block.
- **Treat LinkedIn, data broker and social URLs as non-evidence.** The fetcher doesn't try them, and Phase 2 verification drops leads that rely only on them.
- **Measure with the eval:** "Source actually fetched" should go from 0% toward 100%, and verified useful leads per query should rise above 0.90.

- **[Claude]** `docker/searxng/` (`docker-compose.yml` + `settings.yml`): JSON output enabled, a few engines (e.g. duckduckgo, brave, mojeek, wikipedia), limiter off for local use, served at `http://localhost:8888`.
- **[You]** `search_client.py`: `async def search(query, max_results=8) -> list[SearchHit]` with fields `{url, title, snippet, engine}`. It needs a timeout, retry once, and dedup by URL. A `SEARCH_PROVIDER` setting picks the provider.
- **[Claude]** Brave Search API provider. **Compare SearXNG, Brave and today's DuckDuckGo baseline with the eval**, then pick the default from the data.
- **[Pair]** The planner (`planner.py`) outputs **search queries** (3–6), not URLs, and does the PERSON / COMPANY / GENERAL classification in the same call. That saves one LLM call per query.
- **[Pair]** **Non-LinkedIn source strategies** in the planner:
  - company team and leadership pages
  - conference speaker lists and talk pages
  - GitHub contributors to projects in the user's stack
  - papers and author pages
  - engineering blogs
  - alumni pages and news
- **[Claude]** `fetcher.py`:
  - Fetches the top N unique result URLs concurrently, with a per-domain limit.
  - Extracts main text with **trafilatura** (already installed, currently unused).
  - Detects blocks: HTTP 403 or 429, CAPTCHA or "unusual traffic" markers, or almost no text. A blocked page is marked and skipped, never sent to the LLM.
  - Uses BrowserUse only for pages that need JavaScript, with `max_steps` and a timeout.
- **[Claude]** A `page_cache` Mongo collection (`url`, `text`, `fetched_at`) with a TTL index of about 24 hours.
- Re-run the eval. Expect grounding and lead count to go up.

## Phase 1b: LLM provider switch

**Why:** every LLM call goes through `claude_code_invoke` in `llm_provider.py`, which runs the Claude Code CLI on a personal subscription. That can't be the production setup. Do this **before Phase 2**: Phase 2 tunes the extraction prompts, and they should be tuned on the model that will actually ship.

- **[Pair]** Replace `claude_code_invoke` with `llm_invoke(system, user, schema=None)`. `LLM_PROVIDER` picks the backend:
  - `claude_cli`: today's behaviour, for local development.
  - `groq`: an OpenAI-compatible client with the model `openai/gpt-oss-120b` and structured (JSON) output. The same client also works for Ollama Cloud and OpenRouter.

  Keep one function and one environment variable; no provider classes.
- **[Pair]** Handle rate limits: on HTTP 429, wait and retry once, then return a clear "busy, try again shortly" error to the user. Log token usage per call, so free-tier limits can be planned.
- **[Claude]** Point `get_agent_llm` at the same setting.
- **The eval judge stays on Claude locally** (`claude_cli`). It never ships, and a fixed judge keeps scores comparable across pipeline models.
- **Measure:** run the quick set with `LLM_PROVIDER=claude_cli` and with `groq`, then `--compare`. Watch verified useful leads, fabricated leads and latency. If gpt-oss is clearly worse at extraction, look at the prompt and the input size before switching models.
- **Later, only if rate limits hit:** a small fast model for classification and the larger model for synthesis.

## Phase 2: Grounded extraction and verification

- **[Pair]** Extraction prompt and schema (`planner.py` synthesizer, `Lead` in `llm_provider.py`): each lead gets an `evidence` quote, and `source_url` must be one of the provided URLs.
- **[You]** `verify.py`, plain code with no LLM:
  - Normalize names (case, accents, middle initials) and check that the name appears in the cached page text.
  - Keep `email` only if it appears literally on that page. Otherwise set it to `None`.
  - Drop or flag leads that fail these checks.
- **[You]** Dedupe and merge leads by normalized name plus company, keeping all their sources.
- Re-run the eval. Grounding should be close to 100%.

## Phase 3: Transparent ranking

- **[Pair]** `ranking.py`, with features computed in code from the lead, its evidence, `resume_profile` and memory:
  - Shared school, shared past company, overlapping skills and keywords, match with target roles, location.
  - Strength of evidence (number of sources, team or author page vs snippet).
  - Memory preferences, e.g. preferred seniority or excluded companies.
  - A penalty for leads already shown to this user.

  Simple weighted scoring first; tune the weights against the eval.
- **[Claude]** One small LLM call writes the "why they fit" text for the top results only, using the structured profile instead of the raw résumé.
- **[Claude]** Match tags on each card in `Home.vue`, e.g. "UMD alum", "PyTorch".

## Phase 3.5: Encrypt sensitive fields (before memory)

Atlas already provides TLS and disk encryption at rest. Neither protects against someone holding database credentials or a leaked dump or backup.

- **[Pair]** `crypto_store.py`, app-side envelope encryption with AES-GCM using Python's `cryptography` package:
  - one data key per user, wrapped by a master key kept outside the database (an environment variable now, a KMS later);
  - `encrypt_field(user_id, text)` and `decrypt_field(user_id, blob)`.
- **[You]** Encrypt the free-text fields: `users.resume_text`, the memory fact `text`, and chat message `content`. Leave index fields readable: `user_id`, timestamps, `kind`, `confidence`, `session_id`.
- **[Claude]** A one-time migration that encrypts existing plaintext documents.
- **"Clear my data" deletes the user's data key** (crypto-shredding), so leftover copies, including those in backups, become unreadable.
- **The limit:** the LLM still receives plain text while it processes a request. Say this clearly in the privacy note in the UI.
- Upgrade path: MongoDB Client-Side Field Level Encryption or Queryable Encryption, if encrypted fields ever need to be searchable.

## Phase 4: User memory

| Layer | What it holds | How it's written | How it's used |
|---|---|---|---|
| Profile | Résumé facts (`resume_profile`) | Replaced on every upload | Ranking features, planner context |
| Facts | Preferences, goals, exclusions | Background LLM call after each query and feedback, merged with existing facts with a confidence score; user can edit | Exclusions are **hard filters**, preferences are **ranking weights**, and a short summary goes to the planner |
| History | Past queries, leads shown, 👍 / not relevant, contacted | Recorded automatically | No repeated people, follow-ups, learning what the user likes |

Facts stay small (tens of items), so they fit in a prompt with no embeddings. Add vector search only if they grow.

- **Data:** a `user_memory` collection, one document per user:
  ```
  { user_id, facts: [ { id, kind: "preference"|"goal"|"exclusion"|"context",
                        text, source: "resume"|"chat"|"feedback"|"user",
                        confidence, pinned, created_at, updated_at } ],
    seen_leads: [ { key, first_shown_at } ], updated_at }
  ```
  Résumé-derived facts are replaced whenever a new résumé is uploaded.
- **[You] Write path,** `memory.py`. After a response is sent, a FastAPI `BackgroundTasks` job runs one cheap LLM call over the query, the mode and any feedback. It proposes new or updated facts, which are merged with the existing ones by normalized text, with confidence adjusted. Seen leads are recorded too.
- **[You] Read path:** `build_user_context(user_id)` returns a compact block of about 800 tokens: the profile, top facts (pinned first) and the last 5 queries. The planner, ranker and general chat path all use it.
- **[Claude]** Pass the last few chat turns to the planner, so follow-ups like "narrow it down to Seattle" work.
- **[Claude]** Feedback and UI:
  - 👍 / "Not relevant" buttons on cards.
  - A "What Reacher knows about you" panel (edit, pin, delete).
  - Endpoints `GET /memory`, `PATCH /memory/{fact_id}`, `DELETE /memory/{fact_id}`, `DELETE /memory`.
- **Privacy:** memory only ever comes from the user's own chats, uploads and feedback. "Clear all" really deletes it. No sensitive categories are stored.
- Add multi-turn and preference cases to the eval, e.g. "exclude FAANG" set once and then respected in later queries.

## Phase 5: Speed and robustness

- **[Claude]** Use a faster model for planning, extraction and memory calls (model choice per call in `claude_code_invoke`).
- **[Claude]** try/except plus a friendly fallback in `/processQuery` for CLI timeouts and bad JSON.
- **[Claude]** Raise the frontend's 30s `REQUEST_TIMEOUT_MS` in `Home.vue`, which cuts off searches today.
- **[You]** Save `/enrich` results back to the chat's leads.

---

## Files

- **New:** `search_client.py`, `fetcher.py`, `verify.py`, `ranking.py`, `crypto_store.py`, `memory.py`, `eval/`, and `docker/searxng/` at the repo root.
- **Changed:**
  - `pipeline.py` (stage order)
  - `planner.py` (prompts, schemas)
  - `llm_provider.py` (`Lead.evidence`, model per call)
  - `app.py` (history and context passed to the pipeline, memory endpoints, indexes)
  - `scraper.py` (reused or retired)
  - `Frontend/vue-project/src/components/Home.vue`
- **Reused:** `resume_profile.py` (`ResumeProfile`, `extract_resume_profile`, `format_resume_profile`), `ensure_resume_profile` / `_persist_resume_profile` in `app.py`, and `claude_code_invoke` in `llm_provider.py`.

## Verification

- `docker compose up` in `docker/searxng`, then `curl "http://localhost:8888/search?q=test&format=json"` returns results.
- `python eval/run_eval.py` after each phase, compared with the baseline. Targets:
  - grounding of at least 95% after Phase 2;
  - higher mean relevance after Phase 3;
  - preference cases passing after Phase 4.
- `pytest` unit tests for the pure-code parts: name matching, email-on-page check, dedup and merge, ranking features, memory fact merging, and an encrypt → decrypt round-trip (plus failure after key deletion).
- After Phase 3.5, the encrypted fields in Mongo hold ciphertext, and the app still shows résumé and chat text normally.
- In the app (backend on 8000, frontend on 5173), run a people query, a company query and a follow-up:
  - cards show evidence-backed leads and match tags;
  - the memory panel shows editable facts;
  - deleting a fact changes the next result.

---

## Fine-tuning (earlier work)

Google Colab notebook for fine-tuning the browser agent: https://colab.research.google.com/drive/1uZFYmmHKuHEKdKwPZYGqRPmxHjWGTQyI?usp=sharing (see also `finetune_ollama_browser_agent.md`).
