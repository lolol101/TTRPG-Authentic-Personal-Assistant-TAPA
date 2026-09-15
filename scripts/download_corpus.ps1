<#
.SYNOPSIS
    Докачивает корпус правил pf2.ru — с паузами и повторами.

.DESCRIPTION
    pf2.ru блокирует краулер по частоте запросов, и блокировка приходит и
    уходит сама: то sitemap отдаёт 403, то снова 200. Одиночный запуск
    падает на первом же отказе и теряет несколько часов.

    Скрипт ждёт и повторяет. Пауза между попытками намеренно большая:
    частые повторы — это ровно то, из-за чего блокировка и наступает.

    Уже скачанные страницы лежат в HTML-кэше, поэтому повтор не качает их
    заново — он продолжает с того места, где остановился.

.PARAMETER Sections
    Какие разделы качать. По умолчанию — те, что ещё не добраны.

.PARAMETER Attempts
    Сколько раз пробовать. По умолчанию 10.

.PARAMETER PauseMinutes
    Пауза между попытками в минутах. По умолчанию 20.

.EXAMPLE
    .\scripts\download_corpus.ps1

.EXAMPLE
    .\scripts\download_corpus.ps1 -Sections feats -Attempts 3
#>

[CmdletBinding()]
param(
    [string[]] $Sections = @('spells', 'equipment', 'feats'),
    [int] $Attempts = 10,
    [int] $PauseMinutes = 20
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

$packageDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'packages\pf2e-data'
if (-not (Test-Path $packageDir)) {
    throw "Не нашёл $packageDir — запускай из репозитория TAPA."
}

# Тот же User-Agent, что и у краулера: проверять доступность под другим
# именем бессмысленно — блокируют именно его.
$UserAgent = 'TAPA-pf2e-data/0.1 (research assistant; contact via github.com/lolol101)'

function Test-SiteReachable {
    # Именно GET: на HEAD pf2.ru отвечает 405, и проверка приняла бы это
    # за блокировку, простояв впустую несколько часов.
    try {
        $r = Invoke-WebRequest -Uri 'https://pf2.ru/sitemap.xml' -Method Get `
            -Headers @{ 'User-Agent' = $UserAgent } -UseBasicParsing -TimeoutSec 30
        return $r.StatusCode -eq 200
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        if ($code -eq 403) { return $false }
        # Что-то другое — сеть, таймаут. Пусть решает сам краулер.
        Write-Host "  (проверка вернула $code, пробую всё равно)" -ForegroundColor DarkGray
        return $true
    }
}

Write-Host ''
Write-Host "Разделы: $($Sections -join ', ')" -ForegroundColor Cyan
Write-Host "Попыток: $Attempts, пауза между ними: $PauseMinutes мин" -ForegroundColor Cyan
Write-Host ''

for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
    Write-Host "=== Попытка $attempt из $Attempts — $(Get-Date -Format 'HH:mm:ss') ===" -ForegroundColor Yellow

    if (-not (Test-SiteReachable)) {
        Write-Host 'pf2.ru сейчас блокирует (403). Жду, не долблю.' -ForegroundColor DarkYellow
    } else {
        Push-Location $packageDir
        try {
            # Вывод идёт прямо в терминал: прогресс-бар перерисовывается
            # на месте, в файл он лёг бы нечитаемой кашей.
            & uv run python -m app.corpus --only @Sections
            $code = $LASTEXITCODE
        } finally {
            Pop-Location
        }

        if ($code -eq 0) {
            Write-Host ''
            Write-Host 'Готово: все разделы скачаны.' -ForegroundColor Green
            exit 0
        }

        Write-Host ''
        Write-Host "Прогон закончился с кодом $code — часть разделов не далась." -ForegroundColor DarkYellow
    }

    if ($attempt -lt $Attempts) {
        $until = (Get-Date).AddMinutes($PauseMinutes).ToString('HH:mm:ss')
        Write-Host "Следующая попытка в $until. Прервать — Ctrl+C." -ForegroundColor DarkGray
        Start-Sleep -Seconds ($PauseMinutes * 60)
    }
}

Write-Host ''
Write-Host "Попытки кончились. Скачанное никуда не делось — запусти скрипт снова позже." -ForegroundColor Red
exit 1
