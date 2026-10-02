# POSCENTER Loyalty Cloud - Operations Runbook

## 1. System Scope & Verification Status

> [!IMPORTANT]
> Operations teams must observe the following documented project boundaries:
> - **Real SMS adapter = NOT IMPLEMENTED**: SMS delivery is disabled (`SMS_PROVIDER_MODE=disabled`). User authentication relies on WhatsApp messages via Wappi.
> - **Real ONE / TASK-009B = DEFERRED**: Real POSCENTER ONE database discovery and live catalog integration are deferred pending on-premise hardware validation.
> - **Production TLS deployment = NOT VERIFIED/NOT DEPLOYED**: Smoke verification runs behind Nginx over local HTTP port 8080. Live infrastructure must configure edge TLS termination (e.g., AWS ALB, Cloudflare, Let's Encrypt).
> - **SLA 99% = NOT VERIFIED**: Uptime targets are not formally validated.
> - **p95 <= 500 ms = NOT VERIFIED**: Response latency under peak production load is unverified.

---

## 2. Health Probes & Monitoring

The application provides two standard HTTP endpoints:

### Liveness Probe (`GET /health/live`)
- **Purpose**: Kubernetes / Docker orchestrator liveness check.
- **Behavior**: Returns `200 OK` with `{"status": "ok"}` if the Python ASGI process is accepting requests. Does not query database or external systems.
- **Fail Action**: Restart container if liveness fails repeatedly.

### Readiness Probe (`GET /health/ready`)
- **Purpose**: Traffic routing readiness check.
- **Behavior**: Verifies connectivity and query execution on PostgreSQL and Redis, and checks for pending database migrations.
- **Return Codes**:
  - `200 OK` when both database and cache are operational and no migrations are pending:
    ```json
    {
      "status": "ready",
      "components": {
        "database": "ok",
        "redis": "ok"
      }
    }
    ```
  - `503 Service Unavailable` if either dependency is unhealthy:
    ```json
    {
      "status": "not_ready",
      "components": {
        "database": "unavailable",
        "redis": "ok"
      }
    }
    ```
- **Security**: Readiness probe responses strictly omit raw connection URLs, credentials, and internal error strings.

---

## 3. Log Inspection & Troubleshooting

- All production logs are emitted in structured JSON format (`LOG_FORMAT=json`).
- Request traces are correlated via `X-Request-ID` (preserved if incoming, or generated as a UUID).
- **PII & Credential Redaction**: Passwords, OTP codes, JWTs, agent keys, connection strings, phone numbers, barcodes, and cookies are automatically sanitized before output.
- **Inspecting logs**:
  ```bash
  # View backend logs
  docker compose -f deploy/compose.prod-smoke.yml logs -f backend

  # View proxy access logs (JSON formatted, query strings excluded)
  docker compose -f deploy/compose.prod-smoke.yml logs -f proxy
  ```

---

## 4. Incident Response & Procedures

### Incident: Database Unavailable (`503 on /health/ready`)
1. Verify PostgreSQL container status:
   ```bash
   docker compose -f deploy/compose.prod-smoke.yml ps postgres
   ```
2. Check PostgreSQL connection and logs:
   ```bash
   docker compose -f deploy/compose.prod-smoke.yml logs --tail=50 postgres
   ```
3. Test connectivity directly using `pg_isready`:
   ```bash
   docker exec -it loyalty_postgres pg_isready -U poscenter_app -d poscenter_loyalty_smoke
   ```

### Incident: Migration Pending (`503 on /health/ready`)
1. Trigger migration service:
   ```bash
   docker compose -f deploy/compose.prod-smoke.yml run --rm migration
   ```
2. Verify schema status:
   ```bash
   docker exec -it loyalty_postgres psql -U poscenter_app -d poscenter_loyalty_smoke -c "SELECT version_num FROM alembic_version;"
   ```

### Incident: Redis Disconnected (`503 on /health/ready`)
1. Check Redis container health:
   ```bash
   docker exec -it loyalty_redis redis-cli ping
   ```
2. Restart Redis container if unresponsive:
   ```bash
   docker compose -f deploy/compose.prod-smoke.yml restart redis
   ```
