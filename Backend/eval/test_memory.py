"""Tests for memory.merge_facts(). No Mongo, no LLM."""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from memory import GUESS, GUESS_MAX, MAX_FACTS, SAID, MemoryOp, merge_facts


def fact(fid, said=False, conf=None, pinned=False, source="chat", age_days=0):
    t = datetime.now(timezone.utc) - timedelta(days=age_days)
    return {
        "id": fid, "kind": "preference", "text": f"fact {fid}", "said": said,
        "confidence": conf if conf is not None else (SAID if said else GUESS),
        "source": source, "pinned": pinned, "created_at": t, "updated_at": t,
    }


def test_add_said_and_guess():
    out = merge_facts([], [
        MemoryOp(op="add", kind="exclusion", text="Exclude Meta", said=True),
        MemoryOp(op="add", kind="preference", text="Likes startups"),
    ])
    conf = {f["text"]: f["confidence"] for f in out}
    assert conf == {"Exclude Meta": SAID, "Likes startups": GUESS}


def test_add_needs_text_and_kind():
    assert merge_facts([], [MemoryOp(op="add", text="no kind")]) == []


def test_reinforce_guess_caps():
    facts = [fact("a")]
    for _ in range(5):
        facts = merge_facts(facts, [MemoryOp(op="reinforce", fact_id="a")])
    assert facts[0]["confidence"] == GUESS_MAX
    assert facts[0]["said"] is False


def test_reinforce_said_upgrades_guess():
    out = merge_facts([fact("a")], [MemoryOp(op="reinforce", fact_id="a", said=True)])
    assert out[0]["said"] is True and out[0]["confidence"] == SAID


def test_guess_cannot_drop_said_fact():
    out = merge_facts([fact("a", said=True)], [MemoryOp(op="drop", fact_id="a")])
    assert len(out) == 1


def test_said_can_drop_said_fact():
    out = merge_facts([fact("a", said=True)], [MemoryOp(op="drop", fact_id="a", said=True)])
    assert out == []


def test_chat_cannot_touch_pinned_or_user_facts():
    facts = [fact("p", pinned=True), fact("u", source="user")]
    ops = [
        MemoryOp(op="drop", fact_id="p", said=True),
        MemoryOp(op="replace", fact_id="u", kind="goal", text="changed", said=True),
    ]
    out = merge_facts(facts, ops)
    assert {f["id"]: f["text"] for f in out} == {"p": "fact p", "u": "fact u"}


def test_replace_keeps_id():
    out = merge_facts([fact("a")], [MemoryOp(op="replace", fact_id="a", text="Seattle", said=True)])
    assert out[0]["id"] == "a" and out[0]["text"] == "Seattle" and out[0]["confidence"] == SAID


def test_made_up_id_ignored():
    facts = [fact("a")]
    out = merge_facts(facts, [MemoryOp(op="drop", fact_id="zzz", said=True)])
    assert [f["id"] for f in out] == ["a"]


def test_input_not_mutated():
    facts = [fact("a")]
    merge_facts(facts, [MemoryOp(op="reinforce", fact_id="a")])
    assert facts[0]["confidence"] == GUESS


def test_text_is_cut():
    out = merge_facts([], [MemoryOp(op="add", kind="goal", text="x" * 500, said=True)])
    assert len(out[0]["text"]) == 120


def test_cap_drops_weakest_guess():
    facts = [fact(f"s{i}", said=True) for i in range(MAX_FACTS - 1)]
    facts += [fact("old", age_days=30), fact("new")]
    out = merge_facts(facts, [])
    ids = {f["id"] for f in out}
    assert len(out) == MAX_FACTS and "old" not in ids and "new" in ids


# --- apply_exclusions -------------------------------------------------------

from memory import apply_exclusions, exclusion_target


def excl(text, said=True, conf=0.9):
    return {"id": "x", "kind": "exclusion", "text": text, "said": said, "confidence": conf}


COMPANIES = [
    {"name": "Google", "title": "Search and AI", "company": "Mountain View, CA"},
    {"name": "Meta", "title": "Social media", "company": "Menlo Park, CA"},
    {"name": "Microsoft", "title": "Competes with Meta in AI", "company": "Redmond, WA"},
    {"name": "Metabase", "title": "BI tool", "company": "SF"},
]
PEOPLE = [
    {"name": "Jane Doe", "title": "ML Engineer", "company": "Meta Platforms"},
    {"name": "Sam Lee", "title": "ML Engineer", "company": "Facebook"},
    {"name": "Ana Ruiz", "title": "ML Engineer", "company": "NVIDIA"},
]


def test_exclusion_target_wording():
    for text in ["Exclude Meta", "Exclude people from Meta", "Don't show me people from Meta",
                 "Meta is not preferred", "No Meta employees"]:
        assert exclusion_target(text) == "meta", text


def test_excludes_company_card_only_by_name():
    names = [c["name"] for c in apply_exclusions(COMPANIES, [excl("Exclude Meta")])]
    assert names == ["Google", "Microsoft", "Metabase"]   # description mention and Metabase stay


def test_excludes_people_by_company_and_alias():
    names = [p["name"] for p in apply_exclusions(PEOPLE, [excl("Exclude people from Meta")])]
    assert names == ["Ana Ruiz"]


def test_guess_or_low_confidence_never_hides():
    assert len(apply_exclusions(COMPANIES, [excl("Exclude Meta", said=False, conf=0.85)])) == 4
    assert len(apply_exclusions(COMPANIES, [excl("Exclude Meta", conf=0.5)])) == 4


def test_no_facts_keeps_all():
    assert apply_exclusions(PEOPLE, []) == PEOPLE
