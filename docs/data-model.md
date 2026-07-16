# Data Model & Schema Mapping

## Overview

The PL1 Migration Service maps legacy PL1 data structures to the modern v2 schema. This document describes the mapping rules and validation logic.

## Source Schema (Legacy PL1)

Legacy tables use fixed-width character fields and EBCDIC encoding. Key tables:

| Legacy Table | Records (approx) | Encoding |
|---|---|---|
| `CUSTMAST` | 2.4M | EBCDIC |
| `ORDHDR` | 8.1M | EBCDIC |
| `ORDDTL` | 24M | EBCDIC |
| `INVMST` | 450K | EBCDIC |

## Target Schema (Modern v2)

Modern tables use UTF-8, JSONB metadata columns, and UUID primary keys:

| Target Table | Source | Transform Rules |
|---|---|---|
| `customers` | `CUSTMAST` | Strip padding, convert dates ISO 8601 |
| `orders` | `ORDHDR` + `ORDDTL` | Join on order_number, nest line items as JSONB array |
| `inventory` | `INVMST` | Map warehouse codes via lookup table |

## Validation Rules

Before a migration job runs, the engine validates:

1. **Schema compatibility** — all source columns have a mapping
2. **Referential integrity** — foreign keys resolvable in target
3. **Data type coercion** — no silent truncation (fail on overflow)
4. **Duplicate detection** — primary key uniqueness in source batch

## Rollback Snapshots

Before each job, a point-in-time snapshot is created:

- Stored in S3 as Parquet files
- Includes all target tables affected by the job
- Retention: 30 days (configurable per tenant)
- Restore tested monthly in staging

## Performance Tuning

| Parameter | Default | Recommended (large) |
|---|---|---|
| `batch_size` | 1000 | 5000 |
| `worker_count` | 4 | 8 |
| `parallel_tables` | 1 | 3 |
| `memory_limit_mb` | 512 | 2048 |

Jobs exceeding 1M records should use `parallel_tables > 1` and increase `worker_count`.

## Known Mapping Issues

- `CUSTMAST.PHONE` field contains mixed formats (with/without country code) — normalized in transform
- `ORDHDR.SHIP_DATE` uses Julian date format in legacy — converted to ISO 8601
- Null padding in EBCDIC fields appears as spaces — stripped during extraction
