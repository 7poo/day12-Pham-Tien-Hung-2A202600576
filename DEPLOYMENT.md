# Deployment Information

## Current Status

The service is production-ready locally, but no public cloud deployment was performed because
this workspace does not contain Railway, Render, or GCP credentials.

## Local URL

`http://localhost:8000`

## Platform Configuration

- Railway: `06-lab-complete/railway.toml`
- Render: `06-lab-complete/render.yaml`
- Docker Compose: `06-lab-complete/docker-compose.yml`

## Verification Commands

```bash
cd 06-lab-complete
docker compose up --build -d
curl http://localhost:8000/health
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: dev-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
docker compose down
```

## Required Production Variables

- `AGENT_API_KEY`
- `JWT_SECRET`
- `REDIS_URL`
- `ENVIRONMENT=production`
- `PORT`
- `RATE_LIMIT_PER_MINUTE=10`
- `MONTHLY_BUDGET_USD=10`

Replace this section with the public URL and screenshots after deploying with an authenticated
cloud account.
