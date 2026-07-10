# ETL documentation

Match-timed data pipeline: AWS scheduler dispatches GitHub Actions to scrape ESPN, transform, and publish to S3/DynamoDB.

| Doc | Read when… |
|-----|------------|
| **[V1_TO_V2.md](../V1_TO_V2.md)** | Full system v1 → v2 transition |
| **[ARCHITECTURE.md](../ARCHITECTURE.md)** | Full system C4 model + AWS deployment map |
| **[OVERVIEW.md](OVERVIEW.md)** | First read — end-to-end map and cross-boundary contract |
| **[SCHEDULER.md](SCHEDULER.md)** | GHA didn't fire, duplicate dispatches, trigger windows |
| **[PIPELINE.md](PIPELINE.md)** | Scrape/transform/publish failures, fingerprints, API stale |

**Runbook:** [`../../etl/README.md`](../../etl/README.md) (Makefile, artifacts, env vars)

**Parent index:** [docs/README.md](../README.md)
