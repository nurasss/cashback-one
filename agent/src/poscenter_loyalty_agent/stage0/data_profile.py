"""Data profile collector for POSCENTER ONE loyalty subsystem.

Strictly read-only data profiling:
- Only SELECT (ВЫБРАТЬ) queries.
- Zero INSERT/UPDATE/DELETE/WRITE operations.
- Zero locks, transactions, or temp tables (no ПОМЕСТИТЬ).
- ZERO raw customer/business data (no codes, barcodes, phones, names, receipt numbers,
  store names, or raw balances) written to output or console.
- Every query wrapped in try/except to allow partial execution without failure.
"""

from __future__ import annotations

import json
import logging
import re
import statistics
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from poscenter_loyalty_agent.stage0.sanitizer import validate_safe_output

logger = logging.getLogger(__name__)

# verified by Stage 0 metadata probe 2026-10-17, POSCENTERONE 2.0.0.26.9
CATALOG_BONUS_CARDS = "Справочник.БонусныеКарты"
# verified by Stage 0 metadata probe 2026-10-17, POSCENTERONE 2.0.0.26.9
CATALOG_WAREHOUSES = "Справочник.МестаХранения"
# verified by Stage 0 metadata probe 2026-10-17, POSCENTERONE 2.0.0.26.9
ACCUMULATION_REGISTER_BONUS_BALANCES = "РегистрНакопления.ОстаткиБонусныхКарт"
# verified by Stage 0 metadata probe 2026-10-17, POSCENTERONE 2.0.0.26.9
ACCUMULATION_REGISTER_BONUS_SALES = "РегистрНакопления.ПродажиПоБонуснымКартам"
# verified by Stage 0 metadata probe 2026-10-17, POSCENTERONE 2.0.0.26.9
DOCUMENT_CHECK = "Документ.Чек"
# verified by Stage 0 metadata probe 2026-10-17, POSCENTERONE 2.0.0.26.9
DOCUMENT_BONUS_CARD_MOVEMENT = "Документ.ДвижениеБонусныхКарт"
# verified by Stage 0 metadata probe 2026-10-17, POSCENTERONE 2.0.0.26.9
DOCUMENT_CASH_SHIFT_REPORT = "Документ.ОтчетКассовойСмены"
# verified by Stage 0 metadata probe 2026-10-17, POSCENTERONE 2.0.0.26.9
CATALOG_POS = "Справочник.POS"


def is_valid_ean13(val: str) -> bool:
    """Check if string is a valid EAN13 code with matching checksum."""
    if len(val) != 13 or not val.isdigit():
        return False
    digits = [int(c) for c in val]
    checksum = sum(digits[i] if i % 2 == 0 else digits[i] * 3 for i in range(12))
    check_digit = (10 - (checksum % 10)) % 10
    return check_digit == digits[12]


def compute_length_stats(lengths: list[int]) -> dict[str, Any]:
    """Compute min, max, mode, and median of length distribution."""
    if not lengths:
        return {"min": 0, "max": 0, "mode": 0, "median": 0, "count": 0}
    try:
        mode_val = statistics.mode(lengths)
    except Exception:
        mode_val = min(lengths)
    return {
        "min": min(lengths),
        "max": max(lengths),
        "mode": mode_val,
        "median": float(statistics.median(lengths)),
        "count": len(lengths),
    }


def profile_text_field(values: list[str]) -> dict[str, Any]:
    """Profile code/name fields for format, length, checksum, and duplicates without storing raw values."""
    empty_cnt = 0
    only_digits_cnt = 0
    exact_13_digits_cnt = 0
    valid_ean13_cnt = 0
    has_letters_cnt = 0
    lengths: list[int] = []
    val_counts: Counter[str] = Counter()

    for raw in values:
        s = str(raw or "").strip()
        if not s:
            empty_cnt += 1
            continue
        lengths.append(len(s))
        val_counts[s] += 1
        if s.isdigit():
            only_digits_cnt += 1
            if len(s) == 13:
                exact_13_digits_cnt += 1
                if is_valid_ean13(s):
                    valid_ean13_cnt += 1
        if any(c.isalpha() for c in s):
            has_letters_cnt += 1

    dup_values = sum(1 for v, c in val_counts.items() if c > 1)
    dup_rows = sum(c for v, c in val_counts.items() if c > 1)

    return {
        "empty": empty_cnt,
        "only_digits": only_digits_cnt,
        "exactly_13_digits": exact_13_digits_cnt,
        "valid_ean13": valid_ean13_cnt,
        "duplicate_distinct_values": dup_values,
        "duplicate_total_rows": dup_rows,
        "name_like_has_letters": has_letters_cnt,
        "length_distribution": compute_length_stats(lengths),
    }


def profile_phone_field(values: list[str]) -> dict[str, Any]:
    """Profile phone field for normalizability and digit count without storing raw values."""
    empty_cnt = 0
    normalizable_cnt = 0
    other_cnt = 0
    lengths: list[int] = []

    for raw in values:
        s = str(raw or "").strip()
        if not s:
            empty_cnt += 1
            continue
        digits = re.sub(r"\D", "", s)
        lengths.append(len(digits))
        if (len(digits) == 11 and digits.startswith(("7", "8"))) or (len(digits) == 10 and digits.startswith("7")):
            normalizable_cnt += 1
        else:
            other_cnt += 1

    return {
        "empty": empty_cnt,
        "normalizable": normalizable_cnt,
        "other": other_cnt,
        "digit_length_distribution": compute_length_stats(lengths),
    }


def profile_code_phone_relation(codes: list[str], phones: list[str]) -> dict[str, Any]:
    """Profile relation between Code and Phone in Справочник.БонусныеКарты (7.3)."""
    total = len(codes)
    code_digits_equal_phone_digits = 0
    last_10_digits_match = 0
    code_11_digits_starts_7_or_8 = 0
    code_starts_with_zero = 0

    padded_counts: Counter[str] = Counter()
    non_empty_codes = 0

    for code, phone in zip(codes, phones, strict=False):
        c_str = str(code or "").strip()
        p_str = str(phone or "").strip()

        c_digits = re.sub(r"\D", "", c_str)
        p_digits = re.sub(r"\D", "", p_str)

        if c_digits and p_digits and c_digits == p_digits:
            code_digits_equal_phone_digits += 1

        if len(c_digits) >= 10 and len(p_digits) >= 10 and c_digits[-10:] == p_digits[-10:]:
            last_10_digits_match += 1

        if len(c_digits) == 11 and c_digits.startswith(("7", "8")):
            code_11_digits_starts_7_or_8 += 1

        if c_str.startswith("0"):
            code_starts_with_zero += 1

        if c_str:
            non_empty_codes += 1
            padded_counts[c_str.zfill(13)] += 1

    unique_padded = len(padded_counts)
    dup_padded_values = sum(1 for _, cnt in padded_counts.items() if cnt > 1)
    dup_padded_rows = sum(cnt for _, cnt in padded_counts.items() if cnt > 1)

    return {
        "total_cards": total,
        "code_digits_equal_phone_digits_count": code_digits_equal_phone_digits,
        "code_digits_equal_phone_digits_percent": round(100.0 * code_digits_equal_phone_digits / total, 2) if total > 0 else 0.0,
        "last_10_digits_match_count": last_10_digits_match,
        "last_10_digits_match_percent": round(100.0 * last_10_digits_match / total, 2) if total > 0 else 0.0,
        "code_11_digits_starts_7_or_8_count": code_11_digits_starts_7_or_8,
        "code_11_digits_starts_7_or_8_percent": round(100.0 * code_11_digits_starts_7_or_8 / total, 2) if total > 0 else 0.0,
        "code_starts_with_zero_count": code_starts_with_zero,
        "code_starts_with_zero_percent": round(100.0 * code_starts_with_zero / total, 2) if total > 0 else 0.0,
        "zfill_13": {
            "non_empty_codes_padded": non_empty_codes,
            "unique_values_count": unique_padded,
            "duplicate_distinct_values": dup_padded_values,
            "duplicate_total_rows": dup_padded_rows,
            "has_collisions": dup_padded_values > 0,
        },
    }


def profile_name_frequency(names: list[str]) -> dict[str, Any]:
    """Profile duplicate frequencies for Наименование in Справочник.БонусныеКарты (7.5)."""
    counts: Counter[str] = Counter()
    for raw in names:
        s = str(raw or "").strip()
        if s:
            counts[s] += 1

    dup_distinct = sum(1 for _, cnt in counts.items() if cnt > 1)
    dup_rows = sum(cnt for _, cnt in counts.items() if cnt > 1)

    most_freq_cnt = 0
    most_freq_len = 0
    if counts:
        most_common_name, most_freq_cnt = counts.most_common(1)[0]
        most_freq_len = len(most_common_name)

    return {
        "duplicate_distinct_names": dup_distinct,
        "duplicate_total_rows": dup_rows,
        "most_frequent_count": most_freq_cnt,
        "most_frequent_name_length": most_freq_len,
    }


def profile_bonus_cards(conn: Any) -> dict[str, Any]:
    """3.1 Profile Справочник.БонусныеКарты."""
    section: dict[str, Any] = {"object_name": CATALOG_BONUS_CARDS}
    try:
        q = conn.NewObject("Запрос")
        q.Текст = f"""
        ВЫБРАТЬ
            Т.Код КАК Код,
            Т.Наименование КАК Наименование,
            Т.РучнойКод КАК РучнойКод,
            Т.Телефон КАК Телефон,
            Т.ЭтоГруппа КАК ЭтоГруппа,
            Т.ПометкаУдаления КАК ПометкаУдаления,
            Т.КартаЗапрещена КАК КартаЗапрещена
        ИЗ
            {CATALOG_BONUS_CARDS} КАК Т
        """
        res = q.Выполнить()
        sel = res.Выбрать()

        total = 0
        is_group_cnt = 0
        deletion_mark_cnt = 0
        card_disabled_cnt = 0
        codes: list[str] = []
        names: list[str] = []
        manual_codes: list[str] = []
        phones: list[str] = []

        while sel.Следующий():
            total += 1
            if bool(getattr(sel, "ЭтоГруппа", False)):
                is_group_cnt += 1
            if bool(getattr(sel, "ПометкаУдаления", False)):
                deletion_mark_cnt += 1
            if bool(getattr(sel, "КартаЗапрещена", False)):
                card_disabled_cnt += 1
            codes.append(str(getattr(sel, "Код", "") or ""))
            names.append(str(getattr(sel, "Наименование", "") or ""))
            manual_codes.append(str(getattr(sel, "РучнойКод", "") or ""))
            phones.append(str(getattr(sel, "Телефон", "") or ""))

        section["total_elements"] = total
        section["is_group_count"] = is_group_cnt
        section["deletion_mark_count"] = deletion_mark_cnt
        section["card_disabled_count"] = card_disabled_cnt

        section["code_profile"] = profile_text_field(codes)
        section["name_profile"] = profile_text_field(names)
        section["manual_code_profile"] = profile_text_field(manual_codes)
        section["phone_profile"] = profile_phone_field(phones)
        section["code_phone_relation"] = profile_code_phone_relation(codes, phones)
        section["name_duplicates_analysis"] = profile_name_frequency(names)

        # Clear raw string memory immediately
        del codes, names, manual_codes, phones

        # Check DataVersion (ВерсияДанных)
        try:
            vq = conn.NewObject("Запрос")
            vq.Текст = f"""
            ВЫБРАТЬ
                КОЛИЧЕСТВО(Т.ВерсияДанных) КАК Непустых
            ИЗ
                {CATALOG_BONUS_CARDS} КАК Т
            ГДЕ
                НЕ Т.ВерсияДанных ЕСТЬ NULL
            """
            vres = vq.Выполнить()
            vsel = vres.Выбрать()
            if vsel.Следующий():
                section["data_version"] = {"status": "available", "non_empty_count": int(vsel.Непустых or 0)}
            else:
                section["data_version"] = {"status": "available", "non_empty_count": 0}
        except Exception as vexc:
            section["data_version"] = {
                "status": "unavailable",
                "reason": f"недоступно через COM: {type(vexc).__name__}",
            }

    except Exception as exc:
        logger.error("Failed profiling %s: %s", CATALOG_BONUS_CARDS, exc)
        section["error"] = f"Query failed: {type(exc).__name__}: {exc}"

    return section


def _resolve_type_name(conn: Any, type_obj: Any) -> str:
    """Safely resolve 1C Type object or reference to metadata FullName."""
    if type_obj is None:
        return "Неопределено"
    try:
        if hasattr(conn, "Metadata") and hasattr(conn.Metadata, "FindByType"):
            md = conn.Metadata.FindByType(type_obj)
            if md and hasattr(md, "FullName"):
                return str(md.FullName())
    except Exception:
        pass
    if hasattr(conn, "String"):
        try:
            return str(conn.String(type_obj))
        except Exception:
            pass
    return str(type_obj)


def _resolve_ref_type_name(conn: Any, ref_obj: Any) -> str:
    """Safely resolve 1C Reference object to metadata FullName via TypeOf."""
    if ref_obj is None:
        return "Неопределено"
    try:
        t_val = conn.TypeOf(ref_obj) if hasattr(conn, "TypeOf") else None
        if t_val is not None:
            return _resolve_type_name(conn, t_val)
    except Exception:
        pass
    return _resolve_type_name(conn, ref_obj)


def profile_recorder_types_detailed(conn: Any) -> dict[str, dict[str, int]] | dict[str, str]:
    """Profile movements by exact recorder metadata type with receipt/expense breakdown (7.1)."""
    breakdown: dict[str, dict[str, int]] = {}

    # Method 1: Query grouped by ТИПЗНАЧЕНИЯ(Т.Регистратор)
    try:
        q = conn.NewObject("Запрос")
        q.Текст = f"""
        ВЫБРАТЬ
            ТИПЗНАЧЕНИЯ(Т.Регистратор) КАК ТипРегистратора,
            Т.ВидДвижения КАК ВидДвижения,
            КОЛИЧЕСТВО(*) КАК Кво
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
        СГРУППИРОВАТЬ ПО
            ТИПЗНАЧЕНИЯ(Т.Регистратор),
            Т.ВидДвижения
        """
        sel = q.Выполнить().Выбрать()
        while sel.Следующий():
            t_obj = getattr(sel, "ТипРегистратора", None)
            type_name = _resolve_type_name(conn, t_obj)
            move_kind_raw = getattr(sel, "ВидДвижения", None)
            move_kind_str = str(conn.String(move_kind_raw)) if hasattr(conn, "String") else str(move_kind_raw)
            kvo = int(getattr(sel, "Кво", 0) or 0)

            if type_name not in breakdown:
                breakdown[type_name] = {"total": 0, "receipt": 0, "expense": 0}
            breakdown[type_name]["total"] += kvo
            if "приход" in move_kind_str.lower():
                breakdown[type_name]["receipt"] += kvo
            elif "расход" in move_kind_str.lower():
                breakdown[type_name]["expense"] += kvo
            else:
                breakdown[type_name]["other_kind"] = breakdown[type_name].get("other_kind", 0) + kvo
        return breakdown
    except Exception as exc:
        logger.warning("Method 1 (ТИПЗНАЧЕНИЯ) failed for recorder breakdown: %s. Trying Method 2.", exc)

    # Method 2: Query grouped by Т.Регистратор
    try:
        q_fb = conn.NewObject("Запрос")
        q_fb.Текст = f"""
        ВЫБРАТЬ
            Т.Регистратор КАК Регистратор,
            Т.ВидДвижения КАК ВидДвижения,
            КОЛИЧЕСТВО(*) КАК Кво
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
        СГРУППИРОВАТЬ ПО
            Т.Регистратор,
            Т.ВидДвижения
        """
        sel_fb = q_fb.Выполнить().Выбрать()
        while sel_fb.Следующий():
            ref = getattr(sel_fb, "Регистратор", None)
            type_name = _resolve_ref_type_name(conn, ref)
            move_kind_raw = getattr(sel_fb, "ВидДвижения", None)
            move_kind_str = str(conn.String(move_kind_raw)) if hasattr(conn, "String") else str(move_kind_raw)
            kvo = int(getattr(sel_fb, "Кво", 0) or 0)

            if type_name not in breakdown:
                breakdown[type_name] = {"total": 0, "receipt": 0, "expense": 0}
            breakdown[type_name]["total"] += kvo
            if "приход" in move_kind_str.lower():
                breakdown[type_name]["receipt"] += kvo
            elif "расход" in move_kind_str.lower():
                breakdown[type_name]["expense"] += kvo
            else:
                breakdown[type_name]["other_kind"] = breakdown[type_name].get("other_kind", 0) + kvo
        return breakdown
    except Exception as exc2:
        logger.error("Method 2 fallback also failed for recorder breakdown: %s", exc2)
        return {"error": f"Failed profiling recorders: {exc2}"}


def profile_shift_report_recorders(conn: Any, has_shift_report: bool) -> dict[str, Any]:
    """Profile Документ.ОтчетКассовойСмены as recorder in ОстаткиБонусныхКарт (7.2)."""
    if not has_shift_report:
        return {
            "present_in_recorders": False,
            "total_movements": 0,
            "with_warehouse": 0,
            "warehouse_share_percent": 0.0,
            "distinct_warehouses_count": 0,
            "distinct_pos_count": 0,
        }

    res_dict: dict[str, Any] = {"present_in_recorders": True}
    try:
        # 1. Total movements and movements with non-empty warehouse
        q1 = conn.NewObject("Запрос")
        q1.Текст = f"""
        ВЫБРАТЬ
            КОЛИЧЕСТВО(*) КАК Всего,
            СУММА(ВЫБОР КОГДА ВЫРАЗИТЬ(Т.Регистратор КАК {DOCUMENT_CASH_SHIFT_REPORT}).Склад <> ЗНАЧЕНИЕ({CATALOG_WAREHOUSES}.ПустаяСсылка) И НЕ ВЫРАЗИТЬ(Т.Регистратор КАК {DOCUMENT_CASH_SHIFT_REPORT}).Склад ЕСТЬ NULL ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК СоСкладом
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
        ГДЕ
            Т.Регистратор ССЫЛКА {DOCUMENT_CASH_SHIFT_REPORT}
        """
        sel1 = q1.Выполнить().Выбрать()
        tot = 0
        with_wh = 0
        if sel1.Следующий():
            tot = int(sel1.Всего or 0)
            with_wh = int(sel1.СоСкладом or 0)

        res_dict["total_movements"] = tot
        res_dict["with_warehouse"] = with_wh
        res_dict["warehouse_share_percent"] = round(100.0 * with_wh / tot, 2) if tot > 0 else 0.0

        # 2. Distinct non-empty warehouses
        distinct_wh = 0
        if tot > 0:
            q2 = conn.NewObject("Запрос")
            q2.Текст = f"""
            ВЫБРАТЬ РАЗЛИЧНЫЕ
                ВЫРАЗИТЬ(Т.Регистратор КАК {DOCUMENT_CASH_SHIFT_REPORT}).Склад КАК Склад
            ИЗ
                {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
            ГДЕ
                Т.Регистратор ССЫЛКА {DOCUMENT_CASH_SHIFT_REPORT}
                И ВЫРАЗИТЬ(Т.Регистратор КАК {DOCUMENT_CASH_SHIFT_REPORT}).Склад <> ЗНАЧЕНИЕ({CATALOG_WAREHOUSES}.ПустаяСсылка)
                И НЕ ВЫРАЗИТЬ(Т.Регистратор КАК {DOCUMENT_CASH_SHIFT_REPORT}).Склад ЕСТЬ NULL
            """
            sel2 = q2.Выполнить().Выбрать()
            while sel2.Следующий():
                distinct_wh += 1
        res_dict["distinct_warehouses_count"] = distinct_wh

        # 3. Distinct non-empty POS
        distinct_pos = 0
        if tot > 0:
            q3 = conn.NewObject("Запрос")
            q3.Текст = f"""
            ВЫБРАТЬ РАЗЛИЧНЫЕ
                ВЫРАЗИТЬ(Т.Регистратор КАК {DOCUMENT_CASH_SHIFT_REPORT}).POS КАК POS
            ИЗ
                {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
            ГДЕ
                Т.Регистратор ССЫЛКА {DOCUMENT_CASH_SHIFT_REPORT}
                И ВЫРАЗИТЬ(Т.Регистратор КАК {DOCUMENT_CASH_SHIFT_REPORT}).POS <> ЗНАЧЕНИЕ({CATALOG_POS}.ПустаяСсылка)
                И НЕ ВЫРАЗИТЬ(Т.Регистратор КАК {DOCUMENT_CASH_SHIFT_REPORT}).POS ЕСТЬ NULL
            """
            sel3 = q3.Выполнить().Выбрать()
            while sel3.Следующий():
                distinct_pos += 1
        res_dict["distinct_pos_count"] = distinct_pos

    except Exception as exc:
        logger.error("Failed profiling shift report recorders: %s", exc)
        res_dict["error"] = f"Query failed: {type(exc).__name__}: {exc}"

    return res_dict


def profile_spend_total_realism(conn: Any, total_receipts: int, total_cards: int) -> dict[str, Any]:
    """Profile spend_total attribute (СуммаЧека) on receipt movements in ОстаткиБонусныхКарт (7.4)."""
    res: dict[str, Any] = {}
    try:
        # 1. Receipt records with СуммаЧека > 0
        q1 = conn.NewObject("Запрос")
        q1.Текст = f"""
        ВЫБРАТЬ
            КОЛИЧЕСТВО(*) КАК ЗаписейСЧекомБольше0
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
        ГДЕ
            Т.ВидДвижения = ЗНАЧЕНИЕ(ВидДвиженияНакопления.Приход)
            И Т.СуммаЧека > 0
        """
        sel1 = q1.Выполнить().Выбрать()
        gt0_records = 0
        if sel1.Следующий():
            gt0_records = int(sel1.ЗаписейСЧекомБольше0 or 0)
        res["receipt_records_with_summa_cheka_gt_0"] = gt0_records
        res["receipt_records_total"] = total_receipts
        res["receipt_records_share_percent"] = (
            round(100.0 * gt0_records / total_receipts, 2) if total_receipts > 0 else 0.0
        )

        # 2. Cards with at least one receipt movement with СуммаЧека > 0
        q2 = conn.NewObject("Запрос")
        q2.Текст = f"""
        ВЫБРАТЬ
            КОЛИЧЕСТВО(РАЗЛИЧНЫЕ Т.БонуснаяКарта) КАК КартСЧекомБольше0
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
        ГДЕ
            Т.ВидДвижения = ЗНАЧЕНИЕ(ВидДвиженияНакопления.Приход)
            И Т.СуммаЧека > 0
            И Т.БонуснаяКарта <> ЗНАЧЕНИЕ({CATALOG_BONUS_CARDS}.ПустаяСсылка)
            И НЕ Т.БонуснаяКарта ЕСТЬ NULL
        """
        sel2 = q2.Выполнить().Выбрать()
        gt0_cards = 0
        if sel2.Следующий():
            gt0_cards = int(sel2.КартСЧекомБольше0 or 0)
        res["cards_with_summa_cheka_gt_0"] = gt0_cards
        res["cards_total"] = total_cards
        res["cards_share_percent"] = round(100.0 * gt0_cards / total_cards, 2) if total_cards > 0 else 0.0

    except Exception as exc:
        logger.error("Failed profiling spend_total realism: %s", exc)
        res["error"] = f"Query failed: {type(exc).__name__}: {exc}"

    return res


def profile_bonus_movements(conn: Any, total_cards: int = 0) -> dict[str, Any]:
    """3.2 Profile РегистрНакопления.ОстаткиБонусныхКарт (движения — таблица регистра)."""
    section: dict[str, Any] = {"object_name": ACCUMULATION_REGISTER_BONUS_BALANCES}
    try:
        # 1. Total records, by movement kind (receipt/expense), min/max period
        q1 = conn.NewObject("Запрос")
        q1.Текст = f"""
        ВЫБРАТЬ
            КОЛИЧЕСТВО(*) КАК Всего,
            СУММА(ВЫБОР КОГДА Т.ВидДвижения = ЗНАЧЕНИЕ(ВидДвиженияНакопления.Приход) ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Приход,
            СУММА(ВЫБОР КОГДА Т.ВидДвижения = ЗНАЧЕНИЕ(ВидДвиженияНакопления.Расход) ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Расход,
            МИНИМУМ(Т.Период) КАК МинПериод,
            МАКСИМУМ(Т.Период) КАК МаксПериод
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
        """
        res1 = q1.Выполнить()
        sel1 = res1.Выбрать()
        max_period_dt: datetime | None = None
        if sel1.Следующий():
            section["total_records"] = int(sel1.Всего or 0)
            section["receipt_count"] = int(sel1.Приход or 0)
            section["expense_count"] = int(sel1.Расход or 0)
            min_p = getattr(sel1, "МинПериод", None)
            max_p = getattr(sel1, "МаксПериод", None)
            section["min_period"] = str(min_p) if min_p else None
            section["max_period"] = str(max_p) if max_p else None
            if max_p:
                try:
                    # In pywin32, 1C Date comes as python datetime or pywintypes.Time
                    max_period_dt = datetime.fromisoformat(str(max_p).replace("Z", ""))
                except Exception:
                    pass

        # 2. Recorder types
        q2 = conn.NewObject("Запрос")
        q2.Текст = f"""
        ВЫБРАТЬ
            СУММА(ВЫБОР КОГДА Т.Регистратор ССЫЛКА {DOCUMENT_CHECK} ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК РегистраторЧек,
            СУММА(ВЫБОР КОГДА Т.Регистратор ССЫЛКА {DOCUMENT_BONUS_CARD_MOVEMENT} ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК РегистраторДвижениеБонусныхКарт,
            СУММА(ВЫБОР КОГДА НЕ Т.Регистратор ССЫЛКА {DOCUMENT_CHECK} И НЕ Т.Регистратор ССЫЛКА {DOCUMENT_BONUS_CARD_MOVEMENT} ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Прочие
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
        """
        res2 = q2.Выполнить()
        sel2 = res2.Выбрать()
        if sel2.Следующий():
            section["recorders"] = {
                "document_check": int(sel2.РегистраторЧек or 0),
                "document_bonus_card_movement": int(sel2.РегистраторДвижениеБонусныхКарт or 0),
                "other": int(sel2.Прочие or 0),
            }

        # 3. Uniqueness of (Регистратор, НомерСтроки)
        q3 = conn.NewObject("Запрос")
        q3.Текст = f"""
        ВЫБРАТЬ
            Т.Регистратор КАК Регистратор,
            Т.НомерСтроки КАК НомерСтроки,
            КОЛИЧЕСТВО(*) КАК Кво
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
        СГРУППИРОВАТЬ ПО
            Т.Регистратор,
            Т.НомерСтроки
        ИМЕЮЩИЕ
            КОЛИЧЕСТВО(*) > 1
        """
        res3 = q3.Выполнить()
        sel3 = res3.Выбрать()
        dup_rows = 0
        while sel3.Следующий():
            dup_rows += 1
        section["recorder_line_number_duplicates"] = dup_rows

        # 4. Sum breakdown (<0, =0, >0) by movement kind
        q4 = conn.NewObject("Запрос")
        q4.Текст = f"""
        ВЫБРАТЬ
            Т.ВидДвижения КАК ВидДвижения,
            СУММА(ВЫБОР КОГДА Т.Сумма < 0 ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Меньше0,
            СУММА(ВЫБОР КОГДА Т.Сумма = 0 ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Ноль,
            СУММА(ВЫБОР КОГДА Т.Сумма > 0 ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Больше0
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
        СГРУППИРОВАТЬ ПО
            Т.ВидДвижения
        """
        res4 = q4.Выполнить()
        sel4 = res4.Выбрать()
        sum_breakdown: dict[str, Any] = {}
        while sel4.Следующий():
            kind_str = str(conn.String(sel4.ВидДвижения)) if hasattr(conn, "String") else str(sel4.ВидДвижения)
            sum_breakdown[kind_str] = {
                "less_than_zero": int(sel4.Меньше0 or 0),
                "equal_zero": int(sel4.Ноль or 0),
                "greater_than_zero": int(sel4.Больше0 or 0),
            }
        section["sum_breakdown_by_kind"] = sum_breakdown

        # 5. Decimal places (fractional points)
        q5 = conn.NewObject("Запрос")
        q5.Текст = f"""
        ВЫБРАТЬ
            КОЛИЧЕСТВО(*) КАК Всего,
            СУММА(ВЫБОР КОГДА Т.Сумма <> ВЫРАЗИТЬ(Т.Сумма КАК ЧИСЛО(15, 0)) ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК СДробнойЧастью
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
        """
        res5 = q5.Выполнить()
        sel5 = res5.Выбрать()
        fractional_count = 0
        if sel5.Следующий():
            fractional_count = int(sel5.СДробнойЧастью or 0)
        section["has_fractional_points"] = fractional_count > 0
        section["fractional_records_count"] = fractional_count
        section["max_decimal_places"] = 2 if fractional_count > 0 else 0

        # 6. Empty БонуснаяКарта
        q6 = conn.NewObject("Запрос")
        q6.Текст = f"""
        ВЫБРАТЬ
            КОЛИЧЕСТВО(*) КАК ПустаяКарта
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
        ГДЕ
            Т.БонуснаяКарта = ЗНАЧЕНИЕ({CATALOG_BONUS_CARDS}.ПустаяСсылка)
            ИЛИ Т.БонуснаяКарта ЕСТЬ NULL
        """
        res6 = q6.Выполнить()
        sel6 = res6.Выбрать()
        empty_card_count = 0
        if sel6.Следующий():
            empty_card_count = int(sel6.ПустаяКарта or 0)
        section["empty_bonus_card_count"] = empty_card_count

        # 7. Records in last 30 days
        section["records_last_30_days"] = 0
        if max_period_dt:
            cutoff = max_period_dt - timedelta(days=30)
            try:
                q7 = conn.NewObject("Запрос")
                q7.Текст = f"""
                ВЫБРАТЬ
                    КОЛИЧЕСТВО(*) КАК За30Дней
                ИЗ
                    {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
                ГДЕ
                    Т.Период >= &CutoffDate
                """
                q7.УстановитьПараметр("CutoffDate", cutoff)
                res7 = q7.Выполнить()
                sel7 = res7.Выбрать()
                if sel7.Следующий():
                    section["records_last_30_days"] = int(sel7.За30Дней or 0)
            except Exception as e7:
                section["records_last_30_days_error"] = str(e7)

        # 8. Non-empty Склад and Номер on Документ.Чек recorder
        q8 = conn.NewObject("Запрос")
        q8.Текст = f"""
        ВЫБРАТЬ
            КОЛИЧЕСТВО(*) КАК ВсегоЧеков,
            СУММА(ВЫБОР КОГДА ВЫРАЗИТЬ(Т.Регистратор КАК {DOCUMENT_CHECK}).Склад <> ЗНАЧЕНИЕ({CATALOG_WAREHOUSES}.ПустаяСсылка) И НЕ ВЫРАЗИТЬ(Т.Регистратор КАК {DOCUMENT_CHECK}).Склад ЕСТЬ NULL ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК СоСкладом,
            СУММА(ВЫБОР КОГДА ВЫРАЗИТЬ(Т.Регистратор КАК {DOCUMENT_CHECK}).Номер <> 0 И НЕ ВЫРАЗИТЬ(Т.Регистратор КАК {DOCUMENT_CHECK}).Номер ЕСТЬ NULL ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК СНомером
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
        ГДЕ
            Т.Регистратор ССЫЛКА {DOCUMENT_CHECK}
        """
        res8 = q8.Выполнить()
        sel8 = res8.Выбрать()
        if sel8.Следующий():
            tot_checks = int(sel8.ВсегоЧеков or 0)
            with_wh = int(sel8.СоСкладом or 0)
            with_num = int(sel8.СНомером or 0)
            section["check_recorders"] = {
                "total_movements_from_checks": tot_checks,
                "with_non_empty_warehouse": with_wh,
                "with_non_empty_number": with_num,
                "warehouse_coverage_percent": round(100.0 * with_wh / tot_checks, 2) if tot_checks > 0 else 0.0,
                "number_coverage_percent": round(100.0 * with_num / tot_checks, 2) if tot_checks > 0 else 0.0,
            }

        # 9. Detailed recorder breakdown (7.1)
        det_recorders = profile_recorder_types_detailed(conn)
        section["detailed_recorders"] = det_recorders

        # 10. Shift report recorder profiling (7.2)
        has_shift_report = DOCUMENT_CASH_SHIFT_REPORT in det_recorders or any(
            "ОтчетКассовойСмены" in k for k in det_recorders
        )
        section["shift_report_recorders"] = profile_shift_report_recorders(conn, has_shift_report)

        # 11. spend_total realism (7.4)
        section["spend_total_realism"] = profile_spend_total_realism(
            conn, section.get("receipt_count", 0), total_cards
        )

    except Exception as exc:
        logger.error("Failed profiling %s: %s", ACCUMULATION_REGISTER_BONUS_BALANCES, exc)
        section["error"] = f"Query failed: {type(exc).__name__}: {exc}"

    return section


def profile_bonus_balances_virtual(conn: Any) -> dict[str, Any]:
    """3.3 Profile РегистрНакопления.ОстаткиБонусныхКарт.Остатки() (virtual table)."""
    section: dict[str, Any] = {"table_name": f"{ACCUMULATION_REGISTER_BONUS_BALANCES}.Остатки"}
    try:
        q = conn.NewObject("Запрос")
        q.Текст = f"""
        ВЫБРАТЬ
            КОЛИЧЕСТВО(*) КАК ВсегоКартСОстатком,
            СУММА(ВЫБОР КОГДА Т.СуммаОстаток < 0 ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК КартСОтрицательнымОстатком,
            СУММА(Т.СуммаОстаток) КАК ОбщийОстаток
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES}.Остатки КАК Т
        ГДЕ
            Т.СуммаОстаток <> 0
        """
        res = q.Выполнить()
        sel = res.Выбрать()
        if sel.Следующий():
            cards_with_bal = int(sel.ВсегоКартСОстатком or 0)
            neg_cards = int(sel.КартСОтрицательнымОстатком or 0)
            raw_sum = float(sel.ОбщийОстаток or 0.0)
            sign_str = "> 0" if raw_sum > 0 else ("< 0" if raw_sum < 0 else "= 0")

            section["cards_with_non_zero_balance"] = cards_with_bal
            section["cards_with_negative_balance"] = neg_cards
            section["total_balance_sign"] = sign_str
        else:
            section["cards_with_non_zero_balance"] = 0
            section["cards_with_negative_balance"] = 0
            section["total_balance_sign"] = "= 0"
    except Exception as exc:
        logger.error("Failed profiling balances virtual table: %s", exc)
        section["error"] = f"Query failed: {type(exc).__name__}: {exc}"

    return section


def profile_bonus_sales_turnover(conn: Any) -> dict[str, Any]:
    """3.4 Profile РегистрНакопления.ПродажиПоБонуснымКартам.Обороты()."""
    section: dict[str, Any] = {"table_name": f"{ACCUMULATION_REGISTER_BONUS_SALES}.Обороты"}
    try:
        q = conn.NewObject("Запрос")
        q.Текст = f"""
        ВЫБРАТЬ
            КОЛИЧЕСТВО(РАЗЛИЧНЫЕ Т.БонуснаяКарта) КАК КартСОборотом,
            СУММА(Т.СуммаОборот) КАК ОбщийОборот
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_SALES}.Обороты КАК Т
        """
        res = q.Выполнить()
        sel = res.Выбрать()
        if sel.Следующий():
            cards_cnt = int(sel.КартСОборотом or 0)
            raw_sum = float(sel.ОбщийОборот or 0.0)
            sign_str = "> 0" if raw_sum > 0 else ("< 0" if raw_sum < 0 else "= 0")
            section["cards_with_turnover"] = cards_cnt
            section["total_turnover_sign"] = sign_str
        else:
            section["cards_with_turnover"] = 0
            section["total_turnover_sign"] = "= 0"
    except Exception as exc:
        logger.error("Failed profiling turnover virtual table: %s", exc)
        section["error"] = f"Query failed: {type(exc).__name__}: {exc}"

    return section


def profile_checks(conn: Any) -> dict[str, Any]:
    """3.5 Profile Документ.Чек."""
    section: dict[str, Any] = {"object_name": DOCUMENT_CHECK}
    try:
        q = conn.NewObject("Запрос")
        q.Текст = f"""
        ВЫБРАТЬ
            КОЛИЧЕСТВО(*) КАК ВсегоЧеков,
            СУММА(ВЫБОР КОГДА Т.ИнформационнаяКарта <> ЗНАЧЕНИЕ({CATALOG_BONUS_CARDS}.ПустаяСсылка) И НЕ Т.ИнформационнаяКарта ЕСТЬ NULL ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК СКартой,
            СУММА(ВЫБОР КОГДА Т.СуммаНачисленныхБонусов <> 0 ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК СНачисленнымиБонусами,
            СУММА(ВЫБОР КОГДА Т.СуммаСписанныхБонусов <> 0 ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК СоСписаннымиБонусами,
            СУММА(ВЫБОР КОГДА Т.СуммаНачисленныхБонусов <> 0 ИЛИ Т.СуммаСписанныхБонусов <> 0 ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК СБонуснымиОперациями
        ИЗ
            {DOCUMENT_CHECK} КАК Т
        """
        res = q.Выполнить()
        sel = res.Выбрать()
        if sel.Следующий():
            tot = int(sel.ВсегоЧеков or 0)
            with_card = int(sel.СКартой or 0)
            accrued = int(sel.СНачисленнымиБонусами or 0)
            spent = int(sel.СоСписаннымиБонусами or 0)
            any_bonus = int(sel.СБонуснымиОперациями or 0)

            section["total_checks"] = tot
            section["checks_with_card"] = with_card
            section["checks_with_accrued_bonuses"] = accrued
            section["checks_with_spent_bonuses"] = spent
            section["checks_with_any_bonus_operation"] = any_bonus
            section["card_coverage_percent"] = round(100.0 * with_card / tot, 2) if tot > 0 else 0.0
            section["bonus_operation_percent"] = round(100.0 * any_bonus / tot, 2) if tot > 0 else 0.0
    except Exception as exc:
        logger.error("Failed profiling %s: %s", DOCUMENT_CHECK, exc)
        section["error"] = f"Query failed: {type(exc).__name__}: {exc}"

    return section


def profile_monthly_balances_and_dynamics(conn: Any) -> dict[str, Any]:
    """Profile balances at month ends and peak expense day for Документ.ДвижениеБонусныхКарт (7.6)."""
    dates_to_check = [
        "2026-07-31 23:59:59",
        "2026-08-31 23:59:59",
        "2026-09-30 23:59:59",
        "2026-10-31 23:59:59",
    ]
    balances_by_date: list[dict[str, Any]] = []

    for d_str in dates_to_check:
        dt = datetime.strptime(d_str, "%Y-%m-%d %H:%M:%S")
        record: dict[str, Any] = {"date": d_str}
        cards_with_bal = 0
        method = "virtual_table"

        # Try virtual table first
        try:
            q = conn.NewObject("Запрос")
            q.Текст = f"""
            ВЫБРАТЬ
                КОЛИЧЕСТВО(*) КАК КартСОстатком
            ИЗ
                {ACCUMULATION_REGISTER_BONUS_BALANCES}.Остатки(&Период, ) КАК Т
            ГДЕ
                Т.СуммаОстаток <> 0
            """
            q.УстановитьПараметр("Период", dt)
            sel = q.Выполнить().Выбрать()
            if sel.Следующий():
                cards_with_bal = int(sel.КартСОстатком or 0)
        except Exception as exc:
            logger.warning("Virtual table query failed for date %s (%s). Falling back to movements.", d_str, exc)
            method = "movements_fallback"
            try:
                q_fb = conn.NewObject("Запрос")
                q_fb.Текст = f"""
                ВЫБРАТЬ
                    Т.БонуснаяКарта КАК БонуснаяКарта
                ИЗ
                    {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
                ГДЕ
                    Т.Период <= &Период
                СГРУППИРОВАТЬ ПО
                    Т.БонуснаяКарта
                ИМЕЮЩИЕ
                    СУММА(ВЫБОР КОГДА Т.ВидДвижения = ЗНАЧЕНИЕ(ВидДвиженияНакопления.Приход) ТОГДА Т.Сумма ИНАЧЕ -Т.Сумма КОНЕЦ) <> 0
                """
                q_fb.УстановитьПараметр("Период", dt)
                sel_fb = q_fb.Выполнить().Выбрать()
                cards_cnt = 0
                while sel_fb.Следующий():
                    cards_cnt += 1
                cards_with_bal = cards_cnt
            except Exception as exc2:
                logger.error("Movements fallback also failed for date %s: %s", d_str, exc2)
                record["error"] = f"Failed querying balance: {exc2}"

        record["cards_with_non_zero_balance"] = cards_with_bal
        record["calculation_method"] = method
        balances_by_date.append(record)

    # Peak expense day for Документ.ДвижениеБонусныхКарт
    peak_expense_day: dict[str, Any] = {
        "document_type": DOCUMENT_BONUS_CARD_MOVEMENT,
        "peak_date": None,
        "expense_movements_count": 0,
    }
    try:
        qp = conn.NewObject("Запрос")
        qp.Текст = f"""
        ВЫБРАТЬ
            НАЧАЛОПЕРИОДА(Т.Период, ДЕНЬ) КАК ДатаДня,
            КОЛИЧЕСТВО(*) КАК КвоДвижений
        ИЗ
            {ACCUMULATION_REGISTER_BONUS_BALANCES} КАК Т
        ГДЕ
            Т.ВидДвижения = ЗНАЧЕНИЕ(ВидДвиженияНакопления.Расход)
            И Т.Регистратор ССЫЛКА {DOCUMENT_BONUS_CARD_MOVEMENT}
        СГРУППИРОВАТЬ ПО
            НАЧАЛОПЕРИОДА(Т.Период, ДЕНЬ)
        УПОРЯДОЧИТЬ ПО
            КвоДвижений УБЫВ
        """
        selp = qp.Выполнить().Выбрать()
        if selp.Следующий():
            d_val = getattr(selp, "ДатаДня", None)
            d_str = ""
            if d_val:
                try:
                    d_str = str(d_val).split("T")[0].split(" ")[0]
                except Exception:
                    d_str = str(d_val)
            peak_expense_day["peak_date"] = d_str
            peak_expense_day["expense_movements_count"] = int(selp.КвоДвижений or 0)
    except Exception as exc_peak:
        logger.error("Failed querying peak expense day: %s", exc_peak)
        peak_expense_day["error"] = f"Query failed: {exc_peak}"

    return {
        "balances_by_month_end": balances_by_date,
        "peak_expense_day_movement_doc": peak_expense_day,
    }


def collect_data_profile(conn: Any) -> dict[str, Any]:
    """Execute all data profile collectors across live 1C connection."""
    cards = profile_bonus_cards(conn)
    total_cards = int(cards.get("total_elements", 0) or 0)
    movements = profile_bonus_movements(conn, total_cards=total_cards)
    balances = profile_bonus_balances_virtual(conn)
    turnover = profile_bonus_sales_turnover(conn)
    checks = profile_checks(conn)
    monthly_dyn = profile_monthly_balances_and_dynamics(conn)

    profile: dict[str, Any] = {
        "collected_at": datetime.now(UTC).isoformat(),
        "bonus_cards": cards,
        "bonus_movements": movements,
        "bonus_balances": balances,
        "bonus_sales_turnover": turnover,
        "checks": checks,
        "monthly_dynamics": monthly_dyn,
    }

    # Synthesize explicit conclusions for TOR (ТЗ)
    conclusions = []
    cards = profile["bonus_cards"]
    if "code_profile" in cards and "manual_code_profile" in cards:
        code_p = cards["code_profile"]
        m_code_p = cards["manual_code_profile"]
        if code_p.get("duplicate_distinct_values", 0) == 0 and code_p.get("empty", 0) == 0:
            conclusions.append(
                "Первичный идентификатор карты: 'Код' уникален (0 дубликатов, 0 пустых) и рекомендуется как первичный ключ."
            )
        else:
            conclusions.append(
                f"Первичный идентификатор карты: 'Код' имеет {code_p.get('duplicate_distinct_values')} дублей, "
                f"'РучнойКод' имеет {m_code_p.get('duplicate_distinct_values')} дублей. Требуется согласование правила дедупликации."
            )

        if code_p.get("duplicate_distinct_values", 0) > 0 or m_code_p.get("duplicate_distinct_values", 0) > 0:
            conclusions.append("Чистка дубликатов: ТРЕБУЕТСЯ — обнаружены неуникальные значения номеров/кодов карт.")
        else:
            conclusions.append("Чистка дубликатов: НЕ ТРЕБУЕТСЯ — все коды карт уникальны.")

    movs = profile["bonus_movements"]
    if "has_fractional_points" in movs:
        if movs["has_fractional_points"]:
            conclusions.append(
                f"Дробные баллы: ОБНАРУЖЕНЫ ({movs.get('fractional_records_count')} записей с дробной частью). "
                f"В Cloud API требуется передавать баланс с точностью до {movs.get('max_decimal_places', 2)} знаков."
            )
        else:
            conclusions.append("Дробные баллы: НЕ ОБНАРУЖЕНЫ — все суммы начислений и списаний строго целочисленные.")

    bals = profile["bonus_balances"]
    if "cards_with_negative_balance" in bals:
        neg = bals["cards_with_negative_balance"]
        if neg > 0:
            conclusions.append(
                f"Аномалии в остатках: ОБНАРУЖЕНЫ — {neg} карт имеют отрицательный баланс. Требуется правило миграции."
            )
        else:
            conclusions.append("Аномалии в остатках: НЕ ОБНАРУЖЕНЫ — отрицательные балансы отсутствуют.")

    profile["conclusions_for_tor"] = conclusions
    return profile


def generate_data_profile_md(profile: dict[str, Any]) -> str:
    """Generate sanitized, human-readable markdown report for Section 3."""
    lines = [
        "# POSCENTER ONE Data Profile Report (Stage 0)",
        "",
        "> **Data Safety Notice:** Strictly aggregate statistics. Zero customer PII, zero card codes, "
        "zero phone numbers, zero receipt numbers, and zero exact balances are contained in this document.",
        "",
        f"- **Collected At:** `{profile.get('collected_at')}`",
        "",
        "## Выводы для Технического Задания (ТЗ)",
        "",
    ]

    for c in profile.get("conclusions_for_tor", []):
        lines.append(f"- **{c}**")

    lines.append("")
    lines.append("## 3.1. Справочник.БонусныеКарты")
    lines.append("")
    cards = profile.get("bonus_cards", {})
    if "error" in cards:
        lines.append(f"> **Ошибка выполнения:** `{cards['error']}`")
    else:
        lines.append(f"- **Всего элементов:** `{cards.get('total_elements', 0)}`")
        lines.append(f"- **Групп (ЭтоГруппа = Истина):** `{cards.get('is_group_count', 0)}`")
        lines.append(f"- **Помеченных на удаление:** `{cards.get('deletion_mark_count', 0)}`")
        lines.append(f"- **Заблокированных (КартаЗапрещена = Истина):** `{cards.get('card_disabled_count', 0)}`")

        dver = cards.get("data_version", {})
        if dver.get("status") == "available":
            lines.append(f"- **ВерсияДанных (непустых):** `{dver.get('non_empty_count')}`")
        else:
            lines.append(f"- **ВерсияДанных:** `{dver.get('reason', 'недоступно')}`")

        lines.append("")
        lines.append("### Профиль ключевых реквизитов карт")
        lines.append("")
        lines.append("| Реквизит | Пустых | Только цифры | Ровно 13 цифр | Валидный EAN13 | Дублей (значений/строк) | Содержит буквы | Длины (мин/макс/мода/мед) |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for field_key, field_name in (
            ("code_profile", "Код"),
            ("name_profile", "Наименование"),
            ("manual_code_profile", "РучнойКод"),
        ):
            p = cards.get(field_key, {})
            l_dist = p.get("length_distribution", {})
            lens_str = f"{l_dist.get('min')}/{l_dist.get('max')}/{l_dist.get('mode')}/{l_dist.get('median')}"
            dups_str = f"{p.get('duplicate_distinct_values', 0)} / {p.get('duplicate_total_rows', 0)}"
            lines.append(
                f"| `{field_name}` | {p.get('empty', 0)} | {p.get('only_digits', 0)} | "
                f"{p.get('exactly_13_digits', 0)} | {p.get('valid_ean13', 0)} | "
                f"{dups_str} | {p.get('name_like_has_letters', 0)} | `{lens_str}` |"
            )

        phone_p = cards.get("phone_profile", {})
        pl = phone_p.get("digit_length_distribution", {})
        plens_str = f"{pl.get('min')}/{pl.get('max')}/{pl.get('mode')}/{pl.get('median')}"
        lines.append("")
        lines.append("### Профиль поля Телефон")
        lines.append(f"- **Пустых:** `{phone_p.get('empty', 0)}`")
        lines.append(f"- **Нормализуемых (11 цифр с 7/8 или 10 с 7):** `{phone_p.get('normalizable', 0)}`")
        lines.append(f"- **Прочих (нестандартная длина/формат):** `{phone_p.get('other', 0)}`")
        lines.append(f"- **Распределение цифр по длинам (мин/макс/мода/мед):** `{plens_str}`")

        c_rel = cards.get("code_phone_relation", {})
        if c_rel:
            zfill = c_rel.get("zfill_13", {})
            lines.append("")
            lines.append("### Связь Код <-> Телефон (в памяти)")
            lines.append(
                f"- **Код (только цифры) == Телефон (только цифры):** "
                f"`{c_rel.get('code_digits_equal_phone_digits_count', 0)}` ({c_rel.get('code_digits_equal_phone_digits_percent')}%)"
            )
            lines.append(
                f"- **Совпадение последних 10 цифр Кода и Телефона:** "
                f"`{c_rel.get('last_10_digits_match_count', 0)}` ({c_rel.get('last_10_digits_match_percent')}%)"
            )
            lines.append(
                f"- **Код из 11 цифр, начинающийся на 7 или 8:** "
                f"`{c_rel.get('code_11_digits_starts_7_or_8_count', 0)}` ({c_rel.get('code_11_digits_starts_7_or_8_percent')}%)"
            )
            lines.append(
                f"- **Код начинается с '0':** "
                f"`{c_rel.get('code_starts_with_zero_count', 0)}` ({c_rel.get('code_starts_with_zero_percent')}%)"
            )
            lines.append("- **Дополнение кодов нулями до 13 символов (`zfill(13)`):**")
            lines.append(f"  - Непустых дополненных кодов: `{zfill.get('non_empty_codes_padded', 0)}`")
            lines.append(f"  - Уникальных 13-значных значений: `{zfill.get('unique_values_count', 0)}`")
            lines.append(
                f"  - Дублирующихся значений: `{zfill.get('duplicate_distinct_values', 0)}` "
                f"(охватывают строк: `{zfill.get('duplicate_total_rows', 0)}`)"
            )
            lines.append(f"  - Возникают ли коллизии: `{'ДА' if zfill.get('has_collisions') else 'НЕТ'}`")

        n_freq = cards.get("name_duplicates_analysis", {})
        if n_freq:
            lines.append("")
            lines.append("### Анализ дубликатов Наименования (в памяти)")
            lines.append(
                f"- **Уникальных Наименований, встречающихся более 1 раза:** "
                f"`{n_freq.get('duplicate_distinct_names', 0)}` (охватывают строк: `{n_freq.get('duplicate_total_rows', 0)}`)"
            )
            lines.append(
                f"- **Самое частое Наименование:** встречается `{n_freq.get('most_frequent_count', 0)}` раз, "
                f"длина в символах: `{n_freq.get('most_frequent_name_length', 0)}` (само значение скрыто)"
            )

    lines.append("")
    lines.append("## 3.2. РегистрНакопления.ОстаткиБонусныхКарт (движения)")
    lines.append("")
    movs = profile.get("bonus_movements", {})
    if "error" in movs:
        lines.append(f"> **Ошибка выполнения:** `{movs['error']}`")
    else:
        lines.append(f"- **Всего записей движений:** `{movs.get('total_records', 0)}`")
        lines.append(f"  - Приход: `{movs.get('receipt_count', 0)}`")
        lines.append(f"  - Расход: `{movs.get('expense_count', 0)}`")
        lines.append(f"- **Период первого движения:** `{movs.get('min_period', 'Н/Д')}`")
        lines.append(f"- **Период последнего движения:** `{movs.get('max_period', 'Н/Д')}`")
        lines.append(f"- **Движений за последние 30 дней от максимальной даты:** `{movs.get('records_last_30_days', 0)}`")
        lines.append(f"- **Записей с пустой БонуснойКартой:** `{movs.get('empty_bonus_card_count', 0)}`")
        lines.append(f"- **Дубликатов по ключу (Регистратор, НомерСтроки):** `{movs.get('recorder_line_number_duplicates', 0)}`")

        recs = movs.get("recorders", {})
        lines.append("- **Распределение по типам регистраторов:**")
        lines.append(f"  - Документ.Чек: `{recs.get('document_check', 0)}`")
        lines.append(f"  - Документ.ДвижениеБонусныхКарт: `{recs.get('document_bonus_card_movement', 0)}`")
        lines.append(f"  - Прочие: `{recs.get('other', 0)}`")

        lines.append("- **Разбивка сумм движений:**")
        for kind, s_data in movs.get("sum_breakdown_by_kind", {}).items():
            lines.append(
                f"  - {kind}: `<0`: `{s_data.get('less_than_zero')}`, `=0`: `{s_data.get('equal_zero')}`, `>0`: `{s_data.get('greater_than_zero')}`"
            )

        lines.append(f"- **Наличие дробных баллов:** `{movs.get('has_fractional_points')}` (макс. знаков: `{movs.get('max_decimal_places')}`)")

        chk_rec = movs.get("check_recorders", {})
        if chk_rec:
            lines.append("- **Проверка разыменования регистратора (Документ.Чек):**")
            lines.append(f"  - Всего движений от чеков: `{chk_rec.get('total_movements_from_checks', 0)}`")
            lines.append(f"  - Движений с непустым Складом: `{chk_rec.get('with_non_empty_warehouse', 0)}` ({chk_rec.get('warehouse_coverage_percent')}%)")
            lines.append(f"  - Движений с непустым Номером: `{chk_rec.get('with_non_empty_number', 0)}` ({chk_rec.get('number_coverage_percent')}%)")

        det_recs = movs.get("detailed_recorders", {})
        if det_recs:
            lines.append("")
            lines.append("### Распределение движений по типам регистраторов (детально)")
            lines.append("| Тип документа-регистратора | Всего движений | Приход | Расход |")
            lines.append("|---|---|---|---|")
            for t_name, counts in sorted(det_recs.items(), key=lambda x: x[1].get("total", 0), reverse=True):
                lines.append(
                    f"| `{t_name}` | {counts.get('total', 0)} | {counts.get('receipt', 0)} | {counts.get('expense', 0)} |"
                )

        shift_rep = movs.get("shift_report_recorders", {})
        if shift_rep:
            lines.append("")
            lines.append("### Анализ регистратора Документ.ОтчетКассовойСмены")
            lines.append(f"- **Присутствует среди регистраторов:** `{'ДА' if shift_rep.get('present_in_recorders') else 'НЕТ'}`")
            lines.append(f"- **Всего движений от Отчетов кассовой смены:** `{shift_rep.get('total_movements', 0)}`")
            lines.append(
                f"- **Движений с непустым Складом:** `{shift_rep.get('with_warehouse', 0)}` ({shift_rep.get('warehouse_share_percent')}%)"
            )
            lines.append(f"- **Число уникальных складов (Склад <> ПустаяСсылка):** `{shift_rep.get('distinct_warehouses_count', 0)}`")
            lines.append(f"- **Число уникальных POS (POS <> ПустаяСсылка):** `{shift_rep.get('distinct_pos_count', 0)}`")

        sp = movs.get("spend_total_realism", {})
        if sp:
            lines.append("")
            lines.append("### Реалистичность spend_total (СуммаЧека в ОстаткиБонусныхКарт)")
            if "error" in sp:
                lines.append(f"> **Ошибка анализа СуммаЧека:** `{sp['error']}`")
            else:
                lines.append(
                    f"- **Записей Приход с СуммаЧека > 0:** `{sp.get('receipt_records_with_summa_cheka_gt_0', 0)}` "
                    f"из `{sp.get('receipt_records_total', 0)}` ({sp.get('receipt_records_share_percent')}%)"
                )
                lines.append(
                    f"- **Карт с хотя бы одной записью Приход с СуммаЧека > 0:** `{sp.get('cards_with_summa_cheka_gt_0', 0)}` "
                    f"из `{sp.get('cards_total', 0)}` ({sp.get('cards_share_percent')}%)"
                )

    lines.append("")
    lines.append("## 3.3. РегистрНакопления.ОстаткиБонусныхКарт.Остатки() (текущие остатки)")
    lines.append("")
    bals = profile.get("bonus_balances", {})
    if "error" in bals:
        lines.append(f"> **Ошибка выполнения:** `{bals['error']}`")
    else:
        lines.append(f"- **Карт с ненулевым остатком:** `{bals.get('cards_with_non_zero_balance', 0)}`")
        lines.append(f"- **Карт с отрицательным остатком (аномалия):** `{bals.get('cards_with_negative_balance', 0)}`")
        lines.append(f"- **Знак суммарного баланса всех карт:** `{bals.get('total_balance_sign', 'Н/Д')}` (точное значение скрыто)")

    lines.append("")
    lines.append("## 3.4. РегистрНакопления.ПродажиПоБонуснымКартам.Обороты() (обороты)")
    lines.append("")
    sales = profile.get("bonus_sales_turnover", {})
    if "error" in sales:
        lines.append(f"> **Ошибка выполнения:** `{sales['error']}`")
    else:
        lines.append(f"- **Карт с оборотом за всё время:** `{sales.get('cards_with_turnover', 0)}`")
        lines.append(f"- **Знак суммарного оборота:** `{sales.get('total_turnover_sign', 'Н/Д')}` (точное значение скрыто)")

    lines.append("")
    lines.append("## 3.5. Документ.Чек (чеки и бонусные операции)")
    lines.append("")
    checks = profile.get("checks", {})
    if "error" in checks:
        lines.append(f"> **Ошибка выполнения:** `{checks['error']}`")
    else:
        lines.append(f"- **Всего чеков в базе:** `{checks.get('total_checks', 0)}`")
        lines.append(f"- **Чеков с привязанной картой (ИнформационнаяКарта):** `{checks.get('checks_with_card', 0)}` ({checks.get('card_coverage_percent')}%)")
        lines.append(f"- **Чеков с начисленными бонусами:** `{checks.get('checks_with_accrued_bonuses', 0)}`")
        lines.append(f"- **Чеков со списанными бонусами:** `{checks.get('checks_with_spent_bonuses', 0)}`")
        lines.append(f"- **Чеков с любыми бонусными операциями:** `{checks.get('checks_with_any_bonus_operation', 0)}` ({checks.get('bonus_operation_percent')}%)")

    lines.append("")
    lines.append("## 3.6. Динамика остатков по месяцам и пиковые списания")
    lines.append("")
    dyn = profile.get("monthly_dynamics", {})
    if "error" in dyn:
        lines.append(f"> **Ошибка выполнения:** `{dyn['error']}`")
    else:
        lines.append("### Остатки на конец месяцев (динамика активных карт)")
        lines.append("")
        lines.append("| Дата среза | Карт с ненулевым остатком | Метод расчета |")
        lines.append("|---|---|---|")
        for b_entry in dyn.get("balances_by_month_end", []):
            lines.append(
                f"| `{b_entry.get('date')}` | {b_entry.get('cards_with_non_zero_balance', 0)} | `{b_entry.get('calculation_method')}` |"
            )

        lines.append("")
        lines.append("### Пиковый день списаний (Документ.ДвижениеБонусныхКарт)")
        peak = dyn.get("peak_expense_day_movement_doc", {})
        if "error" in peak:
            lines.append(f"> **Ошибка анализа пикового дня:** `{peak['error']}`")
        else:
            lines.append(f"- **Документ:** `{peak.get('document_type')}`")
            lines.append(f"- **Дата пикового дня:** `{peak.get('peak_date') or 'Н/Д'}`")
            lines.append(f"- **Число списаний в пиковый день:** `{peak.get('expense_movements_count', 0)}`")

    return "\n".join(lines)


def write_data_profile_reports(profile: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    """Validate safety and write data_profile.json and data_profile.md."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "data_profile.json"
    md_path = output_dir / "data_profile.md"

    # JSON report
    json_content = json.dumps(profile, indent=2, ensure_ascii=False)
    validate_safe_output(json_content, context="data_profile.json")
    json_path.write_text(json_content, encoding="utf-8")

    # Markdown report
    md_content = generate_data_profile_md(profile)
    validate_safe_output(md_content, context="data_profile.md")
    md_path.write_text(md_content, encoding="utf-8")

    return json_path, md_path
