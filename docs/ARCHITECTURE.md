# POSCENTER Loyalty — High-Level Architecture

## Overview

POSCENTER Loyalty provides customer loyalty card functionality (QR/barcode scanning, cashback balance, and transactions history) for businesses operating on POSCENTER ONE (1C:Enterprise 8.3).

## Data Flow

```text
       POSCENTER ONE (1C 8.3)
                 │
                 ▼ (COM V83.COMConnector, read-only, periodic poll)
             ONE Agent (Windows Service)
                 │
                 ▼ (Outbound HTTPS push: cards, transactions, heartbeat)
           Cloud Backend (FastAPI, PostgreSQL, Redis)
                 │
        ┌────────┴────────┐
        ▼                 ▼
   Mobile App        Admin Panel
(React Native/Expo)   (Web UI)
```

## Core Architectural Invariant

**POSCENTER ONE is the sole source of truth for bonus balances and bonus operations.**

The Cloud Backend stores a mirror of the data. The Mobile App only reads the balance and transactions history. Card issuance and transactions originate in POSCENTER ONE.
The Cloud Backend does not act as an independent balance engine and does not support arbitrary client-side balance mutations.
