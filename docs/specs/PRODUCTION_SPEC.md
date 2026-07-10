# atwc26_v2 — Production deployment & next-phase spec
# Instructions for Cursor. Work top-to-bottom. Each section is a discrete task.
# Prerequisites, exact commands, file edits, and verification steps are all included.
# Do not skip verification steps — each one confirms the previous task worked.

---

# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — INFRASTRUCTURE BOOTSTRAP (one-time, blocks everything else)
# ══════════════════════════════════════════════════════════════════════════════
#
# Context: The Terraform modules, GHA workflows, scripts, and application code
# are all complete. What does not exist yet is:
#   - A live AWS stack (Terraform has never been applied)
#   - GitHub OIDC IAM role (workflows use ATWC26_AWS_ROLE_ARN which doesn't exist)
#   - Lambda packages (infra/build/lambdas/ is empty → Lambda functions have no code)
#   - DynamoDB API cache (table will exist after apply but is empty until first ETL)
#   - ETL scheduler (EventBridge rule doesn't exist → ETL never runs automatically)
#
# These steps must be done in order. Step 1A must be done by the human in the
# AWS console and GitHub UI. Steps 1B–1G are Cursor tasks.

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1A — Human does this (not Cursor): Create the Terraform state bucket
# ──────────────────────────────────────────────────────────────────────────────
#
# This cannot be done by Terraform (chicken-and-egg: Terraform needs S3 for
# its own state). The human runs these AWS CLI commands once:
#
#   BUCKET="atwc26-v2-tfstate-<your-account-id>"
#   aws s3 mb s3://$BUCKET --region us-east-1
#   aws s3api put-bucket-versioning \
#     --bucket $BUCKET \
#     --versioning-configuration Status=Enabled
#   aws s3api put-bucket-encryption \
#     --bucket $BUCKET \
#     --server-side-encryption-configuration \
#     '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
#
# Then the human sets these GitHub repository secrets
# (Settings → Secrets and variables → Actions → New repository secret):
#
#   AWS_REGION                = us-east-1
#   ATWC26_TF_STATE_BUCKET    = atwc26-v2-tfstate-<account-id>
#   ATWC26_RELOAD_SECRET      = <run: python3 -c "import secrets; print(secrets.token_hex(32))">
#
# And generates a GitHub fine-grained PAT:
#   github.com → Settings → Developer settings → Fine-grained tokens → Generate new token
#   Name: atwc26-etl-scheduler
#   Repository access: madmmas/atwc26_v2 only
#   Permissions: Actions → Read and write
#   Save the token — it's used in Step 1B as github_dispatch_token.

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1B — Create terraform.tfvars
# ──────────────────────────────────────────────────────────────────────────────
#
# File: infra/terraform/envs/dev/terraform.tfvars
# This file is gitignored. Create it locally with exact content below.
# REPLACE every <placeholder> with real values.
#
# CREATE infra/terraform/envs/dev/terraform.tfvars:

aws_region   = "us-east-1"
name_prefix  = "atwc26-v2"
environment  = "dev"

# v1 monolith URL — baked into static frontend until DNS cutover
backend_api_url = "https://atwc26.com"

# CORS: allow requests from CloudFront URL (update after first apply)
cors_allow_origins = ["*"]

# GitHub OIDC — creates IAM role for GHA workflows (no long-lived keys)
enable_github_oidc = true
github_org         = "madmmas"
github_repo        = "atwc26_v2"

# ETL scheduler — EventBridge rate(15 min) → Lambda → workflow_dispatch
enable_etl_scheduler  = true
github_dispatch_token = "github_pat_<REPLACE_WITH_REAL_TOKEN>"

# ECS predict — set false for first apply; enable after image is pushed to ECR
enable_ecs_compute  = false
ecs_container_image = ""

# Custom domain (add after first apply and DNS verification):
# aliases             = ["atwc26.com", "www.atwc26.com"]
# acm_certificate_arn = "arn:aws:acm:us-east-1:<account>:certificate/<id>"

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1C — Create backend.hcl
# ──────────────────────────────────────────────────────────────────────────────
#
# File: infra/terraform/envs/dev/backend.hcl
# This file is gitignored. Create it with the state bucket name from Step 1A.
#
# CREATE infra/terraform/envs/dev/backend.hcl:

bucket  = "atwc26-v2-tfstate-<REPLACE_WITH_REAL_BUCKET_NAME>"
key     = "atwc26-v2/dev/terraform.tfstate"
region  = "us-east-1"
encrypt = true

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1D — Store terraform.tfvars as GitHub secret ATWC26_TFVARS
# ──────────────────────────────────────────────────────────────────────────────
#
# The terraform.yml GHA workflow reads the full tfvars from this secret so it
# can run terraform apply without checking the file into git.
#
# Human action: copy the FULL content of infra/terraform/envs/dev/terraform.tfvars
# into a new GitHub secret named ATWC26_TFVARS.
# (Settings → Secrets and variables → Actions → New repository secret)
#
# Cursor verifies this secret exists by checking that terraform.yml references it:

# VERIFY: grep "ATWC26_TFVARS" .github/workflows/terraform.yml
# Expected output contains: secrets.ATWC26_TFVARS

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1E — First Terraform apply: provision all AWS resources
# ──────────────────────────────────────────────────────────────────────────────
#
# This creates: S3 data bucket, DynamoDB table, API Gateway, CloudFront,
# ECR repository, GitHub OIDC IAM role, EventBridge ETL scheduler.
# Lambda functions are created but have no code yet (Step 1F does that).
#
# Trigger via GitHub Actions (requires temporary AWS keys for the first run
# because OIDC role doesn't exist yet):
#
# 1. Set these two TEMPORARY GitHub secrets (delete after Step 1E completes):
#      AWS_ACCESS_KEY_ID     = <your AWS access key>
#      AWS_SECRET_ACCESS_KEY = <your AWS secret key>
#
# 2. Go to: GitHub → Actions → Terraform dev → Run workflow
#    Set action = "terraform-apply"
#    Click "Run workflow"
#
# 3. Wait for the workflow to complete (~5 minutes).
#
# 4. In the workflow run summary, copy these outputs:
#
#    github_actions_role_arn    → set as GitHub secret ATWC26_AWS_ROLE_ARN
#    data_bucket_name           → set as GitHub secret ATWC26_S3_BUCKET
#    dynamodb_table_name        → set as GitHub secret ATWC26_DYNAMODB_TABLE
#    lambda_analytics_name      → set as GitHub secret ATWC26_LAMBDA_ANALYTICS_NAME
#    lambda_predict_name        → set as GitHub secret ATWC26_LAMBDA_PREDICT_NAME
#    ecr_predict_url            → set as GitHub secret ATWC26_ECR_PREDICT_URL
#    cloudfront_url             → save for local testing (not a secret)
#
# 5. Delete the temporary AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY secrets.
#    From this point all GHA workflows use OIDC (no long-lived keys).
#
# VERIFY from the AWS console or CLI:
#   aws s3 ls | grep atwc26
#   aws dynamodb list-tables | grep atwc26
#   aws cloudfront list-distributions | grep atwc26

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1F — Package Lambdas and update function code
# ──────────────────────────────────────────────────────────────────────────────
#
# package_lambdas.sh builds arm64 Linux wheels and zips the analytics and
# predict Lambda functions + shared layer. Terraform then uploads them.
#
# Trigger via GitHub Actions:
#   GitHub → Actions → Terraform dev → Run workflow
#   Set action = "terraform-apply"
#   Click "Run workflow"
#
# The workflow runs package-lambdas first (uploads zips as GHA artifact),
# then runs terraform which picks them up from the artifact and applies.
#
# VERIFY: in the Terraform workflow run, the "Package Lambda artifacts" step
# should output something like:
#   layer.zip    12M
#   analytics.zip 1.2M
#   predict.zip   1.1M
#
# VERIFY Lambda functions have code:
#   aws lambda get-function --function-name atwc26-v2-dev-analytics \
#     --query 'Configuration.CodeSize'
#   # Should return a number > 0

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1G — First full ETL publish to seed DynamoDB and S3
# ──────────────────────────────────────────────────────────────────────────────
#
# DynamoDB API cache is empty after Terraform apply. Lambda cold starts work
# but return empty DynamoDB reads until this first publish runs.
#
# Trigger via GitHub Actions:
#   GitHub → Actions → ETL → Run workflow
#   Leave all inputs at defaults (skip_scrape=false, skip_publish=false)
#   Click "Run workflow"
#
# Watch the workflow steps:
#   - "Scrape ESPN data" should complete in ~5 minutes
#   - "Transform + simulate + QA" should complete in ~3 minutes
#   - "Publish to S3 + DynamoDB + warm compute" should show:
#       API cache written: standings (48), matches (104), players (1251), ...
#
# VERIFY DynamoDB has cache entries:
#   aws dynamodb scan \
#     --table-name <DYNAMODB_TABLE> \
#     --filter-expression "begins_with(PK, :p)" \
#     --expression-attribute-values '{":p":{"S":"API#"}}' \
#     --select COUNT \
#     --region us-east-1 \
#     --output text
#   # Should return a count > 0
#
# VERIFY S3 has artifacts:
#   aws s3 ls s3://<S3_BUCKET>/data/ | head -10
#   # Should list parquet and JSON files

# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — ECS PREDICT SERVICE (warm predictor, no cold start)
# ══════════════════════════════════════════════════════════════════════════════
#
# Context: POST /api/predict currently routes to Lambda predict (cold start
# 2-3s because it loads player profiles on every cold container). ECS keeps
# the Predictor warm in memory. The ECS module, ALB, VPC link, and API Gateway
# routing are all built — just not activated.
#
# Order: push image FIRST, then enable ECS in Terraform.
# If you enable ECS before pushing an image, ECS fails to start.

# ──────────────────────────────────────────────────────────────────────────────
# STEP 2A — Push predict Docker image to ECR
# ──────────────────────────────────────────────────────────────────────────────
#
# Trigger via GitHub Actions:
#   GitHub → Actions → Terraform dev → Run workflow
#   Set action = "deploy-predict-ecs"
#   Click "Run workflow"
#
# This builds the Docker image from services/predict_api/Dockerfile,
# pushes it to ECR as :latest and :<sha>, then attempts ECS update-service.
# ECS update will fail (service doesn't exist yet) — that is expected at this step.
# The important thing is the image is in ECR.
#
# VERIFY image is in ECR:
#   aws ecr list-images \
#     --repository-name atwc26-v2-dev-predict \
#     --region us-east-1 \
#     --query 'imageIds[?imageTag==`latest`]'
#   # Should return the image digest

# ──────────────────────────────────────────────────────────────────────────────
# STEP 2B — Enable ECS in terraform.tfvars
# ──────────────────────────────────────────────────────────────────────────────
#
# EDIT infra/terraform/envs/dev/terraform.tfvars:
# FIND:
#   enable_ecs_compute  = false
#   ecs_container_image = ""
# REPLACE WITH (use real ECR URL from Step 1E output):
#   enable_ecs_compute  = true
#   ecs_container_image = "<ecr_predict_url>:latest"
#
# Then update ATWC26_TFVARS GitHub secret with the new tfvars content.

# ──────────────────────────────────────────────────────────────────────────────
# STEP 2C — Terraform apply with ECS enabled
# ──────────────────────────────────────────────────────────────────────────────
#
# Trigger via GitHub Actions:
#   GitHub → Actions → Terraform dev → Run workflow
#   Set action = "terraform-apply"
#   Click "Run workflow"
#
# This creates: ECS cluster, Fargate task definition, ECS service, ALB,
# VPC link. API Gateway predict route switches from Lambda to ECS.
#
# AFTER APPLY — set these GitHub secrets from terraform outputs:
#   ATWC26_ECS_CLUSTER       = terraform output -raw ecs_cluster_name
#   ATWC26_ECS_SERVICES      = terraform output -raw ecs_service_name
#   ATWC26_ECS_PREDICT_SERVICE = terraform output -raw ecs_service_name
#   ATWC26_PREDICT_SERVICE_URL = http://<compute_alb_dns>
#                                # from: terraform output -raw compute_alb_dns
#
# VERIFY ECS service is running:
#   aws ecs describe-services \
#     --cluster atwc26-v2-dev \
#     --services atwc26-v2-dev-predict \
#     --region us-east-1 \
#     --query 'services[0].{status:status,running:runningCount,desired:desiredCount}'
#   # Expected: {"status": "ACTIVE", "running": 1, "desired": 1}
#
# VERIFY predict health through the ALB:
#   curl http://<compute_alb_dns>/api/health
#   # Expected: {"status":"ok","models_available":["poisson","elo","dixon_coles",...]}

# ──────────────────────────────────────────────────────────────────────────────
# STEP 2D — Re-run ETL publish to update ATWC26_DATA_VERSION on ECS
# ──────────────────────────────────────────────────────────────────────────────
#
# The ECS predict service loads player profiles from S3 on startup. After
# enabling ECS, trigger one ETL run so the publish step also calls the
# predict /reload endpoint to confirm data is fresh.
#
# Trigger via GitHub Actions:
#   GitHub → Actions → ETL → Run workflow
#   Set skip_scrape = false
#   Click "Run workflow"
#
# VERIFY in workflow logs: "Publish to S3 + DynamoDB + warm compute" step
# should show "predict reload: HTTP 200" or similar.

# ══════════════════════════════════════════════════════════════════════════════
# PART 3 — VERIFY CLOUDFRONT END-TO-END
# ══════════════════════════════════════════════════════════════════════════════
#
# Context: Frontend is deployed to S3 + CloudFront via deploy-frontend.yml.
# This part verifies the full stack works through CloudFront before touching DNS.

# ──────────────────────────────────────────────────────────────────────────────
# STEP 3A — Deploy frontend to S3
# ──────────────────────────────────────────────────────────────────────────────
#
# Trigger via GitHub Actions:
#   GitHub → Actions → Deploy frontend → Run workflow
#   Click "Run workflow"
#
# The workflow:
#   1. Reads CloudFront URL + bucket name from Terraform outputs
#   2. Builds Next.js static export with NEXT_PUBLIC_SAME_ORIGIN_API=true
#      (all /api/* calls go through CloudFront → API Gateway, same origin)
#   3. Syncs frontend/out/ to S3 with correct cache headers
#   4. Invalidates CloudFront distribution
#
# VERIFY frontend is accessible:
#   curl -I https://<cloudfront_url>/
#   # Expected: HTTP/2 200, content-type: text/html
#
#   curl -I https://<cloudfront_url>/api/health
#   # Expected: HTTP/2 200, content-type: application/json

# ──────────────────────────────────────────────────────────────────────────────
# STEP 3B — Run the pre-cutover test suite
# ──────────────────────────────────────────────────────────────────────────────
#
# These must all pass before touching DNS:
#
#   # 1. Local smoke tests (no AWS needed)
#   make e2e-v2-local
#   # Expected: all tests pass
#
#   # 2. Contract tests
#   make test-contract
#   # Expected: all tests pass
#
#   # 3. k6 A/B performance comparison
#   #    Replace <cloudfront_url> with the actual CloudFront URL from Step 1E
#   make k6-ab \
#     K6_BASELINE_URL=https://atwc26.com \
#     ATWC26_PERF_CANDIDATE_ANALYTICS_URL=https://<cloudfront_url> \
#     ATWC26_PERF_CANDIDATE_PREDICT_URL=https://<cloudfront_url>
#   # Expected: reports/ab-diff-<timestamp>.json with overall PASS
#   # Pass criteria from docs/ops/CUTOVER.md:
#   #   - error rate <= baseline * 1.10
#   #   - p95 latency <= baseline * 1.25 on all key endpoints

# ──────────────────────────────────────────────────────────────────────────────
# STEP 3C — Verify ETL scheduler fires automatically
# ──────────────────────────────────────────────────────────────────────────────
#
# Wait up to 15 minutes after Part 1 is complete, then check:
#
#   # 1. Check EventBridge rule exists
#   aws events list-rules --name-prefix atwc26-v2-dev --region us-east-1
#
#   # 2. Check dispatch Lambda logs (should show "dispatched workflow" entries)
#   aws logs tail /aws/lambda/atwc26-v2-dev-etl-dispatch \
#     --since 30m \
#     --region us-east-1
#
#   # 3. Check GitHub Actions for auto-triggered ETL runs
#   gh run list --workflow etl.yml --limit 5
#   # Should show a recent run triggered by "schedule" (not workflow_dispatch)

# ══════════════════════════════════════════════════════════════════════════════
# PART 4 — DNS CUTOVER (go live on atwc26.com)
# ══════════════════════════════════════════════════════════════════════════════
#
# Context: v1 monolith continues running throughout. Cutover = point DNS at
# CloudFront. Rollback = point DNS back at v1. No data is lost either way.
#
# Prerequisites: ALL of Parts 1-3 complete and verified.

# ──────────────────────────────────────────────────────────────────────────────
# STEP 4A — Tag v1 before any DNS change
# ──────────────────────────────────────────────────────────────────────────────
#
# Run these commands:
#   git fetch origin main
#   git tag v1-monolith origin/main~50    # approximate SHA before v2 work
#   # Or find the exact SHA: git log --oneline origin/main | grep "before v2"
#   git push origin v1-monolith
#   # Verify:
#   git tag | grep v1

# ──────────────────────────────────────────────────────────────────────────────
# STEP 4B — Add custom domain to CloudFront
# ──────────────────────────────────────────────────────────────────────────────
#
# Prerequisite: ACM certificate in us-east-1 covering atwc26.com and www.atwc26.com
# (create in AWS Certificate Manager if it doesn't exist, then DNS-validate it)
#
# EDIT infra/terraform/envs/dev/terraform.tfvars:
# FIND:
#   # aliases             = ["atwc26.com", "www.atwc26.com"]
#   # acm_certificate_arn = "arn:aws:acm:us-east-1:..."
# REPLACE WITH:
#   aliases             = ["atwc26.com", "www.atwc26.com"]
#   acm_certificate_arn = "arn:aws:acm:us-east-1:<account>:certificate/<id>"
#
# Also update CORS now that we know the final domain:
# FIND:
#   cors_allow_origins = ["*"]
# REPLACE WITH:
#   cors_allow_origins = ["https://atwc26.com", "https://www.atwc26.com"]
#
# Update ATWC26_TFVARS GitHub secret with the new content.
#
# Trigger terraform-apply via GitHub Actions (terraform.yml → terraform-apply).

# ──────────────────────────────────────────────────────────────────────────────
# STEP 4C — Cut DNS
# ──────────────────────────────────────────────────────────────────────────────
#
# In your DNS provider (Route53 or external):
#
#   atwc26.com     CNAME  <cloudfront_domain>.cloudfront.net   TTL=300
#   www.atwc26.com CNAME  <cloudfront_domain>.cloudfront.net   TTL=300
#
# Get CloudFront domain:
#   terraform -chdir=infra/terraform/envs/dev output -raw cloudfront_url
#   # Returns: https://d1abc123xyz.cloudfront.net
#   # Use: d1abc123xyz.cloudfront.net (without https://)
#
# Wait for TTL drain (~5 minutes for short TTLs).
#
# VERIFY:
#   curl -I https://atwc26.com/api/health
#   # Expected: HTTP/2 200 from CloudFront (not v1 monolith)
#   # Check: x-cache: Hit from CloudFront (or Miss — both are fine)

# ──────────────────────────────────────────────────────────────────────────────
# STEP 4D — ROLLBACK PLAN (document before cutting over)
# ──────────────────────────────────────────────────────────────────────────────
#
# If anything is wrong after DNS cutover:
#
#   1. In DNS provider: revert CNAME to point back at v1 origin
#      atwc26.com  CNAME  <v1-origin-domain>   TTL=60
#      Wait 5 minutes for TTL drain.
#
#   2. v1 monolith has been running throughout — it never stopped.
#      All data is intact. No migration to undo.
#
#   3. Root-cause and fix in v2, then re-cut DNS.

# ══════════════════════════════════════════════════════════════════════════════
# PART 5 — NOTEBOOKS (update notebooks/ from outputs)
# ══════════════════════════════════════════════════════════════════════════════
#
# Context: Three updated notebooks were built (analysis.ipynb, history_analysis.ipynb,
# models.ipynb) and are available as downloaded files. This part copies them
# into the repo.

# ──────────────────────────────────────────────────────────────────────────────
# STEP 5A — Replace notebooks
# ──────────────────────────────────────────────────────────────────────────────
#
# Copy the three notebook files into notebooks/:
#   notebooks/analysis.ipynb         ← replaces existing (28 cells, adds §7-§12)
#   notebooks/history_analysis.ipynb ← replaces existing (12 cells, adds Elo progression)
#   notebooks/models.ipynb           ← NEW (26 cells, full model deep-dive)
#
# These notebooks are in the downloaded files from the previous conversation.
# Place them in notebooks/ in the repo root.

# ──────────────────────────────────────────────────────────────────────────────
# STEP 5B — Verify notebooks run
# ──────────────────────────────────────────────────────────────────────────────
#
# From the repo root:
#   pip install jupyter pandas pyarrow numpy matplotlib seaborn scipy xgboost scikit-learn
#   pip install -e packages/atwc26_core
#
#   # Run make etl-train to generate ML artifacts (needed for §7-§10 of analysis.ipynb)
#   make etl-train
#   # Verify these files now exist:
#   ls data/elo_ratings.json data/dc_params.json data/xgb_model.ubj data/xgb_features.json
#
#   # Execute each notebook in place (no browser needed):
#   jupyter nbconvert --to notebook --execute notebooks/analysis.ipynb --inplace
#   jupyter nbconvert --to notebook --execute notebooks/history_analysis.ipynb --inplace
#   jupyter nbconvert --to notebook --execute notebooks/models.ipynb --inplace
#   # Each should complete without errors.

# ──────────────────────────────────────────────────────────────────────────────
# STEP 5C — Commit notebooks
# ──────────────────────────────────────────────────────────────────────────────
#
#   git add notebooks/
#   git commit -m "notebooks: update analysis + history; add models deep-dive"
#   git push

# ══════════════════════════════════════════════════════════════════════════════
# PART 6 — SIMULATION IMPROVEMENTS (stage probabilities)
# ══════════════════════════════════════════════════════════════════════════════
#
# Context: The current Monte Carlo simulation outputs only P(win title) per team.
# This part adds per-round reach probabilities (P(reach QF), P(reach SF), etc.)
# which transforms the winner chart from a single bar to a round-by-round progression.
# ~80 lines added to tournament.py. No Terraform or infra changes needed.

# ──────────────────────────────────────────────────────────────────────────────
# STEP 6A — Add stage_probabilities to run_simulation output
# ──────────────────────────────────────────────────────────────────────────────
#
# File to edit: packages/atwc26_core/atwc26_core/tournament.py
#
# FIND the run_simulation function signature:
#   def run_simulation(
#       store: ...,
#       predictor: ...,
#       trials: int = DEFAULT_TRIALS,
#       seed: int | None = None,
#   ) -> dict[str, float]:
#
# REPLACE the return type annotation:
#   ) -> dict[str, float]:
# WITH:
#   ) -> dict:
#
# FIND inside run_simulation, the wins counter initialisation.
# It currently looks like: wins: dict[str, int] = defaultdict(int)
# ADD a second counter immediately after it:
#   stage_reaches: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
#
# The ROUND NAMES in the bracket are exactly:
#   "Round of 32", "Round of 16", "Quarterfinals", "Semifinals", "Final"
#   (Third Place Match is also present — include it)
#
# FIND the inner loop where a winner is determined in each knockout match.
# This is the block that sets round_results[(rname, pos, "match_winner")] = winner.
# AFTER setting winner, ADD:
#   if winner[0]:   # winner[0] is team_name (may be None for unresolved slots)
#       stage_reaches[winner[0]][rname] += 1
#
# FIND where wins[champion] += 1 is called (at the end of each trial).
# It currently looks like: wins[champion] += 1
# AFTER it, ADD:
#   if champion:
#       stage_reaches[champion]["title"] += 1
#
# FIND the return statement at the end of run_simulation.
# It currently returns: return dict(wins) or similar.
# REPLACE the entire return block with:
#
#   probabilities = {team: wins[team] / trials for team in wins}
#
#   stage_probabilities = {}
#   for team, stages in stage_reaches.items():
#       stage_probabilities[team] = {
#           stage: round(count / trials, 4)
#           for stage, count in stages.items()
#       }
#
#   return {
#       "probabilities":     probabilities,
#       "stage_probabilities": stage_probabilities,
#   }

# ──────────────────────────────────────────────────────────────────────────────
# STEP 6B — Update simulation_artifacts.py to write stage_probabilities
# ──────────────────────────────────────────────────────────────────────────────
#
# File to edit: packages/atwc26_core/atwc26_core/simulation_artifacts.py
#
# FIND where winner_probabilities.json is written.
# It currently serialises a dict with keys like: generated_at, probabilities, seed, trials.
#
# UPDATE the dict being written to include stage_probabilities.
# FIND the payload dict construction (something like):
#   payload = {
#       "generated_at": ...,
#       "probabilities": result,
#       "seed": seed,
#       "trials": trials,
#   }
# REPLACE WITH (result is now a dict with "probabilities" and "stage_probabilities" keys):
#   payload = {
#       "generated_at":       datetime.now(timezone.utc).isoformat(),
#       "probabilities":      result["probabilities"],
#       "stage_probabilities": result.get("stage_probabilities", {}),
#       "seed":               seed,
#       "trials":             trials,
#   }

# ──────────────────────────────────────────────────────────────────────────────
# STEP 6C — Update WinnerProbability type in frontend/lib/api.ts
# ──────────────────────────────────────────────────────────────────────────────
#
# File to edit: frontend/lib/api.ts
#
# FIND:
#   export type WinnerProbability = {
#     team_name: string;
#     flag_url?: string | null;
#     probability: number;
#     eliminated: boolean;
#   };
#
# REPLACE WITH:
#   export type StageProbabilities = {
#     "Round of 32"?:       number;
#     "Round of 16"?:       number;
#     "Quarterfinals"?:     number;
#     "Semifinals"?:        number;
#     "Final"?:             number;
#     "Third Place Match"?: number;
#     title?:               number;
#   };
#
#   export type WinnerProbability = {
#     team_name: string;
#     flag_url?: string | null;
#     probability: number;
#     eliminated: boolean;
#     stage_probabilities?: StageProbabilities;
#   };

# ──────────────────────────────────────────────────────────────────────────────
# STEP 6D — Update tests for the new simulation output shape
# ──────────────────────────────────────────────────────────────────────────────
#
# File to edit: tests/etl/test_simulate.py
#
# FIND any assertion that checks the return type of run_simulation.
# For example: assert isinstance(result, dict) or assert "probabilities" in result
#
# UPDATE assertions:
#   # Old (result was dict[str, float]):
#   assert isinstance(result, dict)
#   assert all(isinstance(v, float) for v in result.values())
#
#   # New (result is dict with two sub-dicts):
#   assert "probabilities" in result
#   assert "stage_probabilities" in result
#   assert all(isinstance(v, float) for v in result["probabilities"].values())
#   assert sum(result["probabilities"].values()) <= 1.0 + 1e-6

# ──────────────────────────────────────────────────────────────────────────────
# STEP 6E — Also fix api_cache/builders.py if it reads probabilities
# ──────────────────────────────────────────────────────────────────────────────
#
# File to check: packages/atwc26_core/atwc26_core/api_cache/builders.py
#
# FIND any builder that reads winner_probabilities.json or calls run_simulation.
# If it accesses result["probabilities"] directly, it is already correct.
# If it accesses result.items() or result.get(team_name) assuming a flat dict:
#   UPDATE to use result["probabilities"].items() or result["probabilities"].get(team_name)

# ──────────────────────────────────────────────────────────────────────────────
# STEP 6F — Run tests and verify
# ──────────────────────────────────────────────────────────────────────────────
#
#   make etl-local
#   PYTHONPATH=. pytest tests/etl/test_simulate.py -v
#
#   # Verify winner_probabilities.json now contains stage_probabilities:
#   python3 -c "
#   import json
#   from pathlib import Path
#   wp = json.loads(Path('data/winner_probabilities.json').read_text())
#   print('keys:', list(wp.keys()))
#   alive = [t for t,p in wp['probabilities'].items() if p > 0]
#   print('alive teams:', alive[:4])
#   if alive:
#       t = alive[0]
#       print(f'{t} stages:', wp.get('stage_probabilities',{}).get(t))
#   "
#   # Expected: keys contain stage_probabilities
#   # Expected: stage shows round-by-round probabilities for top teams

# ──────────────────────────────────────────────────────────────────────────────
# STEP 6G — Commit and push
# ──────────────────────────────────────────────────────────────────────────────
#
#   git add packages/atwc26_core/ tests/etl/test_simulate.py frontend/lib/api.ts
#   git commit -m "feat(simulate): add per-round stage probabilities to winner simulation"
#   git push
#
# The ETL pipeline will pick this up on the next run (either automatic via
# EventBridge scheduler, or manual workflow_dispatch).

# ══════════════════════════════════════════════════════════════════════════════
# PART 7 — SMALL FIXES (bugs from previous analysis)
# ══════════════════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────────────────
# STEP 7A — Fix cache_headers.py CACHE_RULES ordering bug
# ──────────────────────────────────────────────────────────────────────────────
#
# File to edit: services/shared/cache_headers.py
#
# Bug: /api/matches/760414 matches "/api/matches" (30s TTL) before
#      "/api/matches/" (86400s TTL) because startswith() uses first match.
#
# FIND the CACHE_RULES list.
# REPLACE the entire CACHE_RULES list with (specific paths BEFORE generic ones):
#
#   CACHE_RULES: list[tuple[str, str]] = [
#       # Exact paths first
#       ("/api/health",               "no-store"),
#       # Specific sub-paths before their collection parent
#       ("/api/matches/",             "public, max-age=86400, stale-while-revalidate=3600"),
#       ("/api/players/",             "public, max-age=3600,  stale-while-revalidate=600"),
#       ("/api/teams/",               "public, max-age=300,   stale-while-revalidate=120"),
#       # Collection endpoints after sub-paths
#       ("/api/standings",            "public, max-age=60,   stale-while-revalidate=30"),
#       ("/api/matches",              "public, max-age=30,   stale-while-revalidate=15"),
#       ("/api/bracket",              "public, max-age=300,  stale-while-revalidate=60"),
#       ("/api/winner-probabilities", "public, max-age=300,  stale-while-revalidate=60"),
#       ("/api/overview",             "public, max-age=120,  stale-while-revalidate=60"),
#       ("/api/teams",                "public, max-age=300,  stale-while-revalidate=120"),
#       ("/api/leaderboard",          "public, max-age=120,  stale-while-revalidate=60"),
#       ("/api/players",              "public, max-age=60,   stale-while-revalidate=30"),
#   ]

# ──────────────────────────────────────────────────────────────────────────────
# STEP 7B — Fix api.ts missing next_cursor type on players
# ──────────────────────────────────────────────────────────────────────────────
#
# File to edit: frontend/lib/api.ts
#
# FIND:
#   players: (q: string) => get<{ count: number; players: Player[] }>(`/api/players?${q}`),
# REPLACE WITH:
#   players: (q: string) => get<{
#     count:       number;
#     page_size:   number;
#     next_cursor: string | null;
#     players:     Player[];
#   }>(`/api/players?${q}`),

# ──────────────────────────────────────────────────────────────────────────────
# STEP 7C — Bump ETL simulate trials CI from 100 to 1000
# ──────────────────────────────────────────────────────────────────────────────
#
# File to edit: .github/workflows/ci.yml
#
# FIND inside the "etl" job:
#   ATWC26_SIMULATE_TRIALS: "100"
# REPLACE WITH:
#   ATWC26_SIMULATE_TRIALS: "1000"
#
# NOTE: etl.yml already uses 1000 — this fixes ci.yml only.

# ──────────────────────────────────────────────────────────────────────────────
# STEP 7D — Commit all fixes
# ──────────────────────────────────────────────────────────────────────────────
#
#   git add services/shared/cache_headers.py frontend/lib/api.ts .github/workflows/ci.yml
#   git commit -m "fix: cache_headers ordering, api.ts cursor type, ci simulate trials"
#   git push

# ══════════════════════════════════════════════════════════════════════════════
# PART 8 — AFTER CUTOVER: future phases (not urgent, do after tournament ends)
# ══════════════════════════════════════════════════════════════════════════════

# Phase U — Prod Terraform env
#   Copy infra/terraform/envs/dev/ to infra/terraform/envs/prod/
#   Change: name_prefix="atwc26-v2-prod", environment="prod"
#   Use separate state key: "atwc26-v2/prod/terraform.tfstate"
#   Add acm_certificate_arn for prod cert, aliases=["atwc26.com","www.atwc26.com"]
#   Add deploy-prod.yml workflow with manual approval gate (environment: production)

# Phase V — k6 threshold gate
#   Edit k6/lib/thresholds.js to add:
#     http_req_duration: ["p(95)<500"],
#     http_req_failed: ["rate<0.01"],
#   Edit .github/workflows/performance.yml to add --exit-on-error to k6 run command
#   This makes CI fail on performance regression instead of just logging it

# Phase W — S3 lifecycle + Lambda reserved concurrency
#   Edit infra/terraform/modules/s3-data/main.tf:
#     Add lifecycle rule: raw/ prefix → INTELLIGENT_TIERING after 30 days
#   Edit infra/terraform/modules/lambda-analytics/main.tf:
#     Add: reserved_concurrent_executions = 2
#   Prevents cold-start storm on traffic spike while CloudFront absorbs the load

# ══════════════════════════════════════════════════════════════════════════════
# VERIFICATION SUMMARY — run these after all parts are complete
# ══════════════════════════════════════════════════════════════════════════════

# 1. ETL auto-runs every 15 minutes:
#    gh run list --workflow etl.yml --limit 10
#    # Should show runs with trigger "schedule"

# 2. Lambda analytics reads from DynamoDB (not DataStore):
#    curl https://atwc26.com/api/standings
#    # Should respond in < 300ms (DynamoDB read, not parquet load)

# 3. ECS predict is warm (no cold start):
#    time curl -X POST https://atwc26.com/api/predict \
#      -H "Content-Type: application/json" \
#      -d '{"team_a":{"team_name":"Belgium","players":[]},"team_b":{"team_name":"Spain","players":[]}}'
#    # Should respond in < 200ms (warm ECS, not Lambda cold start)
#    # NOTE: empty players array may return 400 — that's fine, we're testing latency

# 4. CloudFront caches match detail correctly (should be 86400s, not 30s):
#    curl -I https://atwc26.com/api/matches/760414
#    # Check: cache-control: public, max-age=86400

# 5. Notebooks run:
#    jupyter nbconvert --to notebook --execute notebooks/models.ipynb --inplace
#    # Should complete without errors

# 6. Stage probabilities in winner simulation:
#    python3 -c "
#    import json; from pathlib import Path
#    wp = json.loads(Path('data/winner_probabilities.json').read_text())
#    print('stage_probabilities present:', 'stage_probabilities' in wp)
#    alive = [t for t,p in wp['probabilities'].items() if p > 0]
#    if alive: print(alive[0], wp['stage_probabilities'].get(alive[0]))
#    "