"""Инвентаризация только объекта Метаданные; кандидаты не являются маппингом."""

from __future__ import annotations

from typing import Any

from common import identifier, safe_error

CATEGORIES = {
    "Документы": ("Documents", "document"),
    "РегистрыНакопления": ("AccumulationRegisters", "register"),
    "РегистрыСведений": ("InformationRegisters", "information_register"),
    "Справочники": ("Catalogs", "catalog"),
    "Перечисления": ("Enums", "enum"),
    "ПланыОбмена": ("ExchangePlans", "exchange_plan"),
    "Константы": ("Constants", "constant"),
}
KEYWORDS = (
    "продаж", "чек", "возврат", "оплат", "касс", "смен", "остат", "товар",
    "номенклатур", "склад", "взаиморасчет", "контрагент", "поставщик", "покупател",
    "долг", "сотрудник", "цен", "себестоим", "штрихкод",
)
KNOWN = {
    ("document", "чек"),
    ("document", "отчеткассовойсмены"),
    ("catalog", "местахранения"),
    ("catalog", "pos"),
}


def prop(obj: Any, *names: str) -> Any:
    for name in names:
        try:
            value = getattr(obj, name)
            if value is not None:
                return value
        except Exception:
            continue
    raise AttributeError("Свойство метаданных недоступно")


def items(collection: Any) -> list[Any]:
    try:
        count = int(collection.Count())
        return [collection.Get(i) for i in range(count)]
    except (AttributeError, TypeError):
        return list(collection)


def object_name(obj: Any) -> str:
    return identifier(str(prop(obj, "Name", "Имя")))


def synonym(obj: Any) -> str:
    try:
        return str(prop(obj, "Synonym", "Синоним"))
    except Exception:
        return ""


def is_candidate(kind: str, name: str, label: str) -> bool:
    text = (name + " " + label).casefold().replace("ё", "е")
    return (kind, name.casefold().replace("ё", "е")) in KNOWN or any(k in text for k in KEYWORDS)


def representation(conn: Any, value: Any) -> str:
    try:
        return str(conn.String(value))
    except Exception:
        return "недоступно"


def field_info(conn: Any, field: Any) -> dict[str, str]:
    name = object_name(field)
    try:
        type_name = representation(conn, prop(field, "Type", "Тип"))
    except Exception:
        type_name = "недоступно"
    return {"name": name, "synonym": synonym(field), "type": type_name}


def read_list(obj: Any, names: tuple[str, ...], secret: str) -> tuple[list[Any], dict[str, str] | None]:
    try:
        return items(prop(obj, *names)), None
    except Exception as exc:
        return [], safe_error(exc, secret)


def full_name(obj: Any) -> str:
    try:
        value = prop(obj, "FullName", "ПолноеИмя")
        value = value() if callable(value) else value
        parts = str(value).split(".")
        return ".".join(identifier(part) for part in parts)
    except Exception:
        return object_name(obj)


def describe(conn: Any, obj: Any, kind: str, secret: str) -> dict[str, Any]:
    result: dict[str, Any] = {"errors": {}}
    errors: dict[str, Any] = result["errors"]
    for key, names in (
        ("standard_attributes", ("StandardAttributes", "СтандартныеРеквизиты")),
        ("attributes", ("Attributes", "Реквизиты")),
        ("dimensions", ("Dimensions", "Измерения")),
        ("resources", ("Resources", "Ресурсы")),
    ):
        applicable = (
            key == "attributes"
            or (key == "standard_attributes" and kind in {"document", "catalog"})
            or (key in {"dimensions", "resources"} and kind in {"register", "information_register"})
        )
        if not applicable:
            continue
        values, error = read_list(obj, names, secret)
        result[key] = []
        if error:
            errors[key] = error
        for value in values:
            try:
                result[key].append(field_info(conn, value))
            except Exception as exc:
                errors[key] = safe_error(exc, secret)

    if kind in {"document", "catalog"}:
        tabs, error = read_list(obj, ("TabularSections", "ТабличныеЧасти"), secret)
        result["tabular_sections"] = []
        if error:
            errors["tabular_sections"] = error
        for tab in tabs:
            try:
                fields, field_error = read_list(tab, ("Attributes", "Реквизиты"), secret)
                section = {
                    "name": object_name(tab),
                    "synonym": synonym(tab),
                    "attributes": [field_info(conn, f) for f in fields],
                }
                if field_error:
                    section["error"] = field_error
                result["tabular_sections"].append(section)
            except Exception as exc:
                errors["tabular_sections"] = safe_error(exc, secret)

        all_fields = result.get("standard_attributes", []) + result.get("attributes", [])
        result["possible_creation_or_change_dates"] = [
            f for f in all_fields
            if any(part in (f["name"] + " " + f["synonym"]).casefold().replace("ё", "е")
                   for part in ("создан", "изменен", "изменения", "изменён", "created", "modified", "updated"))
        ]
    if kind == "document":
        try:
            result["posting"] = representation(conn, prop(obj, "Posting", "Проведение"))
        except Exception as exc:
            errors["posting"] = safe_error(exc, secret)
        movements, error = read_list(obj, ("RegisterRecords", "Registers", "Движения"), secret)
        result["register_movements"] = []
        if error:
            errors["register_movements"] = error
        else:
            try:
                result["register_movements"] = [full_name(m) for m in movements]
            except Exception as exc:
                errors["register_movements"] = safe_error(exc, secret)
    if kind == "register":
        try:
            result["register_kind"] = representation(conn, prop(obj, "RegisterType", "ВидРегистра"))
        except Exception as exc:
            errors["register_kind"] = safe_error(exc, secret)
        registrars, error = read_list(obj, ("Recorders", "Registrars", "Регистраторы"), secret)
        result["recorders"] = []
        if error:
            errors["recorders"] = error
        else:
            try:
                result["recorders"] = [full_name(r) for r in registrars]
            except Exception as exc:
                errors["recorders"] = safe_error(exc, secret)
    return result


def exchange_contents(obj: Any, secret: str) -> dict[str, Any]:
    values, error = read_list(obj, ("Content", "Composition", "Состав"), secret)
    if error:
        return {"available": False, "error": error}
    try:
        return {"available": True, "members": [full_name(value) for value in values]}
    except Exception as exc:
        return {"available": False, "error": safe_error(exc, secret)}


def inventory(conn: Any, secret: str) -> tuple[dict[str, Any], dict[tuple[str, str], Any]]:
    root = prop(conn, "Metadata", "Метаданные")
    result: dict[str, Any] = {
        "notice": "Кандидат, требует подтверждения; эвристика не доказывает назначение.",
        "categories": {},
        "exchange_plans": [],
    }
    lookup: dict[tuple[str, str], Any] = {}
    for category, (english, kind) in CATEGORIES.items():
        section: dict[str, Any] = {"objects": []}
        result["categories"][category] = section
        try:
            collection = prop(root, english, category)
            for obj in items(collection):
                name = object_name(obj)
                label = synonym(obj)
                lookup[(kind, name)] = obj
                candidate = is_candidate(kind, name, label)
                entry: dict[str, Any] = {"name": name, "synonym": label}
                if candidate:
                    entry["candidate"] = "кандидат, требует подтверждения"
                    if kind in {"document", "catalog", "register", "information_register"}:
                        entry["details"] = describe(conn, obj, kind, secret)
                section["objects"].append(entry)
                if kind == "exchange_plan":
                    result["exchange_plans"].append({"name": name, **exchange_contents(obj, secret)})
        except Exception as exc:
            section["error"] = safe_error(exc, secret)
    return result, lookup
