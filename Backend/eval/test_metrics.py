"""Unit tests for eval/metrics.py. Run from Backend: python -m pytest eval -q"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import metrics  # noqa: E402


def test_normalize_strips_accents_and_punctuation():
    assert metrics.normalize("José  O'Neil-Smith") == "jose o neil smith"


def test_match_name_exact():
    assert metrics.match_name("Anjulie Agrusa", "Speakers: Anjulie Agrusa, NVIDIA") == "exact"


def test_match_name_partial_when_reordered_or_middle_name():
    assert metrics.match_name("John Smith", "Smith, John - Staff Engineer") == "partial"
    assert metrics.match_name("John Smith", "John Q. Smith leads the team") == "partial"


def test_match_name_ignores_initials_in_lead_name():
    assert metrics.match_name("John Q. Smith", "Our lead, John Smith, said") == "partial"


def test_match_name_missing_and_no_substring_false_positive():
    assert metrics.match_name("Ann Lee", "Annette Leeson works here") == "missing"
    assert metrics.match_name("Ann Lee", "") == "missing"


def test_email_on_page():
    assert metrics.email_on_page("a.b@nvidia.com", "Contact: A.B@NVIDIA.com") is True
    assert metrics.email_on_page("guess@nvidia.com", "no emails here") is False
    assert metrics.email_on_page(None, "anything") is None


def test_detect_block():
    assert metrics.detect_block(429, "x" * 1000) == "http_429"
    assert metrics.detect_block(200, "Please complete the CAPTCHA" + "x" * 500).startswith("marker:")
    assert metrics.detect_block(200, "short") == "too_little_text"
    assert metrics.detect_block(200, "Real article text " * 50) is None
    ddg_challenge = "Unfortunately, bots use DuckDuckGo too. Please complete the following challenge" + " x" * 200
    assert metrics.detect_block(200, ddg_challenge).startswith("marker:")


def test_source_type_examples_from_first_run():
    st = metrics.source_type
    assert st("https://www.linkedin.com/in/luna-kong-71657351") == "linkedin"
    assert st("https://in.linkedin.com/in/jashojit") == "linkedin"
    assert st("https://rocketreach.co/nick-gupta-email_19480498") == "data_broker"
    assert st("https://www.zoominfo.com/p/Gene-Liu/11640137907") == "data_broker"
    assert st("https://pytorch2024.sched.com/directory/speakers") == "conference"
    assert st("https://developer.nvidia.com/blog/author/pstjohn/") == "blog"
    assert st("https://blogs.nvidia.com/blog/nvidia-life-sidney-knowles/") == "blog"
    assert st("https://github.com/vllm-project/vllm") == "code"
    assert st("https://arxiv.org/abs/2309.06180") == "paper"
    assert st("https://www.ycombinator.com/companies/foo") == "directory"
    assert st("https://ece.umd.edu/news/story/nvidia-names-umd") == "news"
    assert st("https://example.com/about/team") == "team_page"
    assert st("https://example.com/products") == "other"
    assert st("") == "none"


def test_lead_key_dedupes_initials_and_case():
    assert metrics.lead_key("John Q. Smith") == metrics.lead_key("john smith")
