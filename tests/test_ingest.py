from ingest import codeforces, atcoder


def test_fetch_ratings_returns_list():
    assert isinstance(codeforces.fetch_ratings(), list)


def test_fetch_atcoder_returns_list():
    assert isinstance(atcoder.fetch_ratings(limit=10), list) 