# Project Map

## Purpose
Reacher is a lead-finding tool: users submit a query (and optionally a resume), and the system scrapes the web for matching people or companies, then returns personalized results.

## Requirements
- Classify user queries as PERSON, COMPANY, or GENERAL
- Generate search plans (DuckDuckGo URLs) via LLM
- Scrape those URLs, following links and using a browser agent for JS-heavy pages
- Synthesize scraped data into structured leads ranked by relevance to the user's resume
- Google OAuth login, chat history persistence, resume upload (PDF/DOCX)

## Components
- **Backend/app.py** — FastAPI server, routes, query classification, chat sessions, Google OAuth, resume parsing
- **Backend/planner.py** — LLM-driven plan generation (search URLs) and result synthesis (structured leads)
- **Backend/pipeline.py** — Orchestrates planner → scraper → browser agent → synthesizer
- **Backend/scraper.py** — HTTP scraping with BeautifulSoup, link following, JS-detection
- **Backend/llm_provider.py** — Claude Code CLI wrapper, ChatClaudeCode LangChain adapter, Pydantic models
- **Backend/resume_profile.py** — One-shot LLM extraction of a structured ResumeProfile (cached on the user in MongoDB)
- **Backend/few_shot.py** — Few-shot examples for the browser agent
- **Frontend/vue-project/src/components/Home.vue** — Main UI: resume upload, chat, lead cards
- **Frontend/vue-project/src/components/ChatHistory.vue** — Sidebar chat history

## Main Flow
```
User (Vue frontend)
  |-- POST /processQuery (session_id + user_id + message) -->
  FastAPI app.py process_query
    |-- load user from MongoDB; ensure_resume_profile (cached, or extract once via Claude CLI)
    |-- classify query (Claude CLI) --> parse_mode --> PERSON | COMPANY | GENERAL
    |
    |-- PERSON --> pipeline.find_leads
    |     |-- planner.generate_plan() (Claude CLI, PlanResponse) --> [search URLs]
    |     |-- scraper.scrape_with_follow() --> [ScrapedPage] (+ up to 4 team/people links)
    |     |-- _render_js_pages: browser_use Agent (ChatClaudeCode) for need_js pages
    |     |-- planner.synthesize_results() (Claude CLI, SynthesisResponse) --> JSON string
    |-- COMPANY --> pipeline.find_companies (same, but scrape_multiple, company prompts)
    |-- GENERAL --> Claude CLI direct response (REACHER_SYSTEM_PROMPT + resume)
    |
    |-- normalize_result --> (summary, leads); push both messages to MongoDB chats
    |-- plain JSON response {response, leads, session_id}

GET /enrich/{session_id} -- SSE: browser_use agent looks up emails for leads without one
All Claude calls: llm_provider._claude_code --> `claude -p --output-format json` subprocess
```

## Data and Trust Boundaries
- **MongoDB** (Motor async driver) — stores users, chat sessions, messages
- **Google OAuth** — verifies the user once at /callback; the backend then sets a 7-day HS256 JWT in an HttpOnly, SameSite=Lax cookie (`reacher_token`, secret `JWT_SECRET` in Backend/.env). `get_current_user` guards every user route; the frontend learns identity from GET /me.
- **External scraping** — DuckDuckGo search + arbitrary URLs via httpx
- **browser-use Agent** — headless Playwright browser for JS-rendered pages
- **Claude Code CLI** — LLM calls via subprocess (billing to user's plan, no API key)
- **Environment** — .env file with MongoDB URI, Google OAuth client secret, etc.

## Build and Deployment
- Backend: `cd Backend && python app.py` (FastAPI on uvicorn)
- Frontend: `cd Frontend/vue-project && npm run dev` (Vite dev server)
- Python venv at `D:\Reacher\venv`

## Unknowns
- Deployment target not yet determined (runs locally)
- Error handling strategy for failed scrapes / LLM timeouts
- Rate limiting on scraping
- run_agent in app.py is defined but not called by any route
