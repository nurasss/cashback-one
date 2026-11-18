"""Read-only probe: is `СуммаЧека` in РегистрНакопления.ОстаткиБонусныхКарт usable as the receipt amount
of each bonus operation?

Run ONLY on KONS2 against the test ONE base (C:\\1C_data\\int), with the existing x86 agent environment:

    C:\\cashback-venv\\Scripts\\python.exe docs\\tools\\receipt-amount-probe\\probe_receipt_amount.py
        --out reports\\receipt-amount-probe-kons2-2026-11-18

What it does:
  * connects to ONE with OneComConnector using ONLY the ONE_CONNECTION_STRING variable that the owner sets
    hidden in their own PowerShell session (as for the Stage 0 profile); the agent service settings are not read;
  * reads metadata names/types and runs a fixed set of aggregate `ВЫБРАТЬ` queries;
  * writes probe.json and probe.md with counts only. Cards and registrar documents appear as local labels
    (C1, R1, ...); barcodes, phones, names, document numbers, GUIDs and the connection string are never written.

What it never does: write to 1C, start/stop the agent service, open the agent StateStore, talk to the cloud.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REGISTER = "РегистрНакопления.ОстаткиБонусныхКарт"
REGISTER_NAME = "ОстаткиБонусныхКарт"
CARD_DIM = "БонуснаяКарта"
AMOUNT = "Сумма"
RECEIPT = "СуммаЧека"
DOCS_TO_DESCRIBE = ("Чек", "ОтчетКассовойСмены", "ДвижениеБонусныхКарт")
SAMPLE_ROW_LIMIT = 60

INCOME = "ЗНАЧЕНИЕ(ВидДвиженияНакопления.Приход)"
EXPENSE = "ЗНАЧЕНИЕ(ВидДвиженияНакопления.Расход)"

QUERIES: dict[str, str] = {
    # 1. How many rows have a receipt amount, by movement kind and registrar document type.
    "coverage": f"""
ВЫБРАТЬ
    В.Вид КАК Вид,
    В.ТипРегистратора КАК ТипРегистратора,
    КОЛИЧЕСТВО(*) КАК Строк,
    СУММА(ВЫБОР КОГДА В.СЧ > 0 ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК СЧекомБольше0,
    СУММА(ВЫБОР КОГДА В.СЧ = 0 ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК СЧекомРавно0,
    СУММА(ВЫБОР КОГДА В.СЧ < 0 ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК СЧекомМеньше0,
    МИНИМУМ(В.Период) КАК ПервыйПериод,
    МАКСИМУМ(В.Период) КАК ПоследнийПериод
ИЗ
    (ВЫБРАТЬ
        Т.ВидДвижения КАК Вид,
        ТИПЗНАЧЕНИЯ(Т.Регистратор) КАК ТипРегистратора,
        Т.{RECEIPT} КАК СЧ,
        Т.Период КАК Период
    ИЗ
        {REGISTER} КАК Т) КАК В
СГРУППИРОВАТЬ ПО
    В.Вид,
    В.ТипРегистратора
""",
    # 2. Same registrar + card + moment: several rows? Same receipt amount repeated (per item) or different?
    "rows_per_moment": f"""
ВЫБРАТЬ
    В.Строк КАК Строк,
    В.РазныхСумм КАК РазныхСумм,
    КОЛИЧЕСТВО(*) КАК Групп
ИЗ
    (ВЫБРАТЬ
        Т.Регистратор КАК Регистратор,
        Т.{CARD_DIM} КАК Карта,
        Т.Период КАК Период,
        КОЛИЧЕСТВО(*) КАК Строк,
        КОЛИЧЕСТВО(РАЗЛИЧНЫЕ Т.{RECEIPT}) КАК РазныхСумм
    ИЗ
        {REGISTER} КАК Т
    ГДЕ
        Т.ВидДвижения = {INCOME}
    СГРУППИРОВАТЬ ПО
        Т.Регистратор,
        Т.{CARD_DIM},
        Т.Период) КАК В
СГРУППИРОВАТЬ ПО
    В.Строк,
    В.РазныхСумм
""",
    # 3. Same registrar + card over the whole shift: how many moments (checks?) per shift.
    "rows_per_shift_card": f"""
ВЫБРАТЬ
    В.Строк КАК Строк,
    В.РазныхМоментов КАК РазныхМоментов,
    В.РазныхСумм КАК РазныхСумм,
    КОЛИЧЕСТВО(*) КАК Групп
ИЗ
    (ВЫБРАТЬ
        Т.Регистратор КАК Регистратор,
        Т.{CARD_DIM} КАК Карта,
        КОЛИЧЕСТВО(*) КАК Строк,
        КОЛИЧЕСТВО(РАЗЛИЧНЫЕ Т.Период) КАК РазныхМоментов,
        КОЛИЧЕСТВО(РАЗЛИЧНЫЕ Т.{RECEIPT}) КАК РазныхСумм
    ИЗ
        {REGISTER} КАК Т
    ГДЕ
        Т.ВидДвижения = {INCOME}
    СГРУППИРОВАТЬ ПО
        Т.Регистратор,
        Т.{CARD_DIM}) КАК В
СГРУППИРОВАТЬ ПО
    В.Строк,
    В.РазныхМоментов,
    В.РазныхСумм
""",
    # 4. Accrued bonus as a percent of the receipt amount: clusters near the tier percents mean СуммаЧека is
    #    the receipt total the bonus was calculated from.
    "accrual_percent": f"""
ВЫБРАТЬ ПЕРВЫЕ 25
    В.Процент КАК Процент,
    КОЛИЧЕСТВО(*) КАК Строк
ИЗ
    (ВЫБРАТЬ
        ВЫРАЗИТЬ(Т.{AMOUNT} * 100 / Т.{RECEIPT} КАК ЧИСЛО(8, 1)) КАК Процент
    ИЗ
        {REGISTER} КАК Т
    ГДЕ
        Т.ВидДвижения = {INCOME}
        И Т.{RECEIPT} > 0) КАК В
СГРУППИРОВАТЬ ПО
    В.Процент
УПОРЯДОЧИТЬ ПО
    Строк УБЫВ
""",
    # 5. Redemption rows: do they sit on the same registrar + card + moment as an accrual (same check)?
    "expense_pairing": f"""
ВЫБРАТЬ
    КОЛИЧЕСТВО(*) КАК МоментовСписания,
    СУММА(ВЫБОР КОГДА П.Регистратор ЕСТЬ NULL ТОГДА 0 ИНАЧЕ 1 КОНЕЦ) КАК СНачислениемВТотЖеМомент
ИЗ
    (ВЫБРАТЬ РАЗЛИЧНЫЕ
        Т.Регистратор КАК Регистратор,
        Т.{CARD_DIM} КАК Карта,
        Т.Период КАК Период
    ИЗ
        {REGISTER} КАК Т
    ГДЕ
        Т.ВидДвижения = {EXPENSE}) КАК Р
        ЛЕВОЕ СОЕДИНЕНИЕ (ВЫБРАТЬ РАЗЛИЧНЫЕ
            Т.Регистратор КАК Регистратор,
            Т.{CARD_DIM} КАК Карта,
            Т.Период КАК Период
        ИЗ
            {REGISTER} КАК Т
        ГДЕ
            Т.ВидДвижения = {INCOME}) КАК П
        ПО Р.Регистратор = П.Регистратор
            И Р.Карта = П.Карта
            И Р.Период = П.Период
""",
    # 6. The most recent registrar that has receipt amounts (sample source).
    "latest_registrar": f"""
ВЫБРАТЬ ПЕРВЫЕ 1
    Т.Регистратор КАК Регистратор,
    Т.Период КАК Период
ИЗ
    {REGISTER} КАК Т
ГДЕ
    Т.{RECEIPT} > 0
УПОРЯДОЧИТЬ ПО
    Т.Период УБЫВ
""",
    "sample_rows": f"""
ВЫБРАТЬ ПЕРВЫЕ {SAMPLE_ROW_LIMIT}
    Т.Период КАК Период,
    Т.НомерСтроки КАК НомерСтроки,
    Т.ВидДвижения КАК Вид,
    Т.{CARD_DIM}.Код КАК КартаКод,
    Т.{AMOUNT} КАК Сумма,
    Т.{RECEIPT} КАК СуммаЧека
ИЗ
    {REGISTER} КАК Т
ГДЕ
    Т.Регистратор = &Регистратор
УПОРЯДОЧИТЬ ПО
    Т.Период,
    Т.НомерСтроки
""",
}


def assert_read_only(text: str) -> None:
    if not text.strip().upper().startswith("ВЫБРАТЬ"):
        raise ValueError("only ВЫБРАТЬ queries are allowed")
    lowered = text.lower()
    for forbidden in ("записать", "удалить", "поместить", "уничтожить"):
        if forbidden in lowered:
            raise ValueError(f"forbidden keyword in query: {forbidden}")


def to_plain(conn: Any, value: Any) -> Any:
    """COM value → JSON-friendly value without personal data (callers decide what is emitted)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return str(Decimal(str(value)).normalize())
    if isinstance(value, Decimal):
        return str(value.normalize())
    if isinstance(value, datetime):
        return value.replace(tzinfo=None).isoformat(sep=" ")
    try:
        return str(conn.String(value))
    except Exception:  # noqa: BLE001 - diagnostic tool, keep going
        return type(value).__name__


def run_query(conn: Any, text: str, fields: list[str], params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    assert_read_only(text)
    query = conn.NewObject("Запрос")
    query.Текст = text
    for name, value in (params or {}).items():
        query.УстановитьПараметр(name, value)
    selection = query.Выполнить().Выбрать()
    rows: list[dict[str, Any]] = []
    while selection.Следующий():
        rows.append({field: getattr(selection, field) for field in fields})
    return rows


def describe_metadata(conn: Any) -> dict[str, Any]:
    """Names and types of the register fields and of the documents that may hold the receipt."""
    out: dict[str, Any] = {}
    md = conn.Метаданные
    register = md.РегистрыНакопления.Найти(REGISTER_NAME)
    if register is None:
        out["register"] = "NOT FOUND"
    else:
        reg: dict[str, Any] = {"kind": to_plain(conn, register.ВидРегистра)}
        for part, attr in (("dimensions", "Измерения"), ("resources", "Ресурсы"), ("attributes", "Реквизиты")):
            reg[part] = [
                {"name": str(item.Имя), "type": to_plain(conn, item.Тип)} for item in getattr(register, attr)
            ]
        out["register"] = reg
    docs: dict[str, Any] = {}
    for doc_name in DOCS_TO_DESCRIBE:
        doc = md.Документы.Найти(doc_name)
        if doc is None:
            docs[doc_name] = "NOT FOUND"
            continue
        docs[doc_name] = {
            "attributes": [{"name": str(a.Имя), "type": to_plain(conn, a.Тип)} for a in doc.Реквизиты],
            "tabular_sections": [
                {
                    "name": str(ts.Имя),
                    "attributes": [{"name": str(a.Имя), "type": to_plain(conn, a.Тип)} for a in ts.Реквизиты],
                }
                for ts in doc.ТабличныеЧасти
            ],
            "writes_bonus_register": any(str(r.Имя) == REGISTER_NAME for r in doc.Движения),
        }
    out["documents"] = docs
    return out


def anonymize_sample(conn: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels: dict[str, str] = {}
    result = []
    for row in rows:
        card_key = str(row["КартаКод"])
        label = labels.setdefault(card_key, f"C{len(labels) + 1}")
        period = row["Период"]
        result.append(
            {
                "time": period.strftime("%H:%M:%S") if isinstance(period, datetime) else to_plain(conn, period),
                "line": int(row["НомерСтроки"]),
                "kind": to_plain(conn, row["Вид"]),
                "card": label,
                "bonus": to_plain(conn, row["Сумма"]),
                "receipt_amount": to_plain(conn, row["СуммаЧека"]),
            }
        )
    return result


def collect(conn: Any) -> dict[str, Any]:
    report: dict[str, Any] = {"collected_at_utc": datetime.now(UTC).isoformat(), "sections": {}}
    sections = report["sections"]

    def section(name: str, fn: Any) -> None:
        started = time.perf_counter()
        try:
            sections[name] = {"result": fn()}
        except Exception as exc:  # noqa: BLE001 - record and continue with the next independent section
            sections[name] = {"error": f"{type(exc).__name__}: {exc}"}
        sections[name]["seconds"] = round(time.perf_counter() - started, 3)

    section("metadata", lambda: describe_metadata(conn))
    plain = lambda rows: [{k: to_plain(conn, v) for k, v in r.items()} for r in rows]  # noqa: E731
    section(
        "coverage",
        lambda: plain(run_query(conn, QUERIES["coverage"], [
            "Вид", "ТипРегистратора", "Строк", "СЧекомБольше0", "СЧекомРавно0", "СЧекомМеньше0",
            "ПервыйПериод", "ПоследнийПериод",
        ])),
    )
    section("rows_per_moment", lambda: plain(run_query(conn, QUERIES["rows_per_moment"], ["Строк", "РазныхСумм", "Групп"])))
    section(
        "rows_per_shift_card",
        lambda: plain(run_query(conn, QUERIES["rows_per_shift_card"], ["Строк", "РазныхМоментов", "РазныхСумм", "Групп"])),
    )
    section("accrual_percent", lambda: plain(run_query(conn, QUERIES["accrual_percent"], ["Процент", "Строк"])))
    section(
        "expense_pairing",
        lambda: plain(run_query(conn, QUERIES["expense_pairing"], ["МоментовСписания", "СНачислениемВТотЖеМомент"])),
    )

    def sample() -> dict[str, Any]:
        latest = run_query(conn, QUERIES["latest_registrar"], ["Регистратор", "Период"])
        if not latest:
            return {"note": "no rows with СуммаЧека > 0"}
        registrar = latest[0]["Регистратор"]
        rows = run_query(conn, QUERIES["sample_rows"], ["Период", "НомерСтроки", "Вид", "КартаКод", "Сумма", "СуммаЧека"],
                         {"Регистратор": registrar})
        period = latest[0]["Период"]
        return {
            "registrar": "R1",
            "registrar_date": period.strftime("%Y-%m-%d") if isinstance(period, datetime) else None,
            "rows_shown": len(rows),
            "row_limit": SAMPLE_ROW_LIMIT,
            "rows": anonymize_sample(conn, rows),
        }

    section("sample_latest_registrar", sample)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Проверка СуммаЧека — результат скрипта", "", f"Собрано (UTC): {report['collected_at_utc']}", ""]
    for name, body in report["sections"].items():
        lines.append(f"## {name} ({body.get('seconds')} с)")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(body.get("result", body.get("error")), ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def connect() -> tuple[Any, Any]:
    """Connection string comes only from the ONE_CONNECTION_STRING variable of this PowerShell session.

    The agent service settings (.env.service) are deliberately not read: they belong to SYSTEM/Administrators.
    """
    from poscenter_loyalty_agent.one_com import OneComConnector

    connection_string = os.environ.get("ONE_CONNECTION_STRING", "").strip()
    if not connection_string:
        raise SystemExit("ONE_CONNECTION_STRING is not set in this session; STOP")
    connector = OneComConnector(connection_string)
    return connector, connector.connect()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="output folder for probe.json and probe.md")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    connector = None
    try:
        from poscenter_loyalty_agent.one_com import sanitize_connection_string
    except Exception:  # noqa: BLE001
        def sanitize_connection_string(text: str) -> str:
            return text
    try:
        connector, conn = connect()
        report = collect(conn)
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        print(sanitize_connection_string(traceback.format_exc()), file=sys.stderr)
        return 1
    finally:
        if connector is not None:
            try:
                connector.disconnect()
            except Exception:  # noqa: BLE001
                pass
    (out / "probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "probe.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"written: {out / 'probe.json'} and {out / 'probe.md'}")
    errors = [n for n, b in report["sections"].items() if "error" in b]
    if errors:
        print("sections with errors: " + ", ".join(errors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
