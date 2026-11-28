from fastapi import FastAPI, UploadFile, File, Request, Depends, HTTPException, BackgroundTasks, Path
from contextlib import asynccontextmanager
import jwt
import secrets
from fastapi.middleware.cors import CORSMiddleware
from browser_use import Browser, SystemPrompt
from browser_use.agent.service import Agent
from browser_use.agent.views import AgentOutput
from browser_use.browser.browser import BrowserConfig
from llm_provider import get_agent_llm, claude_code_invoke, LLMUnavailableError
from langchain_core.messages import BaseMessage
from collections import deque
from threading import Lock
import random
from few_shot import FEW_SHOT_EXAMPLES
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv
import os
from starlette.responses import JSONResponse, RedirectResponse
import requests
import nest_asyncio
nest_asyncio.apply()
import asyncio
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from pydantic import BaseModel, ConfigDict, Field, field_validator
from motor.motor_asyncio import AsyncIOMotorClient
# from langchain_groq import ChatGroq
import pipeline
from docx import Document
from io import BytesIO
import json
from sse_starlette.sse import EventSourceResponse
import re
from planner import parse_json, route_and_plan
from pypdf import PdfReader
from resume_profile import extract_resume_profile
from memory import (
    update_memory, build_user_context, apply_exclusions,
    list_memory, edit_fact, delete_fact, clear_memory, add_fact, MemoryFull,
    should_update_memory,
    FactKind, MAX_TEXT, MAX_FACTS,
)


class CustomSystemPrompt(SystemPrompt):
    def __init__(self, *args, task_examples="", **kwargs):
        super().__init__(*args, **kwargs)
        self.task_examples = task_examples


    def important_rules(self):
        existing = super().important_rules()
        return existing + "\n" + SYSTEM_PROMPT + "\n" + self.task_examples

class ChatRequest(BaseModel):
    session_id: str
    message: str


def _env_str(key: str) -> str:
    v = os.getenv(key)
    return (v or "").strip()


def _mongo_connection_uri() -> str | None:
    user = _env_str("MONGODB_USERNAME")
    password = _env_str("MONGODB_PASSWORD")
    host = _env_str("MONGODB_HOST")
    if user and password and host:
        return (
            f"mongodb+srv://{quote_plus(user)}:{quote_plus(password)}@{host}/"
            "?retryWrites=true&w=majority"
        )
    uri = _env_str("MONGODB_CONNECTION_STRING")
    return uri or None


async def upsert_user_from_oauth(user_info: dict) -> bool:
    if users_collection is None:
        raise RuntimeError(
            "MongoDB is not configured. Set MONGODB_USERNAME, MONGODB_PASSWORD, and "
            "MONGODB_HOST, or set MONGODB_CONNECTION_STRING."
        )

    email = (user_info.get("email") or "").strip()
    if not email:
        raise ValueError("Google userinfo did not include an email")

    google_sub = user_info.get("sub")
    name = user_info.get("name") or ""
    picture = user_info.get("picture") or ""

    now = datetime.now(timezone.utc)
    try:
        result = await users_collection.update_one(
            {"email": email},
            {
                "$setOnInsert": {
                    "email": email,
                    "google_sub": google_sub,
                    "name": name,
                    "picture": picture,
                    "created_at": now,
                }
            },
            upsert=True,
        )
    except OperationFailure as exc:
        err = str(exc).lower()
        if getattr(exc, "code", None) == 8000 or "bad auth" in err or "authentication failed" in err:
            raise RuntimeError(
                "MongoDB Atlas rejected the database username or password. In Atlas, open "
                "Database Access → your user → Edit Password, then update MONGODB_PASSWORD "
                "(and MONGODB_CONNECTION_STRING if you use it). If the password contains "
                "@ : / ? # % or spaces, use MONGODB_USERNAME, MONGODB_PASSWORD, and "
                "MONGODB_HOST in .env so the app can encode them correctly."
            ) from exc
        raise

    return result.upserted_id is not None


def classify_task(query):
    query = query.lower()
    keywords = {
        "extract_info": ["email", "phone", "address", "hours", "price", "cost" , "find the", "get the", "fetch", "what is the", "how much"],
        "search": ["search for", "look up", "find on", "jobs", "restaurants",
                   "trending", "top rated", "best", "most popular"],
        "form_fill": ["fill", "submit", "sign up", "register", "contact form",
                      "apply", "enter", "type in"],
        "navigation": ["latest", "newest", "blog", "news", "deadline",
                        "announcement", "check", "browse", "go to"],
        "comparison": ["compare", "vs", "versus", "difference between",
                        "which is better", "which has more"],
        "error_recovery": [],
    }

    scores = {}
    for category, words in keywords.items():
        scores[category] = sum(1 for w in words if w in query)

    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    else:
        return "navigation"
    

def select_examples(query: str, k: int = 3, include_recovery: bool = False) -> list:
    category = classify_task(query)
    pool = list(FEW_SHOT_EXAMPLES.get(category, []))
 
    if len(pool) < k:
        fallback = list(FEW_SHOT_EXAMPLES.get("navigation", []))
        random.shuffle(fallback)
        pool.extend(fallback[:k - len(pool)])
 
    selected = random.sample(pool, min(k, len(pool)))
 
    if include_recovery and FEW_SHOT_EXAMPLES.get("error_recovery"):
        recovery = random.choice(FEW_SHOT_EXAMPLES["error_recovery"])
        if len(selected) >= k:
            selected[-1] = recovery 
        else:
            selected.append(recovery)
 
    return selected


def format_few_shot_examples(examples: list) -> str:
    lines = []
    for i, ex in enumerate(examples, 1):
        lines.append(f"Example {i}: {ex['task']}")
        for step in ex["steps"]:
            action = step["action"]
            if action == "go_to_url":
                lines.append(f"  → go_to_url: {step['url']}")
            elif action == "click_element":
                lines.append(f"  → click_element: {step['target']}")
            elif action == "input_text":
                lines.append(f"  → input_text: [{step['target']}] \"{step['text']}\"")
            elif action == "scroll_down":
                lines.append(f"  → scroll_down: {step['amount']} times")
            elif action == "select_dropdown":
                lines.append(f"  → select_dropdown: [{step['target']}] = \"{step['value']}\"")
            elif action == "extract_page_content":
                lines.append(f"  → extract_page_content")
            elif action == "go_back":
                lines.append(f"  → go_back")
            elif action == "done":
                lines.append(f"  → done: {step['text']}")
        lines.append("")
    return "\n".join(lines)


def memory_callback(data):
    with memory_lock:
        live_memory.append(data)


async def run_agent(task):
    with memory_lock:
        live_memory.clear()

    browser = Browser(config=BrowserConfig(headless=True))

    selected_few_shots = select_examples(task, 3, True)
    few_shot_string = format_few_shot_examples(selected_few_shots)

    live_traces = []
    agent = Agent(
        llm=llm, 
        task=task,
        browser=browser,
        system_prompt_class=lambda *a, **kw: CustomSystemPrompt(*a, task_examples=few_shot_string, **kw),
        use_vision=False,
        max_input_tokens=16000,
        max_failures=10,
        max_actions_per_step=3,
    )

    def on_step(state, model_output, step_info=None):
        print(f">>> MEMORY UPDATED")  
        if model_output:
            with memory_lock:
                live_memory.append({
                    "step": len(live_memory) + 1,
                    "memory": str(model_output.current_state) if hasattr(model_output, 'current_state') else str(model_output),
                    "action": str(model_output.action) if hasattr(model_output, 'action') else None,
                })

    agent.register_new_step_callback = on_step

    result = await agent.run()

    return task, result, agent, live_traces


def parse_mode(text):
    words = re.sub(r"[^A-Z]", " ", text.upper()).split()
    for mode in ("PERSON", "COMPANY", "GENERAL"):
        if mode in words:
            return mode
    
    return "GENERAL"


def normalize_result(result):
    """Turn a pipeline result into (summary, leads)."""
    if isinstance(result, str):
        try:
            result = parse_json(result)
        except (json.JSONDecodeError, TypeError):
            return result, []
    if isinstance(result, dict):
        summary = result.get("summary") or result.get("suggestions") or ""
        return summary, result.get("leads") or []
    
    return result, []


_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")


def _clean_domain(value) -> str | None:
    """'https://www.NVIDIA.com/careers' -> 'nvidia.com'. Anything that isn't a plain domain -> None.

    The browser puts this into a Google favicon URL, so only a strict domain may pass.
    """
    if not isinstance(value, str):
        return None
    d = value.strip().lower()
    d = re.sub(r"^[a-z]+://", "", d).split("/")[0].split("?")[0].split(":")[0]
    if d.startswith("www."):
        d = d[4:]
    return d if _DOMAIN_RE.match(d) else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup. create_index is a no-op if the index already exists.
    for name, coll in (("user_keys", user_keys_collection), ("user_memory", user_memory_collection)):
        if coll is None:
            continue
        try:
            await coll.create_index("user_id", unique=True)
        except Exception as e:
            print(f"WARNING: could not create {name} index: {e}")
    yield


app = FastAPI(lifespan=lifespan)

origins = ["http://localhost:5173"]
app.add_middleware(
    CORSMiddleware, 
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LLMUnavailableError)
async def llm_unavailable_handler(request: Request, exc: LLMUnavailableError):
    # Log only the error kind; the detail can echo prompt text.
    print(f"WARNING: LLM unavailable on {request.url.path} (limit_reached={exc.limit_reached})")
    message = (
        "Reacher's AI service has hit its usage limit. Please try again later."
        if exc.limit_reached
        else "Reacher's AI service is unavailable right now. Please try again in a few minutes."
    )
    return JSONResponse({"error": message}, status_code=503)

SYSTEM_PROMPT = """You are a people-finding assistant for cold outreach. Follow these rules:

1. Go to Google and search for the person, role, or company.
2. Look for LinkedIn profiles, company team pages, or about pages.
3. Extract names, titles, and email patterns.
4. Present results clearly and say done. Do NOT over-browse.
"""

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is not set. Add a long random value to Backend/.env.")
JWT_ALGORITHM = "HS256"
TOKEN_COOKIE = "reacher_token"
TOKEN_TTL = timedelta(days=7)
FRONTEND_URL = "http://localhost:5173"

llm = get_agent_llm()
live_memory = deque(maxlen=100)
memory_lock = Lock()


CLIENT_SECRET_FILE = os.getenv("CLIENT_SECRET_FILE")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_STATE_PATH = "/callback"
OAUTH_STATE_TTL_SECONDS = 600

_mongo_uri = _mongo_connection_uri()
mongo_client = (
    AsyncIOMotorClient(_mongo_uri, serverSelectionTimeoutMS=10_000) if _mongo_uri else None
)

if mongo_client is not None:
    mongo_db = mongo_client["reacher"]
    users_collection = mongo_db["users"]
    chats_collection = mongo_db["chats"]
    user_keys_collection = mongo_db["user_keys"]
    user_memory_collection = mongo_db["user_memory"]
else:
    mongo_db = None
    users_collection = None
    chats_collection = None
    user_keys_collection = None
    user_memory_collection = None


user_current_chat = {}

REACHER_SYSTEM_PROMPT = """You are Reacher, an assistant that helps users find the right people and companies to reach out to for jobs, networking and cold outreach.

What you can do:
- Find specific people (e.g. "ML engineers at Nvidia", "Who leads backend eng at Stripe?")
- Discover companies (e.g. "Cybersecurity startups hiring in DC")
- Use the user's uploaded resume to rank results and highlight shared backgrounds
- Give advice on cold emails, networking and job searching

Rules:
- You are Reacher. Never say you are ChatGPT or any other assistant, and never mention the underlying model.
- Keep answers short (under 150 words) and practical. Avoid large tables.
- If a question is unrelated to careers, networking or outreach, answer briefly, then explain how Reacher can help.
- When helpful, end with 1-2 example searches the user could try.
"""

MAX_RESUME_BYTES = 5 * 1024 * 1024


def _normalize_resume_text(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines()]
    return "\n".join(line for line in lines if line)


def extract_resume_text(filename: str, contents: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        reader = PdfReader(BytesIO(contents))
        parts = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                parts.append(page_text)
        text = "\n".join(parts)
    elif name.endswith(".docx"):
        doc = Document(BytesIO(contents))
        text = "\n".join(p.text for p in doc.paragraphs if p.text and p.text.strip())
    else:
        raise ValueError("Unsupported file type")

    normalized = _normalize_resume_text(text)
    if not normalized:
        raise ValueError("Could not extract any text from the resume")
    return normalized


@app.get("/")
def root():
    return {"Hello World"}


@app.get("/callback")
async def callback(request: Request, code: str, state: str):
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if not expected_state or not secrets.compare_digest(expected_state.encode(), state.encode()):
        return _clear_oauth_state(JSONResponse({"error": "Invalid state"}, status_code=400))

    flow = Flow.from_client_secrets_file(CLIENT_SECRET_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = "http://localhost:8000/callback"
    flow.fetch_token(code=code)

    credentials = flow.credentials

    user_info = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"}
    ).json()

    name = user_info.get("name", "")
    email = user_info.get("email", "")

    try:
        await upsert_user_from_oauth(user_info)
    except (RuntimeError, ValueError) as e:
        return _clear_oauth_state(JSONResponse({"error": str(e)}, status_code=500))

    response = _clear_oauth_state(RedirectResponse(f"{FRONTEND_URL}/"))
    response.set_cookie(
        TOKEN_COOKIE,
        create_token(email, name),
        max_age=int(TOKEN_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=False,  # localhost runs over plain HTTP; turn on with HTTPS
        path="/",
    )
    return response


def create_token(email: str, name: str) -> str:
    now = datetime.now(timezone.utc)
    claims = {"sub": email, "name": name, "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(TOKEN_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in")
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    email = claims.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return {"email": email, "name": claims.get("name", "")}


@app.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@app.post("/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(TOKEN_COOKIE, path="/", samesite="lax", httponly=True)
    return response


@app.get("/auth/google")
def google_login():
    flow = Flow.from_client_secrets_file(CLIENT_SECRET_FILE, scopes=SCOPES)
    flow.redirect_uri = "http://localhost:8000/callback"
    authorization_url, state = flow.authorization_url(access_type='offline', prompt='select_account')

    response = RedirectResponse(authorization_url)
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=OAUTH_STATE_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,  # localhost runs over plain HTTP; turn on with HTTPS
        path=OAUTH_STATE_PATH,
    )
    return response


def _clear_oauth_state(response):
    response.delete_cookie(OAUTH_STATE_COOKIE, path=OAUTH_STATE_PATH, samesite="lax", httponly=True)
    return response
    

async def _persist_resume_profile(user_id: str, resume_text: str) -> tuple[dict | None, str | None]:
    """Extract structured profile and cache it on the user. Returns (profile, error)."""
    try:
        profile = await extract_resume_profile(resume_text)
        data = profile.model_dump()
        await users_collection.update_one(
            {"email": user_id},
            {
                "$set": {
                    "resume_profile": data,
                    "resume_profile_updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return data, None
    except Exception as e:
        await users_collection.update_one(
            {"email": user_id},
            {"$unset": {"resume_profile": "", "resume_profile_updated_at": ""}},
        )
        return None, str(e)


async def ensure_resume_profile(user_id: str, user: dict | None) -> dict | None:
    """Return cached resume_profile, or extract+cache once if only resume_text exists."""
    if not user or users_collection is None or not user_id:
        return None
    existing = user.get("resume_profile")
    if isinstance(existing, dict) and existing:
        return existing
    resume_text = (user.get("resume_text") or "").strip()
    if not resume_text:
        return None
    data, _err = await _persist_resume_profile(user_id, resume_text)
    return data


@app.post("/uploadResume")
async def uploadResume(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    user_id = user["email"]
    if users_collection is None:
        return JSONResponse({"error": "Database is not configured"}, status_code=503)

    contents = await file.read()
    if len(contents) > MAX_RESUME_BYTES:
        return JSONResponse({"error": "Resume must be under 5MB"}, status_code=400)

    try:
        text = extract_resume_text(file.filename or "", contents)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    await users_collection.update_one(
        {"email": user_id}, {"$set": {"resume_text": text}}
    )

    profile, profile_error = await _persist_resume_profile(user_id, text)
    response = {
        "filename": file.filename,
        "size": len(contents),
        "chars": len(text),
        "profile_extracted": profile is not None,
    }
    if profile_error:
        response["warning"] = f"Resume saved, but profile extraction failed: {profile_error}"
    return response


# @app.post("/processQuery")
# async def process_query(query: ChatRequest):
#     now = datetime.now(timezone.utc)
#     user_msg = {"role": "user", "content": query.message, "timestamp": now}

#     user = await users_collection.find_one({"email": query.user_id})
#     resume_text = user.get("resume_text", "") if user else ""

#     assistant_response = await pipeline.find_leads(query.message, llm, resume_text)

#     assistant_msg = {"role": "assistant", "content": assistant_response, "timestamp": now}

#     await chats_collection.update_one(
#         {"session_id": query.session_id},
#         {
#             "$push": {"messages": {"$each": [user_msg, assistant_msg]}},
#             "$set": {"updated_at": now},
#             "$setOnInsert": {
#                 "user_id": query.user_id,
#                 "created_at": now,
#                 "title": query.message[:50],
#             },
#         },
#         upsert=True
#     )

#     return {"response": assistant_response, "session_id": query.session_id}

RECENT_QUERY_COUNT = 5


async def _recent_queries(user_id: str, limit: int = RECENT_QUERY_COUNT) -> list[str]:
    """The user's last few messages across all chats, oldest first."""
    if chats_collection is None:
        return []
    pipeline_stages = [
        {"$match": {"user_id": user_id}},
        {"$unwind": "$messages"},
        {"$match": {"messages.role": "user"}},
        {"$sort": {"messages.timestamp": -1}},
        {"$limit": limit},
        {"$project": {"_id": 0, "content": "$messages.content"}},
    ]
    rows = await chats_collection.aggregate(pipeline_stages).to_list(length=limit)
    return [r["content"] for r in reversed(rows) if isinstance(r.get("content"), str)]


async def _update_memory_safely(user_id: str, message: str, mode: str, recent: list[str]):
    """Background job: never raises, never logs user text."""
    try:
        await update_memory(
            user_memory_collection, user_keys_collection, user_id, message, mode, recent
        )
    except Exception as e:
        print(f"WARNING: memory update failed: {type(e).__name__}")


async def _classify_mode(message: str) -> str:
    """Fallback classifier, used only when route_and_plan's reply can't be parsed."""
    text = await claude_code_invoke(
        system="You are a classifier. Respond with exactly one word.",
        user=(
            "Classify this query into exactly one category:\n"
            "- PERSON: asking to find specific people, professionals, or employees\n"
            "- COMPANY: asking to discover companies, startups or organizations\n"
            "- GENERAL: anything else (factual question, greetings, etc)\n\n"
            f"Respond with only one word: PERSON, COMPANY or GENERAL.\n\nquery: {message}"
        ),
    )
    return parse_mode(text)


@app.post("/processQuery")
async def process_query(
    query: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    user_id = current_user["email"]

    existing_chat = await chats_collection.find_one({"session_id": query.session_id}, {"user_id": 1})
    if existing_chat and existing_chat.get("user_id") != user_id:
        return JSONResponse({"error": "Chat not found"}, status_code=404)

    user = await users_collection.find_one({"email": user_id}) if users_collection is not None else None
    resume_text = user.get("resume_text", "") if user else ""
    resume_profile = await ensure_resume_profile(user_id, user)

    # Read recent queries before this message is saved, so it isn't counted twice.
    try:
        recent = await _recent_queries(user_id)
    except Exception:
        recent = []
    ctx = await build_user_context(
        user_memory_collection, user_keys_collection, user_id, resume_profile, recent
    )

    # One LLM call both classifies the query and plans its searches.
    try:
        mode, plan = await route_and_plan(query.message, profile=resume_profile, memory=ctx.text)
    except LLMUnavailableError:
        raise
    except Exception as e:
        # Reply didn't match the schema: fall back to the old one-word classifier;
        # find_leads / find_companies then plan on their own.
        print(f"WARNING: route_and_plan failed ({type(e).__name__}); using classifier fallback")
        mode, plan = await _classify_mode(query.message), None

    if mode == "PERSON":
        result = await pipeline.find_leads(
            query.message, llm, resume_text, resume_profile=resume_profile, memory=ctx.text, plan=plan
        )
    elif mode == "COMPANY":
        result = await pipeline.find_companies(
            query.message, llm, resume_text, resume_profile=resume_profile, memory=ctx.text, plan=plan
        )
    else:
        system = REACHER_SYSTEM_PROMPT
        if resume_text:
            system += f"\n\nThe user's resume (use it to personalize answers):\n{resume_text[:3000]}"
        if ctx.facts:
            system += f"\n\nWhat the user has told Reacher before (respect it):\n{ctx.text}"

        direct_text = await claude_code_invoke(system=system, user=query.message)
        result = {"summary": direct_text, "leads": []}

    summary, leads = normalize_result(result)
    for lead in leads:
        if isinstance(lead, dict):
            lead["domain"] = _clean_domain(lead.get("domain"))
    kept = apply_exclusions(leads, ctx.facts)
    if len(kept) != len(leads):
        print(f"INFO: exclusions removed {len(leads) - len(kept)} lead(s)")   # count only, no names
    leads = kept

    # Most messages change nothing, so skip the LLM memory call unless the
    # message has a cue (or is picked for the occasional pattern check).
    if (
        user_memory_collection is not None
        and user_keys_collection is not None
        and should_update_memory(query.message, random.random())
    ):
        background_tasks.add_task(_update_memory_safely, user_id, query.message, mode, ctx.recent)

    assistant_msg = {
        "role": "assistant",
        "content": summary,
        "leads": leads,
        "mode": mode,
        "timestamp": now,
    }

    await chats_collection.update_one(
        {"session_id": query.session_id, "user_id": user_id},
        {
            "$push": {
                "messages": {"$each": [
                    {"role": "user", "content": query.message, "timestamp": now},
                    assistant_msg
                ]}
            },
            "$set": {"updated_at": now},
            "$setOnInsert": {
                "created_at": now,
                "title": query.message[:50],
            },
        },
        upsert=True,
    )

    return {"response": summary, "leads": leads, "session_id": query.session_id}


# --- /memory: the user's own view of what Reacher remembers -----------------
# user_id always comes from the JWT cookie, never from the request,
# so a user can only ever read or change their own memory.

FACT_ID = Path(..., pattern=r"^f_[0-9a-f]{8}$")


def _clean_fact_text(v):
    if v is None:
        return v
    v = " ".join(v.split())
    if not v:
        raise ValueError("text cannot be empty")
    return v


class MemoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, max_length=MAX_TEXT)
    kind: FactKind | None = None
    pinned: bool | None = None

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v):
        return _clean_fact_text(v)


class MemoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: FactKind
    text: str = Field(max_length=MAX_TEXT)
    pinned: bool = False

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v):
        return _clean_fact_text(v)


def _require_memory_db():
    if user_memory_collection is None or user_keys_collection is None:
        raise HTTPException(status_code=503, detail="Memory is unavailable right now")


@app.get("/memory")
async def get_memory(current_user: dict = Depends(get_current_user)):
    _require_memory_db()
    facts = await list_memory(user_memory_collection, user_keys_collection, current_user["email"])
    return {"facts": facts}


@app.post("/memory", status_code=201)
async def create_memory_fact(body: MemoryCreate, current_user: dict = Depends(get_current_user)):
    _require_memory_db()
    try:
        fact = await add_fact(
            user_memory_collection, user_keys_collection, current_user["email"],
            body.kind, body.text, pinned=body.pinned,
        )
    except MemoryFull:
        raise HTTPException(
            status_code=409,
            detail=f"Memory is full ({MAX_FACTS} items). Delete something first.",
        )
    return {"fact": fact}


@app.patch("/memory/{fact_id}")
async def patch_memory_fact(
    body: MemoryPatch,
    fact_id: str = FACT_ID,
    current_user: dict = Depends(get_current_user),
):
    _require_memory_db()
    if body.text is None and body.kind is None and body.pinned is None:
        raise HTTPException(status_code=422, detail="Nothing to change")
    fact = await edit_fact(
        user_memory_collection, user_keys_collection, current_user["email"], fact_id,
        text=body.text, kind=body.kind, pinned=body.pinned,
    )
    if fact is None:
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"fact": fact}


@app.delete("/memory/{fact_id}")
async def delete_memory_fact(fact_id: str = FACT_ID, current_user: dict = Depends(get_current_user)):
    _require_memory_db()
    if not await delete_fact(user_memory_collection, current_user["email"], fact_id):
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"deleted": fact_id}


@app.delete("/memory")
async def delete_all_memory(current_user: dict = Depends(get_current_user)):
    _require_memory_db()
    await clear_memory(user_memory_collection, current_user["email"])
    return {"cleared": True}


async def find_contact_for_person(person, browser, llm, timeout=45):
    task = (
        f"Find the email address for {person["name"]},"
        f"{person['title']} at {person['company']}."
        f"Search on DuckDuckGo, check personal websites, "
        f"university pages, or company pages. "
        f"Return ONLY the email address. If not found, say NOT FOUND"
    )

    agent = Agent(
        llm = llm,
        task = task,
        browser = browser,
        max_actions_per_step=5,
        max_input_tokens=16000,
        max_failures=10,
    )

    try:
        result = await asyncio.wait_for(agent.run(), timeout=timeout)
        return {"name": person["name"], "contact": result.final_result() or "NOT_FOUND"}
    except asyncio.TimeoutError:
        return {"name": person["name"], "contact": "TIMED_OUT"}



@app.get("/enrich/{session_id}")
async def enrich_contacts(session_id: str, user: dict = Depends(get_current_user)):
    doc = await chats_collection.find_one({"session_id": session_id, "user_id": user["email"]})
    if not doc:
        return JSONResponse({"error": "Chat not found"}, status_code=404)
    
    last_assistant_msg = None
    for msg in reversed(doc.get("messages", [])):
        if msg["role"] == "assistant" and msg.get("leads"):
            last_assistant_msg = msg
            break

    if not last_assistant_msg:
        return JSONResponse({"error": "No leads to enrich"}, status_code=404)
    
    leads = last_assistant_msg["leads"]
    needs_enrichment = [l for l in leads if not l.get("email")]

    async def event_stream():
        for person in needs_enrichment:
            contact = await find_contact_for_person(person, pipeline.browser, llm, timeout=45)
            yield {
                "event": "contact_info found",
                "data": json.dumps({
                    "name": person["name"],
                    "contact": contact["contact"],
                })
            }

        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_stream())



@app.get("/chats")
async def get_chats(user: dict = Depends(get_current_user)):
    cursor = chats_collection.find({"user_id": user["email"]},{"session_id": 1, "title": 1, "updated_at": 1, "messages": {"$slice": -1}}).sort("updated_at", -1).limit(50)

    chats = []
    async for doc in cursor:
        last_msg = doc.get("messages", [{}])[-1] if doc.get("messages") else {}
        chats.append({
            "session_id": doc.get("session_id"),
            "title": doc.get("title", "Untitled"),
            "updated_at": doc.get("updated_at", "").isoformat() if doc.get("updated_at") else "",
            "preview": (last_msg.get("content") or "")[:80],
            "message_content": None,
        })

    return {"chats": chats}


@app.get("/chat/{session_id}")
async def get_chat(session_id: str, user: dict = Depends(get_current_user)):
    doc = await chats_collection.find_one({"session_id": session_id, "user_id": user["email"]})

    if not doc:
        return JSONResponse({"error": "Chat not found"}, status_code=404)

    return {
        "session_id": doc.get("session_id"),
        "title": doc.get("title", "Untitled"),
        "messages": [
            {"role": m["role"], "content": m["content"], "leads": m.get("leads", [])}
            for m in doc.get("messages", [])
        ],
    }