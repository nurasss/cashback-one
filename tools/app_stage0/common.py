"""Общие безопасные границы для локального инструмента APP Stage 0."""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from poscenter_loyalty_agent.stage0.sanitizer import sanitize_text, validate_safe_output

REPO_ROOT = Path(__file__).resolve().parents[2]
IDENTIFIER = re.compile(r"^[^\W\d]\w*$", re.UNICODE)
FORBIDDEN = re.compile(r"\b(?:ПОМЕСТИТЬ|УНИЧТОЖИТЬ|ДЛЯ\s+ИЗМЕНЕНИЯ)\b", re.IGNORECASE)
SAFE_ERROR_WORDS = {
    "ошибка", "ошибке", "запроса", "запрос", "поле", "поля", "полей", "таблица",
    "таблицы", "не", "найдено", "найден", "обнаружено", "ожидается", "неверный",
    "неверное", "недопустимое", "имя", "тип", "значение", "параметр", "параметра",
    "синтаксическая", "синтаксический", "символ", "операция", "невозможно", "доступ",
    "отказано", "выражение", "метод", "ком", "com", "error", "query",
    "field", "not", "found", "syntax", "invalid", "type", "parameter", "failed",
}


class InputError(ValueError):
    """Ошибка входных данных без включения пользовательского содержимого."""


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise InputError("Недопустимое имя метаданных.")
    return value


def validate_query(text: str) -> None:
    """Пакеты, изменение и временные таблицы запрещены до создания COM-запроса."""
    if not isinstance(text, str):
        raise InputError("Недопустимый текст запроса.")
    # Комментарий распознаётся только вне строкового литерала. Двойная кавычка
    # внутри литерала 1С экранируется повтором; незакрытые конструкции отклоняем.
    parts: list[str] = []
    quoted = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            parts.append(char)
            if quoted and index + 1 < len(text) and text[index + 1] == '"':
                parts.append('"')
                index += 2
                continue
            quoted = not quoted
            index += 1
        elif not quoted and text.startswith("//", index):
            end = text.find("\n", index + 2)
            index = len(text) if end < 0 else end
            parts.append(" ")
        elif not quoted and text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise InputError("Запрещённый текст запроса.")
            index = end + 2
            parts.append(" ")
        else:
            parts.append(char)
            index += 1
    if quoted:
        raise InputError("Запрещённый текст запроса.")
    cleaned = "".join(parts).strip()
    if (
        not re.match(r"^ВЫБРАТЬ\b", cleaned, re.IGNORECASE)
        or FORBIDDEN.search(cleaned)
        or ";" in cleaned
        or "/*" in cleaned
        or "*/" in cleaned
    ):
        raise InputError("Запрещённый текст запроса.")


def safe_error(exc: Exception, secret: str = "") -> dict[str, str]:
    """Оставить только общеупотребимые слова ошибки, скрыть произвольные данные.

    sanitize_text не распознаёт ФИО и произвольные фрагменты строки подключения,
    поэтому непроверенные слова и числа дополнительно не выводятся.
    """
    text = sanitize_text(str(exc))
    if secret:
        text = text.replace(secret, " ")
    words = re.findall(r"[^\W\d_]+", text, re.UNICODE)
    retained = [word for word in words if word.casefold() in SAFE_ERROR_WORDS]
    message = " ".join(retained[:30]) or "Подробности скрыты"
    message += " [прочие сведения скрыты]"
    error_type = type(exc).__name__
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", error_type):
        error_type = "Error"
    return {"type": error_type, "message": sanitize_text(message)}


def output_dir(value: str) -> Path:
    target = Path(value).expanduser().resolve()
    if target == REPO_ROOT or REPO_ROOT in target.parents:
        raise InputError("Папка результатов должна быть вне репозитория.")
    if os.name == "nt":
        import ctypes

        # Сверка содержит коммерческие данные. UNC и сетевые диски не считаются
        # локальными; неизвестный тип диска тоже отклоняется до создания файлов.
        drive = target.drive
        if not drive or drive.startswith("\\\\"):
            raise InputError("Папка результатов должна находиться на локальном диске.")
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive + "\\")
        if drive_type not in {2, 3, 6}:  # removable, fixed, RAM disk
            raise InputError("Папка результатов должна находиться на локальном диске.")
    return target


def secret_fragments(secret: str) -> list[str]:
    fragments = [secret] if secret else []
    for match in re.finditer(r"(?:^|;)\s*[^=;]+\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^;]*))", secret):
        value = next((part.strip() for part in match.groups() if part is not None), "")
        if len(value) >= 4:
            fragments.append(value)
    return fragments


def check_output(content: str, secret: str = "") -> None:
    validate_safe_output(content, context="APP Stage 0")
    if any(fragment in content for fragment in secret_fragments(secret)):
        raise InputError("Обнаружена строка подключения в результате; запись запрещена.")


def safe_print(content: str, secret: str = "", *, file: Any = None) -> None:
    check_output(content, secret)
    print(content, file=file)


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def write_files(directory: Path, files: dict[str, str], secret: str, *, exclusive: bool = False) -> None:
    """Проверить все результаты до создания папки и до открытия любого файла."""
    directory = output_dir(str(directory))
    paths: dict[Path, str] = {}
    for name, content in files.items():
        if Path(name).name != name:
            raise InputError("Недопустимое имя файла результата.")
        check_output(content, secret)
        path = directory / name
        if path.is_symlink() or path.resolve().parent != directory:
            raise InputError("Недопустимая ссылка файла результата.")
        if exclusive and path.exists():
            raise InputError("Файл сверки уже существует.")
        paths[path] = content
    directory.mkdir(parents=True, exist_ok=True)
    for path, content in paths.items():
        flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)


def as_number(value: Any) -> int | float:
    if isinstance(value, bool):
        raise ValueError("Ожидалось число.")
    number = float(value or 0)
    if not math.isfinite(number):
        raise ValueError("Ожидалось конечное число.")
    return int(number) if number.is_integer() else number


def as_count(value: Any) -> int:
    number = as_number(value)
    if int(number) != number or number < 0:
        raise ValueError("Ожидалось неотрицательное целое.")
    return int(number)


def as_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    raise ValueError("Ожидалась дата COM.")


class QueryRunner:
    """Единая точка исполнения: тайминг включает проход по результату COM."""

    def __init__(self, conn: Any, slow_seconds: float, secret: str = "", clock: Callable[[], float] = time.monotonic):
        self.conn = conn
        self.slow_seconds = slow_seconds
        self.secret = secret
        self.clock = clock
        self.slow_objects: set[str] = set()

    def run(
        self,
        object_key: str,
        name: str,
        text: str,
        params: dict[str, Any],
        consume: Callable[[Any], None],
        *,
        heavy: bool = False,
    ) -> dict[str, Any]:
        validate_query(text)
        if heavy and object_key in self.slow_objects:
            return {"query": name, "status": "пропущено из-за медленного запроса"}
        start = self.clock()
        rows = 0
        error = None
        try:
            query = self.conn.NewObject("Запрос")
            query.Текст = text
            for key, value in params.items():
                query.УстановитьПараметр(key, value)
            selection = query.Выполнить().Выбрать()
            while selection.Следующий():
                rows += 1
                consume(selection)
        except Exception as exc:
            error = safe_error(exc, self.secret)
        elapsed = max(0.0, self.clock() - start)
        if elapsed > self.slow_seconds:
            self.slow_objects.add(object_key)
        result: dict[str, Any] = {
            "query": name,
            "status": "error" if error else "ok",
            "duration_ms": round(elapsed * 1000, 3),
            "result_rows": rows,
        }
        if error:
            result["error"] = error
        return result
