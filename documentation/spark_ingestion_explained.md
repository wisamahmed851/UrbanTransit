# How Spark Ingestion Works (explainer)

Phase 2 moves the generated raw files into HDFS and turns them into typed, partitioned
Parquet with PySpark. Measured results: [reports/ingestion_report.md](../reports/ingestion_report.md).

## The pieces, in Laravel / NestJS terms

| Piece | What it is | Analogy |
|---|---|---|
| **HDFS** (`/urbantransit/...`) | Distributed file system (single node here) holding raw files, Parquet and quarantine | Laravel `Storage` disk / an S3 bucket |
| `hdfs_scripts/upload_raw.sh` | Creates the folder layout, uploads, re-counts rows/bytes from HDFS | A deploy script that copies files and checks checksums |
| **SparkSession** (`spark_jobs/common.py`) | Entry point to Spark: config + connection to the engine | `DB::connection()` / a NestJS provider |
| **DataFrame** | A distributed table; operations are *lazy* (a plan) until an action (`count`, `write`) runs | An Eloquent query builder: nothing hits the DB until `->get()` |
| **Explicit schema** (`spark_jobs/schemas.py`) | `StructType` listing each column and type | A migration / `$casts` / a TypeORM entity |
| **Schema inference** | Spark guesses types by scanning the data first | Letting the DB guess types from the first CSV import |
| **PERMISSIVE mode + `_corrupt_record`** | Bad rows are kept, raw text stored in one column | A validation pipe that sends bad messages to a dead-letter queue instead of throwing |
| **Quarantine** (`/urbantransit/quarantine/<table>/`) | Rows that failed type parsing, with the failing column | The `failed_jobs` table |
| **Parquet** (`/urbantransit/parquet/<table>/`) | Columnar, compressed (Snappy), typed storage | A properly indexed table instead of a CSV dump |
| **partitionBy("year_month")** | One sub-folder per month; queries on a month read only that folder | Table partitioning in MySQL/Postgres |

## The flow for one table (`spark_jobs/ingest_raw.py`)

```
HDFS raw/<table>/*.csv  --count lines-->  rows in
        |
        | spark.read.schema(explicit + _corrupt_record).option("mode","PERMISSIVE").csv(folder)
        v
   typed DataFrame (all monthly files at once)  --persist-->  rows read
        |
        +-- _corrupt_record IS NOT NULL --> quarantine/<table>/ (JSON: raw line, file, failing columns)
        |
        +-- _corrupt_record IS NULL -----> + year_month --> repartition(year_month)
                                             --> parquet/<table>/year_month=YYYY-MM/part-*.snappy.parquet
                                             --> read back + count
check: rows in == OK + quarantined == rows read, and Parquet rows == OK
```

## Key ideas

* **Lazy evaluation.** `spark.read...` and `.filter(...)` only build a plan. Work happens on
  actions like `count()` or `write`. We `persist()` the parsed DataFrame so the files are
  parsed once and reused for the counts, the quarantine and the Parquet write.
* **Why keep bad rows?** Dropping them (`DROPMALFORMED`) would hide data-quality problems,
  and failing the job (`FAILFAST`) would stop the pipeline for one bad value. Quarantine
  keeps every row accountable: *rows in = OK + quarantined*.
* **Strict time parsing.** `spark.sql.legacy.timeParserPolicy=CORRECTED` means an impossible
  timestamp such as `2025-13-45 25:61:00` is a parse failure, not silently rolled over.
* **Column pruning off for CSV** during ingestion, so every column is parsed even when a
  count only needs one - otherwise a bad value in an unused column could go unnoticed.
* **No cleaning in Phase 2.** Type-valid defects (duplicates, negative counts, unknown IDs,
  out-of-range numbers) are stored as they are; Phase 3 checks and cleans them.
* **Small files are avoided** by `repartition(partition_column)` before `partitionBy`, so each
  month (or GPS day) is written by one task as one file, and reference tables are written with
  `coalesce(1)`.

## Running it

```bash
# inside WSL, repo root, venv active
bash hdfs_scripts/start_hdfs.sh && bash hdfs_scripts/status_hdfs.sh
bash hdfs_scripts/upload_raw.sh full            # layout + upload + verify
python spark_jobs/infer_schemas.py --mode full  # inference vs explicit comparison
python spark_jobs/ingest_raw.py --mode full     # quarantine + Parquet + reconciliation
python spark_jobs/ingestion_report.py --mode full
```
