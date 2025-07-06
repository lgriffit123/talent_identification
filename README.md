# talent_identification

# Development & Debugging

To force fresh pulls and ignore the on-disk cache:

```bash
TI_SKIP_CACHE=1 make run
```

This deletes the use of `ingest/catalog.json` for that run without removing the file.

## Logging

Set the log level (default INFO) with an env var:

```bash
TI_LOGLEVEL=DEBUG make run
```

This prints verbose diagnostics from each ingestion step to help debug why a source might return 0 rows.

## Kaggle credentials

Kaggle's API requires an authentication token (`kaggle.json`).  The fetcher
will look for credentials in the following order:

1. `KAGGLE_USERNAME` and `KAGGLE_KEY` environment variables.
2. `KAGGLE_CONFIG_DIR` environment variable pointing to a directory containing
   `kaggle.json`.
3. A `kaggle.json` file placed at either:
   * the project root (`talent_identification/kaggle.json`), or
   * the current working directory when running the pipeline.

If none of these are found, Kaggle data will be skipped automatically (no
errors, just an empty result set).  To generate a token:

1. Go to your Kaggle account → **Account** → *Create New API Token*.
2. Move the downloaded `kaggle.json` into one of the locations above or export
   the variables:

```bash
export KAGGLE_USERNAME=<username>
export KAGGLE_KEY=<key>
```

Then run the pipeline again:

```bash
TI_SKIP_CACHE=1 make run
```

You should now see a non-zero count for Kaggle.