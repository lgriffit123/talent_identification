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

Python ≥ 3.9 is required. (3.11+ recommended for faster asyncio internals; the code stays 3.9-compatible.)

---

## 3. Quick Start

```bash
$ make run                     # = python3 main.py
```

After ~30 s you'll have `report.md` in the repo root.

### Force a fresh download

```bash
$ TI_SKIP_CACHE=1 make run     # bypasses ingest/cache.json for this invocation
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
| **Codeforces** | `ingest/codeforces.py` | Top N rated users via `user.ratedList`, plus per-user `registrationTimeSeconds`. |
| **LeetCode** | `ingest/leetcode.py` | Contest leaderboard for a given slug (`weekly-contest-457` by default). GraphQL call enriches each handle with `joinDate`. |
| **Kaggle** | `ingest/kaggle.py` | Meta-Kaggle CSVs (Users, Kernels, Datasets …) converted into a numeric "skill" score. |

Each ingestor returns a list with unified keys: `name, handle, country, rating, rank, source, platform_first_seen`.

Data is cached once per day under `ingest/catalog.json`.

### 5.2 Entity Resolution

`etl/entity_resolution.py`

* RapidFuzz token-sort ratio ≥ 88 → same person.
* Aggregates `handles` dict so one profile can hold multiple platform IDs.

### 5.3 Scoring Logic

Implemented in `etl/scoring.py`.  Per-profile fields computed in `main.py`:

```
TalentScore = (base + momentum + geo + rising) * versatility_factor
              + multi_platform_bonus + rank_bonus + fresh_bonus
```

• **base** – sigmoid-scaled `rating_z` (z-score inside platform). 0-1000 range.
• **momentum** – `delta_sigma × 50` (σ-change vs. yesterday).
• **geo** – up to +100 for #1 in country.
• **rising** – +50 if momentum > +1.5 σ.
• **versatility_factor** – +10 % per extra platform (capped +25 %).
• **multi_platform_bonus** – flat +50 if a user appears on >1 platform.
• **rank_bonus** – up to +300 for podium AtCoder ranks (placeholder example).
• **fresh_bonus** – +25 when `days_active < 365`.

Reason strings in the report list all contributing factors, e.g.

```
• rating 2920 on codeforces
• z +3.62
• Δσ +1.4
• geo +88 (top 2.0 % in IN)
• Rising star
• fresh entrant (joined 2024-06-07 — leetcode)
```

### 5.4 Reporting

`etl/report.py` writes `report.md` with:

1. Global Top-25 table (name, primary handle, score, reasons).
2. Country sections for the five countries with the most users in the raw data.

---

## 6. Caching Behaviour & Quirks

* **Daily Cache** – All raw payloads are timestamped; multiple runs on the same day reuse data.
* **Skip Cache** – set `TI_SKIP_CACHE=1` to force fresh pulls.
* **LeetCode Cloudflare** – If Cloudflare challenges appear, install Playwright & run `playwright install firefox`; the code will solve the challenge automatically.
* **Codeforces Rate-Limit** – Registration date is a per-user API call; the function is memoised and will degrade gracefully if rate-limited.
* **urllib3 LibreSSL Warning** – macOS Python < 3.11 ships LibreSSL; it's a *warning* only.

---

## 7. Extending / Customising

* Add new ingest source → drop a file into `ingest/` returning the unified dict format.
* Adjust weightings → tweak constants in `etl/scoring.py`.
* Add new bonuses → compute the metric in `main.py`, feed it into the profiles, then reference it inside `interestingness_score()`.

PRs welcome – especially for additional data sources or alternative scoring heuristics!
