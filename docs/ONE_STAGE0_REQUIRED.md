# POSCENTER ONE Stage 0 Discovery Requirement

> [!IMPORTANT]
> **Real POSCENTER ONE metadata mapping is NOT implemented.**
> **Exact 1C object names must be discovered from a pilot ONE database.**

---

## 1. Context & Architectural Constraint

In accordance with Section 1 of `TZ_loyalty_app_v1.1` and project core invariants:
* **POSCENTER ONE (1C:Enterprise 8.3)** is the sole source of truth for loyalty balances and transactions.
* The Cloud Backend maintains a mirror of the data synchronized by the on-premises Windows Agent via `V83.COMConnector`.
* Exact metadata object and field names in 1C are **not finalized** in the base specification and must be determined from a pilot copy of the client infobase.

---

## 2. Prohibition of Speculative Metadata Names

In the Windows Agent codebase (`agent/`), it is strictly forbidden to use guessed or speculative 1C object names.

**Rule:** If an exact metadata object name is not verified and recorded during Stage 0 Discovery against a real pilot database, it does not exist for the system.

---

## 3. Stage 0 Discovery Checklist for Pilot POSCENTER ONE Database

Before implementing the real COM adapter in **TASK-009**, the integration engineer must discover and record:

1. **Card Metadata:**
   - Exact card metadata object name
   - Exact barcode field name (13-digit string)
   - Exact phone field name
   - Exact customer full name field name
   - Exact blocked / deletion mark field name
   - Exact timestamp / change version field name for delta extraction

2. **Balance Register:**
   - Exact balance register name
   - Exact card dimension name
   - Exact balance resource name

3. **Transaction / Movement Source:**
   - Exact transaction/movement source
   - Exact stable source identifiers (unique movement key)
   - Exact timestamp field name
   - Exact operation type indicator (accrual / redemption)
   - Exact amount and balance after fields
   - Exact receipt / store reference fields

---

## 4. Opaque Cursor Contract for TASK-009

The real ONE adapter implemented in TASK-009 must construct stream cursors conforming to the following mandatory contract:

- **Deterministic**: Produces the identical cursor for identical pagination positions.
- **Opaque to Runtime**: Treated by the agent runtime as an arbitrary opaque string token without internal parsing.
- **Zero PII**: Strictly prohibited from containing customer phone numbers, full names, or card barcodes.
- **Zero Credentials**: Strictly prohibited from containing passwords, connection strings, or infobase authentication data.
- **Stateless & Process-Independent**: Does not depend on volatile process memory; fully restorable from SQLite persistence upon agent restart.

---

## 5. Default Runtime Behavior

Until Stage 0 Discovery is completed, the Windows Agent defaults to:
```text
ONE_ADAPTER_MODE=stub
```
In this mode, the agent starts the service, performs Heartbeat reporting to the Cloud API, and explicitly halts extraction attempts with:
`ONE_MAPPING_NOT_CONFIGURED: POSCENTER ONE metadata mapping is not yet configured. See docs/ONE_STAGE0_REQUIRED.md`.
