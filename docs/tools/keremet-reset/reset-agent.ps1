# Cashback One: перезапуск агента KeremEt с чистым состоянием.
# Ничего не удаляет: файлы состояния переносятся в копию C:\cashback-stage0\state_keremet_before_reset_<время>.
# Ключ агента, пароль 1С и mapping не меняются; интервал синхронизации ставится 1 минута (копия настроек — в папке копии). База 1С не открывается.
$ErrorActionPreference = 'Stop'
$service = 'POSCENTERLoyaltyAgent'
$dataDir = 'C:\ProgramData\POSCENTER\LoyaltyAgent'
$stateDir = Join-Path $dataDir 'state'
$logFile = Join-Path $dataDir 'logs\agent.log'

function Finish($code) {
    Write-Host ''
    Read-Host 'Нажмите Enter, чтобы закрыть окно'
    exit $code
}

try {
    Write-Host '=== Cashback One: перезапуск агента KeremEt ===' -ForegroundColor Cyan
    Write-Host ''
    if ($env:COMPUTERNAME -eq 'KONS2') {
        Write-Host 'Это компьютер KONS2. Здесь запускать нельзя.' -ForegroundColor Red
        Finish 1
    }
    $svc = Get-Service $service -ErrorAction SilentlyContinue
    if (-not $svc) { Write-Host 'Агент не установлен на этом компьютере.' -ForegroundColor Red; Finish 1 }
    if (-not (Test-Path $stateDir)) { Write-Host "Нет папки $stateDir" -ForegroundColor Red; Finish 1 }
    $files = @(Get-ChildItem $stateDir -File)
    if ($files.Count -eq 0) { Write-Host 'Папка состояния уже пустая. Ничего делать не нужно.' -ForegroundColor Yellow; Finish 0 }

    Write-Host "Компьютер: $env:COMPUTERNAME"
    Write-Host "Будут перенесены в копию файлы: $($files.Name -join ', ')"
    Write-Host ''
    Read-Host 'Нажмите Enter, чтобы продолжить (или закройте окно, чтобы отменить)'

    Write-Host '1/4 Останавливаю агента...'
    if ($svc.Status -ne 'Stopped') { Stop-Service $service; (Get-Service $service).WaitForStatus('Stopped', '00:01:00') }

    $ts = Get-Date -Format 'yyyyMMdd_HHmmss'
    $backup = "C:\cashback-stage0\state_keremet_before_reset_$ts"
    Write-Host "2/4 Переношу файлы состояния в $backup ..."
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    foreach ($f in $files) { Move-Item $f.FullName $backup }
    $left = @(Get-ChildItem $stateDir -File)
    if ($left.Count -ne 0) { throw "В папке состояния остались файлы: $($left.Name -join ', ')" }

    $envFile = Join-Path $dataDir 'config\.env.service'
    if (Test-Path $envFile) {
        Copy-Item $envFile (Join-Path $backup 'env.service.bak') -Force
        $lines = Get-Content $envFile
        if ($lines -match '^AGENT_POLL_INTERVAL_SECONDS=') {
            $lines = $lines -replace '^AGENT_POLL_INTERVAL_SECONDS=.*$', "AGENT_POLL_INTERVAL_SECONDS='60'"
        } else {
            $lines += "AGENT_POLL_INTERVAL_SECONDS='60'"
        }
        Set-Content -Path $envFile -Value $lines -Encoding ASCII
        Write-Host '    Интервал синхронизации: 1 минута.'
    }

    Write-Host '3/4 Запускаю агента...'
    Start-Service $service
    (Get-Service $service).WaitForStatus('Running', '00:02:00')

    Write-Host '4/4 Жду первую отправку (до 3 минут)...'
    $since = Get-Date
    $deadline = $since.AddMinutes(3)
    $ok = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 15
        if (Test-Path $logFile) {
            $hit = Select-String -Path $logFile -Pattern 'ACK received' | Select-Object -Last 1
            if ($hit -and ((Get-Item $logFile).LastWriteTime -gt $since)) { $ok = $true; break }
        }
    }
    Write-Host ''
    Write-Host 'Последние строки журнала агента (их можно переслать):' -ForegroundColor Cyan
    if (Test-Path $logFile) {
        Select-String -Path $logFile -Pattern 'ONE read completed|ACK received|ERROR' | Select-Object -Last 8 | ForEach-Object { $_.Line }
    }
    Write-Host ''
    if ($ok) { Write-Host 'ГОТОВО. Агент работает и начал отправлять данные.' -ForegroundColor Green }
    else { Write-Host 'Агент запущен. Отправка ещё не видна — сфотографируйте это окно и пришлите.' -ForegroundColor Yellow }
    Write-Host "Копия прежнего состояния: $backup"
    Finish 0
}
catch {
    Write-Host ''
    Write-Host "ОШИБКА: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Сфотографируйте это окно и пришлите. Агента можно запустить вручную: Start-Service POSCENTERLoyaltyAgent'
    Finish 1
}
