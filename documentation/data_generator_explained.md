# How the Data Generator Works (explainer)

A short tour of `data_generator/` for someone who knows Laravel/NestJS but is new to
Python data work. Details: [dataset_generation_methodology.md](dataset_generation_methodology.md).

## The big picture in Laravel terms

| Python piece | What it does | Laravel / NestJS analogy |
|---|---|---|
| `documentation/schemas/*.json` | Defines the 12 tables: columns, types, PK, FK | Migrations / TypeORM entities |
| `schema_registry.py` | Reads those definitions; renders the data dictionary and ERD | `Schema::getColumnListing()` |
| `generator_config.yaml` + `config.py` | All knobs (dates, rates, defect %) per mode | `config/*.php` + `.env` overrides |
| `generate.py` | CLI that runs everything in order | `php artisan db:seed` |
| `network.py`, `calendar_schedules.py`, `passengers.py` | Build reference data (stops, routes, fleet, timetables, card holders) | Seeders for lookup tables |
| `simulation.py` | Simulates every trip and derives trips, counts, tickets, delays, GPS | Model factories - but one shared simulation instead of independent fakes |
| `defects.py` | Deliberately corrupts a few rows and writes a manifest | A test fixture that records which records are bad |
| `validate_dataset.py` | Re-reads the files and checks volumes, keys and defects | A feature test suite (`php artisan test`) |
| `dataset_stats.py` | Computes the statistics report from the files | A reporting command |

## Python ideas used (quick glossary)

* **NumPy array** - a typed column of numbers. `a * 2` doubles every element at once
  ("vectorised"), which is ~100x faster than a Python `for` loop. Most of the generator is
  written this way.
* **pandas DataFrame** - an in-memory table (rows x named columns), like a Laravel
  Collection of arrays with SQL-like `groupby`, `merge` (join) and `to_csv`.
* **Seeded random generator** - `make_rng(42, "trips", 2025, 9)` always produces the same
  random numbers, like Faker with `$faker->seed(42)`. Each month and purpose has its own
  stream, so regenerating September does not change October.
* **dataclass** - a small typed class for holding data (like a NestJS DTO).

## One month, step by step (`simulation.simulate_month`)

1. **Plan trips** - turn timetable rows ("every 20 min from 07:00 to 10:00") into planned
   departures for each day, plus extra trips around special events.
2. **Demand rate per trip** - how many people per minute arrive at stops for that route and
   time (peak hours, weekends, season, holidays, weather, events).
3. **Static delay drivers** - traffic by time of day, bottleneck junctions, fog/rain, road
   works, protests, breakdowns (plus which trips get cancelled).
4. **Operations loop** (the only plain `for` loop, per route and day, in time order):
   pick a bus -> maybe start late because it is still on its previous trip -> passengers
   waiting = rate x minutes since the previous bus -> board (or be left behind if full) ->
   running time = planned + delays + extra dwell time from heavy boarding.
5. **Derive tables** from that state: trips, passenger_counts, tickets (who tapped in/out and
   where), delays (at which stop and why), GPS pings.

Then `defects.py` damages a controlled number of rows and `writers.py` writes the month's
files before the next month starts (so memory use stays small).

## How to run and check

```bash
# inside WSL: cd /mnt/d/Techwise_2026 && source ~/venvs/urbantransit/bin/activate
python -m data_generator.generate --mode sample --publish-sample   # small, ~5 MB, committed
python -m data_generator.generate --mode full                      # main dataset, ~1.5 GB
python -m data_generator.validate_dataset --mode full              # PASS/FAIL per check
python -m data_generator.dataset_stats --mode full                 # writes dataset_statistics.md
```

## Questions an evaluator may ask

* *Why not generate each table independently?* Tables would contradict each other
  (tickets on cancelled trips, delays that do not match times). Deriving from one simulation
  keeps them consistent, so data-quality checks later find only the defects we injected.
* *How do you know the defect counts are right?* `validate_dataset.py` finds every defect
  again from the files with an independent rule and must match the manifest exactly.
* *Is it reproducible?* Yes - same config and seed give byte-identical files (SHA-256 checked).
