# POSCENTER Loyalty Windows Agent

Windows background agent and synchronization foundation for POSCENTER Loyalty.

## Overview

The `poscenter-loyalty-agent` runs on-premises alongside POSCENTER ONE (1C:Enterprise). It provides:
- Reliable, durable at-least-once synchronization of loyalty cards and bonus transactions to the Cloud API.
- Opaque cursor checkpointing in local SQLite (`agent_state.db`).
- Zero PII / secret persistence.
- Automatic retry with exponential backoff and jitter.
- Stalled cursor detection and prevention.
- Independent background heartbeat loop.
- Windows Service wrapper (`win32serviceutil.ServiceFramework`) with full cross-platform compatibility.
- Safe default `ONE_ADAPTER_MODE=stub` requiring Stage 0 metadata discovery (`docs/ONE_STAGE0_REQUIRED.md`).

## Quickstart

### Installation
```bash
pip install -e .
```

### Validate Configuration
```bash
poscenter-loyalty-agent check-config
```

### Run Foreground Agent
```bash
poscenter-loyalty-agent run
```

### View Status
```bash
poscenter-loyalty-agent status
```

### Run Tests
```bash
pytest tests/ -v
```

## Documentation
- POS-сервис динамического QR для Cash (LAN, выключен по умолчанию): [POS_QR_INTEGRATION.md](../docs/POS_QR_INTEGRATION.md)
- Complete Architecture: [AGENT_ARCHITECTURE.md](../docs/AGENT_ARCHITECTURE.md)
- Stage 0 Discovery Requirements: [ONE_STAGE0_REQUIRED.md](../docs/ONE_STAGE0_REQUIRED.md)
