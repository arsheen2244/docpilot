# Deploying

## CI/CD (GitHub Actions, `.github/workflows/ci.yml`)

| Job | Runs on | What it does |
|---|---|---|
| `test` | every push and pull request | `pytest`, eval gate on the dev split (fails below the floors in the workflow), smoke test of a live uvicorn |
| `docker` | after `test` | builds the image, runs the container, smoke-tests it |
| `publish` | push to `main` or a `v*` tag | pushes `ghcr.io/<owner>/docpilot` tagged `sha-<commit>`, `latest` (main) and the version (tags) |
| `deploy` | push to `main`, **only if** the `GCP_PROJECT_ID` repository variable is set | deploys to Cloud Run and smoke-tests the live URL |

`publish` needs no setup: it uses the built-in `GITHUB_TOKEN`. The image is private by default; make it public under
the package's settings on GitHub if you want others to pull it.

Release a version: `git tag v0.1.0`, then `git push origin v0.1.0`.

## One-time setup for the Cloud Run deploy job (needs your GCP account)

1. Create a project and enable the APIs:

       gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com

2. Store the API key DocPilot will accept in Secret Manager:

       printf "%s" "<your-api-key>" | gcloud secrets create docpilot-api-keys --data-file=-

3. Create a service account for GitHub with `roles/run.admin`, `roles/cloudbuild.builds.editor`,
   `roles/artifactregistry.admin`, `roles/storage.admin`, `roles/iam.serviceAccountUser` and
   `roles/secretmanager.secretAccessor`. Download a JSON key for it.
   (Workload Identity Federation avoids a long-lived key; swap the `auth` step's `credentials_json` for
   `workload_identity_provider` + `service_account` if you set it up.)

4. In the GitHub repo, under Settings → Secrets and variables → Actions:
   - Variables: `GCP_PROJECT_ID` (required; turns the job on) and `GCP_REGION` (optional, default `us-central1`).
   - Secrets: `GCP_SA_KEY` (the JSON key) and `DOCPILOT_API_KEY` (the same key as step 2, for the post-deploy smoke test).

The next push to `main` deploys. The service runs with `--max-instances=1` because the rate limiter is in-process
(see "Known weaknesses" in `REMAINING_WORK.md`); raise it after moving the limiter to Redis.

To use a real LLM, add `DOCPILOT_LLM_BASE_URL` and `DOCPILOT_SMALL_MODEL` with `env_vars:` and `DOCPILOT_LLM_API_KEY`
as another Secret Manager entry under `secrets:` in the deploy step.

## Manual deploy (without CI)

    gcloud run deploy docpilot --source . --region <region> --allow-unauthenticated --max-instances=1 \
      --set-secrets DOCPILOT_API_KEYS=docpilot-api-keys:latest

## After deploying

    python scripts/smoke_api.py https://<service-url> <key>
    k6 run -e BASE=https://<service-url> -e API_KEY=<key> loadtest/ask.js

For an honest p95, deploy with `DOCPILOT_CACHE=0` and a raised `DOCPILOT_RATE_PER_MIN` for the run (see the comment at
the top of `loadtest/ask.js`). Record the live URL, the p95 from k6, the instance size and the date in the README.
