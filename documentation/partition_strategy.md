# Partition Strategy (Parquet in HDFS)

Where the numbers below come from: the Phase 2 ingestion run of the `full` dataset,
see [reports/ingestion_report.md](../reports/ingestion_report.md) (section 7) and
`hdfs dfs -du /urbantransit/parquet/<table>` in `reports/processing_logs/`.

## Decisions per table

| Table | Rows | Partition column | Partitions | Why |
|---|---|---|---|---|
| tickets | 3.03M | `year_month` (from `service_date`) | 12 | Revenue, ridership and card-usage analyses are per period; monthly folders let Spark read only the months a query needs (partition pruning). Month is also how the raw files arrive. |
| trips | 2.10M | `year_month` | 12 | Punctuality, cancellations and headway analyses are by period; trips are joined to tickets/counts/delays of the same month. |
| passenger_counts | 1.94M | `year_month` | 12 | Occupancy and demand forecasting use monthly/seasonal windows. |
| delays | 0.99M | `year_month` | 12 | Delay trends by month/season; joins with trips of the same month. |
| gps_events | 1.14M | `event_date` (from `event_time`) | 7 | GPS is a 7-day window analysed per day (bunching, speeds); one folder per day matches the daily JSON Lines files. |
| stops, routes, route_stops, vehicles, passengers, schedules, service_calendar | 11 to 58,000 | none | - | Small reference tables (under 4 MB raw): partitioning would only create tiny files. Each is written as one Parquet file and broadcast in joins. |

## Why month (and not day, route or stop)?

* **Query pattern:** the SRS analyses (seasonality, monthly KPIs, forecasting windows)
  filter by period far more often than by a single route.
* **File size:** measured monthly ticket partitions are **6.6-9.0 MB** of Snappy Parquet
  (one file each). Daily partitions would be ~0.2-0.3 MB files - 365 tiny files per table,
  which is the classic "small files" problem for HDFS (every file costs NameNode memory and
  a task at read time). Route-level partitions (118 folders x 12 months) would be worse.
* **Low cardinality, even spread:** 12 values, each with a similar row count (the busiest
  month is about 1.3x the quietest), so no partition is skewed.
* **Stable key:** `service_date` is never corrupted by the injected defects, so every row gets
  a valid partition value (`entry_time` is not used because some values are invalid).

Monthly files are below the 128 MB HDFS block size; that is acceptable here because the
whole Parquet dataset is 276 MB and fewer, larger files (e.g. quarterly) would lose monthly
pruning for little benefit. If the data grows ~10x, the same layout gives ~70-90 MB files,
close to one block each - the layout scales without changes.

## How small files are avoided

* `repartition(<partition column>)` before `write.partitionBy(<partition column>)`: all rows
  of a month go to one task, so each month folder contains exactly **one** Parquet file
  (12 files per big table instead of up to 12 x shuffle partitions).
* Reference tables are written with `coalesce(1)` (one file each).
* Result: **62 Parquet files** for the whole dataset = 4 monthly tables x 12 + 7 GPS days + 7
  reference tables (see the file counts in the ingestion report).

## Spark settings for local mode (8 GB WSL, 4 cores)

| Setting | Value | Reason |
|---|---|---|
| `spark.master` | `local[*]` | single machine, all 4 cores |
| `spark.driver.memory` | 4g | driver = executor in local mode; leaves room for HDFS daemons (~1.4 GB) and the OS inside the 8 GB WSL limit |
| `spark.sql.shuffle.partitions` | 8 | the default 200 would create 200 tiny tasks/files for a few hundred MB; 8 = 2 x cores |
| `spark.sql.adaptive.enabled` (+ coalesce partitions) | true | Spark merges small shuffle partitions at run time |
| `spark.sql.parquet.compression.codec` | snappy | fast to read/write, splittable; Parquet is 21% of the raw size overall |
| `spark.local.dir` | `~/spark_tmp` | shuffle/spill space inside the WSL disk, not `/tmp` (see DEV_LOG Phase 0) |

## Reading the partitions

```python
tickets = spark.read.parquet("hdfs://localhost:9000/urbantransit/parquet/tickets")
jan = tickets.filter("year_month = '2026-01'")   # only the 2026-01 folder is read (partition pruning)
```
