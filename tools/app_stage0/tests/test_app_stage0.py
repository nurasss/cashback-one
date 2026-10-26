"""Проверки на синтетическом COM; реальная ONE и Windows не используются."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_stage0  # noqa: E402
from common import REPO_ROOT, InputError, QueryRunner, output_dir, write_files  # noqa: E402
from poscenter_loyalty_agent.one_com import COMConnectionError  # noqa: E402
from poscenter_loyalty_agent.stage0.sanitizer import SecuritySanitizerError  # noqa: E402

FAKE_NAME = "Тестов Тест Тестович"
FAKE_PHONE = "+" + "7" + "999" + "0000000"
FAKE_BARCODE = "0" + "123" + "456789012"
FAKE_CONNECTION = 'File="sample-directory";Usr="mock-user";Pwd="mock-password";'


class Collection:
    def __init__(self, *values):
        self.values = values

    def Count(self):
        return len(self.values)

    def Get(self, index):
        return self.values[index]


def field(name):
    return SimpleNamespace(Name=name, Synonym=name, Type="Строка")


def fake_metadata():
    tab = SimpleNamespace(Name="Позиции", Synonym="Строки", Attributes=Collection(
        field("Товар"), field("ВидОплаты")))
    document = SimpleNamespace(
        Name="Чек", Synonym="Продажа", Attributes=Collection(field("Итог"), field("ДатаСоздания")),
        StandardAttributes=Collection(field("Дата")), TabularSections=Collection(tab),
        Posting="Разрешено", RegisterRecords=Collection(),
    )
    catalog = SimpleNamespace(
        Name="Товары", Synonym="Товары", Attributes=Collection(field("Штрихкод")),
        StandardAttributes=Collection(), TabularSections=Collection(),
    )
    register = SimpleNamespace(
        Name="ОстаткиТест", Synonym="Остатки", Attributes=Collection(),
        Dimensions=Collection(field("Товар")), Resources=Collection(field("Количество")),
        RegisterType="Остатки", Recorders=Collection(document),
    )
    turnover = SimpleNamespace(
        Name="ОборотыТест", Synonym="Продажи", Attributes=Collection(),
        Dimensions=Collection(field("Товар")), Resources=Collection(field("Количество")),
        RegisterType="Обороты", Recorders=Collection(document),
    )
    plan = SimpleNamespace(Name="ОбменТест", Synonym="Обмен", Content=Collection(document))
    return SimpleNamespace(
        Documents=Collection(document), Catalogs=Collection(catalog),
        AccumulationRegisters=Collection(register, turnover), InformationRegisters=Collection(),
        Enums=Collection(), ExchangePlans=Collection(plan), Constants=Collection(),
    )


class Selection:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.current = {}

    def Следующий(self):
        try:
            self.current = next(self.rows)
            return True
        except StopIteration:
            return False

    def __getattr__(self, name):
        if name in self.current:
            return self.current[name]
        raise AttributeError(name)


class FakeQuery:
    def __init__(self, conn):
        self.conn = conn
        self.Текст = ""
        self.params = {}

    def УстановитьПараметр(self, name, value):
        self.params[name] = value

    def Выполнить(self):
        self.conn.executed.append(self.Текст)
        self.conn.calls.append((self.Текст, dict(self.params)))
        if self.conn.fail_on and self.conn.fail_on in self.Текст:
            raise RuntimeError("Ошибка поля " + FAKE_NAME + " " + FAKE_PHONE + " " + FAKE_CONNECTION)
        if "КАК Первая" in self.Текст:
            rows = [{"Всего": 3, "Проведено": 2, "Удалено": 1,
                     "Первая": datetime(2025, 1, 1, 12), "Последняя": datetime(2026, 1, 1, 18)}]
        elif "КАК Месяц" in self.Текст:
            rows = [{"Месяц": datetime(2026, 1, 1), "Количество": 3}]
        elif "Т.ВерсияДанных" in self.Текст:
            rows = [{"Количество": 3}]
        elif "КАК Строк" in self.Текст:
            rows = [{"Строк": 2}, {"Строк": 1}]
        elif "КАК Вид" in self.Текст:
            rows = [{"Вид": "Наличные", "Количество": 2}, {"Вид": FAKE_NAME, "Количество": 1}]
        elif "КАК Длина" in self.Текст:
            rows = [{"Длина": 13, "Всего": 2, "Цифровых": 2}]
        elif "КАК Нулевых" in self.Текст:
            rows = [{"Всего": 5, "Нулевых": 0, "Отрицательных": 1}]
        elif "КАК Группы" in self.Текст:
            rows = [{"Всего": 3, "Группы": 1, "Удалено": 0}]
        elif "КАК Поле0" in self.Текст:
            rows = [{"Поле0": FAKE_PHONE, "Поле1": FAKE_BARCODE},
                    {"Поле0": FAKE_NAME, "Поле1": FAKE_BARCODE}]
        elif "КАК Сумма" in self.Текст:
            rows = [{"Количество": 3, "Сумма": 42.5}]
        else:
            rows = [{"Количество": 1}]
        selection = Selection(rows)
        return SimpleNamespace(Выбрать=lambda: selection)


class FakeConnection:
    def __init__(self, fail_on=None):
        self.Metadata = fake_metadata()
        self.fail_on = fail_on
        self.executed = []
        self.calls = []
        self.created = 0

    def NewObject(self, kind):
        assert kind == "Запрос"
        self.created += 1
        return FakeQuery(self)

    def String(self, value):
        return str(value)


def install_connector(monkeypatch, connection):
    class Connector:
        def __init__(self, connection_string):
            assert connection_string == FAKE_CONNECTION

        def connect(self):
            return connection

        def disconnect(self):
            pass

    monkeypatch.setattr(app_stage0, "OneComConnector", Connector)
    monkeypatch.setenv("ONE_CONNECTION_STRING", FAKE_CONNECTION)


def target_file(tmp_path):
    value = {"targets": [
        {"kind": "document", "name": "Чек", "sections": ["Позиции"],
         "benchmark_sections": ["Позиции"], "crosscheck_amount_field": "Итог",
         "payments": [{"section": "Позиции", "field": "ВидОплаты", "allowed_values": ["Наличные"]}]},
        {"kind": "catalog", "name": "Товары", "barcode_fields": ["Штрихкод"]},
        {"kind": "register", "name": "ОстаткиТест", "register_kind": "balance"},
        {"kind": "register", "name": "ОборотыТест", "register_kind": "turnover"},
    ]}
    path = tmp_path / "targets.json"
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.parametrize("text", [
    "УДАЛИТЬ ИЗ Документ.Чек",
    "ВЫБРАТЬ 1 ПОМЕСТИТЬ Временная",
    "ВЫБРАТЬ 1 ДЛЯ /* комментарий */ ИЗМЕНЕНИЯ",
    "ВЫБРАТЬ 1 УНИЧТОЖИТЬ",
    "ВЫБРАТЬ 1; УДАЛИТЬ ИЗ Документ.Чек",
    "// скрыто\n УДАЛИТЬ ИЗ Документ.Чек",
    'ВЫБРАТЬ "//"; УДАЛИТЬ ИЗ Документ.Чек',
    'ВЫБРАТЬ "незакрытая строка',
    "ВЫБРАТЬ 1 /* незакрытый комментарий",
])
def test_invalid_query_never_reaches_com(text):
    conn = FakeConnection()
    runner = QueryRunner(conn, 60)
    with pytest.raises(InputError):
        runner.run("key", "name", text, {}, lambda row: None)
    assert conn.created == 0


def test_valid_query_can_start_after_comments():
    conn = FakeConnection()
    result = QueryRunner(conn, 60).run("key", "name", "// комментарий\nВЫБРАТЬ 1", {}, lambda row: None)
    assert result["status"] == "ok"
    assert conn.created == 1


def test_missing_connection_string_is_safe(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("ONE_CONNECTION_STRING", raising=False)
    code = app_stage0.main(["metadata", "--output-dir", str(tmp_path / "out")])
    captured = capsys.readouterr()
    assert code == 1
    assert "ONE_CONNECTION_STRING" in captured.err
    assert not (tmp_path / "out").exists()
    assert captured.out == ""


def test_connection_failure_never_prints_or_writes_secret(monkeypatch, tmp_path, capsys, caplog):
    class BrokenConnector:
        def __init__(self, connection_string):
            self.secret = connection_string

        def connect(self):
            logging.getLogger("poscenter_loyalty_agent.one_com").error(self.secret)
            raise RuntimeError(self.secret + " " + FAKE_NAME)

        def disconnect(self):
            pass

    monkeypatch.setenv("ONE_CONNECTION_STRING", FAKE_CONNECTION)
    monkeypatch.setattr(app_stage0, "OneComConnector", BrokenConnector)
    code = app_stage0.main(["metadata", "--output-dir", str(tmp_path / "out")])
    captured = capsys.readouterr()
    assert code == 1
    assert FAKE_CONNECTION not in captured.out + captured.err + caplog.text
    assert "mock-password" not in captured.out + captured.err + caplog.text
    assert FAKE_NAME not in captured.out + captured.err + caplog.text
    assert "(RuntimeError)" in captured.err
    assert not (tmp_path / "out").exists()


def test_connection_error_type_is_shown_without_details(monkeypatch, tmp_path, capsys):
    class FailingConnector:
        def __init__(self, connection_string):
            self.secret = connection_string

        def connect(self):
            raise COMConnectionError("ONE_CONNECTION_FAILED: " + self.secret + " " + FAKE_NAME)

        def disconnect(self):
            pass

    monkeypatch.setenv("ONE_CONNECTION_STRING", FAKE_CONNECTION)
    monkeypatch.setattr(app_stage0, "OneComConnector", FailingConnector)
    assert app_stage0.main(["metadata", "--output-dir", str(tmp_path / "out")]) == 1
    captured = capsys.readouterr()
    assert "(COMConnectionError)" in captured.err
    assert "ONE_CONNECTION_FAILED" not in captured.err
    assert "mock-password" not in captured.out + captured.err
    assert FAKE_NAME not in captured.out + captured.err


def test_benchmark_uses_last_document_day(monkeypatch, tmp_path):
    conn = FakeConnection()
    install_connector(monkeypatch, conn)
    directory = tmp_path / "results"
    assert app_stage0.main(["profile", "--output-dir", str(directory), "--targets", str(target_file(tmp_path))]) == 0
    # Последний документ фейковой базы — 2026-01-01 18:00, далеко от сегодняшней даты.
    periods = [params for text, params in conn.calls if "КАК Поле0" in text]
    assert periods == [
        {"Начало": datetime(2026, 1, 1), "Конец": datetime(2026, 1, 2)},
        {"Начало": datetime(2025, 12, 26), "Конец": datetime(2026, 1, 2)},
    ]
    profile = json.loads((directory / "profile.json").read_text(encoding="utf-8"))
    assert [b["period"] for b in profile["benchmarks"]] == [
        {"start": "2026-01-01", "end_exclusive": "2026-01-02"},
        {"start": "2025-12-26", "end_exclusive": "2026-01-02"},
    ]


def test_benchmark_is_skipped_without_last_document_date(monkeypatch, tmp_path):
    conn = FakeConnection(fail_on="КАК Первая")
    install_connector(monkeypatch, conn)
    directory = tmp_path / "results"
    assert app_stage0.main(["profile", "--output-dir", str(directory), "--targets", str(target_file(tmp_path))]) == 0
    assert not any("КАК Поле0" in text for text in conn.executed)
    profile = json.loads((directory / "profile.json").read_text(encoding="utf-8"))
    assert [b["status"] for b in profile["benchmarks"]] == [
        "не проверено: неизвестна дата последнего документа",
    ] * 2


def test_profile_discards_names_phones_barcodes_and_unapproved_payments(monkeypatch, tmp_path, capsys):
    conn = FakeConnection()
    install_connector(monkeypatch, conn)
    targets = target_file(tmp_path)
    directory = tmp_path / "results"
    code = app_stage0.main(["profile", "--output-dir", str(directory), "--targets", str(targets)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "Файл создан.\n"
    assert captured.err == ""
    texts = [(directory / name).read_text(encoding="utf-8")
             for name in ("metadata.json", "profile.json", "APP_STAGE0_SUMMARY.md")]
    for text in texts + [captured.out, captured.err]:
        assert FAKE_NAME not in text
        assert FAKE_PHONE not in text
        assert FAKE_BARCODE not in text
        assert FAKE_CONNECTION not in text
        assert "mock-password" not in text
    profile = json.loads(texts[1])
    document = profile["objects"][0]
    statistics = next(q["statistics"] for q in document["queries"] if "statistics" in q)
    assert statistics == {"documents": 3, "mean": 1.0, "median": 1.0, "p95": 2, "max": 2}
    payment = next(q for q in document["queries"] if q["query"].startswith("оплаты:"))
    assert payment["data"] == [{"type": "Наличные", "count": 2}]
    assert payment["other_count"] == 1
    assert len(profile["benchmarks"]) == 2
    assert all(q["status"] == "ok" and q["result_rows"] == 2 for q in profile["benchmarks"])
    balance = profile["objects"][2]
    assert next(q for q in balance["queries"] if q["query"] == "строки остатков")["data"][0] == {
        "total": 5, "zero_all_resources": 0, "negative_any_resource": 1,
    }
    assert any(q["query"] == "строк оборотов за месяц" and q["status"] == "ok"
               for q in profile["objects"][3]["queries"])


def test_metadata_inventory_marks_candidates_and_exchange_content(monkeypatch, tmp_path, capsys):
    conn = FakeConnection()
    install_connector(monkeypatch, conn)
    directory = tmp_path / "metadata"
    assert app_stage0.main(["metadata", "--output-dir", str(directory)]) == 0
    assert capsys.readouterr().out == "Файл создан.\n"
    result = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    assert len(result["categories"]) == 7
    doc = result["categories"]["Документы"]["objects"][0]
    assert doc["candidate"] == "кандидат, требует подтверждения"
    assert doc["details"]["possible_creation_or_change_dates"][0]["name"] == "ДатаСоздания"
    assert doc["details"]["tabular_sections"][0]["attributes"][0]["name"] == "Товар"
    assert result["exchange_plans"][0] == {"name": "ОбменТест", "available": True, "members": ["Чек"]}
    assert not conn.executed


def test_error_in_one_query_does_not_stop_other_queries(monkeypatch, tmp_path):
    conn = FakeConnection(fail_on="КАК Первая")
    install_connector(monkeypatch, conn)
    targets = target_file(tmp_path)
    directory = tmp_path / "results"
    assert app_stage0.main(["profile", "--output-dir", str(directory), "--targets", str(targets)]) == 0
    profile = json.loads((directory / "profile.json").read_text(encoding="utf-8"))
    queries = profile["objects"][0]["queries"]
    assert queries[0]["status"] == "error"
    assert queries[0]["error"]["type"] == "RuntimeError"
    assert any(q["status"] == "ok" for q in queries[1:])
    content = (directory / "profile.json").read_text(encoding="utf-8")
    assert FAKE_NAME not in content
    assert FAKE_PHONE not in content
    assert FAKE_CONNECTION not in content


def test_slow_query_skips_following_heavy_query():
    conn = FakeConnection()
    clock = iter([0.0, 2.0])
    runner = QueryRunner(conn, 1, clock=lambda: next(clock))
    first = runner.run("same-object", "first", "ВЫБРАТЬ 1", {}, lambda row: None)
    second = runner.run("same-object", "heavy", "ВЫБРАТЬ 2", {}, lambda row: None, heavy=True)
    assert first["duration_ms"] == 2000
    assert second["status"] == "пропущено из-за медленного запроса"
    assert conn.created == 1


def test_repository_output_and_symlink_are_rejected(monkeypatch, tmp_path, capsys):
    install_connector(monkeypatch, FakeConnection())
    assert app_stage0.main(["metadata", "--output-dir", str(REPO_ROOT / "tools" / "forbidden")]) == 1
    assert "вне репозитория" in capsys.readouterr().err
    link = tmp_path / "repo-link"
    link.symlink_to(REPO_ROOT, target_is_directory=True)
    with pytest.raises(InputError):
        output_dir(str(link / "nested"))


def test_validation_happens_before_any_file_is_written(tmp_path):
    folder = tmp_path / "result"
    with pytest.raises(SecuritySanitizerError):
        write_files(folder, {"safe.txt": "Безопасно", "unsafe.txt": FAKE_PHONE}, "")
    assert not folder.exists()


def test_crosscheck_does_not_print_numbers(monkeypatch, tmp_path, capsys):
    conn = FakeConnection()
    install_connector(monkeypatch, conn)
    targets = target_file(tmp_path)
    directory = tmp_path / "results"
    code = app_stage0.main(["crosscheck", "--output-dir", str(directory), "--targets", str(targets),
                           "--date", "2026-10-01"])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "Файл создан.\n"
    assert not any(character.isdigit() for character in captured.out + captured.err)
    content = json.loads((directory / "crosscheck-2026-10-01.json").read_text(encoding="utf-8"))
    assert content["receipt_count"] == 3
    assert content["sales_sum"] == 42.5


def test_arbitrary_target_and_connection_flag_are_rejected(monkeypatch, tmp_path, capsys):
    conn = FakeConnection()
    install_connector(monkeypatch, conn)
    targets = tmp_path / "invalid.json"
    targets.write_text(json.dumps({"targets": [{"kind": "document", "name": "Чек;УДАЛИТЬ"}]}), encoding="utf-8")
    assert app_stage0.main(["profile", "--output-dir", str(tmp_path / "out"), "--targets", str(targets)]) == 1
    assert not conn.executed
    assert app_stage0.main(["metadata", "--output-dir", str(tmp_path / "out"),
                            "--connection-string", FAKE_CONNECTION]) == 1
    captured = capsys.readouterr()
    assert FAKE_CONNECTION not in captured.out + captured.err
