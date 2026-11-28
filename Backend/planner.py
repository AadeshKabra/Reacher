import json
from llm_provider import claude_code_invoke, PlanResponse, RoutedPlan, SynthesisResponse
from resume_profile import format_resume_profile

PLANNER_PROMPT = """You are a research planner for FINDING PEOPLE for cold outreach.
Given a user query and an optional structured user profile, output a JSON plan with search URLs to scrape.

RULES:
- Your goal is to FIND PEOPLE with names, job titles and contact information.
- Use DuckDuckGo for search (NOT Google — it blocks bots)
- Search format: https://duckduckgo.com/html/?q=YOUR+QUERY
- Replace spaces with + in the query.
- Do NOT link to generic career/about pages - these don't have individual people
- Do NOT include LinkedIn URLs (they block scraping)
- Output 2-4 URLs maximum
- The user query is the primary intent — never ignore it in favor of the profile
- When a profile is provided, combine query intent with profile skills, companies, schools, locations, and target roles
- Prefer warm-path angles when they fit the query (alumni + company, shared stack + team pages, industry speakers)
- Follow USER MEMORY: never search for anything it excludes; use its preferences and goals to shape searches.
  Items marked (guess) are hints only.
- Use RECENT QUERIES only to understand follow-ups (e.g. "narrow it down to Seattle"); otherwise plan for the current query.

GOOD SEARCH STRATEGIES for finding people:
- "site:nvidia.com ML engineer team" — finds team pages
- "nvidia machine learning engineer name email" — finds profiles
- "nvidia ML engineer speaker conference" — finds people who gave talks
- "nvidia machine learning blog author" — finds people who write
- "UMD alumni Stripe engineer" — alumni / warm-path style searches when school fits

Respond with ONLY valid JSON, no markdown:
{{
  "steps": [
    {{"url": "https://...", "goal": "what to extract from this page"}}
  ]
}}

User query: {query}

USER PROFILE (structured):
{profile}

{memory}"""

def parse_json(text: str):
  """Parse LLM JSON output, tolerating JSON fences"""
  cleaned = text.strip()
  if cleaned.startswith("```"):
    cleaned = cleaned.split("\n", 1)[-1]
  if cleaned.endswith("```"):
    cleaned = cleaned.rsplit("```", 1)[0]
  return json.loads(cleaned.strip())


async def generate_plan(query, prompt=None, profile=None, memory="No memory yet"):
  prompt = prompt or PLANNER_PROMPT
  result = await claude_code_invoke(
      system="You are a research planner. Respond with only valid JSON.",
      user=prompt.format(
          query=query,
          profile=format_resume_profile(profile),
          memory=memory or "No memory yet",
      ),
      schema=PlanResponse,
  )
  return [{"url": s.url, "goal": s.goal} for s in result.steps]


ROUTE_AND_PLAN_PROMPT = """You are the router and research planner for Reacher, an app that finds PEOPLE and COMPANIES for job-search cold outreach.

STEP 1. Classify the user query into exactly one mode:
- PERSON: find specific people, professionals or employees
- COMPANY: discover companies, startups or organizations
- GENERAL: anything else (advice, factual question, greeting, cold-email help)

STEP 2. If the mode is GENERAL, return "steps": []. Otherwise output 2-4 search URLs to scrape.

RULES FOR ALL SEARCHES:
- Use DuckDuckGo for search (NOT Google — it blocks bots)
- Search format: https://duckduckgo.com/html/?q=YOUR+QUERY
- Replace spaces with + in the query.
- Do NOT include LinkedIn URLs (they block scraping)
- The user query is the primary intent — never ignore it in favor of the profile
- Follow USER MEMORY: never search for anything it excludes; use its preferences and goals to shape searches.
  Items marked (guess) are hints only.
- Use RECENT QUERIES only to understand follow-ups (e.g. "narrow it down to Seattle"); otherwise plan for the current query.

PERSON mode:
- Goal: find people with names, job titles and contact information.
- Do NOT link to generic career/about pages - these don't have individual people
- Combine query intent with profile skills, companies, schools, locations and target roles
- Prefer warm-path angles when they fit (alumni + company, shared stack + team pages, industry speakers)
- Good strategies: "site:nvidia.com ML engineer team", "nvidia machine learning engineer name email",
  "nvidia ML engineer speaker conference", "nvidia machine learning blog author", "UMD alumni Stripe engineer"

COMPANY mode:
- Goal: find companies, startups or organizations matching the query.
- Prefer lists and directories: "top cybersecurity startups DC", "site:builtin.com", "site:ycombinator.com/companies", "site:wellfound.com"
- Bias toward companies that fit the user's skills, industries, locations and target roles while still answering the query

Respond with ONLY valid JSON, no markdown:
{{
  "mode": "PERSON" | "COMPANY" | "GENERAL",
  "steps": [
    {{"url": "https://...", "goal": "what to extract from this page"}}
  ]
}}

User query: {query}

USER PROFILE (structured):
{profile}

{memory}"""


async def route_and_plan(query, profile=None, memory="No memory yet") -> tuple[str, list[dict]]:
  """One LLM call that classifies the query and, for PERSON/COMPANY, plans the searches.

  Replaces the separate classifier call. Returns (mode, steps); steps is [] for GENERAL.
  """
  result = await claude_code_invoke(
      system="You are a query router and research planner. Respond with only valid JSON.",
      user=ROUTE_AND_PLAN_PROMPT.format(
          query=query,
          profile=format_resume_profile(profile),
          memory=memory or "No memory yet",
      ),
      schema=RoutedPlan,
  )
  steps = [] if result.mode == "GENERAL" else [{"url": s.url, "goal": s.goal} for s in result.steps]
  return result.mode, steps


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

{memory}

Present results clearly with names, titles, companies, and any contact info found. 
If you found relevant links that might have more info, mention them. 

PRIORITAZATION:
- Rank people who share the user's skills, industry, or interests higher
- Highlight shared backgrounds (same school, similar tech stack, overlapping experience)
- Flag potential "warm paths" - alumni connections, shared technologies, common interests
{memory_rules}

Respond with ONLY valid JSON, no markdown:
{{
  "leads":[
    {{
      "name": "Full Name",
      "title": "Job Title",
      "company": "Company Name",
      "email": "email if found, otherwise null",
      "source_url": "where_you_found_them",
      "relevance": "Why this person is a good fit based on the user's background and the query"
    }}
  ],
  "suggestions": "A brief summary of what relevant was found"
}}
"""


SYNTH_MEMORY_RULES = """- Follow USER MEMORY: never include, recommend, or name in the summary anything it excludes.
- Rank results that match its preferences and goals higher. Items marked (guess) are hints only:
  they may nudge the order but must never remove a result.
- Ignore RECENT QUERIES here; they are only for planning."""


async def synthesize_results(query, scraped_pages: list, resume_text="", prompt=None, memory=""):
  prompt = prompt or SYNTHESIZER_PROMPT
  scraped_text = ""
  for page in scraped_pages:
      if page.success:
          scraped_text += f"\n--- From: {page.url} ---\n"
          scraped_text += f"Title: {page.title}\n"
          scraped_text += page.text[:3000] + "\n"

  result = await claude_code_invoke(
      system="You are a people-finding assistant. Respond with only valid JSON.",
      user=prompt.format(
          query=query,
          scraped_data=scraped_text,
          resume=resume_text if resume_text else "No resume provided",
          memory=memory or "No memory yet",
          memory_rules=SYNTH_MEMORY_RULES if memory and memory != "No memory yet" else "",
      ),
      schema=SynthesisResponse,
  )
  return json.dumps(result.model_dump())



COMPANY_PLANNER_PROMPT = """You are a research planner for DISCOVERING COMPANIES.
Given a user query and an optional structured user profile, output a JSON plan with search URLs to scrape.

RULES:
- Your goal is to FIND COMPANIES, startups or organizations matching the query.
- Use DuckDuckGo for search (NOT Google — it blocks bots)
- Search format: https://duckduckgo.com/html/?q=YOUR+QUERY
- Replace spaces with + in the query.
- Prefer lists and directories: "top cybersecurity startups DC", "site:builtin.com", "site:ycombinator.com/companies", "site:wellfound.com"
- Do NOT include LinkedIn URLs (they block scraping)
- Output 2-4 URLs maximum
- The user query is the primary intent — never ignore it in favor of the profile
- When a profile is provided, bias searches toward companies that fit the user's skills, industries, locations, and target roles while still answering the query
- Follow USER MEMORY: never search for anything it excludes; use its preferences and goals to shape searches.
  Items marked (guess) are hints only.
- Use RECENT QUERIES only to understand follow-ups (e.g. "narrow it down to Seattle"); otherwise plan for the current query.

Respond with ONLY valid JSON, no markdown:
{{
  "steps": [
    {{"url": "https://...", "goal": "what to extract from this page"}}
  ]
}}

User query: {query}

USER PROFILE (structured):
{profile}

{memory}"""


COMPANY_SYNTHESIZER_PROMPT = """
You are a company-discovery assistant that personalizes results based on the user's background.
TASK: From the scraped data below, extract specific companies matching the query.

USER'S RESUME:
{resume}

IMPORTANT:
- Only include REAL companies found in the data — do NOT make up companies
- If nothing relevant was found, return an empty list and suggest better searches in "summary"
- Rank companies that fit the user's skills and interests higher
{memory_rules}

User Query: {query}

Scraped Data: {scraped_data}

{memory}

Respond with ONLY valid JSON, no markdown:
{{
  "leads": [
    {{
      "name": "Company Name",
      "title": "One-line description of what they do",
      "company": "Location or stage if known, otherwise empty string",
      "email": null,
      "source_url": "company website or where you found it",
      "relevance": "Why this company fits the user's background and the query",
      "domain": "the company's own website domain, like nvidia.com, or null if unsure"
    }}
  ],
  "summary": "A brief summary of what was found"
}}
"""