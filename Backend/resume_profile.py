"""Resume domain: structured profile schema and one-shot LLM extraction."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from llm_provider import claude_code_invoke

RESUME_PROFILE_SYSTEM = (
    "You extract structured career profiles from resumes. "
    "Respond with only valid JSON matching the schema."
)

RESUME_PROFILE_PROMPT = """Extract a compact career profile from this resume for lead-finding search.

Rules:
- Use ONLY facts present in the resume. Do not invent employers, schools, or skills.
- Prefer concrete nouns useful in web search (technologies, company names, school names, role titles).
- Keep lists short and high-signal:
  - target_roles: up to 5 (recent titles and/or roles they appear to seek)
  - skills: up to 8
  - industries: up to 5
  - companies: up to 5 (past/current employers)
  - schools: up to 3
  - locations: up to 3
  - keywords: up to 8 extra search-friendly terms not already covered above
- summary: 1-2 sentences on who they are professionally
- If a field is unknown, use an empty string or empty list

Resume:
{resume_text}
"""

_PROFILE_LIST_CAPS = {
    "target_roles": 5,
    "skills": 8,
    "industries": 5,
    "companies": 5,
    "schools": 3,
    "locations": 3,
    "keywords": 8,
}


class ResumeProfile(BaseModel):
    """Compact resume signals for search planning and ranking."""

    summary: str = ""
    target_roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    schools: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


def _trim_resume_profile(profile: ResumeProfile) -> ResumeProfile:
    data = profile.model_dump()
    for key, cap in _PROFILE_LIST_CAPS.items():
        values = data.get(key) or []
        trimmed: list[str] = []
        seen: set[str] = set()
        for item in values:
            text = " ".join(str(item).split()).strip()
            if not text:
                continue
            key_lower = text.lower()
            if key_lower in seen:
                continue
            seen.add(key_lower)
            trimmed.append(text)
            if len(trimmed) >= cap:
                break
        data[key] = trimmed
    data["summary"] = " ".join((data.get("summary") or "").split()).strip()
    return ResumeProfile.model_validate(data)


async def extract_resume_profile(resume_text: str) -> ResumeProfile:
    """One-shot LLM extraction of all resume sections into ResumeProfile."""
    text = (resume_text or "").strip()
    if not text:
        raise ValueError("resume_text is empty")

    # Cap input size so extraction stays focused and within CLI timeouts.
    truncated = text[:12000]
    result = await claude_code_invoke(
        system=RESUME_PROFILE_SYSTEM,
        user=RESUME_PROFILE_PROMPT.format(resume_text=truncated),
        schema=ResumeProfile,
    )
    if not isinstance(result, ResumeProfile):
        raise RuntimeError("Resume profile extraction did not return ResumeProfile")
    return _trim_resume_profile(result)


def format_resume_profile(profile: ResumeProfile | dict | None) -> str:
    """Compact text block for planner/synthesizer prompts."""
    if profile is None:
        return "No profile provided"
    if isinstance(profile, dict):
        profile = ResumeProfile.model_validate(profile)
    return json.dumps(profile.model_dump(), ensure_ascii=False, indent=2)
