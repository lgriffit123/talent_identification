# Talent Identification Pipeline

Identify top technical talent across competitive programming and data-science platforms.

---

## 1. What This Repo Does

Runs an end-to-end ETL pipeline that:
1. **Ingests** public leaderboards from Codeforces, LeetCode contests, and the Meta-Kaggle dataset.
2. **Resolves** duplicate identities across platforms via fuzzy-matching.
3. **Scores** every person on a multi-factor "TalentScore".
4. **Outputs** a Markdown report (`report.md`) containing:
   • Global Top-25
   • Country-specific Top-5 lists (for the five most-represented regions)
   • Per-user explanation of *why* they ranked highly.

All network traffic is cached per day so repeat runs are fast and gentle on public APIs.

---

## 2. Installation

```bash
# Clone and jump in
$ git clone …/talent_identification.git && cd talent_identification

# First-time setup
$ make install        # installs `pip` deps from requirements.txt
```

Python ≥ 3.9 is required (3.11+ recommended).

---

## 3. Quick Start

```bash
$ make run                     # = python3 main.py
```

After ~30 s you'll have `report.md` in the repo root.

### Force a fresh download

```bash
$ TI_SKIP_CACHE=1 make run     # bypasses ingest/catalog.json for this run
```

### Verbose logging

```bash
$ TI_LOGLEVEL=DEBUG make run
```

---

## 4. Required Environment Variables / API Keys

| Variable | Purpose | How to obtain |
|-----------|---------|---------------|
| `KAGGLE_USERNAME` & `KAGGLE_KEY` | Auth for Kaggle API (Meta-Kaggle download) | Create a Kaggle token (Account → API → *Create New Token*).<br/>Save `kaggle.json` under `~/.kaggle/` **or** export the vars. |
| `LEETCODE_SESSION`, `LEETCODE_CSRF` (optional) | Gives LeetCode access to contest API if Cloudflare blocks you. | Copy cookies from an authenticated browser session. |
| `TI_SKIP_CACHE` | `1/true/yes` → ignore daily cache. | One-off per run. |
| `TI_LOGLEVEL` | `DEBUG / INFO / WARNING` | Controls console verbosity. |

You can also place them in a `.env` file at repo root – it's auto-loaded by `main.py`.

---

## 5. Pipeline Internals

### 5.1 Ingest Stage

| Source | File | What we fetch |
|--------|------|---------------|
| **Codeforces** | `ingest/codeforces.py` | Top-N rated users via `user.ratedList`. |
| **LeetCode** | `ingest/leetcode.py` | Contest leaderboard for a given slug (`weekly-contest-457` by default). |
| **Kaggle** | `ingest/kaggle.py` | Meta-Kaggle CSVs (Users, Kernels, Datasets …) converted into a numeric "skill" score. |

Each ingestor returns a list with unified keys:
`name, handle, country, rating, rank, source, platform_first_seen`.

> `platform_first_seen` now comes from **our own** first observation of the handle.
> Per-platform "join" dates were removed because they were slow/brittle to fetch.

### 5.2 Entity Resolution

`etl/entity_resolution.py`

* RapidFuzz token-sort ratio ≥ 88 → same person.
* Aggregates a `handles` dict so one profile can hold multiple platform IDs.

### 5.3 Scoring Logic

Implemented in `etl/scoring.py`.  Per-profile fields computed in `main.py`:

```
TalentScore = (base + momentum + geo + rising) * versatility_factor
              + multi_platform_bonus + rank_bonus + fresh_bonus
```

See the source for details on each component.

### 5.4 Reporting

`etl/report.py` writes `report.md` with the global and per-country leaderboards plus explanation bullets.

---

## 6. Caching Behaviour & Quirks

* **Daily Cache** – `ingest/catalog.json` keeps a *per-day* snapshot:

  ```json
  {
    "2024-07-09": { "codeforces": [...], "leetcode": [...], "kaggle": [...] },
    "2024-07-08": { "codeforces": [...], "leetcode": [...], "kaggle": [...] }
  }
  ```
  Runs on the same day reuse today's entry; new days append a fresh bucket so historical rankings remain available for analysis.
* **Skip Cache** – set `TI_SKIP_CACHE=1` to force fresh pulls.
* **LeetCode Cloudflare** – If Cloudflare challenges appear, install Playwright & run `playwright install firefox`; the code will solve the challenge automatically.
* **Codeforces Rate-Limit** – The registration-date endpoint is *not* called anymore; fewer API calls, fewer 429s.

---

## 7. Extending / Customising

* **Add a new ingest source** → drop a file into `ingest/` returning the unified dict format.
* **Adjust weightings** → tweak constants in `etl/scoring.py`.
* **Add new bonuses** → compute the metric in `main.py`, feed it into the profiles, then reference it in `interestingness_score()`.

PRs welcome – especially for additional data sources or alternative scoring heuristics!