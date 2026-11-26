"""Unit tests for the judge-based scoring rules in run_eval.py (no LLM calls).

Run from Backend:
    python -c "import sys; sys.path.insert(0,'eval'); import test_scoring as t; n=[x for x in dir(t) if x.startswith('test_')]; [getattr(t,x)() for x in n]; print('passed', len(n), 'tests')"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_eval import is_useful, lead_gain, ndcg  # noqa: E402


def j(rm, fit=None, fabricated=False):
    return {"request_match": rm, "user_fit": fit, "fabricated": fabricated}


def test_useful_rules_match_the_agreed_examples():
    assert is_useful(j(3, 1))            # Peter St. John: ML Engineer
    assert is_useful(j(2, 1))            # Jashojit Mukherjee: adjacent role, still useful
    assert is_useful(j(2, 2))            # Syed Ahmed: adjacent role + PyTorch warm path
    assert not is_useful(j(1, 1))        # Chester Chen: senior manager, not asked for
    assert is_useful(j(1, 2))            # partial match but a strong warm path
    assert not is_useful(j(0, 0, True))  # Erlich Bachman: fabricated
    assert not is_useful(None)


def test_gain_ignores_fit_without_profile_and_zeroes_fabricated():
    assert lead_gain(j(3, None)) == 3
    assert lead_gain(j(2, 2)) == 4
    assert lead_gain(j(3, 2, True)) == 0


def test_ndcg_prefers_exact_matches_first():
    best_first = [lead_gain(j(3, 1)), lead_gain(j(2, 1)), lead_gain(j(1, 1))]
    assert ndcg(best_first) == 1.0
    # an adjacent-role lead listed above an exact ML Engineer lowers order quality
    swapped = [lead_gain(j(2, 1)), lead_gain(j(3, 1)), lead_gain(j(1, 1))]
    assert ndcg(swapped) < 1.0
    assert ndcg([0, 0]) is None


def test_ndcg_penalizes_burying_a_strong_lead():
    # p01 with profile, as returned: Chester Chen (2) sits above Syed Ahmed (4)
    p01 = [4, 4, 3, 4, 4, 2, 4, 3, 2]
    # nDCG stays high when most leads are strong, so small drops matter (0.971 here)
    assert ndcg(p01) < 0.98
    assert ndcg(sorted(p01, reverse=True)) == 1.0
