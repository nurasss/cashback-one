# TASK-009 FIX-B Report: Stage-0 Evidence Layer & Environment Consistency Remediation

## Environment Artifact Consistency

Устранено расхождение между артефактами `environment.json` и `STAGE0_DISCOVERY_REPORT.md`:
- Ранее `environment.json` записывался до выполнения probe и не перезаписывался после повышения флага `real_one_metadata_discovery = VERIFIED`.
- Теперь оба артефакта строго синхронизированы и формируются на базе единого финального объекта `env_result`.
- Флаги:
  - `REAL_WINDOWS_SERVICE`
  - `REAL_V83_COMCONNECTOR`
  - `REAL_ONE_CONNECTION`
  - `REAL_ONE_METADATA_DISCOVERY`
  - `REAL_ONE_MAPPING`
  в обоих файлах всегда идентичны.

---

## Successful Real Probe Semantics

Для реального `ComMetadataProvider` на Windows закреплен следующий строгий порядок:
1. Выполняется `check_environment` (формирует начальный `env_result`, где `real_one_metadata_discovery = NOT VERIFIED`).
2. Производится реальное извлечение метаданных `discover_metadata()`.
3. Выполняется валидация безопасности и запись инвентаря `write_inventory_reports(inventory, output_dir)`.
4. **ТОЛЬКО ПОСЛЕ** успешного завершения шагов 2 и 3 флаг повышается:
   `env_result.verification_flags.real_one_metadata_discovery = FLAG_VERIFIED`.
5. Перезаписывается финальный `environment.json`.
6. Формируется финальный `STAGE0_DISCOVERY_REPORT.md` с тем же статусом `VERIFIED`.

---

## Failed Probe Semantics

При возникновении любых сбоев во время реального зондирования:
- COM-исключения (`COMError`, потеря сетевого соединения с сервером 1С, сбой авторизации);
- ошибки обхода коллекций объектов метаданных;
- ошибки сериализации;

флаг `real_one_metadata_discovery` строго остается `NOT VERIFIED`. В блоке `except` артефакты `environment.json` и `STAGE0_DISCOVERY_REPORT.md` гарантированно обновляются со значением `NOT VERIFIED`, а CLI завершается с ненулевым кодом выхода (`exit 1`).

---

## Sanitizer Failure Semantics

Если в обнаруженных метаданных (например, в пользовательских синонимах объектов или реквизитов) обнаружены открытые пароли, фрагменты строк подключения или PII:
- `validate_safe_output` выбрасывает `SecuritySanitizerError` во время `write_inventory_reports`.
- Повышение флага до `VERIFIED` не происходит (так как шаг 4 выполняется строго после шага 3).
- В артефактах `environment.json` флаг остается `NOT VERIFIED`.
- Никакие небезопасные файлы на диск не записываются.

---

## Verified Evidence Requirement

В строгом режиме валидатора:
```bash
poscenter-loyalty-agent stage0 validate-mapping <file.json> --require-verified
```
для всех 16 обязательных P0-решений по маппингу установлено строгое правило подтверждения:
- Наличие поля со статусом `state == "VERIFIED"` обязательно сопровождается непустым массивом `evidence` (`len(evidence) >= 1`).
- Каждый элемент массива `evidence`:
  - обязан быть непустой строкой после `.strip()`;
  - обязан проходить строгий placeholder-скан (отсутствие `TODO`, `TBD`, `guess`, `example`, `synthetic`, `mock`, `placeholder`);
  - обязан проходить сканер PII и учетных данных.

### Примечание о доказательствах (Audit Trail)
Поле `evidence` является аудиторским следом (audit trail / human-review evidence) и инженерным обоснованием для перекрестной проверки, а **НЕ** криптографическим доказательством времени выполнения. Валидатор гарантирует корректность схемы, статус, наличие ссылок на свидетельства, целостность SHA-256 и безопасность данных. Проведение независимого инженерного аудита реального запуска Phase B на Windows остается обязательным требованием.

---

## Empty Evidence Rejection

Разработаны и проверены регрессионные тесты:
- Если хотя бы одно обязательное P0-поле имеет `state == "VERIFIED"`, но `evidence: []` — валидатор отклоняет артефакт:
  ```text
  Mandatory mapping field 'cards.barcode_field' is VERIFIED but has no verification evidence.
  ```
- Если `evidence` содержит только пробельные символы (`evidence: ["   "]`) — валидатор также отклоняет артефакт и выставляет `is_valid = False`.

---

## Candidate vs Verified Boundary

По-прежнему строго соблюдается граница:
- Артефакты с `artifact_kind == "synthetic_example"` никогда не могут пройти `--require-verified`.
- Артефакты со статусами `CANDIDATE` не могут пройти `--require-verified`.
- До успешного заполнения всех обязательных полей реальными идентификаторами и свидетельствами статус `REAL_ONE_MAPPING` остается строго `NOT VERIFIED`.

---

## Fake Provider Isolation

Изоляция тестового двойника `FakeMetadataProvider` сохранена:
- `--use-fake-provider` разрешен исключительно при `AGENT_ENV=test`.
- Использование fake provider никогда не повышает флаг `REAL_ONE_METADATA_DISCOVERY` (он всегда остается `NOT VERIFIED`).

---

## Phase B Status

На текущей macOS-машине реальный запуск Phase B не производился и не симулировался.
Итоговый нормативный статус:

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

Все 74 теста агента успешно пройдены:
```bash
PYTHONPATH=agent/src pytest agent/tests -v
# Результат: 74 passed in 2.99s
```

Включены новые тесты:
- `test_real_probe_success_updates_environment_json_and_report`
- `test_real_probe_failure_leaves_environment_json_not_verified`
- `test_real_probe_sanitizer_failure_leaves_not_verified`
- `test_verified_mapping_empty_evidence_rejected`
- `test_verified_mapping_whitespace_evidence_rejected`

---

## Backend Regression

Все не-медленные тесты бэкенда пройдены:
```bash
pytest -v -m "not slow"
# Результат: 176 passed, 29 skipped in 14.24s
```

---

## PostgreSQL Regression

Все 29 тестов конкурентности PostgreSQL пройдены:
```bash
POSTGRES_TEST_URL="postgresql+asyncpg://nuras@localhost:5432/poscenter_loyalty_test" pytest -v tests/test_postgres_*.py
# Результат: 29 passed in 8.83s
```

---

## Ruff

Проверка качества кода завершена без замечаний:
- Agent: `ruff check agent/src agent/tests` — All checks passed!
- Backend: `ruff check app tests migrations` — All checks passed!

---

## Mypy

Статическая проверка типов пройдена успешно:
- Agent: `mypy src tests` — Success: no issues found in 35 source files
- Backend: `mypy app migrations` — Success: no issues found in 41 source files

---

## Compileall

Компиляция байткода завершена без ошибок:
- Agent: `python -m compileall src tests` — 0 errors
- Backend: `python -m compileall app tests migrations` — 0 errors

---

## Git Status

Измененные и созданные файлы:
- `agent/src/poscenter_loyalty_agent/stage0/cli.py`
- `agent/src/poscenter_loyalty_agent/stage0/report.py`
- `agent/src/poscenter_loyalty_agent/stage0/validator.py`
- `agent/src/poscenter_loyalty_agent/stage0/__init__.py`
- `agent/tests/test_stage0.py`
- `docs/TASK_009_FIX_B_REPORT.md`

---

## Branch

`main`

---

## HEAD

Перед фиксацией: `7b5d7a7d54e81ff646438de7ed181d7309f4e0ad`
