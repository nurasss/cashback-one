# Keremet: включение передачи оборота — 2026-11-13

## Основание и пределы

Владелец после объяснения выключенной настройки явно поручил: «Давай. Делаем».
Это разрешение на включение передачи оборота установленным агентом и штатный перезапуск службы на боевом компьютере Keremet. Это не подтверждение полноты истории покупок, возвратов, серверного личного статуса или начислений на кассе.

По присланным снимкам параметр AGENT_LIFETIME_TURNOVER_ENABLED не найден в .env.service, системном окружении и значении Environment службы. В коде агента значение по умолчанию False. Механизм передачи проверялся на тестовой базе, не на боевой истории Keremet.

У куратора нет прямого доступа к этому компьютеру. Блок ниже подготовлен для человека, который присылал снимки PowerShell; куратор его на Windows не выполнял. Не запускать на KONS2 вместо Keremet.

## Выполнение

В административном Windows PowerShell на компьютере Keremet вставить весь блок один раз и нажать Enter.
Это уже изменение настройки и перезапуск службы, не диагностическая команда.

Блок проверяет хеш принятого EXE 0.5.0, исходное состояние службы и отсутствие параметра; создаёт уникальную копию конфига в той же защищённой папке и применяет к копии ACL исходного файла, не меняя ACL оригинала. Копия сверяется по хешу. Затем к исходному UTF-8 файлу дописывается только новый параметр без перезаписи существующих байтов, проверяется его наличие и выполняется штатный Restart-Service без Force и без завершения процессов.

Упало или неожиданно — СТОП и обезличенный сырой вывод. Не повторять блок после ошибки, не выполнять автоматический откат и не править остальные настройки. Если ошибка случилась после добавления параметра, он может уже находиться в файле; дальнейшие действия согласовать отдельно. Копию конфига и его содержимое в чат не отправлять.

~~~powershell
& {
    $ErrorActionPreference = 'Stop'
    $serviceName = 'POSCENTERLoyaltyAgent'
    $configPath = 'C:\ProgramData\POSCENTER\LoyaltyAgent\config\.env.service'
    $exePath = 'C:\Program Files (x86)\POSCENTER\LoyaltyAgent\CashbackOneAgent.exe'
    $expectedHash = '0CAEB24E0AB1507C80F1B56C88A8D12D35D9882886592AD799B6ABFC1E2F0073'
    if ((Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash -ne $expectedHash) { throw 'STOP: unexpected agent EXE' }
    if ((Get-Service -Name $serviceName).Status -ne 'Running') { throw 'STOP: service is not running' }
    if (Select-String -LiteralPath $configPath -SimpleMatch -Pattern 'AGENT_LIFETIME_TURNOVER_ENABLED' -Quiet) { throw 'STOP: setting already exists; do not repeat' }
    $backupPath = $configPath + '.bak-' + [guid]::NewGuid().ToString('N')
    $originalAcl = Get-Acl -LiteralPath $configPath
    [IO.File]::Copy($configPath, $backupPath, $false)
    Set-Acl -LiteralPath $backupPath -AclObject $originalAcl
    if ((Get-FileHash -LiteralPath $configPath).Hash -ne (Get-FileHash -LiteralPath $backupPath).Hash) { throw 'STOP: backup mismatch' }
    Write-Output ('Backup: ' + $backupPath)
    [IO.File]::AppendAllText($configPath, [Environment]::NewLine + 'AGENT_LIFETIME_TURNOVER_ENABLED=true' + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    if (-not (Select-String -LiteralPath $configPath -Pattern '^\s*AGENT_LIFETIME_TURNOVER_ENABLED=true\s*$' -Quiet)) { throw 'STOP: setting verification failed' }
    Restart-Service -Name $serviceName
    (Get-Service -Name $serviceName).WaitForStatus('Running', [TimeSpan]::FromSeconds(60))
    Get-Service -Name $serviceName | Select-Object Name, Status
}
~~~

## Что не менять

SQLite, WAL/SHM, HMAC-ключ, API-ключ, строку подключения, маппинг, конфигурацию и данные 1С, серверный флаг расчёта статуса, мобильные манифесты и APK не менять. Не запускать второй экземпляр агента, sync_now, full_resync или сброс состояния.

## После выполнения

Прислать только последние строки результата с именем и статусом службы или обезличенную ошибку. Рабочий статус Running подтверждает запуск, но не получение правильного оборота.
После подтверждённого выполнения куратор проверяет обычный штатный цикл через сервер READ ONLY: heartbeat, наличие ошибки, количество карт с непустым spend_total, распределение положительных/нулевых значений и свежесть данных. Ни нулевые, ни положительные значения сами по себе не доказывают полноту реальной истории. При ошибке или сомнительных результатах — СТОП, без самостоятельных сбросов и повторных изменений.
