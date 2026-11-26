# Deploying (untested here: needs your cloud account)

Cloud Run (GCP) with the in-memory store and extractive/offline stack, or an external OpenAI-compatible LLM:

    gcloud run deploy docpilot --source . --region <region> --allow-unauthenticated=false \
      --set-env-vars DOCPILOT_API_KEYS=<key>,DOCPILOT_LLM_BASE_URL=<url>,DOCPILOT_SMALL_MODEL=<model> \
      --set-secrets DOCPILOT_LLM_API_KEY=<secret>:latest

Then `python scripts/smoke_api.py https://<service-url> <key>` and
`k6 run -e BASE=https://<service-url> -e API_KEY=<key> loadtest/ask.js`.
In-process rate limiting is per instance; use Redis if you run more than one instance (your LLM Gateway project already has the Lua limiter).
Record the live URL, p95 latency from k6 and the date you measured it in the README.
