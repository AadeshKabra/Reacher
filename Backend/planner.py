import json, os
from langchain_openai import ChatOpenAI


llm = ChatOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
    model="llama-3.3-70b-versatile",
    temperature=0.2,
)

PLANNER_PROMPT = """You are a research planner for FINDING PEOPLE for cold outreach.
Given a user query, output a JSON plan with search URLs to scrape.

RULES:
- Your goal is to FIND PEOPLE with names, job titles and contact information.
- Use DuckDuckGo for search (NOT Google — it blocks bots)
- Search format: https://duckduckgo.com/html/?q=YOUR+QUERY
- Replace spaces with + in thee query.
- Do NOT link to generic career/about pages - these don't have individual people
- Do NOT include LinkedIn URLs (they block scraping)
- Output 2-4 URLs maximum

GOOD SEARCH STRATEGIES for fiding people:
- "site:nvidia.com ML engineer team" — finds team pages
- "nvidia machine learning engineer name email" — finds profiles
- "nvidia ML engineer speaker conference" — finds people who gave talks
- "nvidia machine learning blog author" — finds people who write

Respond with ONLY valid JSON, no markdown:
{{
  "steps": [
    {{"url": "https://...", "goal": "what to extract from this page"}}
  ]
}}

User query: {query}"""


async def generate_plan(query):
    response = await llm.ainvoke(PLANNER_PROMPT.format(query=query))
    plan = json.loads(response.content)
    return plan["steps"]


SYNTHESIZER_PROMPT = """
You are a people-finding assistant that personalizes results based on the user's background.
TASK: From the scraped data below, extract specific people with their details.

USER' RESUME:
{resume}

For each person found, include:
- Full name
- Job title / role
- Company
- Any contact info (email, social profile URLs)
- Source URL where you found them

IMPORTANT:
- Only include REAL people you found in the data — do NOT make up names
- If the data doesn't contain specific people, say "No specific individuals found"
  and suggest better search strategies
- Do NOT recommend visiting LinkedIn or career pages — that's not actionable

User Query: {query}

Scraped Data: {scraped_data}

Present results clearly with names, titles, companies, and any contact info found. 
If you found relevant links that might have more info, mention them. 

PRIORITAZATION:
- Rank people who share the user's skills, industry, or interests higher
- Highlight shared backgrounds (same school, similar tech stack, overlapping experience)
- Flag potential "warm paths" - alumni connections, shared technologies, common interests
"""


async def synthesize_results(query, scraped_pages: list, resume_text=""):
    scraped_text = ""
    for page in scraped_pages:
        if page.success:
            scraped_text += f"\n--- From: {page.url} ---\n"
            scraped_text += f"Title: {page.title}\n"
            scraped_text += page.text[:3000] + "\n"

    response = await llm.ainvoke(SYNTHESIZER_PROMPT.format(query=query, scraped_data=scraped_text, resume=resume_text if resume_text else "No resume provided"))

    return response.content

