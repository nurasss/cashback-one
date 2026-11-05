# Инвентаризация тестового Windows-компьютера (Read-Only), 2026-11-05

**Дата проверки:** 5 ноября 2026 г.  
**Рабочий каталог:** `C:\Users\ШОУРУМ\Desktop\cashback-one`  
**Режим:** Только чтение (PowerShell без повышения прав). Изменения в систему не вносились.

---

## Сырой вывод по пунктам 1–9

### 1. Компьютер

- **Имя компьютера:** `KONS2` *(в промптах и ранних отчётах условно обозначался как `DESKTOP-VND8ELJ`)*
- **Текущий пользователь:** `kons2\консультант 1с`
- **Версия Windows:** Майкрософт Windows 10 Pro, версия 1909, сборка `10.0.18363.628` (64-разрядная)
- **Время последней загрузки системы:** `05.11.2026 09:56:16`
- **Дисковое пространство (`Get-PSDrive -PSProvider FileSystem`):**
  - Диск `C:`
    - Занято: 99 482 173 440 байт (~92,65 GB)
    - Свободно: 19 874 082 816 байт (~18,51 GB)

---

### 2. Служба агента

- **Служба Windows (`POSCENTERLoyaltyAgent`):**
  - **Статус:** `Running`
  - **Тип запуска:** `Automatic` (`AUTO_START (DELAYED)`)
  - **Учетная запись службы:** `LocalSystem`
  - **Командная строка службы:** `"C:\Program Files (x86)\POSCENTER\LoyaltyAgent\CashbackOneAgent.exe" service-run`
- **Установленный исполняемый файл:**
  - Путь: `C:\Program Files (x86)\POSCENTER\LoyaltyAgent\CashbackOneAgent.exe`
  - Версия (`--version`): `poscenter-loyalty-agent 0.2.2`
- **Процесс:**
  - PID: `9160`
  - Имя: `CashbackOneAgent.exe`
  - Время запуска процесса (`CreationDate` via CIM Win32_Process): `05.11.2026 09:58:37` *(запущен службой автоматически через 2 минуты 21 секунду после загрузки ОС)*

---

### 3. Журнал агента (`C:\ProgramData\POSCENTER\LoyaltyAgent\logs\agent.log`)

Размер файла: **915 626 байт**, последнее обновление: **2026-11-05 10:09:02**.

#### Последние 30 строк журнала (персональные данные и чувствительные поля маскированы):
```text
2026-11-04 20:09:01 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.110s
2026-11-04 20:14:02 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1714, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=1.079s
2026-11-04 20:14:03 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.094s
2026-11-04 20:19:04 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1714, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=1.093s
2026-11-04 20:19:04 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.110s
2026-11-04 20:24:05 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1714, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=1.078s
2026-11-04 20:24:05 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.094s
2026-11-04 20:29:06 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1714, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=1.078s
2026-11-04 20:29:06 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.110s
2026-11-04 20:34:07 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1714, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=1.094s
2026-11-04 20:34:07 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.093s
2026-11-04 20:39:09 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1714, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=1.078s
2026-11-04 20:39:09 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.094s
2026-11-04 20:44:10 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1714, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=1.078s
2026-11-04 20:44:10 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.094s
2026-11-04 20:49:11 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1714, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=1.063s
2026-11-04 20:49:11 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.109s
2026-11-04 20:54:12 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1714, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=1.093s
2026-11-04 20:54:12 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.110s
2026-11-05 09:58:39 [INFO] [poscenter_loyalty_agent.windows_service] Starting POSCENTERLoyaltyAgent via Windows Service Manager...
2026-11-05 09:58:39 [INFO] [poscenter_loyalty_agent.one_mapping] Field 'balance_after' is CANDIDATE: enabled via sequential calculation
2026-11-05 09:58:39 [INFO] [poscenter_loyalty_agent.one_mapping] Field 'receipt_ref' is CANDIDATE: enabled for ОтчетКассовойСмены
2026-11-05 09:58:39 [INFO] [poscenter_loyalty_agent.one_mapping] Field 'store' is CANDIDATE: enabled for ОтчетКассовойСмены
2026-11-05 09:58:39 [INFO] [poscenter_loyalty_agent.runtime] Starting POSCENTER Loyalty Agent v0.2.2 (adapter_mode=com, interval=300s)
2026-11-05 09:59:00 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1714, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=19.141s
2026-11-05 09:59:00 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.250s
2026-11-05 10:04:01 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1714, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=1.062s
2026-11-05 10:04:01 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.094s
2026-11-05 10:09:02 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=cards_snapshot, records_read=1714, changes_to_send=0, skipped_invalid_barcode=4 (empty=0, non_digits=2, too_short=2, too_long=0), duration=1.172s
2026-11-05 10:09:02 [INFO] [poscenter_loyalty_agent.one_com_source] ONE read completed: type=transactions_window, records_read=3, changes_to_send=0, skipped_invalid_barcode=0 (empty=0, non_digits=0, too_short=0, too_long=0), duration=0.109s
```

- **Время последнего успешного цикла `ONE read completed`:**
  - `cards_snapshot`: `2026-11-05 10:09:02` (прочитано записей: 1714, изменений для отправки: 0, длительность 1.172s).
  - `transactions_window`: `2026-11-05 10:09:02` (прочитано записей: 3, изменений для отправки: 0, длительность 0.109s).
- **Значения `skipped_invalid_barcode`:**
  - `cards_snapshot`: `skipped_invalid_barcode=4` (`empty=0, non_digits=2, too_short=2, too_long=0`). *(Снизилось с 7 до 4 в соответствии с правилом длины карт 4–13 цифр с агента 0.2.2)*.
  - `transactions_window`: `skipped_invalid_barcode=0`.
- **Ошибки за последние 7 дней (с 2026-10-29 по 2026-11-05):**
  - Строк уровня `[ERROR]`: **0**
  - Строк уровня `[WARNING]`: **221** (все относятся к временным сбоям сетевого разрешения DNS при отправке heartbeat 2026-11-04):
    1. `2026-11-04 12:04:39 [WARNING] [poscenter_loyalty_agent.runtime] Heartbeat failed (will retry next interval): Network error while sending heartbeat: [Errno 11001] getaddrinfo failed`
    2. `2026-11-04 12:05:39 [WARNING] [poscenter_loyalty_agent.runtime] Heartbeat failed (will retry next interval): Network error while sending heartbeat: [Errno 11001] getaddrinfo failed`
    3. `2026-11-04 12:06:51 [WARNING] [poscenter_loyalty_agent.runtime] Heartbeat failed (will retry next interval): Network error while sending heartbeat: [Errno 11001] getaddrinfo failed`

---

### 4. Порты

- Проверка порта `8765` (`Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue`):
  - **Результат:** Ничего не слушает. Порт свободен, активных соединений нет.

---

### 5. Папки

#### 5.1. `C:\cashback-stage0\`

- Подкаталоги:
  - `agent-0.2.0\`
    - `CashbackOneAgent-Setup-0.2.0.exe` (14 848 085 байт) SHA-256: `FE5B799F246250DCCF1D731BA3D0EFDC9B3E3E03FAB7617E70468AFFFC761CE0`
    - `AGENT_EXE_0_2_0_2026-10-23.md` (15 103 байта)
  - `agent-0.2.1\`
    - `CashbackOneAgent-Setup-0.2.1.exe` (14 848 591 байт) SHA-256: `032D12DD4D51D77238784217DB49E06DB4FDAFA83A0A9EF2D55BDDF93833E710`
    - `AGENT_EXE_0_2_1_2026-10-23.md` (17 095 байт)
  - `agent-0.2.2\`
    - `CashbackOneAgent-Setup-0.2.2.exe` (14 848 654 байта) SHA-256: `4AD1126A203D5A4D410657B791DE36B0B5C7A2E0BF3F0EAAB67517509EEDC3A5`
    - `AGENT_EXE_0_2_2_2026-10-24.md` (16 519 байт)
  - `app-stage0-20261027_1133\` (диагностика подключения 1С: скрипты, json-статусы)
  - `backup_20261021_102647\` (`BACKUP_METADATA.txt`, 395 байт)
  - `backup_20261021_102649\` (`BACKUP_METADATA.txt`, 395 байт)
  - `backup_20261021_102652\` (`BACKUP_METADATA.txt`, 395 байт)
  - `backup_20261021_111230\` (настоящий системный бэкап, доступ закрыт DACL SYSTEM/Admin)
  - `backup_admin_20261022_051351\` ... `backup_admin_20261022_061008\` (6 бэкапов index.html админки)
  - `backup_upgrade_0_2_0_20261023_162353\` (отчёт обновления 0.2.0)
  - `backup_upgrade_0_2_1_20261023_175236\` (отчёт обновления 0.2.1)
  - `backup_upgrade_0_2_2_20261024_014315\` (отчёт обновления 0.2.2)
  - `dryrun\` (тестовые SQLite-базы `agent_state_dryrun.db`, `test_disc.db`, `test_shared.db`)
  - `scratch_debug\`
  - `service\` (скрипты `check_service.ps1`, `install_service.ps1`, `uninstall_service.ps1`, лог установки)
  - `task040_deploy_20261021T074115Z\` (`backend_cards_patch.tgz`, `deployment.json`)
  - `windows-test-kit\`
    - `CashbackOneAgent-Setup.exe` (14 795 475 байт) SHA-256: `3B3A45E628EBFFFB2CEA2412FA2C04DE16136E974055319975F3372C94CFD9D1`
    - `check_windows_install.ps1`, `SHA256SUMS.txt`, `TEST_WINDOWS_RU.md`
  - `__pycache__\`
- Файлы в корне `C:\cashback-stage0\`:
  - `CashbackOneAgent-Setup.exe` (14 796 864 байта) SHA-256: `4AA0F72EB8955AA5DB8C3B845C9B45036E96D28218F19FF511EABA4EEA70D56C` (Setup версии 0.1.0)
  - `windows-test-kit.rar` (14 198 332 байта)
  - `cashback.tgz` (107 891 байт)
  - `stage0_mapping.json` (8377 байт)
  - Файлы отчётов и сценариев (`report_19.md` – `report_40_cards_list.md`, скрипты верификации и подготовки)

#### 5.2. `C:\cb-keys`

- **Наличие:** ДА (папка существует)
- **Количество файлов:** 2 файла
- *Примечание:* Содержимое файлов и их имена защищены правилом изоляции секретов и не считывались.

#### 5.3. Все каталоги `C:\cb-*`

1. `C:\cb-build` — 1 элемент (`tools\innosetup\ISCC.exe` и сопутствующие файлы Inno Setup)
2. `C:\cb-dl` — 3 элемента
3. `C:\cb-keys` — защищённая папка с ключами (2 файла)
4. `C:\cb-old` — 1 элемент
5. `C:\cb-out` — 8 элементов
6. `C:\cb-pos-smoke` — 5 элементов
7. `C:\cb-pos-smoke-021` — 3 элемента
8. `C:\cb-pos-smoke-022` — 3 элемента

#### 5.4. `%ProgramData%\POSCENTER\LoyaltyAgent\`

- Каталоги:
  - `\config`
  - `\logs`
  - `\mapping`
  - `\state`
- Файлы (только метаданные):
  - `\config\.env.service` (325 байт, дата изменения: `21.10.2026 11:12:31`)
  - `\logs\agent.log` (915 626 байт, дата изменения: `05.11.2026 10:09:02`)
  - `\mapping\stage0_mapping.json` (8 377 байт, дата изменения: `19.10.2026 12:45:19`)
  - `\state\` — доступ закрыт дескриптором безопасности DACL (SYSTEM / Administrators only; отказ доступа неповышенной консоли ожидаем по регламенту).

---

### 6. 1С

- **База данных `C:\1C_data\int`:**
  - **Наличие:** ДА
  - **Общий размер каталога:** 1 298 976 385 байт (~1 238,8 МБ)
  - **Дата изменения:** `05.11.2026 09:58:58` *(база не открывалась)*
- **Установленные версии платформы 1С:**
  - В `C:\Program Files\1cv8`:
    - `bin` (x64 runtime)
  - В `C:\Program Files (x86)\1cv8`:
    - `8.3.16.1148`
    - `8.3.19.1467`
    - `8.3.8.1652`
    - `common`
    - `conf`
- **COM-коннектор (`V83.COMConnector`):**
  - **Зарегистрирован:** ДА
  - **ProgID:** `1CV83 COM Connector Class`
  - **CLSID:** `{181E893D-73A4-4722-B61D-D604B3D67D47}`
  - **InprocServer32 (WOW6432Node):** `C:\Program Files (x86)\1cv8\8.3.19.1467\bin\comcntr.dll` (ThreadingModel: Both)

---

### 7. Репозиторий `C:\Users\ШОУРУМ\Desktop\cashback-one`

- **Последние 3 коммита (`git log --oneline -3`):**
  - `4774d79 docs: clarify pull in Windows inventory prompt`
  - `3b6e43e docs: read-only Windows inventory prompt`
  - `5bbc7df docs: prompts and reports for push, server content, APK 1.0.12, per-client apps, agent 0.3.0 build`
- **Текущий хеш коммита (`git rev-parse HEAD`):**
  `4774d79de1dc8d7ae851c78729cfc7fa4ec6b5fc`
- **Статус рабочей копии (`git status --short`):**
  - `?? reports/APP_STAGE0_ONE_PROFILE_2026-10-27.md` *(неотслеживаемый файл отчёта)*
- **Синхронизация с `origin/main`:**
  - Ветка `main` синхронизирована: `Your branch is up to date with 'origin/main'`. (Отставания нет).

---

### 8. Python и инструменты сборки

- **Системный Python в PATH:**
  - `C:\Users\ШОУРУМ\AppData\Local\Microsoft\WindowsApps\python.exe` (Windows Store stub)
- **Установленные версии через Python Launcher (`py -0p`):**
  - `Python 3.11 (64-bit)`: `C:\Users\ШОУРУМ\AppData\Local\Programs\Python\Python311\python.exe`
  - `Python 3.11-32 (32-bit)`: `C:\Users\ШОУРУМ\AppData\Local\Programs\Python\Python311-32\python.exe`
- **Виртуальные окружения:**
  - `C:\cashback-venv\Scripts\python.exe` — Python 3.11.9 (32-bit) *(основное окружение агента)*
  - `C:\cashback-build-venv\Scripts\python.exe` — Python 3.11.9 (32-bit) *(окружение сборки PyInstaller)*
  - `C:\cashback-backend-venv\Scripts\python.exe` — Python 3.11.3 (64-bit) *(локальное backend-окружение)*
- **Inno Setup:**
  - **Наличие:** ДА
  - **Путь:** `C:\cb-build\tools\innosetup\ISCC.exe`
  - **Версия:** Inno Setup 6 Command-Line Compiler (Jordan Russell / Martijn Laan)

---

### 9. Касса (POSCENTER Cash)

- **Статус:** **НЕ УСТАНОВЛЕН**.
- **Проверки:**
  - Ярлыки кассы на Рабочем столе и в Главном меню: отсутствуют.
  - Папки `C:\Program Files\POSCENTER`, `C:\Program Files\Cash`, `C:\POSCENTER`, `C:\Cash`: отсутствуют.
  - В `C:\Program Files (x86)\POSCENTER` содержится **только** `LoyaltyAgent`.
  - В реестре установленных программ (Uninstall) запись POSCENTER Cash отсутствует.
- **Что установлено из кассового ПО:**
  - На компьютере установлена кассовая программа «Штрих-М Кассир» (ярлыки в меню программ) и драйверы торгового оборудования («Драйвер устройств ввода», «Тест драйвера», «XPrinter Driver V7.77»).

---

## Итог: установленные компоненты и их работоспособность

| Компонент | Расположение | Версия | Статус / Работоспособность | Примечание |
|---|---|---|---|---|
| **Операционная система** | `KONS2` | Windows 10 Pro 1909 (18363) x64 | Работает стабильно | Свободно 18,51 GB на диске C: |
| **Служба агента** | `C:\Program Files (x86)\POSCENTER\LoyaltyAgent\CashbackOneAgent.exe` | 0.2.2 | **Running** (PID 9160) | Автозапуск (Delayed), запущен 05.11.2026 09:58:37 |
| **Синхронизация с ONE** | `C:\ProgramData\POSCENTER\LoyaltyAgent\logs\agent.log` | — | **Работает стабильно** | Циклы каждые 5 мин без ошибок. Последний: 05.11 10:09:02 (1714 карт, skipped=4) |
| **Локальная база ONE** | `C:\1C_data\int` | POSCENTERONE 2.0.0.26.9 | Доступна (1,24 GB) | Читается агентом через COM без блокировок |
| **Платформа 1С** | `C:\Program Files (x86)\1cv8\8.3.19.1467` | 8.3.19.1467 x86 | Установлена | COM-коннектор зарегистрирован (`comcntr.dll`) |
| **Python venv (Agent)** | `C:\cashback-venv` | Python 3.11.9 (32-bit) | Готов к работе | Использовался для тестов и запуска |
| **Python venv (Build)** | `C:\cashback-build-venv` | Python 3.11.9 (32-bit) | Готов к работе | Содержит PyInstaller и зависимости сборки |
| **Python venv (Backend)**| `C:\cashback-backend-venv` | Python 3.11.3 (64-bit) | Готов к работе | Локальное окружение backend |
| **Inno Setup** | `C:\cb-build\tools\innosetup\ISCC.exe` | Inno Setup 6 | Готов к сборке | Локальный компилятор инсталляторов |
| **Репозиторий Git** | `C:\Users\ШОУРУМ\Desktop\cashback-one` | коммит `4774d79` | Синхронизирован | Ветка main, совпадает с origin/main |
| **Касса POSCENTER Cash**| — | — | **Не установлена** | На машине только «Штрих-М Кассир» |
| **Порт 8765** | — | — | Не слушает | Локальный POS API сервер выключен/не запущен |

---

## Что лишнее (старые проверочные папки и временные данные)

> [!NOTE]
> В соответствии с инструкцией, никакие файлы и каталоги **не удалялись**. Ниже приведён список кандидатов на очистку для оценки владельцем.

| Каталог / Файл | Размер / Состав | Назначение / История | Рекомендация |
|---|---|---|---|
| `C:\cashback-stage0\windows-test-kit` | ~45 MB | Комплект ручного тестирования 0.1.0 с устаревшим Setup (`3B3A45E6...`) | *Удалять — решение владельца* |
| `C:\cashback-stage0\windows-test-kit.rar` | 14,2 MB | Архив старого комплекта ручного тестирования | *Удалять — решение владельца* |
| `C:\cashback-stage0\CashbackOneAgent-Setup.exe` | 14,8 MB | Старый Setup версии 0.1.0 (`4AA0F72E...`) | *Удалять — решение владельца* |
| `C:\cashback-stage0\agent-0.2.0` | 14,9 MB | Setup 0.2.0 (неактуален, текущий 0.2.2, откат на 0.2.1) | *Удалять — решение владельца* |
| `C:\cashback-stage0\backup_20261021_102647` .. `102652` | < 2 KB | 3 пустых mock-бэкапа от инцидента отладки №35 | *Удалять — решение владельца* |
| `C:\cashback-stage0\backup_admin_*` | < 10 KB | 6 резервных копий index.html админки от 22.10.2026 | *Удалять — решение владельца* |
| `C:\cashback-stage0\dryrun` | ~8,8 MB | SQLite-файлы тестовых прогонов первой загрузки | *Удалять — решение владельца* |
| `C:\cashback-stage0\scratch_debug` | пустая | Временная папка отладки | *Удалять — решение владельца* |
| `C:\cb-pos-smoke` | 5 файлов | Временная папка smoke-теста Setup 0.2.0 | *Удалять — решение владельца* |
| `C:\cb-pos-smoke-021` | 3 файла | Временная папка smoke-теста Setup 0.2.1 | *Удалять — решение владельца* |
| `C:\cb-pos-smoke-022` | 3 файла | Временная папка smoke-теста Setup 0.2.2 | *Удалять — решение владельца* |
| `C:\cb-old` | 1 элемент | Старая папка от 19.10.2026 | *Удалять — решение владельца* |
| `C:\cb-dl` | 3 элемента | Загруженные файлы от 21.10.2026 | *Удалять — решение владельца* |
| `C:\cb-out` | 8 элементов | Выходные артефакты от 22.10.2026 | *Удалять — решение владельца* |
| `C:\cb-keys` | 2 файла | Папка с ключами. Содержит секреты. Не удалять без ведома владельца! | **Не удалять без прямой команды и резервной копии** |
