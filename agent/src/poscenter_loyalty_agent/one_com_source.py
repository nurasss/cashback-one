"""POSCENTER ONE COM-based LoyaltySource implementation."""

from __future__ import annotations

import asyncio
import gc
import logging
import re
import secrets
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, TypeVar

from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.models import (
    CardSyncItem,
    SourceBatch,
    TransactionSyncItem,
)
from poscenter_loyalty_agent.one_com import sanitize_connection_string
from poscenter_loyalty_agent.one_cursor import (
    CardsDoneCursor,
    CardsPageCursor,
    TxDoneCursor,
    TxPageCursor,
    decode_cards_cursor,
    decode_tx_cursor,
    encode_cards_done_cursor,
    encode_cards_page_cursor,
    encode_tx_done_cursor,
    encode_tx_page_cursor,
)
from poscenter_loyalty_agent.one_mapping import (
    DOC_RETAIL_REPORT,
    FIELD_CARD_BLOCKED,
    FIELD_DELETION_MARK,
    FIELD_DOC_NUMBER,
    FIELD_LINE_NUMBER,
    FIELD_NAME,
    FIELD_REGISTRAR,
    FIELD_WAREHOUSE,
    MappingValidationError,
    OneMappingConfig,
)
from poscenter_loyalty_agent.one_time import convert_one_datetime, to_one_naive_datetime
from poscenter_loyalty_agent.phone_norm import normalize_phone
from poscenter_loyalty_agent.source import LoyaltySource, SourceError
from poscenter_loyalty_agent.state_store import (
    StateStore,
    compute_card_hmac,
    get_or_create_state_key,
)

logger = logging.getLogger("poscenter_loyalty_agent.one_com_source")

T = TypeVar("T")

DIGITS_RE = re.compile(r"^\d+$")
DECIMAL_4 = Decimal("0.0001")


def _sta_thread_init() -> None:
    try:
        import pythoncom

        pythoncom.CoInitialize()
    except Exception:
        pass


def _sta_thread_uninit() -> None:
    try:
        import pythoncom

        pythoncom.CoUninitialize()
    except Exception:
        pass


class OneComError(SourceError):
    """Base error for POSCENTER ONE COM adapter."""


class OneComConnectionError(OneComError):
    """Raised when connecting or communicating with 1C COMConnector fails."""


class OneComQueryError(OneComError):
    """Raised when 1C query execution fails."""


class OneComLoyaltySource(LoyaltySource):
    """Production 1C:Enterprise COM loyalty source (ONE_ADAPTER_MODE=com)."""

    def __init__(
        self,
        settings: AgentSettings,
        state_store: StateStore,
        mapping_config: OneMappingConfig,
        com_connector: Any = None,
    ) -> None:
        self.settings = settings
        self.state_store = state_store
        self.mapping_config = mapping_config
        self._custom_connector = com_connector

        # Thread pool with persistent STA apartment per worker thread
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="one_com_sta",
            initializer=_sta_thread_init,
        )
        self._connection: Any = None
        self._last_warning: str | None = None
        self._hmac_key: bytes = get_or_create_state_key(settings.state_key_path)

        # Inspection counters (used in dry-run and health reporting)
        self.counters: dict[str, int] = {
            "cards_skipped_empty_code": 0,
            "cards_skipped_non_digits": 0,
            "cards_skipped_too_short": 0,
            "cards_skipped_too_long": 0,
            "cards_balance_clamped": 0,
            "tx_skipped_empty_code": 0,
            "tx_skipped_non_digits": 0,
            "tx_skipped_too_short": 0,
            "tx_skipped_too_long": 0,
            "tx_skipped_zero_amount": 0,
            "tx_skipped_unknown_type": 0,
            "tx_filtered_already_sent": 0,
            "tx_balance_after_clamped": 0,
        }
        self.barcodes_with_skipped_tx: set[str] = set()

        # In-memory buffer for active card pagination: (session_id, [(card_uuid, CardSyncItem)])
        self._active_cards_session: tuple[str, list[tuple[str, CardSyncItem]]] | None = None

        # In-memory buffer for active tx pagination: (session_id, [TransactionSyncItem], w_start_iso, w_end_iso)
        self._active_tx_session: tuple[str, list[TransactionSyncItem], str, str] | None = None

    @property
    def last_warning(self) -> str | None:
        return self._last_warning

    # --- Threading & STA Executor ---

    async def _run_in_sta(self, func: Callable[..., T], *args: Any) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, func, *args)

    # --- COM Lifecycle & Query Safety ---

    def _get_connection(self) -> Any:
        if self._connection is not None:
            return self._connection

        try:
            if self._custom_connector is not None:
                if hasattr(self._custom_connector, "Connect"):
                    conn = self._custom_connector.Connect(self.settings.one_connection_string)
                else:
                    conn = self._custom_connector
            else:
                import win32com.client

                connector = win32com.client.Dispatch("V83.COMConnector")
                conn = connector.Connect(self.settings.one_connection_string)
        except Exception as exc:
            raw_exc = str(exc)
            conn_str = self.settings.one_connection_string
            if conn_str:
                raw_exc = raw_exc.replace(conn_str, "***")
            cleaned_msg = sanitize_connection_string(raw_exc)[:300]
            logger.error("COM connection failed: %s", cleaned_msg)
            raise OneComConnectionError(f"Failed to connect to 1C infobase: {cleaned_msg}") from exc

        # Verify configuration identity (Amendment П6)
        try:
            metadata = conn.Metadata
            conf_name = str(getattr(metadata, "Name", ""))
            conf_version = str(getattr(metadata, "Version", ""))
            warn = self.mapping_config.verify_configuration(conf_name, conf_version)
            if warn:
                self._last_warning = warn
        except MappingValidationError:
            self._connection = None
            raise
        except Exception as exc:
            logger.warning("Could not read configuration metadata from 1C: %s", exc)

        self._connection = conn
        return conn

    def _reset_connection(self) -> None:
        self._connection = None
        gc.collect()

    @staticmethod
    def _validate_query_safety(query_text: str) -> None:
        clean = query_text.strip().upper()
        if not clean.startswith("ВЫБРАТЬ"):
            raise ValueError("Query security violation: Only queries starting with 'ВЫБРАТЬ' are allowed")
        for keyword in (
            "ПОМЕСТИТЬ",
            "УДАЛИТЬ",
            "ЗАПИСАТЬ",
            "УСТАНОВИТЬ",
            "ИЗМЕНИТЬ",
            "СОЗДАТЬ",
            "DROP",
            "INSERT",
            "UPDATE",
            "DELETE",
        ):
            if keyword in clean:
                raise ValueError(f"Query security violation: Forbidden keyword '{keyword}' found in 1C query")

    @staticmethod
    def _get_ref_uuid(conn: Any, ref: Any) -> str:
        func = getattr(conn, "XMLСтрока", getattr(conn, "XMLString", None))
        if func:
            try:
                return str(func(ref))
            except Exception:
                pass
        return str(ref)

    def _execute_query(self, conn: Any, query_text: str, params: dict[str, Any] | None = None) -> Any:
        self._validate_query_safety(query_text)
        query = conn.NewObject("Запрос")
        if hasattr(query, "Текст"):
            query.Текст = query_text
        else:
            query.Text = query_text

        if params:
            for p_name, p_val in params.items():
                if hasattr(query, "УстановитьПараметр"):
                    query.УстановитьПараметр(p_name, p_val)
                elif hasattr(query, "SetParameter"):
                    query.SetParameter(p_name, p_val)

        result = query.Выполнить() if hasattr(query, "Выполнить") else query.Execute()
        sel = result.Выбрать() if hasattr(result, "Выбрать") else result.Select()
        return sel

    # --- Cards Logic ---

    def _validate_card_barcode(self, raw_code: str, prefix: str = "cards_") -> str | None:
        code = str(raw_code).strip()
        if not code:
            self.counters[f"{prefix}skipped_empty_code"] += 1
            return None
        if not DIGITS_RE.match(code):
            self.counters[f"{prefix}skipped_non_digits"] += 1
            return None
        if len(code) < 6:
            self.counters[f"{prefix}skipped_too_short"] += 1
            return None
        if len(code) > 15:
            self.counters[f"{prefix}skipped_too_long"] += 1
            return None
        return code

    def _fetch_all_changed_cards_worker(self) -> list[tuple[str, CardSyncItem]]:
        t0 = time.monotonic()
        conn = self._get_connection()
        cfg = self.mapping_config

        query_text = f"""
ВЫБРАТЬ
    К.{cfg.card_id_field} КАК Ссылка,
    К.{cfg.card_barcode_field} КАК Код,
    К.{cfg.card_phone_field} КАК Телефон,
    К.{cfg.card_full_name_field} КАК Наименование,
    К.{FIELD_CARD_BLOCKED} КАК {FIELD_CARD_BLOCKED},
    К.{FIELD_DELETION_MARK} КАК {FIELD_DELETION_MARK},
    ЕСТЬNULL(Ост.{cfg.balance_amount_resource}, 0) КАК Баланс
ИЗ
    Справочник.{cfg.card_catalog_name} КАК К
    ЛЕВОЕ СОЕДИНЕНИЕ РегистрНакопления.{cfg.balance_register_name}.Остатки(, ) КАК Ост
        ПО К.{cfg.card_id_field} = Ост.{cfg.balance_card_dimension}
УПОРЯДОЧИТЬ ПО
    К.{cfg.card_id_field}
"""
        try:
            sel = self._execute_query(conn, query_text)
        except Exception as exc:
            self._reset_connection()
            raise OneComQueryError(f"Failed to query cards from 1C: {exc}") from exc

        known_hashes = self.state_store.get_card_hashes()
        now_utc = datetime.now(UTC)
        changed_items: list[tuple[str, CardSyncItem]] = []
        total_read = 0

        while sel.Следующий() if hasattr(sel, "Следующий") else sel.Next():
            total_read += 1
            card_uuid = self._get_ref_uuid(conn, getattr(sel, "Ссылка", ""))
            raw_barcode = getattr(sel, "Код", "")
            barcode = self._validate_card_barcode(raw_barcode, prefix="cards_")
            if not barcode:
                continue

            raw_phone = getattr(sel, "Телефон", "")
            phone = normalize_phone(raw_phone)

            raw_name = getattr(sel, "Наименование", "")
            full_name = str(raw_name).strip() if raw_name else None

            is_blocked = bool(getattr(sel, FIELD_CARD_BLOCKED, False) or getattr(sel, FIELD_DELETION_MARK, False))
            balance = Decimal(str(getattr(sel, "Баланс", 0))).quantize(DECIMAL_4)

            if self.settings.agent_clamp_negative_balance and balance < Decimal("0"):
                emitted_balance = Decimal("0").quantize(DECIMAL_4)
                was_clamped = True
            else:
                emitted_balance = balance
                was_clamped = False

            raw_payload = f"{barcode}|{phone or ''}|{full_name or ''}|{is_blocked}|{emitted_balance}"
            content_hash = compute_card_hmac(self._hmac_key, raw_payload)

            if card_uuid in known_hashes and known_hashes[card_uuid][0] == content_hash:
                continue

            if was_clamped:
                self.counters["cards_balance_clamped"] += 1

            # Deterministic monotonic observation timestamp
            last_updated = known_hashes[card_uuid][1] if card_uuid in known_hashes else None
            if last_updated:
                dt_last = datetime.fromisoformat(last_updated)
                updated_at = max(now_utc, dt_last + timedelta(microseconds=1))
            else:
                updated_at = now_utc

            item = CardSyncItem(
                barcode=barcode,
                phone=phone,
                full_name=full_name,
                is_blocked=is_blocked,
                balance=emitted_balance,
                updated_at=updated_at,
            )
            changed_items.append((card_uuid, item))

        del sel
        gc.collect()

        duration = time.monotonic() - t0
        logger.info(
            "ONE read completed: type=cards_snapshot, records_read=%d, changes_to_send=%d, duration=%.3fs",
            total_read,
            len(changed_items),
            duration,
        )
        return changed_items

    async def fetch_cards(self, cursor: str | None, limit: int) -> SourceBatch[CardSyncItem]:
        decoded = decode_cards_cursor(cursor)

        # ACK commitment: if incoming cursor advanced, commit previous staged page
        if isinstance(decoded, CardsPageCursor):
            prev_page = decoded.page - 1
            if prev_page >= 1:
                self.state_store.commit_pending_cards(decoded.session_id, page=prev_page)

            # Serve next page from active memory buffer if matching session
            if self._active_cards_session and self._active_cards_session[0] == decoded.session_id:
                all_changed = self._active_cards_session[1]
                start_idx = (decoded.page - 1) * limit
                end_idx = start_idx + limit
                page_slice = all_changed[start_idx:end_idx]
                page_items = [item for _, item in page_slice]
                has_more = end_idx < len(all_changed)

                if has_more:
                    next_cursor = encode_cards_page_cursor(
                        CardsPageCursor(
                            session_id=decoded.session_id,
                            page=decoded.page + 1,
                            last_card_ref_uuid=page_slice[-1][0],
                            total_found=len(all_changed),
                        )
                    )
                else:
                    next_cursor = encode_cards_done_cursor(
                        CardsDoneCursor(
                            session_id=decoded.session_id,
                            total_synced=len(all_changed),
                            completed_at=datetime.now(UTC).isoformat(),
                        )
                    )

                staged = [
                    (
                        c_uuid,
                        compute_card_hmac(
                            self._hmac_key,
                            f"{item.barcode}|{item.phone or ''}|{item.full_name or ''}|{item.is_blocked}|{item.balance}",
                        ),
                        item.updated_at.isoformat(),
                    )
                    for c_uuid, item in page_slice
                ]
                self.state_store.record_pending_cards(decoded.session_id, page=decoded.page, cards=staged)
                return SourceBatch(items=page_items, next_cursor=next_cursor, has_more=has_more)

        elif isinstance(decoded, CardsDoneCursor):
            # Final page acknowledged: commit remaining
            self.state_store.commit_pending_cards(decoded.session_id, None)
            self.state_store.clear_pending_cards(decoded.session_id)
            self._active_cards_session = None

        # Start fresh cycle
        self.state_store.clear_pending_cards()
        all_changed = await self._run_in_sta(self._fetch_all_changed_cards_worker)

        if not all_changed:
            return SourceBatch(items=[], next_cursor=cursor, has_more=False)

        sid = secrets.token_hex(4)
        self._active_cards_session = (sid, all_changed)
        page_slice = all_changed[0:limit]
        page_items = [item for _, item in page_slice]
        has_more = len(all_changed) > limit

        if has_more:
            next_cursor = encode_cards_page_cursor(
                CardsPageCursor(
                    session_id=sid,
                    page=2,
                    last_card_ref_uuid=page_slice[-1][0],
                    total_found=len(all_changed),
                )
            )
        else:
            next_cursor = encode_cards_done_cursor(
                CardsDoneCursor(
                    session_id=sid,
                    total_synced=len(all_changed),
                    completed_at=datetime.now(UTC).isoformat(),
                )
            )

        staged = [
            (
                c_uuid,
                compute_card_hmac(
                    self._hmac_key,
                    f"{item.barcode}|{item.phone or ''}|{item.full_name or ''}|{item.is_blocked}|{item.balance}",
                ),
                item.updated_at.isoformat(),
            )
            for c_uuid, item in page_slice
        ]
        self.state_store.record_pending_cards(sid, page=1, cards=staged)
        return SourceBatch(items=page_items, next_cursor=next_cursor, has_more=has_more)

    # --- Transactions Logic ---

    def _fetch_window_transactions_worker(
        self, window_start: datetime, window_end: datetime
    ) -> list[TransactionSyncItem]:
        t0 = time.monotonic()
        conn = self._get_connection()
        cfg = self.mapping_config

        # 1. Query movements within sliding window, dereferencing card barcode via mapping names
        query_text = f"""
ВЫБРАТЬ
    Т.{cfg.tx_occurred_at_field} КАК Период,
    Т.{FIELD_REGISTRAR} КАК {FIELD_REGISTRAR},
    Т.{FIELD_LINE_NUMBER} КАК {FIELD_LINE_NUMBER},
    Т.{cfg.tx_card_field} КАК БонуснаяКарта,
    Т.{cfg.tx_card_field}.{cfg.card_barcode_field} КАК КартаКод,
    Т.{cfg.tx_type_field} КАК ВидДвижения,
    Т.{cfg.tx_amount_field} КАК Сумма,
    ВЫБОР КОГДА Т.{FIELD_REGISTRAR} ССЫЛКА {DOC_RETAIL_REPORT} ТОГДА ВЫРАЗИТЬ(Т.{FIELD_REGISTRAR} КАК {DOC_RETAIL_REPORT}).{FIELD_DOC_NUMBER} ИНАЧЕ "" КОНЕЦ КАК ЧекНомер,
    ВЫБОР КОГДА Т.{FIELD_REGISTRAR} ССЫЛКА {DOC_RETAIL_REPORT} ТОГДА ВЫРАЗИТЬ(Т.{FIELD_REGISTRAR} КАК {DOC_RETAIL_REPORT}).{FIELD_WAREHOUSE}.{FIELD_NAME} ИНАЧЕ "" КОНЕЦ КАК СкладНаименование
ИЗ
    РегистрНакопления.{cfg.tx_register_name} КАК Т
ГДЕ
    Т.{cfg.tx_occurred_at_field} >= &WindowStart
УПОРЯДОЧИТЬ ПО
    Т.{cfg.tx_occurred_at_field},
    Т.{FIELD_REGISTRAR},
    Т.{FIELD_LINE_NUMBER}
"""
        window_start_naive = to_one_naive_datetime(window_start, tz_name=self.settings.agent_one_timezone)

        try:
            sel = self._execute_query(conn, query_text, {"WindowStart": window_start_naive})
        except Exception as exc:
            self._reset_connection()
            raise OneComQueryError(f"Failed to query transactions from 1C: {exc}") from exc

        raw_movements: list[dict[str, Any]] = []
        cards_in_window: set[str] = set()
        total_query_rows = 0

        while sel.Следующий() if hasattr(sel, "Следующий") else sel.Next():
            total_query_rows += 1
            if total_query_rows > self.settings.agent_one_max_window_rows:
                raise SourceError("Transaction window exceeded maximum allowed rows limit")

            raw_period = getattr(sel, "Период", None)
            period_utc = convert_one_datetime(raw_period, tz_name=self.settings.agent_one_timezone)

            reg_uuid = self._get_ref_uuid(conn, getattr(sel, FIELD_REGISTRAR, ""))
            line_num = int(getattr(sel, FIELD_LINE_NUMBER, 0))
            card_uuid = self._get_ref_uuid(conn, getattr(sel, "БонуснаяКарта", ""))

            raw_barcode = getattr(sel, "КартаКод", "")
            barcode = self._validate_card_barcode(raw_barcode, prefix="tx_")
            if not barcode:
                continue

            move_kind_raw = getattr(sel, "ВидДвижения", "")
            move_kind_str = (
                str(getattr(conn, "String", str)(move_kind_raw))
                if hasattr(conn, "String")
                else str(move_kind_raw)
            )
            canonical_type = cfg.tx_type_mapping.get(move_kind_str)
            if canonical_type is None:
                self.counters["tx_skipped_unknown_type"] += 1
                if barcode:
                    self.barcodes_with_skipped_tx.add(barcode)
                logger.warning("Skipping 1C transaction movement with unknown movement kind")
                continue

            amount = Decimal(str(getattr(sel, "Сумма", 0))).quantize(DECIMAL_4)

            receipt_ref: str | None = None
            raw_receipt = getattr(sel, "ЧекНомер", None)
            if raw_receipt and str(raw_receipt).strip():
                receipt_ref = str(raw_receipt).strip()

            store: str | None = None
            raw_store = getattr(sel, "СкладНаименование", None)
            if raw_store and str(raw_store).strip():
                store = str(raw_store).strip()

            cards_in_window.add(card_uuid)
            raw_movements.append(
                {
                    "period_utc": period_utc,
                    "reg_uuid": reg_uuid,
                    "line_num": line_num,
                    "card_uuid": card_uuid,
                    "barcode": barcode,
                    "type": canonical_type,
                    "amount": amount,
                    "receipt_ref": receipt_ref,
                    "store": store,
                }
            )

        del sel
        gc.collect()

        if not raw_movements:
            duration = time.monotonic() - t0
            logger.info(
                "ONE read completed: type=transactions_window, records_read=%d, changes_to_send=%d, duration=%.3fs",
                total_query_rows,
                0,
                duration,
            )
            return []

        # 2. Query initial balance at WindowStart for all cards in window (Design section 2.3 & Amendment П4)
        # MUST succeed: if initial balances cannot be fetched, raise SourceError immediately!
        running_balances: dict[str, Decimal] = {}
        if cards_in_window:
            balance_query = f"""
ВЫБРАТЬ
    Т.{cfg.balance_card_dimension} КАК БонуснаяКарта,
    Т.{cfg.balance_amount_resource} КАК НачальныйОстаток
ИЗ
    РегистрНакопления.{cfg.balance_register_name}.Остатки(&WindowStart, ) КАК Т
"""
            try:
                bal_sel = self._execute_query(conn, balance_query, {"WindowStart": window_start_naive})
                while bal_sel.Следующий() if hasattr(bal_sel, "Следующий") else bal_sel.Next():
                    c_id = self._get_ref_uuid(conn, getattr(bal_sel, "БонуснаяКарта", ""))
                    if c_id in cards_in_window:
                        val = getattr(bal_sel, "НачальныйОстаток", None)
                        if val is None:
                            raise SourceError(f"Missing initial balance value for card {c_id}")
                        running_balances[c_id] = Decimal(str(val)).quantize(DECIMAL_4)
                del bal_sel
                gc.collect()
            except SourceError:
                self._reset_connection()
                raise
            except Exception as exc:
                self._reset_connection()
                raise SourceError(f"Failed to fetch initial balances for window at {window_start}: {exc}") from exc

            for c_id in cards_in_window:
                if c_id not in running_balances:
                    running_balances[c_id] = Decimal("0").quantize(DECIMAL_4)

        # 3. Sort strictly by (Период, UUID Регистратора, НомерСтроки)
        raw_movements.sort(key=lambda m: (m["period_utc"], m["reg_uuid"], m["line_num"]))

        # 4. Calculate balance_after across WHOLE window, then filter known operations (Amendment П4)
        known_tx_ids = self.state_store.get_known_tx_ids()
        candidate_items: list[TransactionSyncItem] = []

        for m in raw_movements:
            c_uuid = m["card_uuid"]
            amt = m["amount"]
            cur_bal = running_balances.get(c_uuid, Decimal("0").quantize(DECIMAL_4))

            if m["type"] == "accrual":
                new_bal = (cur_bal + amt).quantize(DECIMAL_4)
            else:
                new_bal = (cur_bal - amt).quantize(DECIMAL_4)
            running_balances[c_uuid] = new_bal

            # Zero-amount filter (Design section 6.1)
            if amt <= 0:
                self.counters["tx_skipped_zero_amount"] += 1
                if m["barcode"]:
                    self.barcodes_with_skipped_tx.add(m["barcode"])
                continue

            # Filter already sent transactions (Amendment П4: balance_after was computed above!)
            ext_id = f"{m['reg_uuid']}:{m['line_num']}"
            if ext_id in known_tx_ids:
                self.counters["tx_filtered_already_sent"] += 1
                continue

            if self.settings.agent_clamp_negative_balance and new_bal < Decimal("0"):
                emitted_balance_after = Decimal("0").quantize(DECIMAL_4)
                self.counters["tx_balance_after_clamped"] += 1
            else:
                emitted_balance_after = new_bal

            item = TransactionSyncItem(
                external_id=ext_id,
                barcode=m["barcode"],
                type=m["type"],
                amount=amt,
                balance_after=emitted_balance_after,
                occurred_at=m["period_utc"],
                receipt_ref=m["receipt_ref"] if cfg.receipt_ref_enabled else None,
                store=m["store"] if cfg.store_enabled else None,
            )
            candidate_items.append(item)

        duration = time.monotonic() - t0
        logger.info(
            "ONE read completed: type=transactions_window, records_read=%d, changes_to_send=%d, duration=%.3fs",
            total_query_rows,
            len(candidate_items),
            duration,
        )
        return candidate_items

    async def fetch_transactions(self, cursor: str | None, limit: int) -> SourceBatch[TransactionSyncItem]:
        decoded = decode_tx_cursor(cursor)

        # ACK commitment: if incoming cursor advanced, commit staged pending transactions
        if cursor is not None:
            self.state_store.commit_pending_tx(cursor)

        now_utc = datetime.now(UTC)

        if isinstance(decoded, TxPageCursor):
            if self._active_tx_session:
                sid, all_candidates, w_start_iso, w_end_iso = self._active_tx_session
                target_id = f"{decoded.last_doc_uuid}:{decoded.last_line}"
                idx = 0
                for i, tx in enumerate(all_candidates):
                    if tx.external_id == target_id:
                        idx = i + 1
                        break

                page_items = all_candidates[idx : idx + limit]
                has_more = (idx + limit) < len(all_candidates)

                if has_more:
                    last_item = page_items[-1]
                    doc_u, l_num = last_item.external_id.split(":")
                    next_cursor = encode_tx_page_cursor(
                        TxPageCursor(
                            window_start=w_start_iso,
                            window_end=w_end_iso,
                            last_period=last_item.occurred_at.isoformat(),
                            last_doc_uuid=doc_u,
                            last_line=int(l_num),
                        )
                    )
                else:
                    hw = all_candidates[-1]
                    hw_u, hw_l = hw.external_id.split(":")
                    next_cursor = encode_tx_done_cursor(
                        TxDoneCursor(
                            hw_period=hw.occurred_at.isoformat(),
                            hw_doc_uuid=hw_u,
                            hw_line=int(hw_l),
                            completed_at=datetime.now(UTC).isoformat(),
                        )
                    )

                staged = [(tx.external_id, tx.occurred_at.isoformat()) for tx in page_items]
                self.state_store.record_pending_tx(next_cursor, staged)
                return SourceBatch(items=page_items, next_cursor=next_cursor, has_more=has_more)
            else:
                # Restart scenario (Item 2.2): no active memory session!
                # Window boundaries are taken from cursor, NOT now - lookback
                window_start = datetime.fromisoformat(decoded.window_start)
                window_end = datetime.fromisoformat(decoded.window_end)
                w_start_iso = decoded.window_start
                w_end_iso = decoded.window_end

                candidates = await self._run_in_sta(
                    self._fetch_window_transactions_worker, window_start, window_end
                )
                if not candidates:
                    return SourceBatch(items=[], next_cursor=cursor, has_more=False)

                sid = secrets.token_hex(4)
                self._active_tx_session = (sid, candidates, w_start_iso, w_end_iso)

                page_items = candidates[0:limit]
                has_more = len(candidates) > limit

                if has_more:
                    last_item = page_items[-1]
                    doc_u, l_num = last_item.external_id.split(":")
                    next_cursor = encode_tx_page_cursor(
                        TxPageCursor(
                            window_start=w_start_iso,
                            window_end=w_end_iso,
                            last_period=last_item.occurred_at.isoformat(),
                            last_doc_uuid=doc_u,
                            last_line=int(l_num),
                        )
                    )
                else:
                    hw = candidates[-1]
                    hw_u, hw_l = hw.external_id.split(":")
                    next_cursor = encode_tx_done_cursor(
                        TxDoneCursor(
                            hw_period=hw.occurred_at.isoformat(),
                            hw_doc_uuid=hw_u,
                            hw_line=int(hw_l),
                            completed_at=now_utc.isoformat(),
                        )
                    )

                staged = [(tx.external_id, tx.occurred_at.isoformat()) for tx in page_items]
                self.state_store.record_pending_tx(next_cursor, staged)
                return SourceBatch(items=page_items, next_cursor=next_cursor, has_more=has_more)

        # Fresh window query (Initial load, Done cursor, or fallback on decode failure)
        if cursor is None:
            if self.settings.agent_one_initial_history_days > 0:
                window_start = now_utc - timedelta(days=self.settings.agent_one_initial_history_days)
            else:
                window_start = datetime(1990, 1, 1, 0, 0, 0, tzinfo=UTC)
            window_end = now_utc
        elif isinstance(decoded, TxDoneCursor):
            try:
                hw_dt = datetime.fromisoformat(decoded.hw_period)
                window_start = hw_dt - timedelta(days=self.settings.agent_one_lookback_days)
            except Exception:
                window_start = now_utc - timedelta(days=self.settings.agent_one_lookback_days)
            window_end = now_utc
        else:
            # Fallback for corrupted or unrecognized cursor token (Item 1.2)
            logger.warning("Failed to decode transactions cursor token; falling back to initial window")
            if self.settings.agent_one_initial_history_days > 0:
                window_start = now_utc - timedelta(days=self.settings.agent_one_initial_history_days)
            else:
                window_start = datetime(1990, 1, 1, 0, 0, 0, tzinfo=UTC)
            window_end = now_utc

        candidates = await self._run_in_sta(self._fetch_window_transactions_worker, window_start, window_end)

        # Prune transactions older than (window_start - 1 day) from local ledger (Item 1.3)
        cutoff_iso = (window_start - timedelta(days=1)).isoformat()
        self.state_store.prune_tx_ledger(cutoff_iso)

        if not candidates:
            return SourceBatch(items=[], next_cursor=cursor, has_more=False)

        sid = secrets.token_hex(4)
        w_start_iso = window_start.isoformat()
        w_end_iso = window_end.isoformat()
        self._active_tx_session = (sid, candidates, w_start_iso, w_end_iso)

        page_items = candidates[0:limit]
        has_more = len(candidates) > limit

        if has_more:
            last_item = page_items[-1]
            doc_u, l_num = last_item.external_id.split(":")
            next_cursor = encode_tx_page_cursor(
                TxPageCursor(
                    window_start=w_start_iso,
                    window_end=w_end_iso,
                    last_period=last_item.occurred_at.isoformat(),
                    last_doc_uuid=doc_u,
                    last_line=int(l_num),
                )
            )
        else:
            hw = candidates[-1]
            hw_u, hw_l = hw.external_id.split(":")
            next_cursor = encode_tx_done_cursor(
                TxDoneCursor(
                    hw_period=hw.occurred_at.isoformat(),
                    hw_doc_uuid=hw_u,
                    hw_line=int(hw_l),
                    completed_at=now_utc.isoformat(),
                )
            )

        staged = [(tx.external_id, tx.occurred_at.isoformat()) for tx in page_items]
        self.state_store.record_pending_tx(next_cursor, staged)
        return SourceBatch(items=page_items, next_cursor=next_cursor, has_more=has_more)

    # --- Health & Shutdown ---

    def _ping_worker(self) -> bool:
        try:
            conn = self._get_connection()
            if hasattr(conn, "String"):
                conn.String(1)
            return True
        except Exception as exc:
            logger.warning("1C COM health check failed: %s", exc)
            self._reset_connection()
            return False

    async def check_health(self) -> bool:
        return await self._run_in_sta(self._ping_worker)

    async def close(self) -> None:
        self._connection = None
        gc.collect()
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, _sta_thread_uninit)
        except Exception:
            pass
        self._executor.shutdown(wait=True)
        gc.collect()
