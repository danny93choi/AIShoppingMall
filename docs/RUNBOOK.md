# Runbook

## Local startup

Run `make dev`, then verify `GET http://localhost:8000/health/ready`.

## Readiness failure

1. Run `docker compose ps` and inspect PostgreSQL and Redis health.
2. Run `docker compose logs postgres redis api`.
3. Verify `DATABASE_URL` and `REDIS_URL` point to Compose service names from inside containers.
4. Do not expose raw credentials or connection URLs in incident notes.

Operational recovery procedures required by later phases will be added with their infrastructure.

