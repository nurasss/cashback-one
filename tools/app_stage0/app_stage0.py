"""Локальный read-only CLI для первоначального исследования POSCENTER APP."""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app_profile import collect_profile, crosscheck, select_targets
from common import InputError, check_output, json_text, output_dir, safe_print, write_files
from metadata import inventory
from poscenter_loyalty_agent.one_com import OneComConnector


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InputError("Неверные аргументы. Используйте --help.")

    def _print_message(self, message: str | None, file: Any = None) -> None:
        if message:
            check_output(message, os.environ.get("ONE_CONNECTION_STRING", ""))
            super()._print_message(message, file)


def make_parser() -> SafeParser:
    parser = SafeParser(description="APP Stage 0: только чтение ONE.")
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=SafeParser)
    for name in ("metadata", "profile", "crosscheck"):
        command = subparsers.add_parser(name)
        command.add_argument("--output-dir", required=True)
        command.add_argument("--slow-query-seconds", type=float, default=60)
        if name in {"profile", "crosscheck"}:
            command.add_argument("--targets", required=True)
        if name == "crosscheck":
            command.add_argument("--date", required=True)
    return parser


def read_targets(path: str) -> Any:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        raise InputError("Не удалось прочитать JSON выбора объектов.") from None


def summary(metadata: dict[str, Any], profile: dict[str, Any] | None = None) -> str:
    lines = ["# APP Stage 0 — сводка", "", metadata["notice"], "", "## Метаданные", ""]
    for category, section in metadata["categories"].items():
        lines.append(f"- {category}: {len(section['objects'])} объектов")
        if "error" in section:
            lines.append("  - Перечисление категории неполное: " + section["error"]["message"])
        for obj in section["objects"]:
            if "candidate" in obj:
                lines.append(f"  - {obj['name']}: кандидат, требует подтверждения")
    lines.extend(["", "## Планы обмена", ""])
    for plan in metadata["exchange_plans"]:
        if plan["available"]:
            lines.append(f"- {plan['name']}: " + (", ".join(plan["members"]) or "состав пуст"))
        else:
            lines.append(f"- {plan['name']}: состав недоступен")
    if profile is not None:
        lines.extend(["", "## Агрегированный профиль", "", "```json", json_text(profile).rstrip(), "```"])
    lines.append("")
    return "\n".join(lines)


def execute(args: argparse.Namespace, secret: str) -> None:
    directory = output_dir(args.output_dir)
    if not math.isfinite(args.slow_query_seconds) or args.slow_query_seconds <= 0:
        raise InputError("Порог медленного запроса должен быть положительным.")
    target_data = read_targets(args.targets) if args.command in {"profile", "crosscheck"} else None
    day = None
    if args.command == "crosscheck":
        try:
            day = datetime.strptime(args.date, "%Y-%m-%d")
            if day.strftime("%Y-%m-%d") != args.date:
                raise ValueError("date")
        except ValueError:
            raise InputError("Дата должна иметь формат YYYY-MM-DD.") from None

    # В существующем соединителе диагностический лог может содержать части ошибки COM.
    # Отключение действует только в этом процессе и не меняет агент или его файлы.
    logger = logging.getLogger("poscenter_loyalty_agent.one_com")
    was_disabled = logger.disabled
    logger.disabled = True
    connector = OneComConnector(connection_string=secret)
    try:
        conn = connector.connect()
        meta, lookup = inventory(conn, secret)
        if args.command == "metadata":
            write_files(directory, {"metadata.json": json_text(meta), "APP_STAGE0_SUMMARY.md": summary(meta)}, secret)
        else:
            targets = select_targets(conn, lookup, target_data, secret)
            if args.command == "profile":
                profile = collect_profile(conn, targets, secret, args.slow_query_seconds)
                write_files(directory, {"metadata.json": json_text(meta), "profile.json": json_text(profile),
                                        "APP_STAGE0_SUMMARY.md": summary(meta, profile)}, secret)
            else:
                assert day is not None
                result = crosscheck(conn, targets, day, secret, args.slow_query_seconds)
                write_files(directory, {f"crosscheck-{day.date().isoformat()}.json": json_text(result)},
                            secret, exclusive=True)
    finally:
        try:
            connector.disconnect()
        finally:
            logger.disabled = was_disabled
    safe_print("Файл создан.", secret)


def main(argv: list[str] | None = None) -> int:
    secret = os.environ.get("ONE_CONNECTION_STRING", "")
    try:
        args = make_parser().parse_args(argv)
        if not secret.strip():
            raise InputError("Не задана переменная ONE_CONNECTION_STRING.")
        execute(args, secret)
        return 0
    except InputError as exc:
        # Сообщения InputError в этом модуле и его зависимостях — только константы.
        safe_print(str(exc), secret, file=sys.stderr)
        return 1
    except Exception as exc:
        # Ни строки COM-ошибки, ни traceback не попадают в консоль. Имя класса
        # (например, COMConnectionError) данных не содержит и помогает диагностике.
        error_type = type(exc).__name__
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", error_type):
            error_type = "Error"
        safe_print(f"Операция не выполнена ({error_type}); подробности скрыты во избежание утечки данных.",
                   secret, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
