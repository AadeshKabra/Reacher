"""Pure helpers for the eval: name matching, email-on-page checks, block detection.

Kept free of I/O and LLM calls so they're easy to unit-test. They're also a reference
for Phase 2's verify.py, which needs the same kind of matching inside the pipeline.
"""

from __future__ import annotations

import re
import unicodedata

# Markers that a fetched page is a bot-check or block page rather than real content.
BLOCK_MARKERS = (
    "captcha",
    "unusual traffic",
    "are you a robot",
    "verify you are human",
    "verifying you are human",
    "access denied",
    "request blocked",
    "enable javascript and cookies to continue",
    "cf-chl",
    "attention required! | cloudflare",
    # DuckDuckGo's HTML endpoint answers with a 200 "anomaly" challenge page when it rate-limits
    "bots use duckduckgo too",
    "anomaly-modal",
    "complete the following challenge",
    "select all squares containing",
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def normalize(text: str) -> str:
    """Lowercase, strip accents, turn punctuation into spaces, collapse whitespace."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    no_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = re.sub(r"[^a-z0-9]+", " ", no_accents.lower())
    return " ".join(cleaned.split())


def name_tokens(name: str) -> list[str]:
    """Name words without single-letter initials ("John Q. Smith" -> ["john", "smith"])."""
    return [tok for tok in normalize(name).split() if len(tok) > 1]


def match_name(name: str, page_text: str) -> str:
    """How well `name` is supported by `page_text`.

    "exact"   - the full normalized name appears as a phrase
    "partial" - first and last name both appear as whole words, but not together
                (e.g. "Smith, John" or a middle name in between)
    "missing" - neither
    """
    norm_name = normalize(name)
    norm_text = normalize(page_text)
    if not norm_name or not norm_text:
        return "missing"

    padded_text = f" {norm_text} "
    if f" {norm_name} " in padded_text:
        return "exact"

    tokens = name_tokens(name)
    if len(tokens) >= 2:
        first, last = tokens[0], tokens[-1]
        if f" {first} " in padded_text and f" {last} " in padded_text:
            return "partial"
    return "missing"


def email_on_page(email: str | None, page_text: str) -> bool | None:
    """True if the email appears literally on the page, None if there's no email to check."""
    if not email:
        return None
    found = {match.lower() for match in EMAIL_RE.findall(page_text or "")}
    return email.strip().lower() in found


def detect_block(status_code: int | None, text: str) -> str | None:
    """A short reason if the response looks like a block or bot check, else None."""
    if status_code in (401, 403, 429, 503):
        return f"http_{status_code}"
    lowered = (text or "")[:5000].lower()
    for marker in BLOCK_MARKERS:
        if marker in lowered:
            return f"marker:{marker}"
    if len((text or "").strip()) < 200:
        return "too_little_text"
    return None


# ---------------------------------------------------------------------------
# Source types: where a lead's evidence comes from
# ---------------------------------------------------------------------------

# Sources we can't fetch or check automatically (login walls, bot protection), so leads
# citing them can't be verified. Everything else counts as "verifiable".
UNVERIFIABLE_SOURCE_TYPES = {"linkedin", "data_broker", "social"}

_DATA_BROKERS = (
    "rocketreach.co", "zoominfo.com", "apollo.io", "contactout.com", "signalhire.com",
    "lusha.com", "leadiq.com", "clearbit.com", "seamless.ai", "hunter.io", "theorg.com",
    "peopledatalabs.com", "salesintel.io", "adapt.io", "datanyze.com",
)
_SOCIAL = ("twitter.com", "x.com", "facebook.com", "instagram.com", "threads.net", "tiktok.com")
_CONFERENCE = ("sched.com", "sessionize.com", "eventbrite.com", "lu.ma", "meetup.com")
_PAPERS = ("arxiv.org", "openreview.net", "dl.acm.org", "ieeexplore.ieee.org", "scholar.google.",
           "semanticscholar.org", "aclanthology.org", "proceedings.")
_BLOG_HOSTS = ("medium.com", "substack.com", "dev.to", "hashnode.", "wordpress.com", "blogspot.")
_DIRECTORIES = ("crunchbase.com", "builtin.com", "builtin", "wellfound.com", "ycombinator.com",
                "angel.co", "glassdoor.com", "indeed.com", "pitchbook.com", "tracxn.com")
_NEWS = ("techcrunch.com", "venturebeat.com", "theverge.com", "wired.com", "forbes.com",
         "businessinsider.com", "reuters.com", "bloomberg.com", "prnewswire.com", "businesswire.com")


def source_type(url: str | None) -> str:
    """Rough category of a source URL, from its host and path."""
    from urllib.parse import urlparse

    if not url or not url.startswith("http"):
        return "none"
    parsed = urlparse(url.lower())
    host = parsed.netloc.split("@")[-1].split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    path = parsed.path

    def host_is(domains) -> bool:
        return any(host == d or host.endswith("." + d) or (d.endswith(".") and d in host) or
                   (not d.endswith(".") and "." not in d and d in host) for d in domains)

    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        return "linkedin"
    if host_is(_DATA_BROKERS):
        return "data_broker"
    if host_is(_SOCIAL):
        return "social"
    if host == "github.com" or host.endswith(".github.io") or host == "gitlab.com":
        return "code"
    if host_is(_PAPERS) or path.endswith(".pdf") and ("paper" in path or "proceedings" in path):
        return "paper"
    if host_is(_CONFERENCE) or any(k in path for k in ("/speaker", "/speakers", "/schedule", "/agenda")):
        return "conference"
    if host_is(_DIRECTORIES):
        return "directory"
    if host_is(_NEWS) or host.startswith("news.") or "/news/" in path or "/press" in path:
        return "news"
    if host_is(_BLOG_HOSTS) or host.startswith("blog.") or host.startswith("blogs.") or "/blog" in path:
        return "blog"
    if any(k in path for k in ("/team", "/people", "/leadership", "/about", "/staff", "/faculty",
                               "/author", "/authors", "/directory")):
        return "team_page"
    return "other"


def lead_key(name: str) -> str:
    """Key for spotting duplicate leads within one answer."""
    tokens = name_tokens(name)
    return " ".join(tokens) if tokens else normalize(name)
