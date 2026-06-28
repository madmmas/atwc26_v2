# v2 API services

Split from the v1 `backend/` monolith for Lambda deployment.

| Service | Port (local) | Routes |
|---------|--------------|--------|
| `analytics_api` | 8001 | overview, teams, players, matches, standings, bracket, winner-probabilities |
| `predict_api` | 8000 | `POST /api/predict` |

Both use `packages/atwc26_core` and `services/shared/`.

## Local dev

```bash
make setup-services
make analytics   # http://localhost:8001
make predict     # http://localhost:8000
make dev-v2      # both APIs + frontend
make test-contract
```

## Lambda packaging

```bash
./infra/scripts/package_lambdas.sh
# -> infra/build/lambdas/{layer,analytics,predict}.zip
```

Then `terraform apply` in `infra/terraform/envs/dev` (uses packaged zips when present).

## Handlers

- Analytics: `analytics_api.handler.handler`
- Predict: `predict_api.handler.handler`
