from ingest import codeforces, kaggle


def test_fetch_ratings_returns_list():
    assert isinstance(codeforces.fetch_ratings(), list)


def test_fetch_leaderboard_returns_list():
    assert isinstance(kaggle.fetch_leaderboard(), list) 