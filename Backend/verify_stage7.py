"""Stage 7 verification: hybrid resume wiring without full scrape/UI."""

from __future__ import annotations

import asyncio
import inspect
import sys
from io import BytesIO

from docx import Document

from app import extract_resume_text, ensure_resume_profile
from planner import generate_plan, COMPANY_PLANNER_PROMPT
from pipeline import find_leads, find_companies
from resume_profile import ResumeProfile, format_resume_profile, _trim_resume_profile


def _ok(name: str) -> None:
    print(f"PASS  {name}")


def _fail(name: str, err: Exception | str) -> None:
    print(f"FAIL  {name}: {err}")
    raise SystemExit(1)


def check_text_extraction() -> None:
    buf = BytesIO()
    doc = Document()
    doc.add_paragraph("Ada Lovelace")
    doc.add_paragraph("University of Maryland")
    doc.add_paragraph("Python, FastAPI")
    doc.save(buf)
    text = extract_resume_text("sample.docx", buf.getvalue())
    if "Ada Lovelace" not in text or "Maryland" not in text:
        _fail("docx extract", text)
    _ok("docx text extraction")

    empty = BytesIO()
    Document().save(empty)
    try:
        extract_resume_text("empty.docx", empty.getvalue())
        _fail("empty docx rejected", "expected ValueError")
    except ValueError:
        _ok("empty docx rejected")


def check_signatures() -> None:
    if "resume_profile" not in inspect.signature(find_leads).parameters:
        _fail("find_leads signature", "missing resume_profile")
    if "resume_profile" not in inspect.signature(find_companies).parameters:
        _fail("find_companies signature", "missing resume_profile")
    if "profile" not in inspect.signature(generate_plan).parameters:
        _fail("generate_plan signature", "missing profile")
    _ok("pipeline/planner signatures")


def check_profile_format() -> None:
    profile = _trim_resume_profile(
        ResumeProfile(
            summary="Backend engineer",
            skills=["Python", "FastAPI"],
            schools=["University of Maryland"],
            companies=["Acme"],
            target_roles=["Backend Engineer"],
        )
    )
    block = format_resume_profile(profile)
    if "Python" not in block or "Maryland" not in block:
        _fail("format_resume_profile", block)
    if format_resume_profile(None) != "No profile provided":
        _fail("format none", format_resume_profile(None))
    _ok("profile format helpers")


async def check_ensure_no_user() -> None:
    result = await ensure_resume_profile("", None)
    if result is not None:
        _fail("ensure_resume_profile empty", result)
    _ok("ensure_resume_profile with no user")


async def check_plans() -> None:
    profile = {
        "summary": "Backend engineer focused on APIs",
        "target_roles": ["Backend Engineer"],
        "skills": ["Python", "FastAPI"],
        "industries": ["Developer tools"],
        "companies": ["Acme"],
        "schools": ["University of Maryland"],
        "locations": ["Washington DC"],
        "keywords": ["API", "distributed systems"],
    }

    no_profile = await generate_plan("backend engineers at Stripe")
    if not no_profile or "url" not in no_profile[0]:
        _fail("plan without profile", no_profile)
    _ok(f"plan without profile ({len(no_profile)} steps)")

    with_profile = await generate_plan(
        "backend engineers at Stripe",
        profile=profile,
    )
    if not with_profile or "url" not in with_profile[0]:
        _fail("plan with profile", with_profile)

    blob = " ".join(f'{s["url"]} {s["goal"]}' for s in with_profile).lower()
    signals = ["maryland", "umd", "python", "fastapi", "alumni", "dc", "washington"]
    hit = [s for s in signals if s in blob]
    print(f"INFO  profile-influenced plan steps:")
    for step in with_profile:
        print(f"      - {step['url']}")
        print(f"        goal: {step['goal']}")
    if not hit:
        print(
            "WARN  profile signals not obvious in URLs/goals "
            "(LLM may still have used profile implicitly)"
        )
        _ok("plan with profile returned steps")
    else:
        _ok(f"plan with profile shows signals: {', '.join(hit)}")

    company = await generate_plan(
        "cybersecurity startups in DC",
        COMPANY_PLANNER_PROMPT,
        profile=profile,
    )
    if not company:
        _fail("company plan", company)
    _ok(f"company plan with profile ({len(company)} steps)")


async def main() -> None:
    print("=== Stage 7 verification ===")
    check_text_extraction()
    check_signatures()
    check_profile_format()
    await check_ensure_no_user()
    print("INFO  calling Claude Code for planner checks (may take a bit)...")
    await check_plans()
    print("=== automated checks complete ===")
    print()
    print("Still do manually in the UI:")
    print("  1. Log in, upload a real PDF/DOCX resume")
    print("  2. Confirm Mongo user has resume_text + resume_profile")
    print("  3. Run a PERSON query and a COMPANY query")
    print("  4. Re-upload a different resume and confirm profile updates")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
