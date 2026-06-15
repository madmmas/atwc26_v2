# AnalyseThisWC26 — Deployment & Operations

A two-service web app plus a reverse proxy:

```
                       ┌────────────────────────────┐
   Browser  ─────────▶ │  Nginx  (TLS, headers,      │
                       │         rate-limit, gzip)   │
                       └───────┬───────────┬─────────┘
                       /        \           \  /api
                      ▼          ▼           ▼
              ┌──────────────┐   ┌────────────────────┐
              │ Frontend     │   │ Backend            │
              │ Next.js 14   │   │ FastAPI + Gunicorn │
              │ (standalone) │   │ Poisson predictor  │
              └──────────────┘   └─────────┬──────────┘
                                           ▼
                                   data/*.parquet  (read-only)
                                   produced by scrape_wc26.py
```

* **Frontend** — Next.js (React/TS/Tailwind/Recharts). Static-ish; calls the API
  from the browser. Served as a self-contained `standalone` build.
* **Backend** — FastAPI app, run by Gunicorn with Uvicorn workers. Loads the
  scraped parquet once at startup and caches all aggregates in memory.
* **Nginx** — single public origin: routes `/api/*` to the backend and everything
  else to the frontend, so the browser makes **same-origin** calls (no CORS).

---

## 1. Local development (no Docker)

> Use a **virtualenv** for the backend so the interpreter running uvicorn always
> matches its installed packages (avoids the classic "No module named pyarrow"
> from a mismatched Python). See [README.md §4](README.md#4-setup--one-time-vs-repeated-commands)
> for the one-time-vs-repeated command breakdown.

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # one-time
pip install -r requirements.txt                     # one-time (re-run on change)
python -m uvicorn app.main:app --reload --port 8000
# Python 3.9 only: also `pip install eval_type_backport`
```

**Frontend** (new terminal)
```bash
cd frontend
cp .env.example .env.local        # one-time — NEXT_PUBLIC_API_URL=http://localhost:8000
npm install                       # one-time (re-run when package.json changes)
npm run dev                        # http://localhost:3000
```

---

## 2. Run the whole stack with Docker Compose

> Requires the Docker daemon running (Docker Desktop / `dockerd`).

```bash
docker compose up --build
# open http://localhost:8080
```

This builds both images, mounts `./data` read-only into the backend, and exposes
the app through Nginx on port **8080**. The frontend is built with
`NEXT_PUBLIC_API_URL=""` so the browser calls same-origin `/api` via Nginx.

**Refreshing data:** re-run the scraper, then restart the backend so it reloads
the parquet:
```bash
python3 scrape_wc26.py
docker compose restart backend
```

---

## 3. Production deployment options

Pick based on how much ops you want to own:

| Option | Frontend | Backend | Notes |
|---|---|---|---|
| **Managed (lowest ops)** | Vercel / Netlify | Render / Railway / Fly.io / AWS App Runner | Push repo, set `NEXT_PUBLIC_API_URL` to the backend URL. Auto-TLS, autoscaling. |
| **Single VM** | container | container | `docker compose up -d` behind the bundled Nginx; add TLS via Let's Encrypt. Cheapest. |
| **Containers at scale** | ECS/Fargate or GKE/EKS | same | Put both behind an ALB/Ingress; scale backend replicas horizontally. |
| **Kubernetes** | Deployment+Service | Deployment+Service+HPA | HPA on CPU; readiness probe `GET /api/health`. |

### TLS
Terminate HTTPS at Nginx (uncomment the `443` block + mount certs) or at the
cloud load balancer. Then enable the HSTS header in `deploy/nginx.conf`.

---

## 4. Scaling for many visitors

The backend is **CPU-bound and read-only** (all data cached in RAM), which makes
it trivial to scale:

* **Vertical:** raise `WEB_CONCURRENCY` (Uvicorn workers ≈ CPU cores).
* **Horizontal:** run N backend replicas behind the proxy/LB — no shared state,
  so they scale linearly. Each holds its own in-memory copy (~tens of MB).
* **Frontend:** it's static output — put it on a **CDN** (Vercel/CloudFront) and
  visitor scaling is effectively free.
* **Caching:** responses are deterministic per dataset. Add
  `Cache-Control: public, max-age=300` on GET analytics endpoints, or a small
  Redis/CDN cache, so repeat traffic never touches Python.
* **Prediction endpoint** is pure CPU math (no I/O) — a single core handles
  thousands of predictions/sec.

**Rule of thumb:** 2–4 small backend replicas + a CDN-hosted frontend comfortably
serve tens of thousands of concurrent fans for this workload.

---

## 5. Security checklist

- [x] Backend runs as **non-root** in-container; data mounted **read-only**.
- [x] Nginx hides version (`server_tokens off`) and sets
      `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`,
      `Permissions-Policy`.
- [x] **Rate limiting** on `/api` (20 r/s, burst 40) to blunt abuse.
- [x] CORS locked to known origins (`ATWC26_CORS_ORIGINS`); same-origin in prod.
- [x] No secrets in the codebase; all config via env vars.
- [ ] Enable **TLS + HSTS** (certs at the proxy or LB).
- [ ] Put a WAF/CDN (Cloudflare/CloudFront) in front for DDoS protection.
- [ ] Add request-size limits and a short read timeout (set: 60s).
- [ ] Pin and scan images (`docker scout` / Trivy) in CI before deploy.

---

## 6. Environment variables

**Backend**
| Var | Default | Purpose |
|---|---|---|
| `ATWC26_DATA_DIR` | `../data` | Where the parquet dataset lives |
| `ATWC26_CORS_ORIGINS` | localhost:3000 | Comma-separated allowed origins |
| `WEB_CONCURRENCY` | `4` | Gunicorn/Uvicorn worker count |

**Frontend**
| Var | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | API base; set `""` for same-origin behind Nginx |

---

## 7. Health & observability

* Liveness/readiness: `GET /api/health` (returns dataset counts).
* Gunicorn access logs to stdout (captured by Docker/orchestrator).
* Add Prometheus via `prometheus-fastapi-instrumentator` if you want metrics.

> Note: the Docker **images were not built in the authoring environment** because
> the Docker daemon was offline there. The compose file validates
> (`docker compose config`) and both services were verified running natively
> (backend on :8000, frontend on :3000, all routes HTTP 200). Run
> `docker compose up --build` on a host with the daemon to produce the images.
