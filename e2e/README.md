# Pre-ONE End-to-End Integration Harness (TASK-013)

Reproducible, hermetic end-to-end integration test harness for POSCENTER Loyalty before connecting to physical 1C / POSCENTER ONE infrastructure.

## Architecture

```
TestLoyaltySource (in-memory DTOs, zero 1C metadata assumptions)
       ↓
Real Agent Runtime (AgentRuntime + StateStore SQLite + ProcessLock)
       ↓
Real HTTP Cloud Client (HttpCloudClient + X-Agent-Key)
       ↓
Real Uvicorn ASGI Process (127.0.0.1:<ephemeral-port>)
       ↓
Real PostgreSQL (poscenter_loyalty_e2e_test with all migrations) + Real Redis
       ↓
Customer-facing & Admin APIs (FastAPI + JWT + Wappi Webhooks)
```

## Critical Boundaries

1. **Test-Double Boundary**:
   - `TestLoyaltySource` is located strictly in `e2e/source.py`.
   - Production code path contains NO fake ONE connector, NO test bypasses, and NO `/test/*` endpoints.
   - Statuses remain:
     - `REAL_WINDOWS_SERVICE = NOT VERIFIED`
     - `REAL_V83_COMCONNECTOR = NOT VERIFIED`
     - `REAL_ONE_CONNECTION = NOT VERIFIED`
     - `REAL_ONE_METADATA_DISCOVERY = NOT VERIFIED`
     - `REAL_ONE_MAPPING = NOT VERIFIED`

2. **Real Infrastructure Invariants**:
   - Real PostgreSQL engine (asyncpg) with all 9 Alembic migrations up to head.
   - Real Redis server (aioredis).
   - Real Uvicorn ASGI HTTP backend subprocess.
   - Real Agent HTTP client and SQLite checkpointing.
   - Zero mocked networks or monkeypatched database sessions.

## Execution

Canonical runner:
```bash
./scripts/run_pre_one_e2e.sh
```

Or via pytest:
```bash
PYTHONPATH=".:backend:agent/src" pytest -v -s -o asyncio_mode=auto e2e/test_pre_one_flow.py
```
