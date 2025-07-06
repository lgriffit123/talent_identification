from ingest import codeforces, atcoder, kaggle
import time


def test_fetch_ratings_returns_list():
    assert isinstance(codeforces.fetch_ratings(), list)


def test_fetch_atcoder_returns_list():
    assert isinstance(atcoder.fetch_ratings(limit=10), list)


def test_codeforces_caching():
    first = codeforces.fetch_ratings(limit=5)
    # Immediately fetch again – should hit cache and be identical
    second = codeforces.fetch_ratings(limit=5)
    assert first == second 


def test_fetch_kaggle_returns_list():
    assert isinstance(kaggle.fetch_leaderboard(limit=10), list) 