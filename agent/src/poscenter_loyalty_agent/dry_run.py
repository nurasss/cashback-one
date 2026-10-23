"""Standalone Dry-Run runner and inspection simulator for POSCENTER Loyalty Agent.

CRITICAL SECURITY AND ARCHITECTURAL GUARANTEES:
1. Pure read-only queries ('ВЫБРАТЬ') to 1C infobase.
2. Completely networkless: DryRunCloudClient simulates Cloud API without opening any sockets.
3. Isolated state: uses dedicated SQLite database (agent_state_dryrun.db) and HMAC key
   located in C:\\cashback-stage0\\dryrun\\ (never touches production ProgramData).
4. Zero PII leakage: all reports and console outputs contain strictly aggregated metrics.
   Verified via validate_safe_output and 30-sample barcode/phone database scan.
"""

from __future__ import annotations

import asyncio
import ctypes
import logging
import os
import random
import sys
import time
from collections import defaultdict
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.models import (
    CardsSyncPayload,
    CardsSyncResult,
    CardSyncItem,
    HeartbeatPayload,
    HeartbeatResult,
    TransactionsSyncPayload,
    TransactionsSyncResult,
    TransactionSyncItem,
)
from poscenter_loyalty_agent.one_com_source import OneComLoyaltySource
from poscenter_loyalty_agent.one_mapping import OneMappingConfig, load_one_mapping
from poscenter_loyalty_agent.stage0.sanitizer import validate_safe_output
from poscenter_loyalty_agent.state_store import StateStore

logger = logging.getLogger("poscenter_loyalty_agent.dry_run")


def get_process_rss_mb() -> float:
    """Return resident set size (RSS) memory of the current process in Megabytes."""
    if sys.platform == "win32":
        try:
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), ctypes.sizeof(pmc)):
                return float(pmc.WorkingSetSize) / (1024 * 1024)
        except Exception:
            pass
    return 0.0


class DryRunCloudClient:
    """Networkless in-memory cloud client that simulates Cloud API responses and records batches."""

    def __init__(self) -> None:
        self.received_cards: list[CardSyncItem] = []
        self.received_tx: list[TransactionSyncItem] = []
        self.cards_batch_count: int = 0
        self.tx_batch_count: int = 0
        self.heartbeat_count: int = 0

    async def sync_cards(self, payload: CardsSyncPayload) -> CardsSyncResult:
        self.received_cards.extend(payload.cards)
        self.cards_batch_count += 1
        return CardsSyncResult(
            received=len(payload.cards),
            created=len(payload.cards),
            updated=0,
            ignored_stale=0,
        )

    async def sync_transactions(self, payload: TransactionsSyncPayload) -> TransactionsSyncResult:
        self.received_tx.extend(payload.transactions)
        self.tx_batch_count += 1
        return TransactionsSyncResult(
            received=len(payload.transactions),
            created=len(payload.transactions),
            duplicates=0,
        )

    async def send_heartbeat(self, payload: HeartbeatPayload) -> HeartbeatResult:
        self.heartbeat_count += 1
        return HeartbeatResult(status="ok")

    async def close(self) -> None:
        pass


@dataclass
class DryRunResult:
    """Holds all aggregated dry-run results and verification checks."""

    # Durations (seconds)
    duration_cycle1: float = 0.0
    duration_cycle2: float = 0.0
    duration_cycle3: float = 0.0
    duration_scenario_d: float = 0.0
    total_duration: float = 0.0
    rss_mb_end: float = 0.0

    # Cycle 1 counts
    cycle1_cards_sent: int = 0
    cycle1_tx_sent: int = 0

    # Cards aggregates
    cards_total_in_1c: int = 0
    cards_skipped_empty_code: int = 0
    cards_skipped_non_digits: int = 0
    cards_skipped_too_short: int = 0
    cards_skipped_too_long: int = 0
    cards_phone_null_count: int = 0
    cards_blocked_count: int = 0
    cards_balance_positive_count: int = 0
    cards_balance_zero_count: int = 0
    cards_balance_negative_count: int = 0
    cards_balance_clamped: int = 0

    # Transactions aggregates
    tx_total_in_1c: int = 0
    tx_accrual_count: int = 0
    tx_redemption_count: int = 0
    tx_skipped_empty_code: int = 0
    tx_skipped_non_digits: int = 0
    tx_skipped_too_short: int = 0
    tx_skipped_too_long: int = 0
    tx_skipped_zero_amount: int = 0
    tx_skipped_unknown_type: int = 0
    tx_filtered_already_sent: int = 0
    tx_balance_after_clamped: int = 0
    tx_min_occurred_str: str = ""
    tx_max_occurred_str: str = ""
    tx_filled_receipt_ref_percent: float = 0.0
    tx_filled_store_percent: float = 0.0

    # Idempotency Cycles 2 & 3
    cycle2_cards_sent: int = 0
    cycle2_tx_sent: int = 0
    cycle3_cards_sent: int = 0
    cycle3_tx_sent: int = 0

    # Scenario D (Cloud Failure Recovery)
    scenario_d_cards_sent: int = 0
    scenario_d_tx_sent: int = 0

    # Balance Reconciliation
    reconciliation_cards_checked: int = 0
    reconciliation_discrepancies: int = 0
    reconciliation_max_discrepancy: Decimal = Decimal("0")
    reconciliation_reasons: dict[str, int] = field(default_factory=dict)
    negative_clamp_check: str = "PASS"

    # Security & PII Verification
    pii_db_check: str = "PASS"
    pii_key_check: str = "PASS"
    pii_log_check: str = "PASS"
    sanitizer_check: str = "PASS"


def _tx_sort_key(tx: TransactionSyncItem) -> tuple[datetime, str, int]:
    """Sort key matching adapter order: (occurred_at, UUID регистратора, int(НомерСтроки))."""
    parts = tx.external_id.rsplit(":", 1)
    if len(parts) == 2:
        try:
            return (tx.occurred_at, parts[0], int(parts[1]))
        except ValueError:
            pass
    return (tx.occurred_at, tx.external_id, 0)


async def run_sync_cycle(
    source: OneComLoyaltySource,
    client: DryRunCloudClient,
    cards_limit: int,
    tx_limit: int,
) -> tuple[int, int]:
    """Execute complete pagination loop for cards and transactions with simulated 2xx ACK."""
    cards_sent = 0
    tx_sent = 0

    # 1. Cards pagination
    while True:
        cursor = source.state_store.get_cursor("cards")
        cards_batch = await source.fetch_cards(cursor=cursor, limit=cards_limit)
        if cards_batch.items:
            cards_sent += len(cards_batch.items)
            await client.sync_cards(CardsSyncPayload(cards=cards_batch.items))
            source.state_store.commit_cursor("cards", cards_batch.next_cursor, synced_at=datetime.now(UTC))
        if not cards_batch.has_more:
            break

    # 2. Transactions pagination
    while True:
        cursor = source.state_store.get_cursor("transactions")
        tx_batch = await source.fetch_transactions(cursor=cursor, limit=tx_limit)
        if tx_batch.items:
            tx_sent += len(tx_batch.items)
            await client.sync_transactions(TransactionsSyncPayload(transactions=tx_batch.items))
            source.state_store.commit_cursor("transactions", tx_batch.next_cursor, synced_at=datetime.now(UTC))
        if not tx_batch.has_more:
            break

    return cards_sent, tx_sent


async def execute_dry_run(
    settings: AgentSettings,
    mapping_config: OneMappingConfig | None = None,
    com_connector: Any = None,
    dryrun_dir: Path | None = None,
    report_file_path: Path | None = None,
    clean_existing: bool = True,
) -> DryRunResult:
    """Execute the full 4-phase standalone dry-run inspection scenario."""
    base_dir = dryrun_dir or Path(r"C:\cashback-stage0\dryrun")
    base_dir.mkdir(parents=True, exist_ok=True)

    db_path = base_dir / "agent_state_dryrun.db"
    key_path = base_dir / "agent_state_dryrun.key"
    log_path = base_dir / "dryrun.log"
    report_path = report_file_path or Path(r"C:\cashback-stage0\dryrun_report.md")

    # Clean existing state artifacts in dryrun directory to start fresh
    if clean_existing:
        for f in (db_path, key_path, log_path, base_dir / "agent_state_dryrun.db-wal", base_dir / "agent_state_dryrun.db-shm"):
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass

    # Ensure mapping is loaded
    mapping_path = settings.one_mapping_path
    if mapping_path is None or not mapping_path.exists():
        fallback_m = Path(r"C:\cashback-stage0\stage0_mapping.json")
        if fallback_m.exists():
            mapping_path = fallback_m
    if mapping_config is None:
        assert mapping_path is not None
        mapping_config = load_one_mapping(mapping_path, require_verified=False)

    # Derive connection string strictly from env if present
    conn_str = os.environ.get("ONE_CONNECTION_STRING") or settings.one_connection_string
    if not conn_str and sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as k:
                conn_str, _ = winreg.QueryValueEx(k, "ONE_CONNECTION_STRING")
        except Exception:
            pass

    # If com_connector was not passed in, but conn_str is available, initialize shared COM connection
    if com_connector is None and conn_str:
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            _root_connector = win32com.client.Dispatch("V83.COMConnector")
            com_connector = _root_connector.Connect(conn_str)
        except Exception as exc:
            logger.warning("Could not pre-initialize shared COM connection: %s", exc)

    # Prepare isolated settings for dry-run
    dry_settings = settings.model_copy(
        update={
            "agent_env": "test" if com_connector else settings.agent_env,
            "one_adapter_mode": "com",
            "one_connection_string": conn_str,
            "agent_state_db_path": db_path,
            "one_state_key_path": key_path,
            "one_mapping_path": mapping_path,
            "dry_run": True,
        }
    )

    result = DryRunResult()
    start_total_time = time.perf_counter()

    cards_limit = dry_settings.agent_card_batch_size
    tx_limit = dry_settings.agent_tx_batch_size

    # =========================================================================
    # Phase A: Cycle 1 (Full Initial Sync)
    # =========================================================================
    t0 = time.perf_counter()
    store1 = StateStore(db_path)
    source1 = OneComLoyaltySource(dry_settings, store1, mapping_config, com_connector=com_connector)
    client1 = DryRunCloudClient()

    cards_c1, tx_c1 = await run_sync_cycle(source1, client1, cards_limit, tx_limit)
    result.duration_cycle1 = time.perf_counter() - t0
    result.cycle1_cards_sent = cards_c1
    result.cycle1_tx_sent = tx_c1

    # Extract source counters
    result.cards_skipped_empty_code = source1.counters["cards_skipped_empty_code"]
    result.cards_skipped_non_digits = source1.counters["cards_skipped_non_digits"]
    result.cards_skipped_too_short = source1.counters["cards_skipped_too_short"]
    result.cards_skipped_too_long = source1.counters["cards_skipped_too_long"]
    result.cards_balance_clamped = source1.counters.get("cards_balance_clamped", 0)

    result.tx_skipped_empty_code = source1.counters["tx_skipped_empty_code"]
    result.tx_skipped_non_digits = source1.counters["tx_skipped_non_digits"]
    result.tx_skipped_too_short = source1.counters["tx_skipped_too_short"]
    result.tx_skipped_too_long = source1.counters["tx_skipped_too_long"]
    result.tx_skipped_zero_amount = source1.counters["tx_skipped_zero_amount"]
    result.tx_skipped_unknown_type = source1.counters["tx_skipped_unknown_type"]
    result.tx_filtered_already_sent = source1.counters["tx_filtered_already_sent"]
    result.tx_balance_after_clamped = source1.counters.get("tx_balance_after_clamped", 0)

    # Calculate cards aggregates
    total_card_skips = (
        result.cards_skipped_empty_code
        + result.cards_skipped_non_digits
        + result.cards_skipped_too_short
        + result.cards_skipped_too_long
    )
    result.cards_total_in_1c = cards_c1 + total_card_skips
    result.cards_phone_null_count = sum(1 for c in client1.received_cards if c.phone is None)
    result.cards_blocked_count = sum(1 for c in client1.received_cards if c.is_blocked)
    result.cards_balance_positive_count = sum(1 for c in client1.received_cards if c.balance > 0)
    result.cards_balance_zero_count = sum(1 for c in client1.received_cards if c.balance == 0)
    result.cards_balance_negative_count = sum(1 for c in client1.received_cards if c.balance < 0)

    # Calculate transactions aggregates
    total_tx_skips = (
        result.tx_skipped_empty_code
        + result.tx_skipped_non_digits
        + result.tx_skipped_too_short
        + result.tx_skipped_too_long
        + result.tx_skipped_zero_amount
        + result.tx_skipped_unknown_type
    )
    result.tx_total_in_1c = tx_c1 + total_tx_skips
    result.tx_accrual_count = sum(1 for t in client1.received_tx if t.type == "accrual")
    result.tx_redemption_count = sum(1 for t in client1.received_tx if t.type == "redemption")

    if client1.received_tx:
        min_dt = min(t.occurred_at for t in client1.received_tx)
        max_dt = max(t.occurred_at for t in client1.received_tx)
        tz_local = ZoneInfo(dry_settings.agent_one_timezone)
        min_loc = min_dt.astimezone(tz_local)
        max_loc = max_dt.astimezone(tz_local)
        result.tx_min_occurred_str = (
            f"{min_dt.strftime('%Y-%m-%d %H:%M:%S UTC')} ({min_loc.strftime('%Y-%m-%d %H:%M:%S')} Local)"
        )
        result.tx_max_occurred_str = (
            f"{max_dt.strftime('%Y-%m-%d %H:%M:%S UTC')} ({max_loc.strftime('%Y-%m-%d %H:%M:%S')} Local)"
        )

        n_tx = len(client1.received_tx)
        result.tx_filled_receipt_ref_percent = (sum(1 for t in client1.received_tx if t.receipt_ref) / n_tx) * 100
        result.tx_filled_store_percent = (sum(1 for t in client1.received_tx if t.store) / n_tx) * 100

    # =========================================================================
    # Phase B: Cycle 2 (Immediate Idempotency Check on Same Source)
    # =========================================================================
    t1 = time.perf_counter()
    client2 = DryRunCloudClient()
    cards_c2, tx_c2 = await run_sync_cycle(source1, client2, cards_limit, tx_limit)
    result.duration_cycle2 = time.perf_counter() - t1
    result.cycle2_cards_sent = cards_c2
    result.cycle2_tx_sent = tx_c2

    # Capture barcodes with skipped movements from source 1 for balance reconciliation
    barcodes_with_skipped = set(getattr(source1, "barcodes_with_skipped_tx", set()))

    # Close source 1
    await source1.close()

    # =========================================================================
    # Phase C: Cycle 3 (Restart Scenario with Fresh Source Instance on Same DB)
    # =========================================================================
    t2 = time.perf_counter()
    store3 = StateStore(db_path)
    source3 = OneComLoyaltySource(dry_settings, store3, mapping_config, com_connector=com_connector)
    client3 = DryRunCloudClient()
    cards_c3, tx_c3 = await run_sync_cycle(source3, client3, cards_limit, tx_limit)
    result.duration_cycle3 = time.perf_counter() - t2
    result.cycle3_cards_sent = cards_c3
    result.cycle3_tx_sent = tx_c3

    await source3.close()

    # =========================================================================
    # Phase D: Scenario D (Cloud Failure & Crash Simulation on Separate DB)
    # =========================================================================
    t3 = time.perf_counter()
    sim_d_db = base_dir / "agent_state_dryrun_sim_d.db"
    sim_d_key = base_dir / "agent_state_dryrun_sim_d.key"
    for f in (sim_d_db, sim_d_key):
        if f.exists():
            f.unlink()

    sim_d_settings = dry_settings.model_copy(
        update={
            "agent_state_db_path": sim_d_db,
            "one_state_key_path": sim_d_key,
        }
    )

    # 1. First run: fetch first page of cards and tx, but NEVER ACK them
    store_d1 = StateStore(sim_d_db)
    source_d1 = OneComLoyaltySource(sim_d_settings, store_d1, mapping_config, com_connector=com_connector)
    await source_d1.fetch_cards(cursor=None, limit=cards_limit)
    await source_d1.fetch_transactions(cursor=None, limit=tx_limit)
    await source_d1.close()  # Simulated crash/timeout before ACK!

    # 2. Recovery run: create fresh source on that DB and perform full cycle
    store_d2 = StateStore(sim_d_db)
    source_d2 = OneComLoyaltySource(sim_d_settings, store_d2, mapping_config, com_connector=com_connector)
    client_d = DryRunCloudClient()
    cards_d, tx_d = await run_sync_cycle(source_d2, client_d, cards_limit, tx_limit)
    result.duration_scenario_d = time.perf_counter() - t3
    result.scenario_d_cards_sent = cards_d
    result.scenario_d_tx_sent = tx_d

    await source_d2.close()

    # Cleanup sim_d files
    for f in (sim_d_db, sim_d_key):
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass

    # =========================================================================
    # Balance Reconciliation (Item 2.3)
    # =========================================================================
    card_balance_map: dict[str, Decimal] = {c.barcode: c.balance for c in client1.received_cards}
    tx_by_barcode: dict[str, list[TransactionSyncItem]] = defaultdict(list)
    for t in client1.received_tx:
        tx_by_barcode[t.barcode].append(t)

    reconciled_cards = 0
    discrepancies = 0
    max_disc = Decimal("0")
    reason_counts: dict[str, int] = defaultdict(int)

    for barcode, tx_list in tx_by_barcode.items():
        if barcode not in card_balance_map:
            continue
        reconciled_cards += 1
        card_bal = card_balance_map[barcode]

        # Sort transactions in adapter order: (occurred_at, UUID регистратора, int(НомерСтроки))
        tx_list.sort(key=_tx_sort_key)
        last_tx = tx_list[-1]
        diff = abs(last_tx.balance_after - card_bal)

        if diff > Decimal("0.0001"):
            discrepancies += 1
            if diff > max_disc:
                max_disc = diff
            # Classify cause according to priority order
            max_occ = max(t.occurred_at for t in tx_list)
            if any(
                abs(t.balance_after - card_bal) <= Decimal("0.0001")
                for t in tx_list
                if t.occurred_at == max_occ
            ):
                reason_counts["same_period_ordering"] += 1
            elif barcode in barcodes_with_skipped or any(t.amount == 0 for t in tx_list):
                reason_counts["skipped_movements"] += 1
            else:
                reason_counts["other"] += 1

    result.reconciliation_cards_checked = reconciled_cards
    result.reconciliation_discrepancies = discrepancies
    result.reconciliation_max_discrepancy = max_disc
    result.reconciliation_reasons = dict(reason_counts)

    # Verification: when clamp is enabled, no emitted balance or balance_after may be negative
    if dry_settings.agent_clamp_negative_balance:
        neg_cards = sum(1 for c in client1.received_cards if c.balance < 0)
        neg_tx = sum(1 for t in client1.received_tx if t.balance_after < 0)
        if neg_cards > 0 or neg_tx > 0:
            result.negative_clamp_check = f"FAIL (neg_cards={neg_cards}, neg_tx={neg_tx})"
        else:
            result.negative_clamp_check = "PASS"
    else:
        result.negative_clamp_check = "DISABLED (clamp=False)"

    # =========================================================================
    # PII Verification (Item 2.5)
    # =========================================================================
    # Check 30 random barcodes and 30 random phones
    wal_path = base_dir / f"{db_path.name}-wal"
    shm_path = base_dir / f"{db_path.name}-shm"
    db_bytes = db_path.read_bytes() if db_path.exists() else b""
    if wal_path.exists():
        db_bytes += wal_path.read_bytes()
    if shm_path.exists():
        db_bytes += shm_path.read_bytes()
    key_bytes = key_path.read_bytes() if key_path.exists() else b""
    log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""

    barcodes_sample = [c.barcode for c in client1.received_cards if c.barcode]
    if len(barcodes_sample) > 30:
        barcodes_sample = random.sample(barcodes_sample, 30)

    phones_sample = [c.phone for c in client1.received_cards if c.phone]
    if len(phones_sample) > 30:
        phones_sample = random.sample(phones_sample, 30)

    pii_db_leak = False
    pii_key_leak = False
    pii_log_leak = False

    for code in barcodes_sample:
        b_code = code.encode("utf-8")
        if b_code in db_bytes:
            pii_db_leak = True
        if b_code in key_bytes:
            pii_key_leak = True
        if code in log_text:
            pii_log_leak = True

    for ph in phones_sample:
        digits_only = ph.lstrip("+")
        b_ph = digits_only.encode("utf-8")
        if b_ph in db_bytes:
            pii_db_leak = True
        if b_ph in key_bytes:
            pii_key_leak = True
        if digits_only in log_text:
            pii_log_leak = True

    if pii_db_leak:
        result.pii_db_check = "FAIL"
    if pii_key_leak:
        result.pii_key_check = "FAIL"
    if pii_log_leak:
        result.pii_log_check = "FAIL"

    result.total_duration = time.perf_counter() - start_total_time
    result.rss_mb_end = get_process_rss_mb()

    # Format Markdown Report
    report_text = generate_dryrun_report_markdown(result, db_path)

    # Validate output through security sanitizer (Item 2.5a)
    try:
        validate_safe_output(report_text, context="DryRun Report")
        result.sanitizer_check = "PASS"
    except Exception as exc:
        result.sanitizer_check = f"FAIL ({exc})"

    # Write report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")

    return result


def generate_dryrun_report_markdown(res: DryRunResult, db_path: Path) -> str:
    """Generate Markdown report containing strictly aggregate values and zero PII."""
    db_size_kb = (db_path.stat().st_size / 1024) if db_path.exists() else 0.0

    return f"""# Отчёт автономного прогона Dry-Run (POSCENTER Loyalty Agent)

Дата и время прогона (UTC): {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}
Режим: ONE_ADAPTER_MODE=com (только запросы ВЫБРАТЬ, сеть полностью отключена)

---

## 1. Сводка по картам лояльности (Цикл 1)
- Всего карт в 1С: **{res.cards_total_in_1c}**
- Принято к отправке: **{res.cycle1_cards_sent}**
- Пропущено по фильтрам (`cards_*`):
  - Пустой штрихкод: **{res.cards_skipped_empty_code}**
  - Нецифровой штрихкод: **{res.cards_skipped_non_digits}**
  - Слишком короткий (<6 цифр): **{res.cards_skipped_too_short}**
  - Слишком длинный (>15 цифр): **{res.cards_skipped_too_long}**
- Телефон отсутствует (null): **{res.cards_phone_null_count}**
- Заблокировано или помечено на удаление: **{res.cards_blocked_count}**
- Баланс положительный (>0): **{res.cards_balance_positive_count}**
- Баланс нулевой (=0): **{res.cards_balance_zero_count}**
- Баланс отрицательный (<0): **{res.cards_balance_negative_count}**
- Обрезано отрицательных балансов (`cards_balance_clamped`): **{res.cards_balance_clamped}**

---

## 2. Сводка по операциям (Цикл 1)
- Всего движений прочитано из 1С: **{res.tx_total_in_1c}**
- Принято к отправке: **{res.cycle1_tx_sent}**
  - Начислений (`accrual`): **{res.tx_accrual_count}**
  - Списаний (`redemption`): **{res.tx_redemption_count}**
- Пропущено по фильтрам (`tx_*`):
  - Невалидный штрихкод карты: **{res.tx_skipped_empty_code + res.tx_skipped_non_digits + res.tx_skipped_too_short + res.tx_skipped_too_long}**
  - Нулевая сумма (`tx_skipped_zero_amount`): **{res.tx_skipped_zero_amount}**
  - Неизвестный вид движения (`tx_skipped_unknown_type`): **{res.tx_skipped_unknown_type}**
  - Ранее отправлено (`tx_filtered_already_sent`): **{res.tx_filtered_already_sent}**
  - Обрезано отрицательных `balance_after` (`tx_balance_after_clamped`): **{res.tx_balance_after_clamped}**
- Временные границы окна операций:
  - Минимум: `{res.tx_min_occurred_str or 'нет операций'}`
  - Максимум: `{res.tx_max_occurred_str or 'нет операций'}`
- Доля заполненных реквизитов:
  - Номер чека (`receipt_ref`): **{res.tx_filled_receipt_ref_percent:.1f}%**
  - Наименование склада (`store`): **{res.tx_filled_store_percent:.1f}%**

---

## 3. Проверка идемпотентности и восстановления (Сценарии A–D)
- **Цикл 1 (Первичная выгрузка):** отправлено карт: **{res.cycle1_cards_sent}**, операций: **{res.cycle1_tx_sent}** (время: {res.duration_cycle1:.2f} с)
- **Цикл 2 (Повтор сразу):** отправлено карт: **{res.cycle2_cards_sent}**, операций: **{res.cycle2_tx_sent}** (ожидается 0 / 0) — **{'PASS' if res.cycle2_cards_sent == 0 and res.cycle2_tx_sent == 0 else 'FAIL'}** (время: {res.duration_cycle2:.2f} с)
- **Цикл 3 (После рестарта):** отправлено карт: **{res.cycle3_cards_sent}**, операций: **{res.cycle3_tx_sent}** (ожидается 0 / 0) — **{'PASS' if res.cycle3_cards_sent == 0 and res.cycle3_tx_sent == 0 else 'FAIL'}** (время: {res.duration_cycle3:.2f} с)
- **Сценарий D (Сбой облака до ACK):** отправлено карт: **{res.scenario_d_cards_sent}**, операций: **{res.scenario_d_tx_sent}** (ожидается равенство Циклу 1) — **{'PASS' if res.scenario_d_cards_sent == res.cycle1_cards_sent and res.scenario_d_tx_sent == res.cycle1_tx_sent else 'FAIL'}** (время: {res.duration_scenario_d:.2f} с)

---

## 4. Сверка балансов карт и цепочки операций
- Карт с операциями в окне проверено: **{res.reconciliation_cards_checked}**
- Расхождений между `balance_after` последней операции и балансом карты: **{res.reconciliation_discrepancies}**
- Максимальное по модулю расхождение: **{res.reconciliation_max_discrepancy}**
- Классификация причин расхождений: {res.reconciliation_reasons or 'расхождений нет'}
- Проверка отсутствия отрицательных значений (clamp): **{res.negative_clamp_check}**

---

## 5. Проверка безопасности и изоляции ПДн
- Проверка хранилища SQLite (`agent_state_dryrun.db`) на 30 случайных номеров/кодов: **{res.pii_db_check}**
- Проверка файла секретного ключа (`agent_state_dryrun.key`): **{res.pii_key_check}**
- Проверка логов (`dryrun.log`): **{res.pii_log_check}**
- Проверка отчёта через `validate_safe_output`: **{res.sanitizer_check}**

---

## 6. Системные ресурсы
- Общее время прогона: **{res.total_duration:.2f} с**
- Размер локальной базы SQLite: **{db_size_kb:.1f} КБ**
- Память процесса (WorkingSet / RSS): **{res.rss_mb_end:.2f} МБ**
"""


def run_dry_run_cli(settings: AgentSettings | None = None) -> int:
    """CLI execution entrypoint for poscenter-loyalty-agent run --dry-run."""
    from poscenter_loyalty_agent.config import get_settings

    active_settings = settings or get_settings()
    try:
        res = asyncio.run(execute_dry_run(active_settings))
        report_text = generate_dryrun_report_markdown(
            res, Path(r"C:\cashback-stage0\dryrun\agent_state_dryrun.db")
        )
        print(report_text)
        return 0
    except Exception as exc:
        print(f"ERROR: Dry-run failed: {exc}", file=sys.stderr)
        return 1
