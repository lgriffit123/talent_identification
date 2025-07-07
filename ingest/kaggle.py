"""Module for deriving Kaggle user skill rankings via the Meta-Kaggle dataset.

This implementation downloads the public Meta-Kaggle dataset (refreshed daily)
using the Kaggle API and computes a simple composite score based on:

• Competition medals (Gold=3, Silver=2, Bronze=1)
• Notebook votes
• Dataset votes
• Discussion posts

The function returns a list of user dictionaries compatible with the rest of
pipeline.
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import pandas as pd

from . import cache

logger = logging.getLogger(__name__)

DATASET_SLUG = "kaggle/meta-kaggle"
DATA_DIR = Path("meta")  # downloaded CSVs stored here

# Only these CSVs are needed to compute the skill score. Downloading them
# individually is ~10× faster than pulling the full 50-file archive.
NEEDED_FILES = [
    "Users.csv",
    "Kernels.csv",
    "KernelVotes.csv",
    "Datasets.csv",
    "DatasetVotes.csv",
    "ForumMessages.csv",
]

MEDAL_WEIGHTS = {"Gold": 3, "Silver": 2, "Bronze": 1}


def _prepare_kaggle_credentials() -> bool:
    """Ensure Kaggle API credentials are present."""
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
    cfg = Path.home() / ".kaggle" / "kaggle.json"
    if cfg.exists():
        try:
            creds = json.loads(cfg.read_text())
            os.environ.setdefault("KAGGLE_USERNAME", creds.get("username", ""))
            os.environ.setdefault("KAGGLE_KEY", creds.get("key", ""))
            return True

        except Exception:
            pass
    logger.warning("Kaggle credentials not found; skipping Kaggle rankings")
    return False


def _download_meta_dataset() -> bool:
    """Download and unzip the Meta-Kaggle dataset if not already present today."""
    from datetime import date
    from pathlib import Path as _P
    from zipfile import ZipFile
    from kaggle import KaggleApi

    stamp_file = DATA_DIR / ".fetched_at"
    today = date.today().isoformat()

    # Skip download if we already fetched today and all needed CSVs exist.
    if stamp_file.exists() and stamp_file.read_text() == today:
        if all((DATA_DIR / f).exists() for f in NEEDED_FILES):
            logger.debug("Meta-Kaggle CSVs already present for today")
            return True

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    api_cli = KaggleApi()
    api_cli.authenticate()

    logger.info("Downloading %d Meta-Kaggle CSVs individually…", len(NEEDED_FILES))
    try:
        for fname in NEEDED_FILES:
            logger.debug("Fetching %s", fname)

            # The API may return the downloaded file path OR boolean False.
            _ = api_cli.dataset_download_file(
                DATASET_SLUG,
                fname,
                path=str(DATA_DIR),
                quiet=True,
                force=True,
            )

            csv_path = DATA_DIR / fname
            zip_path = DATA_DIR / f"{fname}.zip"

            if zip_path.exists():
                with ZipFile(zip_path) as zf:
                    zf.extract(fname, path=str(DATA_DIR))
                zip_path.unlink(missing_ok=True)
            elif not csv_path.exists():
                logger.error("Download for %s did not produce expected files", fname)
                return False

        stamp_file.write_text(today)
        return True
    except Exception as exc:
        if "403" in str(exc) or "forbidden" in str(exc).lower():
            logger.error(
                "Kaggle API reports you have not accepted the license for %s. "
                "Visit https://www.kaggle.com/datasets/kaggle/meta-kaggle, click \"Download\" "
                "once in your browser, then re-run the pipeline.",
                DATASET_SLUG,
            )
        else:
            logger.exception("Failed to download Meta-Kaggle CSVs")
        return False


def _compute_skill(limit: int) -> List[Dict]:
    root = DATA_DIR
    try:
        # Attempt to read CreationDate; fallback if column absent
        try:
            users_df = pd.read_csv(
                root / "Users.csv",
                usecols=["Id", "UserName", "CreationDate"],
                parse_dates=["CreationDate"],
            )
        except ValueError:
            # Older Meta-Kaggle versions lack CreationDate
            users_df = pd.read_csv(root / "Users.csv", usecols=["Id", "UserName"])
            users_df["CreationDate"] = pd.NaT
        # CompetitionResults.csv may not be available; handle gracefully
        comp_path = root / "CompetitionResults.csv"
        if comp_path.exists():
            comp_df = pd.read_csv(comp_path, usecols=["UserId", "Medal"])
        else:
            comp_df = None
        kernels_df = pd.read_csv(root / "Kernels.csv", usecols=["Id", "AuthorUserId"], low_memory=False)
        kvotes_df = pd.read_csv(root / "KernelVotes.csv", low_memory=False)
        ds_df = pd.read_csv(root / "Datasets.csv", usecols=["Id", "CreatorUserId"], low_memory=False)
        dvotes_df = pd.read_csv(root / "DatasetVotes.csv", low_memory=False)
        posts_df = pd.read_csv(root / "ForumMessages.csv", usecols=["PostUserId"], low_memory=False)
    except FileNotFoundError:
        logger.error("Required Meta-Kaggle CSV missing – download likely failed")
        return []

    skill: defaultdict[int, float] = defaultdict(float)

    # Competitions medals
    if comp_df is not None:
        for uid, medal in comp_df.itertuples(index=False):
            skill[uid] += MEDAL_WEIGHTS.get(medal, 0)

    # Notebook votes (handle different column naming between dataset versions)
    if "KernelId" in kvotes_df.columns:
        k_votes = kvotes_df.value_counts("KernelId")
        kernels_df = kernels_df.merge(k_votes, left_on="Id", right_index=True, how="left")
    elif "KernelVersionId" in kvotes_df.columns:
        k_votes = kvotes_df.value_counts("KernelVersionId")
        kernels_df = kernels_df.merge(k_votes, left_on="Id", right_index=True, how="left")
    else:
        k_votes = None

    if k_votes is not None:
        kernels_df["count"] = kernels_df["count"].fillna(0)
        for uid, total_votes in kernels_df.groupby("AuthorUserId")["count"].sum().items():
            skill[uid] += total_votes

    # Dataset votes
    if "DatasetId" in dvotes_df.columns:
        d_votes = dvotes_df.value_counts("DatasetId")
        ds_df = ds_df.merge(d_votes, left_on="Id", right_index=True, how="left")
        ds_df["count"] = ds_df["count"].fillna(0)
        for uid, total_votes in ds_df.groupby("CreatorUserId")["count"].sum().items():
            skill[uid] += total_votes

    # Discussion posts
    for uid, cnt in posts_df["PostUserId"].value_counts().items():
        skill[uid] += cnt

    # Build leaderboard
    leaderboard = (
        pd.Series(skill, name="rating")
        .sort_values(ascending=False)
        .head(limit)
        .rename_axis("Id")
        .reset_index()
        .merge(users_df, left_on="Id", right_on="Id")
    )

    users: List[Dict] = []
    for rank, row in enumerate(leaderboard.itertuples(index=False), 1):
        users.append(
            {
                "name": row.UserName,
                "handle": row.UserName,
                "country": None,
                "rating": float(row.rating),
                "rank": rank,
                "source": "kaggle",
                # "platform_first_seen": row.CreationDate.date().isoformat() if not pd.isna(row.CreationDate) else None,
            }
        )

    # Pad with zero-score users so we always return `limit` entries
    if len(users) < limit:
        remaining = limit - len(users)
        remaining_users = (
            users_df[~users_df["UserName"].isin({u["handle"] for u in users})]
            .head(remaining)
        )
        cur_rank = len(users) + 1
        for _, row in remaining_users.iterrows():
            users.append(
                {
                    "name": row.UserName,
                    "handle": row.UserName,
                    "country": None,
                    "rating": 0.0,
                    "rank": cur_rank,
                    "source": "kaggle",
                    # "platform_first_seen": None,
                }
            )
            cur_rank += 1

    return users


def fetch_leaderboard(limit: int = 300) -> List[Dict]:
    """Fetch Kaggle user rankings via Meta-Kaggle.

    Parameters
    ----------
    limit : int, optional
        Maximum number of users to return, by default 1000.
    """

    logger.info("Fetching Kaggle rankings via Meta-Kaggle (limit=%d)…", limit)

    cached = cache.get_cached("kaggle")
    if cached is not None:
        logger.info("Using cached Kaggle data (%d entries)", len(cached))
        return cached[:limit]

    if not _prepare_kaggle_credentials():
        logger.warning("Kaggle credentials missing – returning empty list")
        return []

    if not _download_meta_dataset():
        return []

    users = _compute_skill(limit)
    if users:
        cache.set_cached("kaggle", users)
        logger.info("Fetched %d Kaggle users via Meta-Kaggle", len(users))
    else:
        logger.warning("Meta-Kaggle processing produced 0 users")
    return users


__all__ = ["fetch_leaderboard"] 