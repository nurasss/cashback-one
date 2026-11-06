# Cashback One: обновление агента KeremEt до 0.4.0 (синхронизация раз в минуту).
# Ничего не удаляет: перед обновлением вся папка агента копируется в C:\cashback-stage0\backup_upgrade_0_4_0_<время>.
# Ключ агента, пароль 1С, mapping и файлы состояния сохраняются. База 1С не открывается.
$ErrorActionPreference = 'Stop'
$service = 'POSCENTERLoyaltyAgent'
$dataDir = 'C:\ProgramData\POSCENTER\LoyaltyAgent'
$logFile = Join-Path $dataDir 'logs\agent.log'
$setup = Join-Path $PSScriptRoot 'CashbackOneAgent-Setup-0.4.0.exe'
$setupSha = '98CFB4004870AB2D29C45F1872FAD868077DBFBD1A68BED1D67354A791594CF1'

function Finish($code) {
    Write-Host ''
    Read-Host 'Нажмите Enter, чтобы закрыть окно'
    exit $code
}

function Read-NewLog($offset) {
    if (-not (Test-Path $logFile)) { return @() }
    $fs = [System.IO.File]::Open($logFile, 'Open', 'Read', 'ReadWrite')
    try {
        if ($fs.Length -lt $offset) { $offset = 0 }
        [void]$fs.Seek($offset, 'Begin')
        $sr = New-Object System.IO.StreamReader($fs)
        return @($sr.ReadToEnd() -split "`r?`n" | Where-Object { $_ })
    } finally { $fs.Close() }
}

try {
    Write-Host '=== Cashback One: обновление агента KeremEt до 0.4.0 ===' -ForegroundColor Cyan
    Write-Host ''
    if ($env:COMPUTERNAME -eq 'KONS2') { Write-Host 'Это компьютер KONS2. Здесь запускать нельзя.' -ForegroundColor Red; Finish 1 }
    $svc = Get-Service $service -ErrorAction SilentlyContinue
    if (-not $svc) { Write-Host 'Агент не установлен на этом компьютере.' -ForegroundColor Red; Finish 1 }
    if (-not (Test-Path (Join-Path $dataDir 'config\.env.service'))) { Write-Host 'Нет настроек агента. Обновлять нельзя.' -ForegroundColor Red; Finish 1 }
    if (-not (Test-Path $setup)) { Write-Host "Нет файла установщика рядом: $setup" -ForegroundColor Red; Finish 1 }
    $hash = (Get-FileHash $setup -Algorithm SHA256).Hash
    if ($hash -ne $setupSha) { Write-Host 'Файл установщика повреждён (контрольная сумма не совпала). Ничего не меняю.' -ForegroundColor Red; Finish 1 }

    Write-Host "Компьютер: $env:COMPUTERNAME"
    Write-Host 'Установщик проверен.'
    Write-Host ''
    Read-Host 'Нажмите Enter, чтобы продолжить (или закройте окно, чтобы отменить)'

    $ts = Get-Date -Format 'yyyyMMdd_HHmmss'
    $backup = "C:\cashback-stage0\backup_upgrade_0_4_0_$ts"
    Write-Host "1/3 Делаю копию папки агента в $backup ..."
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    & robocopy $dataDir $backup /E /COPYALL /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Копия не сделана (robocopy код $LASTEXITCODE). Ничего не меняю." }
    $srcCount = @(Get-ChildItem $dataDir -Recurse -File).Count
    $dstCount = @(Get-ChildItem $backup -Recurse -File).Count
    if ($dstCount -lt $srcCount) { throw "В копии $dstCount файлов из $srcCount. Ничего не меняю." }
    Write-Host "    Скопировано файлов: $dstCount"

    $offset = 0
    if (Test-Path $logFile) { $offset = (Get-Item $logFile).Length }

    Write-Host ''
    Write-Host '2/3 Сейчас откроется установщик. В нём:' -ForegroundColor Yellow
    Write-Host '    - пункт «Сохранить существующие настройки» уже выбран — НЕ менять;'
    Write-Host '    - поля нового ключа и нового пароля оставить ПУСТЫМИ;'
    Write-Host '    - можно нажать «Проверить подключение» (должно быть успешно);'
    Write-Host '    - дальше просто «Далее» / «Установить» / «Завершить».'
    Write-Host '    Если установщик показал ошибку — нажмите «Отмена» и сфотографируйте экран.'
    Write-Host ''
    $p = Start-Process -FilePath $setup -Wait -PassThru
    Write-Host "    Установщик закрыт (код $($p.ExitCode))."
    if ($p.ExitCode -ne 0) { throw "Установка не завершена (код $($p.ExitCode)). Копия: $backup" }

    Write-Host '3/3 Проверяю агента (до 4 минут)...'
    $svc = Get-Service $service
    if ($svc.Status -ne 'Running') { Start-Service $service; (Get-Service $service).WaitForStatus('Running', '00:02:00') }
    $deadline = (Get-Date).AddMinutes(4)
    $started = $false; $cycles = 0; $lines = @()
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 15
        $lines = Read-NewLog $offset
        $started = [bool]($lines | Where-Object { $_ -match 'Starting POSCENTER Loyalty Agent v0\.4\.0 .*interval=60s' })
        $cycles = @($lines | Where-Object { $_ -match 'ONE read completed: type=cards_snapshot' }).Count
        if ($started -and $cycles -ge 2) { break }
    }
    $errors = @($lines | Where-Object { $_ -match '\[(ERROR|CRITICAL)\]|Traceback' })

    Write-Host ''
    Write-Host 'Последние строки журнала агента (их можно переслать):' -ForegroundColor Cyan
    $lines | Where-Object { $_ -match 'Starting POSCENTER|ONE read completed|ACK received|\[ERROR\]|\[CRITICAL\]' } | Select-Object -Last 10 | ForEach-Object { $_ }
    Write-Host ''
    if ($started -and $cycles -ge 2 -and $errors.Count -eq 0) {
        Write-Host 'ГОТОВО. Агент 0.4.0 работает, синхронизация раз в минуту.' -ForegroundColor Green
    } else {
        Write-Host "Проверка не завершена: версия 0.4.0 в журнале: $started, циклов: $cycles, ошибок: $($errors.Count)." -ForegroundColor Yellow
        Write-Host 'Сфотографируйте это окно и пришлите.' -ForegroundColor Yellow
    }
    Write-Host "Копия прежней папки агента: $backup"
    Finish 0
}
catch {
    Write-Host ''
    Write-Host "ОШИБКА: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Сфотографируйте это окно и пришлите.'
    Finish 1
}
