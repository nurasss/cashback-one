"""Только агрегаты и отдельные эталонные выборки по выбранным метаданным."""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Any

from common import InputError, QueryRunner, as_count, as_date, as_number, check_output, identifier
from metadata import describe

PREFIXES = {
    "document": "Документ",
    "catalog": "Справочник",
    "register": "РегистрНакопления",
    "information_register": "РегистрСведений",
}


def select_targets(conn: Any, lookup: dict[tuple[str, str], Any], data: Any, secret: str) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or set(data) != {"targets"} or not isinstance(data["targets"], list):
        raise InputError("Неверный формат targets.")
    result = []
    seen = set()
    for raw in data["targets"]:
        if not isinstance(raw, dict):
            raise InputError("Неверное описание объекта.")
        allowed = {
            "kind", "name", "sections", "benchmark_sections", "barcode_fields", "payments",
            "register_kind", "crosscheck_amount_field",
        }
        if set(raw) - allowed or raw.get("kind") not in PREFIXES:
            raise InputError("Неверный тип или параметр объекта.")
        kind = raw["kind"]
        name = identifier(raw.get("name"))
        key = (kind, name)
        if key in seen or key not in lookup:
            raise InputError("Объект отсутствует в метаданных или повторяется.")
        seen.add(key)
        details = describe(conn, lookup[key], kind, secret)
        if "attributes" in details.get("errors", {}):
            raise InputError("Реквизиты выбранного объекта недоступны.")
        fields = {f["name"] for f in details.get("attributes", []) + details.get("standard_attributes", [])}
        tabs = {tab["name"]: tab for tab in details.get("tabular_sections", []) if "error" not in tab}
        target: dict[str, Any] = {"kind": kind, "name": name, "details": details}
        for list_key in ("sections", "benchmark_sections", "barcode_fields"):
            values = raw.get(list_key, [])
            if not isinstance(values, list) or len(values) != len(set(values)):
                raise InputError("Неверный список реквизитов или табличных частей.")
            values = [identifier(value) for value in values]
            permitted = fields if list_key == "barcode_fields" else set(tabs)
            if any(value not in permitted for value in values):
                raise InputError("Поле или табличная часть не найдены в метаданных.")
            if values and ((list_key == "barcode_fields" and kind != "catalog") or
                           (list_key != "barcode_fields" and kind != "document")):
                raise InputError("Параметр не подходит для типа объекта.")
            target[list_key] = values
        if kind == "register":
            if raw.get("register_kind") not in {"balance", "turnover"}:
                raise InputError("Укажите вид регистра по метаданным.")
            target["register_kind"] = raw["register_kind"]
        elif "register_kind" in raw:
            raise InputError("Вид регистра указан для другого объекта.")
        payments = raw.get("payments", [])
        if not isinstance(payments, list) or (payments and kind != "document"):
            raise InputError("Неверное описание оплат.")
        target["payments"] = []
        for payment in payments:
            if not isinstance(payment, dict) or set(payment) != {"section", "field", "allowed_values"}:
                raise InputError("Неверное описание поля оплаты.")
            section = identifier(payment["section"])
            field = identifier(payment["field"])
            values = payment["allowed_values"]
            if section not in tabs or field not in {f["name"] for f in tabs[section]["attributes"]}:
                raise InputError("Поле оплаты отсутствует в метаданных.")
            if not isinstance(values, list) or any(not isinstance(v, str) or not v or len(v) > 100 for v in values):
                raise InputError("Неверный список допустимых видов оплаты.")
            for value in values:
                check_output(value, secret)
            target["payments"].append({"section": section, "field": field, "allowed_values": values})
        if "crosscheck_amount_field" in raw:
            field = identifier(raw["crosscheck_amount_field"])
            if kind != "document" or field not in fields:
                raise InputError("Поле суммы сверки отсутствует в метаданных документа.")
            target["crosscheck_amount_field"] = field
        result.append(target)
    return result


def beginning_of_month(value: datetime) -> datetime:
    return datetime(value.year, value.month, 1)


def shift_month(value: datetime, months: int) -> datetime:
    index = value.year * 12 + value.month - 1 + months
    return datetime(index // 12, index % 12 + 1, 1)


def fractions(count: int, total: int) -> float | None:
    return round(count / total, 6) if total else None


def run_collect(runner: QueryRunner, key: str, name: str, sql: str, params: dict[str, Any],
                project: Any, *, heavy: bool = False) -> dict[str, Any]:
    rows: list[Any] = []
    result = runner.run(key, name, sql, params, lambda sel: rows.append(project(sel)), heavy=heavy)
    if result["status"] == "ok":
        result["data"] = rows
    return result


def month_query(runner: QueryRunner, key: str, table: str, date_field: str,
                now: datetime) -> dict[str, Any]:
    start = shift_month(beginning_of_month(now), -23)
    end = shift_month(beginning_of_month(now), 1)
    sql = f"""ВЫБРАТЬ НАЧАЛОПЕРИОДА(Т.{date_field}, МЕСЯЦ) КАК Месяц,
КОЛИЧЕСТВО(*) КАК Количество ИЗ {table} КАК Т
ГДЕ Т.{date_field} >= &Начало И Т.{date_field} < &Конец
СГРУППИРОВАТЬ ПО НАЧАЛОПЕРИОДА(Т.{date_field}, МЕСЯЦ)"""
    result = run_collect(runner, key, "по месяцам", sql, {"Начало": start, "Конец": end},
                         lambda s: {"month": as_date(s.Месяц), "count": as_count(s.Количество)})
    result["period"] = {"start": start.date().isoformat(), "end_exclusive": end.date().isoformat()}
    return result


def version_query(runner: QueryRunner, key: str, table: str) -> dict[str, Any]:
    sql = f"ВЫБРАТЬ КОЛИЧЕСТВО(Т.ВерсияДанных) КАК Количество ИЗ {table} КАК Т"
    result = run_collect(runner, key, "ВерсияДанных", sql, {}, lambda s: as_count(s.Количество))
    result["readable"] = result["status"] == "ok"
    return result


def percentiles(histogram: dict[int, int]) -> dict[str, Any]:
    total = sum(histogram.values())
    if not total:
        return {"documents": 0, "mean": None, "median": None, "p95": None, "max": None}

    def at(index: int) -> int:
        count = 0
        for value, amount in sorted(histogram.items()):
            count += amount
            if count > index:
                return value
        raise ValueError("Неверная гистограмма.")

    return {
        "documents": total,
        "mean": round(sum(value * count for value, count in histogram.items()) / total, 4),
        "median": (at((total - 1) // 2) + at(total // 2)) / 2,
        "p95": at(math.ceil(total * 0.95) - 1),
        "max": max(histogram),
    }


def document_profile(runner: QueryRunner, target: dict[str, Any], now: datetime) -> dict[str, Any]:
    key = f"Документ.{target['name']}"
    queries = []
    sql = f"""ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Всего,
СУММА(ВЫБОР КОГДА Т.Проведен ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Проведено,
СУММА(ВЫБОР КОГДА Т.ПометкаУдаления ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Удалено,
МИНИМУМ(Т.Дата) КАК Первая, МАКСИМУМ(Т.Дата) КАК Последняя ИЗ {key} КАК Т"""
    summary = run_collect(runner, key, "документы всего", sql, {}, lambda s: {
        "total": as_count(s.Всего), "posted": as_count(s.Проведено),
        "marked_for_deletion": as_count(s.Удалено), "first_date": as_date(s.Первая),
        "last_date": as_date(s.Последняя),
    })
    queries.append(summary)
    total = None
    if summary["status"] == "ok" and len(summary["data"]) == 1:
        row = summary["data"][0]
        total = row["total"]
        if row["posted"] > total or row["marked_for_deletion"] > total:
            raise ValueError("Некорректные агрегаты документов.")
        row["unposted"] = total - row["posted"]
        for name in ("posted", "unposted", "marked_for_deletion"):
            row[name + "_share"] = fractions(row[name], total)
    queries.append(month_query(runner, key, key, "Дата", now))
    queries.append(version_query(runner, key, key))
    for section in target["sections"]:
        sql = f"""ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Строк
ИЗ {key}.{section} КАК Т СГРУППИРОВАТЬ ПО Т.Ссылка"""
        counts = run_collect(runner, key, "строки на документ: " + section, sql, {},
                             lambda s: as_count(s.Строк), heavy=True)
        if counts["status"] == "ok":
            grouped = counts.pop("data")
            histogram: dict[int, int] = {}
            for count in grouped:
                histogram[count] = histogram.get(count, 0) + 1
            if total is not None and total >= len(grouped):
                histogram[0] = histogram.get(0, 0) + total - len(grouped)
                if histogram[0] == 0:
                    del histogram[0]
                counts["statistics"] = percentiles(histogram)
            else:
                counts["statistics_unavailable"] = "Неизвестно число документов с нулём строк."
        queries.append(counts)
    for payment in target["payments"]:
        section, field = payment["section"], payment["field"]
        start = shift_month(beginning_of_month(now), -2)
        end = shift_month(beginning_of_month(now), 1)
        sql = f"""ВЫБРАТЬ Т.{field} КАК Вид, КОЛИЧЕСТВО(*) КАК Количество
ИЗ {key}.{section} КАК Т ГДЕ Т.Ссылка.Дата >= &Начало И Т.Ссылка.Дата < &Конец
СГРУППИРОВАТЬ ПО Т.{field}"""
        allowed = set(payment["allowed_values"])
        visible: list[dict[str, Any]] = []
        hidden = 0

        def consume(sel: Any, allowed: set[str] = allowed, visible: list[dict[str, Any]] = visible) -> None:
            nonlocal hidden
            count = as_count(sel.Количество)
            value = str(runner.conn.String(sel.Вид))
            if value in allowed:
                visible.append({"type": value, "count": count})
            else:
                hidden += count

        payment_result = runner.run(key, "оплаты: " + section + "." + field, sql,
                                    {"Начало": start, "Конец": end}, consume, heavy=True)
        if payment_result["status"] == "ok":
            payment_result["data"] = visible
            payment_result["other_count"] = hidden
        payment_result["period"] = {"start": start.date().isoformat(), "end_exclusive": end.date().isoformat()}
        queries.append(payment_result)
    return {
        "object": key,
        "queries": queries,
        "backdated_proxy": {
            "status": "не проверено",
            "reason": "Порядок ссылки и номера не доказывает порядок создания; безопасное сравнение не подтверждено.",
        },
    }


def catalog_profile(runner: QueryRunner, target: dict[str, Any]) -> dict[str, Any]:
    key = f"Справочник.{target['name']}"
    sql = f"""ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Всего,
СУММА(ВЫБОР КОГДА Т.ЭтоГруппа ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Группы,
СУММА(ВЫБОР КОГДА Т.ПометкаУдаления ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Удалено
ИЗ {key} КАК Т"""
    queries = [run_collect(runner, key, "справочник всего", sql, {}, lambda s: {
        "total": as_count(s.Всего), "groups": as_count(s.Группы),
        "marked_for_deletion": as_count(s.Удалено),
    }), version_query(runner, key, key)]
    if queries[0]["status"] == "ok" and len(queries[0]["data"]) == 1:
        row = queries[0]["data"][0]
        if row["groups"] > row["total"]:
            raise ValueError("Некорректные агрегаты справочника.")
        row["elements"] = row["total"] - row["groups"]
    for field in target["barcode_fields"]:
        sql = f'''ВЫБРАТЬ ДЛИНАСТРОКИ(СОКРЛП(Т.{field})) КАК Длина,
КОЛИЧЕСТВО(*) КАК Всего,
СУММА(ВЫБОР КОГДА СОКРЛП(Т.{field}) <> "" И НЕ СОКРЛП(Т.{field}) ПОДОБНО "%[^0-9]%"
ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Цифровых ИЗ {key} КАК Т
СГРУППИРОВАТЬ ПО ДЛИНАСТРОКИ(СОКРЛП(Т.{field}))'''
        lengths = run_collect(runner, key, "длины штрихкода: " + field, sql, {}, lambda s: {
            "length": as_count(s.Длина), "count": as_count(s.Всего), "digits_count": as_count(s.Цифровых),
        }, heavy=True)
        if lengths["status"] == "ok":
            total = sum(row["count"] for row in lengths["data"])
            digital = sum(row["digits_count"] for row in lengths["data"])
            lengths["digital_share"] = fractions(digital, total)
        queries.append(lengths)
    return {"object": key, "queries": queries}


def register_profile(runner: QueryRunner, target: dict[str, Any], now: datetime) -> dict[str, Any]:
    prefix = PREFIXES[target["kind"]]
    key = f"{prefix}.{target['name']}"
    queries = [month_query(runner, key, key, "Период", now)]
    if target["kind"] != "register":
        return {"object": key, "queries": queries}
    if target["register_kind"] == "turnover":
        start = shift_month(beginning_of_month(now), -1)
        end = beginning_of_month(now) - timedelta(seconds=1)
        sql = f"""ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Количество
ИЗ {key}.Обороты(&Начало, &Конец, , ) КАК Т"""
        result = run_collect(runner, key, "строк оборотов за месяц", sql, {"Начало": start, "Конец": end},
                             lambda s: as_count(s.Количество), heavy=True)
        result["period"] = {"start": start.date().isoformat(), "end_inclusive": end.date().isoformat()}
        queries.append(result)
    else:
        resources = [identifier(r["name"]) for r in target["details"].get("resources", [])]
        dimensions = [identifier(d["name"]) for d in target["details"].get("dimensions", [])]
        if resources:
            zero = " И ".join(f"Т.{r}Остаток = 0" for r in resources)
            negative = " ИЛИ ".join(f"Т.{r}Остаток < 0" for r in resources)
            sql = f"""ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Всего,
СУММА(ВЫБОР КОГДА {zero} ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Нулевых,
СУММА(ВЫБОР КОГДА {negative} ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Отрицательных
ИЗ {key}.Остатки(&Момент, ) КАК Т"""
            queries.append(run_collect(runner, key, "строки остатков", sql, {"Момент": now}, lambda s: {
                "total": as_count(s.Всего), "zero_all_resources": as_count(s.Нулевых),
                "negative_any_resource": as_count(s.Отрицательных),
            }, heavy=True))
        else:
            queries.append({"query": "строки остатков", "status": "не проверено: ресурсы недоступны"})
        for dimension in dimensions:
            sql = f"""ВЫБРАТЬ КОЛИЧЕСТВО(РАЗЛИЧНЫЕ Т.{dimension}) КАК Количество
ИЗ {key}.Остатки(&Момент, ) КАК Т"""
            queries.append(run_collect(runner, key, "различных значений: " + dimension, sql,
                                       {"Момент": now}, lambda s: as_count(s.Количество), heavy=True))
    return {"object": key, "queries": queries,
            "note": "Виртуальная таблица может не содержать комбинаций с нулевыми остатками."}


def benchmark(runner: QueryRunner, target: dict[str, Any], section: str,
              start: datetime, end: datetime, label: str) -> dict[str, Any]:
    key = f"Документ.{target['name']}"
    tab = next(tab for tab in target["details"]["tabular_sections"] if tab["name"] == section)
    fields = [identifier(field["name"]) for field in tab["attributes"]]
    if not fields:
        return {"query": label, "status": "не проверено: нет доступных реквизитов строк"}
    columns = ", ".join(f"Т.{field} КАК Поле{index}" for index, field in enumerate(fields))
    sql = f"""ВЫБРАТЬ {columns} ИЗ {key}.{section} КАК Т
ГДЕ Т.Ссылка.Дата >= &Начало И Т.Ссылка.Дата < &Конец"""

    def consume(sel: Any) -> None:
        for index in range(len(fields)):
            getattr(sel, f"Поле{index}")

    result = runner.run(key, label, sql, {"Начало": start, "Конец": end}, consume, heavy=True)
    result["section"] = section
    result["period"] = {"start": start.date().isoformat(), "end_exclusive": end.date().isoformat()}
    if result["status"] == "ok":
        seconds = result["duration_ms"] / 1000
        result["rows_per_second"] = round(result["result_rows"] / seconds, 2) if seconds else None
    return result


def collect_profile(conn: Any, targets: list[dict[str, Any]], secret: str, slow_seconds: float,
                    now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    runner = QueryRunner(conn, slow_seconds, secret)
    result: dict[str, Any] = {"objects": [], "benchmarks": [], "date": now.date().isoformat()}
    for target in targets:
        if target["kind"] == "document":
            result["objects"].append(document_profile(runner, target, now))
        elif target["kind"] == "catalog":
            result["objects"].append(catalog_profile(runner, target))
        else:
            result["objects"].append(register_profile(runner, target, now))
    # Эталон привязан к последнему дню с документами, а не к вчерашнему дню:
    # в тестовой базе свежих чеков может не быть, и замер прочитал бы 0 строк.
    for target, profile in zip(targets, result["objects"], strict=True):
        if not target["benchmark_sections"]:
            continue
        last_day = last_data_day(profile)
        for section in target["benchmark_sections"]:
            if last_day is None:
                for label in (BENCHMARK_DAY, BENCHMARK_WEEK):
                    result["benchmarks"].append({
                        "query": label, "section": section,
                        "status": "не проверено: неизвестна дата последнего документа",
                    })
                continue
            day_end = datetime.combine(last_day, time.min) + timedelta(days=1)
            result["benchmarks"].append(benchmark(runner, target, section, day_end - timedelta(days=1), day_end,
                                                  BENCHMARK_DAY))
            result["benchmarks"].append(benchmark(runner, target, section, day_end - timedelta(days=7), day_end,
                                                  BENCHMARK_WEEK))
    return result


BENCHMARK_DAY = "последний день с документами"
BENCHMARK_WEEK = "7 дней по последний день с документами"


def last_data_day(profile: dict[str, Any]) -> date | None:
    """Дата последнего документа из запроса «документы всего», если он выполнен."""
    for query in profile["queries"]:
        if query.get("query") == "документы всего" and query["status"] == "ok" and len(query["data"]) == 1:
            value = query["data"][0]["last_date"]
            return date.fromisoformat(value) if value else None
    return None


def crosscheck(conn: Any, targets: list[dict[str, Any]], day: datetime,
               secret: str, slow_seconds: float) -> dict[str, Any]:
    selected = [t for t in targets if "crosscheck_amount_field" in t]
    if len(selected) != 1:
        raise InputError("Для сверки нужно выбрать ровно один документ и поле суммы.")
    target = selected[0]
    key = f"Документ.{target['name']}"
    field = target["crosscheck_amount_field"]
    sql = f"""ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Количество, СУММА(Т.{field}) КАК Сумма
ИЗ {key} КАК Т ГДЕ Т.Дата >= &Начало И Т.Дата < &Конец"""
    result = run_collect(QueryRunner(conn, slow_seconds, secret), key, "сверка", sql,
                         {"Начало": day, "Конец": day + timedelta(days=1)},
                         lambda s: {"receipt_count": as_count(s.Количество), "sales_sum": as_number(s.Сумма)})
    if result["status"] != "ok" or len(result.get("data", [])) != 1:
        raise InputError("Запрос сверки не выполнен; файл не создан.")
    return {"date": day.date().isoformat(), "document": key, "sum_field": field,
            "note": "Без фильтра проведения, отмены и возвратов; сопоставьте условия отчёта ONE.",
            **result["data"][0]}
