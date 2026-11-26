"""Reacher search-quality eval.

Runs the real pipeline (pipeline.find_leads / find_companies) on a fixed query set and
measures how good the results are, so every change can be compared with a baseline.

Usage (from the Backend folder, with the backend venv):
    python eval/run_eval.py --quick                 # ~5-query dev subset
    python eval/run_eval.py                         # full set
    python eval/run_eval.py --ids p01,c01 --no-judge
    python eval/run_eval.py --label baseline --repeat 2
    python eval/run_eval.py --quick --profiles both   # same queries with and without the profile
    python eval/run_eval.py --compare eval/results/A.json eval/results/B.json
    python eval/run_eval.py --rejudge eval/results/A.json   # re-score saved leads, no searching
    python eval/run_eval.py --rejudge eval/results/A-rejudged.json --no-judge   # metrics only, no LLM

Metrics per query (aggregated in the summary):
    grounding      share of leads whose name appears on the page at their source_url
    source types   where leads come from (blog, conference, LinkedIn, data broker, ...)
    judge          per lead: request_match 0-3, user_fit 0-2 (vs the test profile), fabricated
    useful leads   not fabricated and (request_match >= 2, or request_match 1 with user_fit 2)
    verified       useful leads whose name was also found on their source page
    order quality  nDCG of the returned order, gain = request_match + user_fit
    leads, duplicates, latency, pages fetched / blocked / failed by the pipeline,
    gold recall when a query lists names that should appear.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(EVAL_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")  # so CLAUDE_CODE_* overrides apply, same as the app

import httpx  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from typing import Optional  # noqa: E402

from pydantic import BaseModel, Field  # noqa: E402

import metrics  # noqa: E402

RESULTS_DIR = EVAL_DIR / "results"
CACHE_DIR = EVAL_DIR / "cache" / "pages"
PAGE_CACHE_TTL_SECONDS = 24 * 3600
FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


# ---------------------------------------------------------------------------
# Pipeline instrumentation: record every page the pipeline fetched for a query
# ---------------------------------------------------------------------------

_captured_pages: list = []


def instrument_pipeline(pipeline_module) -> None:
    """Wrap the scraper functions pipeline.py imported, so we can see what it fetched."""
    original_multiple = pipeline_module.scrape_multiple
    original_follow = pipeline_module.scrape_with_follow

    async def scrape_multiple(urls):
        pages = await original_multiple(urls)
        _captured_pages.extend(pages)
        return pages

    async def scrape_with_follow(urls, max_follows):
        pages = await original_follow(urls, max_follows)
        _captured_pages.extend(pages)
        return pages

    pipeline_module.scrape_multiple = scrape_multiple
    pipeline_module.scrape_with_follow = scrape_with_follow


def summarize_pipeline_pages(pages) -> dict:
    """Pipeline-side fetch stats. Pages are read after the run, so JS renders are included."""
    unique = {}
    for page in pages:
        unique[page.url] = page  # later entries (after JS render) win
    blocked, failed, ok, js = 0, 0, 0, 0
    for page in unique.values():
        if page.need_js:
            js += 1
        if not page.success:
            failed += 1
        elif metrics.detect_block(None, page.text):
            blocked += 1  # "successful" fetch whose content is really a block page
        else:
            ok += 1
    return {
        "fetched": len(unique),
        "ok": ok,
        "blocked": blocked,
        "failed": failed,
        "needed_js": js,
        "urls": list(unique.keys()),
    }


# ---------------------------------------------------------------------------
# Independent page fetch for grounding (cached on disk for a day)
# ---------------------------------------------------------------------------

def _cache_path(url: str) -> Path:
    return CACHE_DIR / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.json"


async def fetch_page_text(url: str, client: httpx.AsyncClient) -> dict:
    """Full visible text of a page, for checking leads against. Never tries to bypass blocks."""
    if not url or not url.startswith("http"):
        return {"status": "no_url", "text": ""}

    path = _cache_path(url)
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - cached.get("fetched_at", 0) < PAGE_CACHE_TTL_SECONDS:
            return cached

    try:
        resp = await client.get(url, follow_redirects=True, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        block = metrics.detect_block(resp.status_code, text)
        status = "blocked" if block else "ok"
        record = {"status": status, "block_reason": block, "http": resp.status_code, "text": text}
    except Exception as exc:  # network errors, bad URLs, timeouts
        record = {"status": "fetch_failed", "error": f"{type(exc).__name__}: {exc}"[:300], "text": ""}

    record["fetched_at"] = time.time()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return record


async def ground_leads(leads: list[dict], pipeline_urls: list[str]) -> None:
    """Attach a `grounding` block to each lead (mutates in place)."""
    async with httpx.AsyncClient(headers=FETCH_HEADERS) as client:
        pages = await asyncio.gather(*(fetch_page_text(lead.get("source_url", ""), client) for lead in leads))
    pipeline_set = set(pipeline_urls)
    for lead, page in zip(leads, pages):
        checkable = page["status"] == "ok"
        lead["grounding"] = {
            "page_status": page["status"],
            "source_fetched_by_pipeline": lead.get("source_url") in pipeline_set,
            "name_match": metrics.match_name(lead.get("name", ""), page["text"]) if checkable else "unknown",
            "email_on_page": metrics.email_on_page(lead.get("email"), page["text"]) if checkable else None,
        }


# ---------------------------------------------------------------------------
# LLM relevance judge
# ---------------------------------------------------------------------------

class LeadJudgement(BaseModel):
    index: int
    fabricated: bool
    request_match: int = Field(ge=0, le=3)
    user_fit: Optional[int] = Field(default=None, ge=0, le=2)
    reason: str


class JudgeResponse(BaseModel):
    scores: list[LeadJudgement]


JUDGE_SYSTEM = "You grade search results for a cold-outreach tool. Respond with only valid JSON."

# Two separate scores, because "does this match the request?" and "is this a good contact for
# this particular user?" are different questions. Personalization should show up in user_fit.
JUDGE_PROMPT = """Grade each result on two separate scales. Be strict and consistent.

fabricated (true/false):
  true if the entry is a fictional character, a joke or placeholder profile, a celebrity
  name used as filler, or otherwise not a real, specific {entity}. If true, set
  request_match = 0 and user_fit = 0.

request_match (0-3): does the result answer THE REQUEST?
  3 = exactly what was asked: right company / organization AND the requested role,
      function or topic (e.g. "Machine Learning Engineer" for "ML engineers at Nvidia").
  2 = a closely adjacent individual-contributor role in the same function at the right
      company (e.g. "Software Engineer, PyTorch Core", "Deep Learning Architect",
      "AI Developer Technology Engineer" for a request about ML engineers).
  1 = partly: right company but a different function or seniority - managers, directors
      or executives when the request did not ask for leaders - or someone who may no
      longer be in the role, or a vague / generic entry.
  0 = wrong company or topic, not a specific {entity}, or not answering the request.
  If the request explicitly asks for leaders (e.g. "who leads", "heads of", "managers"),
  then fitting leaders are 3 and individual contributors are 1.

user_fit (0-2): how good a contact is this for THIS USER, given their profile?
  2 = a clear warm path or strong overlap: shared school or past employer, the same core
      skills or tech stack, the same events or communities, or the team they target.
  1 = some overlap (same broad field or industry, a loosely related stack).
  0 = no meaningful overlap with the profile.
{user_fit_rule}

Judge only from the information given. Do not reward having an email. Ignore which
results come first.

Request: {query}

User profile:
{profile}

Results:
{results}

Return an entry for every result index."""

NO_PROFILE_RULE = "  There is NO user profile for this request: set user_fit to null for every result."


def is_useful(judge: dict | None) -> bool:
    """A lead the user would act on: not fabricated, and either an exact or adjacent match
    for the request (request_match >= 2), or a partial match that is a strong warm path."""
    if not judge or judge.get("fabricated"):
        return False
    rm, uf = judge.get("request_match", 0), judge.get("user_fit")
    return rm >= 2 or (rm == 1 and uf == 2)


def lead_gain(judge: dict | None) -> float:
    """How valuable a lead is, for ordering: request match (0-3) plus user fit (0-2) when
    there's a profile. Fabricated or unjudged leads are worth 0."""
    if not judge or judge.get("fabricated"):
        return 0.0
    return float(judge.get("request_match", 0) + (judge.get("user_fit") or 0))


def ndcg(gains: list[float], k: int = 10) -> float | None:
    """Order quality: 1.0 when the most valuable leads come first, lower when strong leads are
    buried below weaker ones. Positions near the top count more (log2 discount).

    Uses the standard exponential form (2^gain - 1), so a lead worth 4 counts 5x a lead worth 2
    instead of 2x. With plain gains, swapping strong and weak leads barely moved the score."""
    import math

    def dcg(values: list[float]) -> float:
        return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(values[:k]))

    ideal = dcg(sorted(gains, reverse=True))
    return round(dcg(gains) / ideal, 3) if ideal > 0 else None


async def judge_leads(query: str, mode: str, profile: dict | None, leads: list[dict]) -> None:
    """Attach `judge` {fabricated, request_match, user_fit, reason} to each lead (mutates in place)."""
    from llm_provider import claude_code_invoke
    from resume_profile import format_resume_profile

    if not leads:
        return
    lines = []
    for i, lead in enumerate(leads):
        # The pipeline's own "relevance" text is left out on purpose so it can't sway the judge.
        lines.append(
            f"[{i}] name: {lead.get('name', '')} | title: {lead.get('title', '')} | "
            f"company: {lead.get('company', '')} | source: {lead.get('source_url', '')}"
        )
    entity = "person" if mode == "people" else "company"
    result = await claude_code_invoke(
        system=JUDGE_SYSTEM,
        user=JUDGE_PROMPT.format(
            entity=entity,
            query=query,
            profile=format_resume_profile(profile),
            results="\n".join(lines),
            user_fit_rule="" if profile else NO_PROFILE_RULE,
        ),
        schema=JudgeResponse,
    )
    by_index = {item.index: item for item in result.scores}
    for i, lead in enumerate(leads):
        item = by_index.get(i)
        if not item:
            lead["judge"] = None
            continue
        judge = {
            "fabricated": item.fabricated,
            "request_match": 0 if item.fabricated else item.request_match,
            "user_fit": None if not profile else (0 if item.fabricated else item.user_fit),
            "reason": item.reason,
        }
        judge["useful"] = is_useful(judge)
        lead["judge"] = judge


# ---------------------------------------------------------------------------
# Running queries
# ---------------------------------------------------------------------------

def load_profiles() -> dict:
    profiles = {}
    for path in (EVAL_DIR / "profiles").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        profiles[data["id"]] = data
    return profiles


def query_metrics(record: dict) -> dict:
    leads = record["leads"]
    n = len(leads)
    keys = [metrics.lead_key(lead.get("name", "")) for lead in leads]
    duplicates = n - len(set(keys))
    matches = [lead.get("grounding", {}).get("name_match") for lead in leads]
    checkable = [m for m in matches if m in ("exact", "partial", "missing")]
    judged = [lead["judge"] for lead in leads if lead.get("judge")]
    request_scores = [j["request_match"] for j in judged]
    fit_scores = [j["user_fit"] for j in judged if j.get("user_fit") is not None]
    source_types = [metrics.source_type(lead.get("source_url")) for lead in leads]
    emails = [lead.get("grounding", {}).get("email_on_page") for lead in leads]
    emails_given = [e for e in emails if e is not None]

    gold = record.get("gold") or []
    gold_recall = None
    if gold:
        found_keys = set(keys)
        gold_recall = sum(1 for g in gold if metrics.lead_key(g) in found_keys) / len(gold)

    return {
        "leads": n,
        "duplicates": duplicates,
        "checkable_leads": len(checkable),
        "grounded_exact": sum(1 for m in checkable if m == "exact"),
        "grounded_partial": sum(1 for m in checkable if m == "partial"),
        "source_fetched_by_pipeline": sum(
            1 for lead in leads if lead.get("grounding", {}).get("source_fetched_by_pipeline")
        ),
        "emails_given": len(emails_given),
        "emails_on_page": sum(1 for e in emails_given if e),
        "judged_leads": len(judged),
        "request_match_scores": request_scores,
        "user_fit_scores": fit_scores,
        "fabricated": sum(1 for j in judged if j.get("fabricated")),
        # Leads the user would act on (see is_useful). Unlike a mean, this doesn't punish an
        # answer for adding a few weak leads after several strong ones.
        "useful_leads": sum(1 for j in judged if is_useful(j)),
        # Useful AND the name was found on its source page: the honest headline number.
        "verified_useful_leads": sum(
            1 for lead in leads
            if is_useful(lead.get("judge"))
            and lead.get("grounding", {}).get("name_match") in ("exact", "partial")
        ),
        # Order quality of the list as returned (None when nothing was judged).
        "ndcg": ndcg([lead_gain(lead.get("judge")) for lead in leads]) if judged else None,
        "source_types": source_types,
        "gold_recall": gold_recall,
    }


async def run_query(item: dict, profiles: dict, pipeline_module, llm, judge: bool, use_profile: bool = True) -> dict:
    """Run one query. With use_profile=False the pipeline gets no résumé or profile, but the
    judge still scores against the query's test profile, so both variants answer the same
    question: how useful is this result to this user?"""
    profile_data = profiles.get(item.get("profile")) if item.get("profile") else None
    judge_profile = profile_data["resume_profile"] if profile_data else None
    resume_profile = judge_profile if use_profile else None
    resume_text = profile_data["resume_text"] if (profile_data and use_profile) else ""

    record = {
        "id": item["id"],
        "group": item.get("group"),
        "mode": item["mode"],
        "profile": item.get("profile"),
        "variant": "with_profile" if (profile_data and use_profile) else "no_profile",
        "query": item["query"],
        "gold": item.get("gold") or [],
        "error": None,
        "summary_text": "",
        "leads": [],
    }

    _captured_pages.clear()
    started = time.perf_counter()
    try:
        find = pipeline_module.find_leads if item["mode"] == "people" else pipeline_module.find_companies
        raw = await find(item["query"], llm, resume_text, resume_profile=resume_profile)
        data = json.loads(raw) if isinstance(raw, str) else raw
        record["leads"] = list(data.get("leads") or [])
        record["summary_text"] = data.get("summary") or data.get("suggestions") or ""
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"[:500]
    record["latency_s"] = round(time.perf_counter() - started, 1)
    record["pages"] = summarize_pipeline_pages(list(_captured_pages))

    if record["leads"]:
        await ground_leads(record["leads"], record["pages"]["urls"])
        if judge:
            try:
                await judge_leads(item["query"], item["mode"], judge_profile, record["leads"])
            except Exception as exc:
                record["judge_error"] = f"{type(exc).__name__}: {exc}"[:300]

    record["metrics"] = query_metrics(record)
    return record


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def summarize(records: list[dict]) -> dict:
    def block(recs: list[dict]) -> dict:
        ms = [r["metrics"] for r in recs]
        total_leads = sum(m["leads"] for m in ms)
        checkable = sum(m["checkable_leads"] for m in ms)
        exact = sum(m["grounded_exact"] for m in ms)
        partial = sum(m["grounded_partial"] for m in ms)
        request_scores = [s for m in ms for s in m["request_match_scores"]]
        fit_scores = [s for m in ms for s in m["user_fit_scores"]]
        judged = sum(m["judged_leads"] for m in ms)
        types = [t for m in ms for t in m["source_types"]]
        type_counts = {t: types.count(t) for t in sorted(set(types), key=lambda x: -types.count(x))}
        verifiable = sum(1 for t in types if t not in metrics.UNVERIFIABLE_SOURCE_TYPES and t != "none")
        latencies = sorted(r["latency_s"] for r in recs if not r["error"])
        pages = [r["pages"] for r in recs]
        fetched = sum(p["fetched"] for p in pages)
        recalls = [m["gold_recall"] for m in ms if m["gold_recall"] is not None]
        return {
            "queries": len(recs),
            "errors": sum(1 for r in recs if r["error"]),
            "zero_lead_queries": sum(1 for r in recs if not r["error"] and not r["leads"]),
            "leads_total": total_leads,
            "leads_per_query": round(total_leads / len(recs), 2) if recs else None,
            "grounded_rate": _rate(exact + partial, checkable),
            "grounded_exact_rate": _rate(exact, checkable),
            "unverifiable_leads": total_leads - checkable,
            "source_fetched_by_pipeline_rate": _rate(sum(m["source_fetched_by_pipeline"] for m in ms), total_leads),
            "duplicate_rate": _rate(sum(m["duplicates"] for m in ms), total_leads),
            "emails_given": sum(m["emails_given"] for m in ms),
            "emails_on_page_rate": _rate(sum(m["emails_on_page"] for m in ms), sum(m["emails_given"] for m in ms)),
            "verifiable_source_rate": _rate(verifiable, total_leads),
            "source_types": type_counts,
            "request_match_mean": round(float(statistics.mean(request_scores)), 3) if request_scores else None,
            "user_fit_mean": round(float(statistics.mean(fit_scores)), 3) if fit_scores else None,
            "fabricated_leads": sum(m["fabricated"] for m in ms),
            "useful_rate": _rate(sum(m["useful_leads"] for m in ms), judged),
            "useful_leads_per_query": round(sum(m["useful_leads"] for m in ms) / len(recs), 2) if recs else None,
            "verified_useful_per_query": (round(sum(m.get("verified_useful_leads", 0) for m in ms) / len(recs), 2)
                                          if recs else None),
            "order_quality_mean": (round(statistics.mean(nd), 3)
                                   if (nd := [m["ndcg"] for m in ms if m.get("ndcg") is not None]) else None),
            "fully_blocked_queries": sum(1 for p in pages if p["fetched"] and p["ok"] == 0),
            "latency_mean_s": round(statistics.mean(latencies), 1) if latencies else None,
            "latency_max_s": latencies[-1] if latencies else None,
            "pipeline_pages_fetched": fetched,
            "pipeline_pages_blocked_rate": _rate(sum(p["blocked"] for p in pages), fetched),
            "pipeline_pages_failed_rate": _rate(sum(p["failed"] for p in pages), fetched),
            "gold_recall_mean": round(statistics.mean(recalls), 3) if recalls else None,
        }

    groups = sorted({r["group"] for r in records if r.get("group")})
    variants = sorted({r.get("variant") for r in records if r.get("variant")})
    return {
        "overall": block(records),
        "by_group": {g: block([r for r in records if r.get("group") == g]) for g in groups},
        "by_variant": {v: block([r for r in records if r.get("variant") == v]) for v in variants},
        "personalization": personalization(records),
    }


def _mean_fit(record: dict) -> float | None:
    scores = record["metrics"]["user_fit_scores"]
    return statistics.mean(scores) if scores else None


def personalization(records: list[dict]) -> dict | None:
    """Pair each query's with-profile and no-profile runs and compare user fit and useful leads.

    Both variants are judged against the same test profile, so the difference is what the
    profile contributed. Pairs where either run was blocked, or had no judged leads, are skipped.
    """
    pairs = {}
    for r in records:
        key = (r["id"], r.get("run", 1))
        pairs.setdefault(key, {})[r.get("variant")] = r

    def blocked(rec: dict) -> bool:
        return rec["pages"]["fetched"] > 0 and rec["pages"]["ok"] == 0

    deltas, useful_deltas, per_query, skipped_blocked = [], [], [], 0
    for (qid, run), variants in sorted(pairs.items()):
        with_p, without_p = variants.get("with_profile"), variants.get("no_profile")
        if not with_p or not without_p:
            continue
        if blocked(with_p) or blocked(without_p):
            skipped_blocked += 1  # a blocked run measures the search engine, not the profile
            continue
        a, b = _mean_fit(with_p), _mean_fit(without_p)
        if a is None or b is None:
            continue
        ua, ub = with_p["metrics"]["useful_leads"], without_p["metrics"]["useful_leads"]
        deltas.append(a - b)
        useful_deltas.append(ua - ub)
        per_query.append({"id": qid, "run": run, "fit_with": round(a, 3),
                          "fit_without": round(b, 3), "fit_delta": round(a - b, 3),
                          "useful_with": ua, "useful_without": ub})
    if not deltas:
        return {"pairs": 0, "skipped_blocked": skipped_blocked} if skipped_blocked else None
    return {
        "pairs": len(deltas),
        "skipped_blocked": skipped_blocked,
        "user_fit_delta_mean": round(statistics.mean(deltas), 3),
        "useful_leads_delta_mean": round(statistics.mean(useful_deltas), 3),
        "profile_better": sum(1 for d in useful_deltas if d > 0),
        "profile_worse": sum(1 for d in useful_deltas if d < 0),
        "no_difference": sum(1 for d in useful_deltas if d == 0),
        "per_query": per_query,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

SUMMARY_ROWS = [
    ("queries", "Queries run"),
    ("errors", "Errors"),
    ("zero_lead_queries", "Queries with 0 leads"),
    ("leads_per_query", "Leads per query"),
    ("grounded_rate", "Grounded (name on source page)"),
    ("grounded_exact_rate", "  of which exact match"),
    ("unverifiable_leads", "Leads with unreadable source"),
    ("source_fetched_by_pipeline_rate", "Source was actually fetched"),
    ("verifiable_source_rate", "Source is checkable (not LinkedIn/broker/social)"),
    ("duplicate_rate", "Duplicate leads"),
    ("emails_given", "Emails returned"),
    ("emails_on_page_rate", "  emails found on source page"),
    ("request_match_mean", "Request match mean (0-3)"),
    ("user_fit_mean", "User fit mean (0-2)"),
    ("fabricated_leads", "Fabricated / joke leads"),
    ("useful_rate", "Useful share of judged leads"),
    ("useful_leads_per_query", "Useful leads per query"),
    ("verified_useful_per_query", "VERIFIED useful leads per query"),
    ("order_quality_mean", "Order quality (nDCG, 1 = best first)"),
    ("fully_blocked_queries", "Queries where every page was blocked"),
    ("latency_mean_s", "Latency mean (s)"),
    ("latency_max_s", "Latency max (s)"),
    ("pipeline_pages_blocked_rate", "Pipeline pages blocked"),
    ("pipeline_pages_failed_rate", "Pipeline pages failed"),
    ("gold_recall_mean", "Gold recall"),
]


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def print_summary(summary: dict) -> None:
    overall = summary["overall"]
    width = max(len(label) for _, label in SUMMARY_ROWS) + 2
    print("\n" + "=" * (width + 12))
    for key, label in SUMMARY_ROWS:
        print(f"{label:<{width}}{_fmt(overall.get(key)):>10}")
    def line(name: str, stats: dict) -> str:
        return (f"[{name}] leads/query {_fmt(stats['leads_per_query'])}, useful/query "
                f"{_fmt(stats['useful_leads_per_query'])}, verified useful/query "
                f"{_fmt(stats.get('verified_useful_per_query'))}, grounded {_fmt(stats['grounded_rate'])}, "
                f"match {_fmt(stats['request_match_mean'])}, fit {_fmt(stats['user_fit_mean'])}, "
                f"latency {_fmt(stats['latency_mean_s'])}s")

    if overall.get("source_types"):
        parts = ", ".join(f"{t} {c}" for t, c in overall["source_types"].items())
        print(f"{'Lead sources':<{width}}{parts}")
    print()
    for group, stats in summary["by_group"].items():
        print(line(group, stats))
    if len(summary.get("by_variant") or {}) > 1:
        print()
        for variant, stats in summary["by_variant"].items():
            print(line(variant, stats))

    p = summary.get("personalization")
    if p and p["pairs"]:
        print(f"\nPersonalization ({p['pairs']} paired queries, both judged against the same test profile; "
              f"{p['skipped_blocked']} pairs skipped because a run was blocked):")
        print(f"  user fit mean, with minus without:  {p['user_fit_delta_mean']:+.2f}")
        print(f"  useful leads, with minus without:   {p['useful_leads_delta_mean']:+.2f}")
        print(f"  profile better {p['profile_better']}, worse {p['profile_worse']}, "
              f"same {p['no_difference']} (by useful leads)")
        for q in p["per_query"]:
            print(f"    {q['id']}: user fit {q['fit_with']:.2f} vs {q['fit_without']:.2f} ({q['fit_delta']:+.2f}), "
                  f"useful leads {q['useful_with']} vs {q['useful_without']}")
    elif p:
        print(f"\nPersonalization: no usable pairs ({p['skipped_blocked']} skipped because a run was blocked)")
    print("=" * (width + 12))


def compare(path_a: Path, path_b: Path) -> None:
    a = json.loads(path_a.read_text(encoding="utf-8"))
    b = json.loads(path_b.read_text(encoding="utf-8"))
    sa, sb = a["summary"]["overall"], b["summary"]["overall"]
    width = max(len(label) for _, label in SUMMARY_ROWS) + 2
    print(f"A: {path_a.name}  ({a['meta'].get('label') or '-'}, {a['meta'].get('git')})")
    print(f"B: {path_b.name}  ({b['meta'].get('label') or '-'}, {b['meta'].get('git')})\n")
    print(f"{'Metric':<{width}}{'A':>10}{'B':>10}{'B - A':>10}")
    for key, label in SUMMARY_ROWS:
        va, vb = sa.get(key), sb.get(key)
        delta = "-"
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            diff = vb - va
            delta = f"{diff:+.3f}" if isinstance(diff, float) else f"{diff:+d}"
        print(f"{label:<{width}}{_fmt(va):>10}{_fmt(vb):>10}{delta:>10}")

    pa, pb = a["summary"].get("personalization"), b["summary"].get("personalization")
    if pa or pb:
        for key, label in (("user_fit_delta_mean", "Personalization: user fit gain"),
                           ("useful_leads_delta_mean", "Personalization: useful leads gain")):
            va, vb = (pa or {}).get(key), (pb or {}).get(key)
            delta = f"{vb - va:+.3f}" if (va is not None and vb is not None) else "-"
            print(f"{label:<{width}}{_fmt(va):>10}{_fmt(vb):>10}{delta:>10}")


async def rejudge(path: Path, call_judge: bool = True) -> None:
    """Re-score the leads of a saved run with the current judge and metrics.

    Useful after changing the rubric or metrics: the pipeline isn't re-run, so no search
    requests are sent and the leads stay exactly the same, only the scoring changes.
    With call_judge=False (--no-judge) the saved judge scores are kept and only the metrics
    are recomputed, so no LLM calls are made at all.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    profiles = load_profiles()
    records = data["queries"]
    judged_queries = [r for r in records if r.get("leads")] if call_judge else []
    for i, record in enumerate(judged_queries, 1):
        profile_data = profiles.get(record.get("profile")) if record.get("profile") else None
        judge_profile = profile_data["resume_profile"] if profile_data else None
        print(f"[{i}/{len(judged_queries)}] judging {record['id']} [{record.get('variant', '-')}] "
              f"({len(record['leads'])} leads)", flush=True)
        record.pop("judge_error", None)
        try:
            await judge_leads(record["query"], record["mode"], judge_profile, record["leads"])
        except Exception as exc:
            record["judge_error"] = f"{type(exc).__name__}: {exc}"[:300]
            print(f"    judge failed: {record['judge_error']}", flush=True)
    for record in records:
        record["metrics"] = query_metrics(record)

    summary = summarize(records)
    data["summary"] = summary
    data["meta"]["rejudged_from"] = path.name
    data["meta"]["rejudged_at"] = datetime.now(timezone.utc).isoformat()
    data["meta"]["rejudged_git"] = git_version()
    data["meta"]["rejudge_called_judge"] = call_judge
    # Recomputing a "-rejudged" file updates it in place instead of stacking suffixes.
    stem = path.stem if path.stem.endswith("-rejudged") else f"{path.stem}-rejudged"
    out_path = path.with_name(f"{stem}.json")
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print_summary(summary)
    print("\nNote: block counts come from the original run and aren't recomputed.")
    print(f"\nSaved {out_path}")


def git_version() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BACKEND_DIR,
                             capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=BACKEND_DIR,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return f"{sha}{'+dirty' if dirty else ''}" or "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reacher search-quality eval")
    parser.add_argument("--quick", action="store_true", help="only queries marked quick")
    parser.add_argument("--ids", help="comma-separated query ids, e.g. p01,c01")
    parser.add_argument("--group", choices=["people", "companies", "alumni"])
    parser.add_argument("--repeat", type=int, default=1, help="run each query N times")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM relevance judge")
    parser.add_argument(
        "--profiles", choices=["as-set", "none", "both"], default="as-set",
        help="as-set: use each query's profile (default); none: run every query without a profile; "
             "both: run profiled queries with AND without it and report the personalization gain",
    )
    parser.add_argument("--delay", type=float, default=5.0,
                        help="seconds to pause between queries, to keep search traffic polite (default 5)")
    parser.add_argument("--stop-after-blocked", type=int, default=3,
                        help="stop the run after this many queries in a row where every search page was "
                             "blocked; 0 = never stop (default 3)")
    parser.add_argument("--label", default="", help="name for this run, e.g. baseline")
    parser.add_argument("--compare", nargs=2, metavar=("A", "B"), help="compare two result files and exit")
    parser.add_argument("--rejudge", metavar="FILE",
                        help="re-score a saved run with the current judge and metrics (no pipeline, "
                             "no search requests); saves <file>-rejudged.json")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.compare:
        compare(Path(args.compare[0]), Path(args.compare[1]))
        return
    if args.rejudge:
        await rejudge(Path(args.rejudge), call_judge=not args.no_judge)
        return

    queries = json.loads((EVAL_DIR / "queries.json").read_text(encoding="utf-8"))["queries"]
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",")}
        queries = [q for q in queries if q["id"] in wanted]
    if args.quick:
        queries = [q for q in queries if q.get("quick")]
    if args.group:
        queries = [q for q in queries if q.get("group") == args.group]
    if not queries:
        print("No queries selected.")
        return

    # Imported here so --compare works without loading the browser stack
    import pipeline
    from llm_provider import get_agent_llm

    instrument_pipeline(pipeline)
    llm = get_agent_llm()
    profiles = load_profiles()

    # Each job is (query, use_profile). "both" adds a no-profile twin for every profiled query.
    jobs = []
    for item in queries:
        if args.profiles == "none":
            jobs.append((item, False))
        elif args.profiles == "both" and item.get("profile"):
            jobs.extend([(item, True), (item, False)])
        else:
            jobs.append((item, True))

    started_at = datetime.now(timezone.utc)
    records = []
    total = len(jobs) * args.repeat
    n = 0
    blocked_streak = 0
    stopped_reason = None
    for run in range(1, args.repeat + 1):
        if stopped_reason:
            break
        for item, use_profile in jobs:  # sequential on purpose: the pipeline shares one browser
            if n and args.delay > 0:
                await asyncio.sleep(args.delay)
            n += 1
            tag = "" if args.profiles == "as-set" else (" [with profile]" if use_profile and item.get("profile") else " [no profile]")
            print(f"[{n}/{total}] {item['id']} ({item['mode']}){tag}: {item['query']}", flush=True)
            record = await run_query(item, profiles, pipeline, llm, judge=not args.no_judge, use_profile=use_profile)
            record["run"] = run
            records.append(record)
            m = record["metrics"]
            status = f"ERROR {record['error']}" if record["error"] else (
                f"{m['leads']} leads, grounded {m['grounded_exact'] + m['grounded_partial']}/{m['checkable_leads']}, "
                f"{record['latency_s']}s"
            )
            print(f"    -> {status}", flush=True)

            # A query is "fully blocked" when it fetched pages and none of them had real content.
            # Several in a row means the search engine is rate-limiting us: more queries would
            # only measure the block and waste LLM calls, so stop and say so.
            pages = record["pages"]
            fully_blocked = pages["fetched"] > 0 and pages["ok"] == 0
            blocked_streak = blocked_streak + 1 if fully_blocked else 0
            if args.stop_after_blocked and blocked_streak >= args.stop_after_blocked:
                stopped_reason = (f"stopped after {blocked_streak} fully blocked queries in a row; "
                                  "the search engine is rate-limiting. Wait a while and re-run.")
                print(f"\n!! {stopped_reason}", flush=True)
                break

    try:
        await pipeline.browser.close()  # avoids "Event loop is closed" noise at exit
    except Exception:
        pass

    summary = summarize(records)
    output = {
        "meta": {
            "label": args.label,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "git": git_version(),
            "args": vars(args),
            "stopped_early": stopped_reason,
            "queries_planned": total,
        },
        "summary": summary,
        "queries": records,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started_at.strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}{'-' + args.label if args.label else ''}.json"
    out_path = RESULTS_DIR / name
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print_summary(summary)
    if stopped_reason:
        print(f"\nNOTE: {stopped_reason} ({len(records)} of {total} queries ran)")
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
