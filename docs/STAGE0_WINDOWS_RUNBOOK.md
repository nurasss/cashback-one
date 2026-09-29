# Stage 0 Windows Execution Runbook — POSCENTER ONE

This runbook specifies the exact procedure for executing **Stage 0 Discovery (Phase B)** on a Windows host with live access to the pilot **POSCENTER ONE** infobase (1C:Enterprise 8.3).

---

## 1. Safety & Critical Rules

> [!CAUTION]
> **Strictly READ-ONLY Execution:**
> - Never execute write, delete, update, or posting methods in 1C.
> - Never mutate infobase data, documents, catalogs, or registers.
> - Zero customer PII or raw secrets must enter reports or mapping files.
> - `ONE_ADAPTER_MODE="stub"` must remain configured until Stage 0 discovery and verified mapping are accepted.

> [!WARNING]
> **Secret Hygiene:**
> - **Never** echo, print, commit, or attach `ONE_CONNECTION_STRING`.
> - Do not pass connection strings on the command line; use environment variables only.
> - Output directory `stage0_output/` is ignored by Git and must remain uncommitted.

---

## 2. Host Prerequisites

1. **Operating System:** Windows 10/11 or Windows Server (x64).
2. **Python Environment:** Python 3.11+ installed and accessible in PowerShell.
3. **pywin32:** Installed in the active virtual environment:
   ```powershell
   pip install pywin32
   ```
4. **1C:Enterprise 8.3 COM Connector:**
   - 1C:Enterprise 8.3 platform client installed.
   - `comcntr.dll` registered as a COM server in Windows:
     ```cmd
     regsvr32 "C:\Program Files\1cv8\8.3.xx.xxxx\bin\comcntr.dll"
     ```
5. **1C Credentials:** A dedicated read-only 1C user account with technical rights to read metadata, catalogs, registers, and documents in the target pilot infobase.

---

## 3. CLI Contract & Capabilities

The Stage 0 CLI commands are exposed via `poscenter-loyalty-agent stage0` (or `python -m poscenter_loyalty_agent.main stage0`):

| Command | Arguments | Purpose |
|---|---|---|
| `stage0 check-environment` | `[--output-dir OUTPUT_DIR]` | Preflight verification of host OS, pywin32, `V83.COMConnector`, and 1C connection. |
| `stage0 probe-metadata` | `[--output-dir OUTPUT_DIR] [--use-fake-provider]` | Strictly read-only extraction of technical 1C metadata inventory. |
| `stage0 validate-mapping` | `mapping_file [--require-verified]` | Validate schema, integrity fingerprint, safety, and verification states of a mapping artifact. |

> [!NOTE]
> **Important Contract Clarifications:**
> - **No `--connection-string` CLI flag exists.** The connection string is read strictly from the `ONE_CONNECTION_STRING` environment variable (via `AgentSettings`).
> - **No `stage0 generate-mapping` CLI command exists.** The file `stage0_mapping.json` is constructed based on confirmed read-only findings from `metadata_inventory.json` / `metadata_inventory.md`, and then validated using `validate-mapping`.

---

## 4. Step-by-Step Execution Procedure

Open PowerShell as an Administrator or authorized service user on the Windows host.

### Step 1: Configure Environment Variables

```powershell
Set-Location -Path "C:\path\to\cashback-one"

$env:PYTHONPATH="agent/src"
$env:AGENT_ENV="development"
$env:ONE_ADAPTER_MODE="stub"

# Set connection string securely (do not print or echo this value)
$env:ONE_CONNECTION_STRING='Srvr="1c-server.local";Ref="pilot_poscenter_one";Usr="loyalty_readonly";Pwd="<SECRET_PASSWORD>";'
```

### Step 2: Verify Host & Connection Readiness

Run the preflight environment check:

```powershell
python -m poscenter_loyalty_agent.main stage0 check-environment
```

**Expected verification status for Windows pilot after preflight check:**
```text
REAL_WINDOWS_SERVICE:        NOT VERIFIED
REAL_V83_COMCONNECTOR:       VERIFIED
REAL_ONE_CONNECTION:         VERIFIED
REAL_ONE_METADATA_DISCOVERY: NOT VERIFIED
REAL_ONE_MAPPING:            NOT VERIFIED
```

> [!NOTE]
> **Windows Host vs Windows Service Boundary:**
> Running Stage 0 on Windows verifies only platform/COM/connectivity conditions.
> It does **NOT** verify Windows Service installation, SCM registration, start/stop behavior, recovery behavior, or service-account execution.
> `REAL_WINDOWS_SERVICE` remains `NOT VERIFIED` throughout Stage 0 (including after `probe-metadata`), and can only become `VERIFIED` after an independent Windows Service lifecycle test.

Artifact created: `stage0_output/environment.json`.

---

### Step 3: Probe Real POSCENTER ONE Metadata (Read-Only)

Execute the technical metadata probe against the live 1C infobase:

```powershell
python -m poscenter_loyalty_agent.main stage0 probe-metadata
```

What this command does:
1. Connects to 1C via `V83.COMConnector` in strictly read-only mode.
2. Extracts technical object names, field types, and synonyms across targeted categories (`Catalogs`, `AccumulationRegisters`, `InformationRegisters`, `Documents`).
3. Executes zero write/post operations.
4. Sanitizes all output to ensure zero customer records, phone numbers, or passwords leak into artifacts.
5. Elevates `REAL_ONE_METADATA_DISCOVERY` to `VERIFIED` upon success.
6. Writes sanitized reports to `stage0_output/`:
   - `stage0_output/metadata_inventory.json`
   - `stage0_output/metadata_inventory.md`
   - `stage0_output/environment.json`
   - `stage0_output/STAGE0_DISCOVERY_REPORT.md`

---

### Step 4: Construct and Validate Stage 0 Mapping

1. Inspect `stage0_output/metadata_inventory.md` and candidate tables.
2. Create `stage0_output/stage0_mapping.json` using `agent/stage0_mapping.example.json` as a structural reference.
3. In `stage0_output/stage0_mapping.json`:
   - Set `"artifact_kind": "real_discovery"`.
   - Map exact confirmed 1C object names for Cards and Transactions.
   - Provide concrete evidence for each verified field.
   - For all mandatory P0 fields, set `"state": "VERIFIED"`.
   - Calculate and set `"mapping_sha256"` (or let the validator compute the fingerprint).

4. Validate the resulting mapping:

```powershell
# Standard structural & schema validation
python -m poscenter_loyalty_agent.main stage0 validate-mapping `
    stage0_output/stage0_mapping.json

# Strict production readiness validation (enforces real_discovery & P0 VERIFIED)
python -m poscenter_loyalty_agent.main stage0 validate-mapping `
    stage0_output/stage0_mapping.json `
    --require-verified
```

---

## 5. Troubleshooting

- **`pywintypes.com_error: (-2147221005, 'Invalid class string', ...)`:**
  `V83.COMConnector` is not registered. Run `regsvr32 comcntr.dll` from the 1C installation directory.
- **Connection failure (authentication / network):**
  Verify the server hostname, base name (`Ref`), user credentials, and network firewall rules for 1C ports (default `1540`, `1541`, `1560:1591`).
- **Probe failure:**
  If probing fails for any reason, the command exits with code `1`, logs the technical failure reason, and preserves `REAL_ONE_METADATA_DISCOVERY = NOT VERIFIED` in all output artifacts.
