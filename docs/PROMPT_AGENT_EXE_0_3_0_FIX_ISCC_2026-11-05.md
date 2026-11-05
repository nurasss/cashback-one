# Промпт исполнителю (Windows): исправление компиляции установщика 0.3.0 — 2026-11-05

Компьютер `KONS2`, репозиторий `C:\Users\ШОУРУМ\Desktop\cashback-one`, PowerShell без повышения прав. Общайся и пиши отчёт по-русски.

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений сверх описанного; секреты и ПДн скрыть.**

## Контекст

Сборка по `docs/PROMPT_AGENT_EXE_0_3_0_2026-11-05.md` правильно остановилась. Тесты дали 12 failed / 281 passed. Причина: Inno Setup 6.7.3 не компилирует `agent/packaging/config_serializer.iss`, строка 170, колонка 47 — `Type mismatch` на `AnsiString(DPAPI_ENTROPY_STR)`. Это ошибка кода 0.3.0: на Mac компилятор Inno Setup не запускался. Ruff, mypy и тесты DPAPI и `check-one` прошли. Служба 0.2.2 не тронута.

## Разрешённая правка (решение куратора)

Только в `agent/packaging/config_serializer.iss`, в двух местах (строки около 170 и 269):

```pascal
EntropyAnsi := AnsiString(DPAPI_ENTROPY_STR);
```
заменить на
```pascal
EntropyAnsi := DPAPI_ENTROPY_STR;
```

Константа состоит только из ASCII, поэтому байты те же, что у агента на Python (`dpapi.py`: `b"POSCENTER_LOYALTY_AGENT_DPAPI_SALT_v1"`). Больше ничего в файле не менять. Покажи `git diff`.

## Шаги

1. `git pull --ff-only origin main`, `git status --short` (кроме этой правки, изменений нет).
2. Правка выше, `git diff -- agent/packaging/config_serializer.iss`.
3. Прямая компиляция `harness_serializer.iss` (как ты делал при диагностике) и `installer.iss` через `C:\cb-build\tools\innosetup\ISCC.exe`.
   - **Новая ошибка компиляции — СТОП**: сырой вывод, строка кода и твоё предложение исправления. Само исправление **не применять**.
4. `pytest agent/tests -v`: ожидается 0 failed (было 281 passed + 12 failed = 293). Иначе СТОП.
5. Обязательно убедись, что DPAPI установщика и агента совместимы. Есть ли в тестах проверка, что значение, зашифрованное кодом Pascal, расшифровывает Python `unprotect_secret`? Назови тест. Если такой проверки нет, проверь вручную в `C:\cb-smoke-030\`: зашифруй тестовым harness выдуманную строку `smoke-not-a-secret` и расшифруй Python-функцией агента. Нужно совпадение (`True`/`False`).
6. Дальше продолжи `docs/PROMPT_AGENT_EXE_0_3_0_2026-11-05.md` с шага сборки установщика до конца: изолированная проверка, хеши прежних Setup, служба 0.2.2 Running.

## Нельзя

Всё из основного промпта: не ставить и не обновлять службу, не читать настоящий `.env.service`, ключи и пароль 1С, не открывать `C:\1C_data\int`, без Release. Commit и push правки — не делать: куратор проверит diff и сохранит сам.

## Отчёт

`reports/AGENT_EXE_0_3_0_2026-11-05.md`: сырой вывод падения и исправления, `git diff`, проверки по основному промпту.

## Дополнение 2 (после второго СТОП): `installer.iss`, строка 366

Остановка была правильной. Решение куратора: предложение принято. Правки из первого раздела оставить, `harness_serializer.iss` уже компилируется, `test_installer_config.py` 16/16.

1. В `agent/packaging/installer.iss`, функция `ExecuteCheckOne`:
   ```pascal
     ProbeExe, ResultJsonFile, CmdParams, JsonContent: string;
   ```
   заменить на
   ```pascal
     ProbeExe, ResultJsonFile, CmdParams: string;
     JsonContent: AnsiString;
   ```
   Больше ничего не менять. Агент пишет файл как `{"code": "ok"}` (`main.py`, `json.dumps`, только ASCII-коды), поэтому `Pos` по `AnsiString` находит те же строки.
2. Если при следующей компиляции снова будет `Type mismatch`, разрешено исправить его без нового СТОП **только при одном условии**. Причина должна быть та же: переменная `string` передаётся во встроенную функцию Inno Setup, которая ждёт `AnsiString` (`LoadStringFromFile`, `SaveStringToFile` и подобные). Исправлять только сменой типа этой переменной на `AnsiString`. Каждую такую правку покажи в `git diff` и в отчёте с номером строки. Любая другая ошибка компиляции — СТОП с сырым выводом и предложением, без правки.
3. Затем шаги 3–6 первого раздела: компиляция `installer.iss`, полный `pytest agent/tests -v` (0 failed), совместимость DPAPI. Тест `test_pascal_harness_serialization_roundtrip` уже ответил на этот вопрос, ручную проверку не повторять. Сборка, изолированная проверка, хеши прежних Setup, служба 0.2.2 Running.
4. Дополнительно в изолированной проверке: из собранного EXE запусти `check-one --output-file C:\cb-smoke-030\r.json` на несуществующей базе. Покажи содержимое `r.json`: в нём только код, без секретов. Оно должно содержать одну из строк, которые ищет `ExecuteCheckOne` (например `"code": "db_not_found"`).
