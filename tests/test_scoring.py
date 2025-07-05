from etl import scoring


def test_interestingness_score_returns_float():
    profile = {"name": "Test", "rating": 1000}
    score = scoring.interestingness_score(profile)
    assert isinstance(score, float) 