# TASK-009 FIX-A Report: Independent Stage-0 Audit Remediation

## Verification-State Model

Введена обязательная строгая модель верификационных состояний для каждого P0/P1 решения по маппингу:
```python
VerificationState = Literal["NOT_STARTED", "CANDIDATE", "VERIFIED"]
```
Для безопасного инкапсулирования каждого сопоставления реализован типизированный generic-wrapper:
```python
class MappingValue(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")
    value: T
    state: VerificationState = "NOT_STARTED"
    evidence: list[str] = Field(default_factory=list)
```

Каждое обязательное P0 поле маппинга теперь строго типизировано как `MappingValue`:
- `cards.source_object`: `MappingValue[str]`
- `cards.stable_source_id`: `MappingValue[str]`
- `cards.barcode_field`: `MappingValue[str]`
- `cards.phone_field`: `MappingValue[str]`
- `cards.full_name_field`: `MappingValue[str]`
- `cards.balance_source`: `MappingValue[str]`
- `cards.blocked_source`: `MappingValue[str]`
- `cards.updated_at_source`: `MappingValue[str]`
- `transactions.source_object`: `MappingValue[str]`
- `transactions.stable_source_id`: `MappingValue[str]`
- `transactions.card_relationship`: `MappingValue[str]`
- `transactions.type_field`: `MappingValue[str]`
- `transactions.type_mapping`: `MappingValue[dict[str, str]]`
- `transactions.amount_field`: `MappingValue[str]`
- `transactions.occurred_at_field`: `MappingValue[str]`
- `cursor_strategy.cards`: `MappingValue[EntityCursorStrategy]`
- `cursor_strategy.transactions`: `MappingValue[EntityCursorStrategy]`

Наличие значения (`value`) само по себе больше ничего не доказывает: статус решения определяется явным полем `state` и подкрепляется ссылками на эмпирические свидетельства пилота в `evidence`.

---

## Candidate vs Verified Boundary

Установлена жесткая граница между предварительным (candidate) и подтвержденным (verified) артефактами:
1. `artifact_kind`:
   - `synthetic_example`: для шаблонов и тестовых синтетических схем;
   - `real_discovery`: для артефактов, полученных в ходе реального пилота.
2. Никакой артефакт не может считаться `VERIFIED`, если хотя бы одно обязательное P0 поле имеет статус `CANDIDATE` или `NOT_STARTED`.
3. Любое присутствие эвристических догадок или синтетических идентификаторов немедленно дисквалифицирует артефакт из перехода в продакшн.

---

## Synthetic Example

Файл `agent/stage0_mapping.example.json` полностью переписан:
- Устранены любые правдоподобные предположительные имена объектов POSCENTER ONE.
- Применены нейтральные синтетические сущности: `SyntheticObjectA`, `SyntheticFieldId`, `SyntheticFieldBarcode`, `SyntheticFieldPhone`, `SyntheticRegisterA`, `SyntheticRecordType`, `SyntheticResAmount`, `SyntheticPeriod` и т.д.
- Конфигурация объявлена как `SyntheticTestConfiguration`.
- Метаданные явно содержат: `artifact_kind = "synthetic_example"`.
- Все состояния маппинга установлены в `CANDIDATE` (или `NOT_STARTED` для опциональных полей).
- Контрольная сумма `mapping_sha256` пересчитана по каноническому алгоритму (`f3fc2131bf52ac8c9cf2b4dc9770472bbe4306b18eba6371bd544a617e1d143b`).

---

## Verified Validator Mode

Команда валидатора расширена режимом строгой проверки `--require-verified`:
```bash
poscenter-loyalty-agent stage0 validate-mapping <file.json> [--require-verified]
```

- **Стандартный режим (без `--require-verified`)**:
  Проверяет корректность JSON, Pydantic-схему, контрольную сумму `mapping_sha256`, отсутствие PII/утечек учетных данных и отсутствие запрещенных плейсхолдеров (`TODO`, `TBD`, `unknown_object`).
- **Строгий режим (`--require-verified`)**:
  Обязывает:
  1. `artifact_kind == "real_discovery"`.
  2. Имя конфигурации не является синтетическим (`SyntheticTestConfiguration` и т.д.).
  3. Все 16 обязательных P0 полей имеют `state == "VERIFIED"`.
  4. Полное отсутствие плейсхолдеров и синтетических слов (включая `example` и `synthetic`).
  5. При нарушении хотя бы одного критерия валидатор завершается с ненулевым кодом выхода (`exit 1`) и выводит детальный список незаверенных полей.

Синтетический шаблон `stage0_mapping.example.json` гарантированно не проходит `--require-verified`.

---

## Metadata Discovery Flag

В `check_environment` исправлена логика установки флагов:
- Наличие `V83.COMConnector` в реестре устанавливает `REAL_V83_COMCONNECTOR = VERIFIED`.
- Успешный `connector.Connect(...)` устанавливает `REAL_ONE_CONNECTION = VERIFIED`.
- Доступность корня `connection.Metadata` **НЕ** переводит `REAL_ONE_METADATA_DISCOVERY` в `VERIFIED`. На этапе предпроверки окружения флаг строго остается `NOT VERIFIED`.
- Флаг `REAL_ONE_METADATA_DISCOVERY` может стать `VERIFIED` только после полного завершения команды `stage0 probe-metadata` с использованием `ComMetadataProvider` на реальной Windows-машине с 1С.
- `FakeMetadataProvider` никогда не повышает верификационные флаги.

---

## Fake Provider Isolation

Синтетический `FakeMetadataProvider` изолирован строго для тестового окружения:
- Запуск `stage0 probe-metadata --use-fake-provider` разрешен **исключительно** при `AGENT_ENV=test`.
- При `AGENT_ENV=development` или `AGENT_ENV=production` использование `--use-fake-provider` прерывается контролируемой ошибкой конфигурации с `exit 1` без генерации каких-либо фиктивных артефактов.
- Добавлены регрессионные тесты изоляции окружений.

---

## Sample Evidence Privacy

Для предотвращения утечек реальных данных клиентов и учетных записей реализован модуль `SampleEvidenceBuilder` (`agent/src/poscenter_loyalty_agent/stage0/sample_evidence.py`):
- Предоставляет безопасный шлюз для анализа сырых выборок в памяти при проведении Phase B pilot run.
- Методы `observe_card_record(...)` обрабатывают поля в кратковременной оперативной памяти и формируют исключительно статистические счетчики и метаданные типов (`sample_size`, `valid_13_digit`, `null_count`, `normalizable_count`, `numeric_type`, `precision`, `allows_negative`).
- Сырые значения номеров телефонов, штрихкодов, ФИО клиентов и паролей **никогда** не сохраняются в агрегатах и не сериализуются в артефакты.
- Регрессионный тест `test_sample_evidence_privacy_secret_person_regression` гарантирует, что строка `Secret Person`, телефон `+77001234567`, штрихкод `0123456789012` и фрагмент `Pwd=secret` полностью отсутствуют в сериализованных артефактах.

---

## Sanitizer Idempotency

Исправлен сканер чувствительных данных в `sanitizer.py`:
- Регулярные выражения `RE_CONN_PARAM` и `RE_SECRET_KEY` оснащены negative lookahead (`(?!\\*\\*\\*REDACTED\\*\\*\\*|\\[REDACTED\\])`).
- Функция `sanitize_text` маскирует учетные данные без создания конструкций, которые повторно идентифицируются сканером как открытые пароли.
- Обеспечено строгое свойство идемпотентности:
  ```python
  clean = sanitize_text(raw)
  scan_for_sensitive_data(clean) == []
  sanitize_text(clean) == clean
  validate_safe_output(clean) # PASS
  ```
- Тест `test_sanitizer_idempotency_and_safety_scan` подтверждает корректную работу.

---

## Metadata Inventory Coverage

Устранено вводящее в заблуждение заявление о «полном инвентаре»:
- Класс инвентаря переименован в `TargetedMetadataInventory` с сохранением алиаса `MetadataInventory`.
- Артефакты инвентаря явно декларируют объем покрытия:
  - `coverage_scope`: `"targeted_loyalty_core"`
  - `probed_categories`: `Catalogs`, `AccumulationRegisters`, `InformationRegisters`, `Documents`
  - `unprobed_categories`: `ChartsOfAccounts`, `ChartsOfCalculationTypes`, `ChartsOfCharacteristicTypes`, `BusinessProcesses`, `Tasks`, `Enums`, `Reports`, `DataProcessors`, `Constants`, `Sequences`, `ExchangePlans`
  - `coverage_limitation`: Явное предупреждение о том, что сканирование сфокусировано на транзакционных объектах лояльности и полный корень метаданных конфигурации не обходился.
- Отчеты Markdown и JSON содержат честное уведомление о границах покрытия.

---

## Platform Version Semantics

Устранена фиктивная привязка версии платформы:
- Точная версия платформы не зашивается хардкодом в `8.3`.
- При отсутствии верифицированного чтения точного билда 1С указывается:
  - `platform_major`: `"8.3"`
  - `platform_version`: `"NOT_AVAILABLE"`
  - `platform_version_state`: `"NOT_STARTED"`
- Статус `platform_version_state = VERIFIED` выставляется только при наличии подтвержденного полного номера сборки (например, `8.3.24.1342`).

---

## Phase B Status

На текущей хост-машине (macOS `darwin`) Phase B не запускалась и не симулировалась.
Статус полностью соответствует требованиям:

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

Все 69 тестов агента успешно пройдены:
```bash
PYTHONPATH=agent/src pytest agent/tests -v
# Результат: 69 passed in 2.60s
```

Включены 12 специализированных тестов Stage 0 в `agent/tests/test_stage0.py`:
- `test_non_windows_environment_reports_not_verified`
- `test_check_environment_does_not_mark_metadata_discovery_verified`
- `test_fake_provider_restricted_to_test_env`
- `test_fake_provider_never_upgrades_real_flags`
- `test_sample_evidence_privacy_secret_person_regression`
- `test_sanitizer_idempotency_and_safety_scan`
- `test_inventory_reports_coverage_truthfully`
- `test_synthetic_example_cannot_pass_require_verified`
- `test_candidate_mapping_cannot_pass_require_verified`
- `test_all_mandatory_verified_mapping_passes_require_verified`
- `test_mapping_fingerprint_tamper_detection`
- `test_candidate_discovery_heuristics`
- `test_security_sanitizer_error_raised`

---

## Backend Regression

Все не-медленные тесты бэкенда успешно пройдены:
```bash
pytest -v -m "not slow"
# Результат: 176 passed, 29 skipped in 13.67s
```

---

## PostgreSQL Regression

Все 29 интеграционных тестов конкурентности PostgreSQL пройдены:
```bash
POSTGRES_TEST_URL="postgresql+asyncpg://nuras@localhost:5432/poscenter_loyalty_test" pytest -v tests/test_postgres_*.py
# Результат: 29 passed in 8.67s
```

---

## Ruff

Линтер выполнен без ошибок:
- Agent: `ruff check agent/src agent/tests` — All checks passed!
- Backend: `ruff check app tests migrations` — All checks passed!

---

## Mypy

Статическая типизация пройдена без замечаний:
- Agent: `mypy src tests` — Success: no issues found in 35 source files
- Backend: `mypy app migrations` — Success: no issues found in 41 source files

---

## Compileall

Байткод компилируется без ошибок:
- Agent: `python -m compileall src tests` — 0 errors
- Backend: `python -m compileall app tests migrations` — 0 errors

---

## Git Status

Измененные и новые файлы:
- `agent/src/poscenter_loyalty_agent/stage0/sanitizer.py`
- `agent/src/poscenter_loyalty_agent/stage0/sample_evidence.py`
- `agent/src/poscenter_loyalty_agent/stage0/mapping_models.py`
- `agent/src/poscenter_loyalty_agent/stage0/metadata_probe.py`
- `agent/src/poscenter_loyalty_agent/stage0/environment.py`
- `agent/src/poscenter_loyalty_agent/stage0/validator.py`
- `agent/src/poscenter_loyalty_agent/stage0/report.py`
- `agent/src/poscenter_loyalty_agent/stage0/cli.py`
- `agent/src/poscenter_loyalty_agent/stage0/__init__.py`
- `agent/stage0_mapping.example.json`
- `agent/tests/test_stage0.py`
- `docs/TASK_009_FIX_A_REPORT.md`

---

## Branch

`main`

---

## HEAD

Перед фиксацией: `dba412c24fee3a21cdd7e0e6cc98b59c4c66b2bf`
