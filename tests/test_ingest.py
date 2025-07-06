from ingest import codeforces, kaggle, leetcode
import time


def test_fetch_ratings_returns_list():
    assert isinstance(codeforces.fetch_ratings(), list)


def test_fetch_kaggle_returns_list():
    assert isinstance(kaggle.fetch_leaderboard(limit=10), list)


def test_fetch_leetcode_returns_list():
    # Without cookies this will return an empty list but still be a list.
    assert isinstance(leetcode.fetch_contest_ranking(limit=0), list) 