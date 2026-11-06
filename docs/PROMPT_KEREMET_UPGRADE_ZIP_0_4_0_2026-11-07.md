# Промпт исполнителю (Windows, KONS2): архив обновления агента KeremEt до 0.4.0 — 2026-11-07

Ты работаешь на `KONS2`, репозиторий `C:\Users\ШОУРУМ\Desktop\cashback-one`, PowerShell без повышения прав. Общайся и пиши отчёт по-русски.

**Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений; секреты и ПДн скрыть.**

## Контекст

На компьютере KeremEt стоит агент 0.3.0 (ключ бизнеса `keremet`). Человек там не технический, поэтому обновление — двойной щелчок по `ZAPUSTIT.cmd`. Куратор написал скрипт `docs/tools/keremet-upgrade-0.4.0/` (`ZAPUSTIT.cmd`, `upgrade-agent.ps1`). Он: отказывается работать на KONS2; проверяет SHA-256 Setup рядом с собой; копирует всю папку `C:\ProgramData\POSCENTER\LoyaltyAgent` в `C:\cashback-stage0\backup_upgrade_0_4_0_<время>`; открывает обычный установщик с подсказками («Сохранить существующие настройки», поля пустые); после установки ждёт в журнале `v0.4.0 … interval=60s` и два цикла, показывает итог.

Твоя задача — только **проверить скрипт и собрать архив**. Компьютер KeremEt не трогать, службу на KONS2 не останавливать и не обновлять (она уже 0.4.0).

## Шаги

1. `git pull --ff-only origin main`, `git log -1 --oneline`. Покажи SHA-256 `docs/tools/keremet-upgrade-0.4.0/ZAPUSTIT.cmd` и `upgrade-agent.ps1`.
2. **Синтаксис:** `[System.Management.Automation.Language.Parser]::ParseFile(<полный путь к upgrade-agent.ps1>, [ref]$null, [ref]$errs)` — `$errs.Count` должно быть 0, иначе СТОП с текстом ошибок. Проверь, что русский текст читается (кодировка UTF-8 с BOM): выведи строку 1 файла.
3. **Защита KONS2:** собери временную папку `C:\cb-kupgrade-check\` (если существует и не пуста — СТОП) с копиями обоих файлов и Setup `C:\cashback-stage0\agent-0.4.0\CashbackOneAgent-Setup-0.4.0.exe`. Запусти в обычном PowerShell (без администратора, не через `ZAPUSTIT.cmd`) `powershell -NoProfile -ExecutionPolicy Bypass -File C:\cb-kupgrade-check\upgrade-agent.ps1` и на вопрос нажми Enter. Ожидается сообщение «Это компьютер KONS2. Здесь запускать нельзя.» и выход **до** любой копии и установки. Покажи вывод; проверь, что новых папок `C:\cashback-stage0\backup_upgrade_0_4_0_*` (кроме уже существующей от обновления KONS2 `…_20261107_013242`) не появилось. Удали `C:\cb-kupgrade-check\`.
4. **Архив:** `C:\cashback-stage0\keremet-upgrade-0.4.0.zip` (если уже есть — СТОП) с тремя файлами в корне архива: `ZAPUSTIT.cmd`, `upgrade-agent.ps1`, `CashbackOneAgent-Setup-0.4.0.exe` (Setup — SHA-256 `98cfb4004870ab2d29c45f1872fad868077dbfbd1a68bed1d67354a791594cf1`, иначе СТОП). Распакуй архив во временную папку и сверь SHA-256 всех трёх файлов с источниками, папку удали. Покажи размер и SHA-256 архива.

## Нельзя

Не запускать скрипт от администратора и через `ZAPUSTIT.cmd`; не запускать Setup; не трогать службу, `C:\ProgramData\POSCENTER`, ONE. Не менять скрипт — если нашёл ошибку, СТОП и опиши. Без commit/push, кроме отчёта.

## Отчёт

`reports/KEREMET_UPGRADE_ZIP_0_4_0_2026-11-07.md`: сырой вывод шагов 1–4. В конце закоммить и отправь в main **только** этот отчёт (`git add` поимённо, `git diff --cached --name-only`, `git pull --ff-only` перед `push`).
