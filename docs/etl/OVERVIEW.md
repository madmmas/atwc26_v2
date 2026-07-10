# ETL System Overview

High-level map of the ATWC26 data pipeline: an **AWS scheduler** dispatches **GitHub Actions** to scrape ESPN, transform data, and publish to S3/DynamoDB so the live API serves fresh artifacts.

| Doc | Read when… |
|-----|------------|
| **[ARCHITECTURE.md](../ARCHITECTURE.md)** | Full system C4 model + AWS estate (frontend, APIs, scheduler, data layer) |
| **[SCHEDULER.md](SCHEDULER.md)** | Debugging missed or duplicate GHA dispatches, trigger windows, EventBridge/Lambda |
| **[PIPELINE.md](PIPELINE.md)** | Debugging scrape/transform/publish, fingerprints, artifacts, compute refresh |
| [`etl/README.md`](../../etl/README.md) | Makefile targets, env vars, artifact tables (operator runbook) |

**Also see:** [`PRODUCTION_SPEC.md`](../specs/PRODUCTION_SPEC.md) (cutover), [`infra/README.md`](../../infra/README.md) (Terraform).

---

## Two cooperating halves

| Half | Where it runs | Responsibility |
|------|---------------|----------------|
| **Scheduler** | AWS (EventBridge + Lambda) | Poll every 5 minutes; decide which matches need ETL; dispatch GitHub Actions |
| **ETL worker** | GitHub Actions (`etl.yml`) | Scrape ESPN → transform → simulate/train → QA → publish to S3/DynamoDB → warm compute |

Scheduling is **not** done by a GitHub cron. The `etl.yml` workflow only accepts `workflow_dispatch` (manual or Lambda-dispatched).

```mermaid
flowchart LR
    subgraph AWS["AWS (Scheduler)"]
        EB[EventBridge<br/>every 5 min]
        L[Lambda<br/>etl-dispatch]
        S3S[(S3<br/>schedule.json)]
        DDB[(DynamoDB<br/>trigger dedup)]
        SM[Secrets Manager<br/>GitHub PAT]
    end

    subgraph External["External"]
        ESPN[ESPN APIs]
        GH[GitHub Actions<br/>etl.yml]
    end

    subgraph AWS2["AWS (Data & Serving)"]
        S3D[(S3<br/>artifacts)]
        DDBM[(DynamoDB<br/>manifest + API cache)]
        LAM[Lambda<br/>Analytics / Predict]
        ECS[ECS Fargate<br/>Predict service]
        APIGW[API Gateway]
        CF[CloudFront]
    end

    EB --> L
    L --> S3S
    L --> DDB
    L --> SM
    L -->|workflow_dispatch| GH
    L -.->|completion probe| ESPN
    GH -->|scrape| ESPN
    GH --> S3D
    GH --> DDBM
    GH -->|bump ATWC26_DATA_VERSION| LAM
    GH -->|forceNewDeployment + /reload| ECS
    CF --> APIGW
    APIGW --> LAM
    APIGW --> ECS
    LAM --> DDBM
    LAM --> S3D
```

---

## Cross-boundary contract

These are the shared interfaces between the scheduler and the pipeline. Both docs reference this section.

### `data/schedule.json`

Published to S3 at `data/schedule.json`. The Lambda dispatcher reads it every 5 minutes; the scrape phase refreshes it via `fetch_schedule.py`.

Per-game structure:

```json
{
  "760414": {
    "kickoff_utc": "2026-06-12T02:00Z",
    "home": "South Korea",
    "away": "Czechia",
    "round_slug": "group-stage",
    "completed": true,
    "status_state": "post",
    "status_name": "STATUS_FULL_TIME"
  }
}
```

`round_slug` controls trigger windows: `group-stage` uses a shorter poll window than knockout rounds. See [SCHEDULER.md § Trigger timing](SCHEDULER.md#trigger-timing-windows).

### DynamoDB trigger keys

Partition key `ETL_TRIGGER#wc26` (same table as the publish manifest):

| SK | Written by | Purpose |
|----|------------|---------|
| `{game_id}#+{offset}` | Lambda dispatcher | Prevents re-dispatching the same time slot |
| `{game_id}#DONE` | `etl.publish` (`mark_games_finished`) | Stops all future scheduler slots for that game |

### Handoff: dispatch → DONE

```mermaid
stateDiagram-v2
    [*] --> Scheduled: Fixture in schedule.json
    Scheduled --> SlotDue: trigger_at in catchup window
    SlotDue --> Dispatched: Lambda writes game_id#+offset
    Dispatched --> GHARunning: GitHub Actions etl.yml
    GHARunning --> DataChanged: ESPN data changed
    GHARunning --> NoChange: Fingerprint unchanged
    NoChange --> Scheduled: Next offset slot may fire
    DataChanged --> Published: etl.publish uploads
    Published --> Done: mark_games_finished → game_id#DONE
    Done --> [*]: All future slots skipped
```

1. **Lambda** POSTs `workflow_dispatch` on `etl.yml` with `inputs.trigger_game_id={game_id}`.
2. **GHA** runs `python -m etl.changed check-trigger $game_id` — skips the run if `{game_id}#DONE` already exists.
3. **Publish** compares pre/post fingerprints; for games whose `data/raw/{id}.json` changed, writes `{game_id}#DONE`.

---

## End-to-end phases

```mermaid
flowchart TB
    subgraph PhaseA["Phase A — AWS Scheduler"]
        A1[EventBridge every 5 min]
        A2[Lambda reads schedule.json]
        A3[Compute due trigger slots]
        A4[Probe ESPN completion]
        A5[Dispatch etl.yml via GitHub API]
    end

    subgraph PhaseB["Phase B — Scrape"]
        B1[Restore state + sync S3]
        B2[Scrape ESPN fixtures/stats]
        B3[Fingerprint compare]
    end

    subgraph PhaseC["Phase C — Transform"]
        C1[Profiles + manifest]
        C2[Simulate + train]
        C3[QA checks]
    end

    subgraph PhaseD["Phase D — Publish"]
        D1[Upload changed artifacts to S3]
        D2[Update DynamoDB manifest + API cache]
        D3[Mark games DONE]
        D4[Refresh Lambda + ECS]
    end

    A1 --> A2 --> A3 --> A4 --> A5
    A5 --> B1 --> B2 --> B3
    B3 -->|changed| C1 --> C2 --> C3
    C3 --> D1 --> D2 --> D3 --> D4
    B3 -->|unchanged| DONE([End — no publish])
    D4 --> LIVE([API serves fresh data])
```

| Phase | Detail doc |
|-------|------------|
| **A** — Scheduler | [SCHEDULER.md](SCHEDULER.md) |
| **B–D** — Pipeline | [PIPELINE.md](PIPELINE.md) |

### In plain language

1. **EventBridge** ticks every 5 minutes and invokes the **ETL dispatch Lambda**.
2. The Lambda loads **schedule.json**, finds due post-match windows, confirms the match is **completed on ESPN**, and dispatches **GitHub Actions**.
3. GHA **scrapes ESPN**, compares fingerprints, and skips work if nothing changed.
4. On change, it **transforms**, **simulates**, optionally **trains**, runs **QA**, then **publishes** to S3 and DynamoDB.
5. Publish marks finished games **DONE**, precomputes **API cache** rows, and **refreshes** Lambda/ECS so the live site serves new data.

---

## When to read which doc

| Symptom | Start here |
|---------|------------|
| GHA never fired after a match ended | [SCHEDULER.md](SCHEDULER.md) — trigger windows, ESPN completion gate, `#+offset` dedup |
| GHA fired but exited immediately | [OVERVIEW.md § Handoff](OVERVIEW.md#handoff-dispatch--done) — `{game_id}#DONE` already set |
| GHA ran but skipped transform/publish | [PIPELINE.md § Change detection](PIPELINE.md#change-detection) — fingerprint unchanged |
| Data published but API stale | [PIPELINE.md § Compute refresh](PIPELINE.md#publish--compute-refresh) — Lambda env bump, ECS reload |
| Manual full refresh | [PIPELINE.md § Manual operations](PIPELINE.md#manual--local-operations) |
