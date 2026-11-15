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
- **Backend/few_shot.py** — Few-shot examples for the browser agent
- **Frontend/vue-project/src/components/Home.vue** — Main UI: resume upload, chat, lead cards
- **Frontend/vue-project/src/components/ChatHistory.vue** — Sidebar chat history

## Main Flow
```
User (Vue frontend)
  |-- POST /processQuery (message + session_id + resume) -->
  FastAPI app.py
    |-- classify query (Claude CLI) --> PERSON | COMPANY | GENERAL
    |
    |-- PERSON/COMPANY --> pipeline.py
    |     |-- planner.generate_plan() (Claude CLI) --> [search URLs]
    |     |-- scraper.scrape_multiple() --> [ScrapedPage]
    |     |-- browser agent (ChatClaudeCode) --> fills JS-rendered pages
    |     |-- planner.synthesize_results() (Claude CLI) --> structured JSON
    |
    |-- GENERAL --> Claude CLI direct response
    |
    |-- store in MongoDB (chat history)
    |-- SSE stream response back to frontend
```

## Data and Trust Boundaries
- **MongoDB** (Motor async driver) — stores users, chat sessions, messages
- **Google OAuth** — user authentication via OAuth2 flow
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
- How resume text is extracted and truncated for LLM context
