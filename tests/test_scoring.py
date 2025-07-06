from etl import scoring


def test_interestingness_score_returns_float_and_reason():
    profile = {"name": "Test", "rating": 1200, "source": "codeforces", "norm": 0.3}
    score, reason = scoring.interestingness_score(profile)
    assert isinstance(score, float)
    assert isinstance(reason, str) 