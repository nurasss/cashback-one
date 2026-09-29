# TASK-009 FIX-C Report: Neutral Metadata & Zero-Assumption Stage-0 Remediation

## Removed Metadata Assumptions

Полностью удалены все угаданные (speculative) имена объектов и полей 1С из исходного кода и документации Stage 0:
- В [`mapping_models.py`](file:///Users/nuras/Desktop/cashback-one/agent/src/poscenter_loyalty_agent/stage0/mapping_models.py):
  - Поле `cards.source_object`: описание очищено от `(e.g. Catalogs.InformationCards)` и заменено на нейтральное:
    `"Exact metadata object identifier discovered from the pilot configuration"`.
  - Поле `cards.stable_source_id`: описание очищено от предположений `(e.g. Ref / UUID)` и заменено на нейтральное:
    `"Exact stable source identifier or deterministic identity expression verified on the pilot configuration"`.
  - Поле `transactions.source_object`: описание очищено от `(e.g. AccumulationRegisters.BonusPoints)` и заменено на нейтральное:
    `"Exact transaction/movement metadata source discovered during Stage 0"`.
  - Поле `cursor_strategy.cards` / `transactions`: описание очищено от `(e.g. keyset_timestamp_ref)` и заменено на нейтральное:
    `"Deterministic cursor pagination strategy identifier"`.

---

## Transaction Type Neutrality

Устранено ограничение, предполагавшее, что канонические типы транзакций в бэкенде жестко сводятся к `accrual/redemption`:
- В [`mapping_models.py`](file:///Users/nuras/Desktop/cashback-one/agent/src/poscenter_loyalty_agent/stage0/mapping_models.py) описание поля `transactions.type_mapping` обновлено:
  `"Verified deterministic mapping from source movement semantics to the canonical Cloud transaction type string"`.
- Контракт бэкенда принимает любую непустую каноническую строку типа транзакции. Конкретные правила сопоставления должны определяться реальной семантикой учетной системы POSCENTER ONE во время Phase B, а не диктоваться фиктивными константами.

---

## Barcode Terminology

Устранено неподтвержденное предположение о том, что 13-значные штрихкоды карт обязательно следуют спецификации EAN / EAN-13:
- Поле `cards.barcode_field` в схеме Pydantic переименовано/описано как `"Field containing 13-digit loyalty-card barcode string"`.
- В генераторе отчета `STAGE0_DISCOVERY_REPORT.md` ([`report.py`](file:///Users/nuras/Desktop/cashback-one/agent/src/poscenter_loyalty_agent/stage0/report.py)) формулировка:
  `"Requires aggregate proof of 13-digit EAN cards in pilot."`
  заменена на:
  `"Requires aggregate proof of the 13-digit loyalty-card barcode field."`.
- В комментариях инспекции [`sample_evidence.py`](file:///Users/nuras/Desktop/cashback-one/agent/src/poscenter_loyalty_agent/stage0/sample_evidence.py) ссылки на стандарт EAN заменены на нейтральную проверку 13 цифр.
- В эвристиках поиска метаданных [`metadata_probe.py`](file:///Users/nuras/Desktop/cashback-one/agent/src/poscenter_loyalty_agent/stage0/metadata_probe.py) ключевые слова штрихкода очищены от `ean`.

---

## Synthetic Example

Файл [`agent/stage0_mapping.example.json`](file:///Users/nuras/Desktop/cashback-one/agent/stage0_mapping.example.json) приведен к полностью нейтральному синтетическому виду:
- Секция `type_mapping` переписана:
  ```json
  "type_mapping": {
    "value": {
      "SyntheticSourceTypeA": "CanonicalTypeA",
      "SyntheticSourceTypeB": "CanonicalTypeB"
    },
    "state": "CANDIDATE",
    "evidence": [
      "Synthetic metadata probe: movement type dictionary"
    ]
  }
  ```
- Канонический SHA-256 хеш артефакта пересчитан: `6f899eefe05796473d5ac3479c9e764304b046d1e6dea5317006802acf4808cf`.
- Шаблон сохраняет статус `artifact_kind = "synthetic_example"` и `state = "CANDIDATE"`, успешно проходит стандартную валидацию и гарантированно отклоняется режимом `--require-verified`.

---

## Zero-Assumption Regression

В тестовый набор [`agent/tests/test_stage0.py`](file:///Users/nuras/Desktop/cashback-one/agent/tests/test_stage0.py) добавлен тест `test_zero_speculative_assumptions_in_stage0_sources`:
- Автоматически сканирует все `.py` файлы в пакете `agent/src/poscenter_loyalty_agent/stage0` и файл шаблона `agent/stage0_mapping.example.json`.
- Проверяет отсутствие маркеров:
  - `Catalogs.InformationCards` / `InformationCards`
  - `AccumulationRegisters.BonusPoints` / `BonusPoints`
  - `EAN-13` / `13-digit EAN`
  - `accrual` / `redemption`
  - `Ref / UUID`
- Полнотекстовый поиск `grep -RniE "InformationCards|BonusPoints|\bEAN\b|EAN-13|13-digit EAN|accrual|redemption" agent/src/poscenter_loyalty_agent/stage0` дает 0 совпадений.

---

## Phase B Status

На текущей macOS-машине реальный запуск Phase B не производился и не симулировался.
Нормативный статус строго сохранен:

```text
TASK-009 PHASE A = COMPLETE
TASK-009 PHASE B = BLOCKED_BY_REAL_ONE_ENVIRONMENT

REAL_WINDOWS_SERVICE = NOT VERIFIED
REAL_V83_COMCONNECTOR = NOT VERIFIED
REAL_ONE_CONNECTION = NOT VERIFIED
REAL_ONE_METADATA_DISCOVERY = NOT VERIFIED
REAL_ONE_MAPPING = NOT VERIFIED

STATUS = READY_FOR_REAL_ONE_DISCOVERY
```

---

## Agent Tests

Все 75 тестов агента успешно пройдены:
```bash
PYTHONPATH=agent/src pytest agent/tests -v
# Результат: 75 passed in 3.09s
```

---

## Backend Regression

Все не-медленные тесты бэкенда пройдены:
```bash
pytest -v -m "not slow"
# Результат: 176 passed, 29 skipped in 13.99s
```

---

## PostgreSQL Regression

Все 29 тестов конкурентности PostgreSQL пройдены:
```bash
POSTGRES_TEST_URL="postgresql+asyncpg://nuras@localhost:5432/poscenter_loyalty_test" pytest -v tests/test_postgres_*.py
# Результат: 29 passed in 8.93s
```

---

## Ruff

Проверка линтером пройдена без замечаний:
- Agent: `ruff check agent/src agent/tests` — All checks passed!
- Backend: `ruff check app tests migrations` — All checks passed!

---

## Mypy

Статическая типизация пройдена успешно:
- Agent: `mypy src tests` — Success: no issues found in 35 source files
- Backend: `mypy app migrations` — Success: no issues found in 41 source files

---

## Compileall

Байткод компилируется без ошибок:
- Agent: `python -m compileall src tests` — 0 errors
- Backend: `python -m compileall app tests migrations` — 0 errors

---

## Git Status

Измененные и созданные файлы:
- `agent/src/poscenter_loyalty_agent/stage0/mapping_models.py`
- `agent/src/poscenter_loyalty_agent/stage0/metadata_probe.py`
- `agent/src/poscenter_loyalty_agent/stage0/report.py`
- `agent/src/poscenter_loyalty_agent/stage0/sample_evidence.py`
- `agent/stage0_mapping.example.json`
- `agent/tests/test_stage0.py`
- `docs/TASK_009_FIX_C_REPORT.md`

---

## Branch

`main`

---

## HEAD

Перед фиксацией: `68492e346510f055bab5c993e06e92e454be04b4`
