from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from browser_use import Browser, SystemPrompt
from browser_use.agent.service import Agent
from browser_use.agent.views import AgentOutput
from browser_use.browser.browser import BrowserConfig
from langchain_ollama import ChatOllama
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
from datetime import datetime, timezone
from urllib.parse import quote, quote_plus
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
# from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
import pipeline
from docx import Document
from io import BytesIO
import json
from sse_starlette.sse import EventSourceResponse


class CustomSystemPrompt(SystemPrompt):
    def __init__(self, *args, task_examples="", **kwargs):
        super().__init__(*args, **kwargs)
        self.task_examples = task_examples


    def important_rules(self):
        existing = super().important_rules()
        return existing + "\n" + SYSTEM_PROMPT + "\n" + self.task_examples

class ChatRequest(BaseModel):
    session_id: str
    user_id: str
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


app = FastAPI()

origins = ["http://localhost:5173"]
app.add_middleware(
    CORSMiddleware, 
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = """You are a people-finding assistant for cold outreach. Follow these rules:

1. Go to Google and search for the person, role, or company.
2. Look for LinkedIn profiles, company team pages, or about pages.
3. Extract names, titles, and email patterns.
4. Present results clearly and say done. Do NOT over-browse.
"""

load_dotenv()

# llm = ChatOllama(model="kimi-k2.5:cloud", temperature=0.4)
llm = ChatOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
    model = "llama-3.3-70b-versatile",
    temperature=0.4,
)
live_memory = deque(maxlen=100)
memory_lock = Lock()


CLIENT_SECRET_FILE = os.getenv("CLIENT_SECRET_FILE")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

oauth_states = {}

_mongo_uri = _mongo_connection_uri()
mongo_client = (
    AsyncIOMotorClient(_mongo_uri, serverSelectionTimeoutMS=10_000) if _mongo_uri else None
)

if mongo_client is not None:
    mongo_db = mongo_client["reacher"]
    users_collection = mongo_db["users"]
    chats_collection = mongo_db["chats"]
else:
    mongo_db = None
    users_collection = None
    chats_collection = None


user_current_chat = {}



@app.get("/")
def root():
    return {"Hello World"}


@app.get("/callback")
async def callback(code, state):
    # if request.args.get('state') != session['state']:
    #     raise Exception('Invalid state')

    if state != oauth_states.get('state'):
        return {"error": "Invalid state"}
    
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
        is_new = await upsert_user_from_oauth(user_info)
    except (RuntimeError, ValueError) as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    q = (
        f"name={quote(name)}&email={quote(email)}&is_new={'true' if is_new else 'false'}"
    )
    return RedirectResponse(f"http://localhost:5173/?{q}")


@app.get("/auth/google")
def google_login():
    flow = Flow.from_client_secrets_file(CLIENT_SECRET_FILE, scopes=SCOPES)
    flow.redirect_uri = "http://localhost:8000/callback"
    authorization_url, state = flow.authorization_url(access_type='offline', prompt='select_account')
    oauth_states['state'] = state

    return RedirectResponse(authorization_url)
    

@app.post("/uploadResume")
async def uploadResume(file: UploadFile = File(...), user_id: str = Form(...)):
    contents = await file.read()
    filename = file.filename.lower()

    if filename.endswith(".pdf"):
        pass
    elif filename.endswith(".docx"):
        doc = Document(BytesIO(contents))
        text = "\n".join([p.text for p in doc.paragraphs])
        print(text)
        
    else:
        return JSONResponse({"error": "Unsupported file type"}, status_code=400)
    
    # print("======================================================")
    # print(contents)
    # print("======================================================")
    await users_collection.update_one(
        {"email": user_id}, {"$set": {"resume_text": text}}
    )

    return {"filename": file.filename, "size": len(contents)}


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

@app.post("/processQuery")
async def process_query(query: ChatRequest):
    now = datetime.now(timezone.utc)

    user = await users_collection.find_one({"email": query.user_id})
    resume_text = user.get("resume_text", "") if user else ""

    # result = await pipeline.find_leads(query.message, llm, resume_text)

    classify_prompt = (
        "Is the following query asking to find, discover, or connect with specific people, "
        "professionals, employees, or leads, at a company? Answer ONLY 'YES' or 'NO'. \n\n"
        f"Query: {query.message}"
    )
    classification = await llm.ainvoke([{"role": "user", "content": classify_prompt}])
    is_lead_query = "yes" in classification.content.strip().lower()

    if is_lead_query:
        result = await pipeline.find_leads(query.message, llm, resume_text)

        if isinstance(result, str):
            cleaned = result.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()
            try:
                result = json.loads(cleaned)
            except (json.JSONDecodeError, TypeError):
                result = {"summary": result, "leads": []}

        if isinstance(result, dict):
            summary = result.get("summary", result.get("suggestions", ""))
            leads = result.get("leads", [])
        else:
            summary = result
            leads = []
    else:
        direct = await llm.ainvoke([{"role": "user", "content": query.message}])
        summary = direct.content
        leads = []

    assistant_msg = {
        "role": "assistant",
        "content": summary,
        "leads": leads,
        "timestamp": now,
    }

    await chats_collection.update_one(
        {"session_id": query.session_id},
        {
            "$push": {
                "messages": {"$each": [
                    {"role": "user", "content": query.message, "timestamp": now},
                    assistant_msg
                ]}
            },
            "$set": {"updated_at": now},
            "$setOnInsert": {
                "user_id": query.user_id,
                "created_at": now,
                "title": query.message[:50],
            },
        },
        upsert=True,
    )

    return {"response": summary, "leads": leads, "session_id": query.session_id}


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
async def enrich_contacts(session_id: str):
    doc = await chats_collection.find_one({"session_id": session_id})
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
            contact = await find_contact_for_person(person, browser, llm, timeout=45)
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
async def get_chats(user_id:str):
    cursor = chats_collection.find({"user_id": user_id}, {"session_id": 1, "title": 1, "updated_at": 1, "messages": {"$slice": -1}}).sort("updated_at", -1).limit(50)

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
async def get_chat(session_id: str):
    doc = await chats_collection.find_one({"session_id": session_id})

    if not doc:
        return JSONResponse({"error": "Chat not found"}, status_code=404)

    return {
        "session_id": doc.get("session_id"),
        "title": doc.get("title", "Untitled"),
        "messages": [{"role": m["role"], "content": m["content"]} for m in doc.get("messages", [])],
    }