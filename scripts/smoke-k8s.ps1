# Script kiem tra hoat dong cua Frontend tren Kubernetes
[CmdletBinding()]
param(
    [string]$Namespace = "default",
    [int]$LocalPort = 8080,
    [string]$ImagePath = "",
    [string]$FrontendService = "ai-recognition-frontend"
)

$ErrorActionPreference = "Stop"

Write-Host "=== KIEM TRA FRONTEND TREN KUBERNETES ===" -ForegroundColor Cyan
Write-Host "Namespace: $Namespace"
Write-Host "Frontend Service: $FrontendService"

# 1. Kiem tra Pods Frontend
Write-Host "`n1. Kiem tra trang thai Pods..." -ForegroundColor Yellow
$pods = kubectl get pods -n $Namespace -l app.kubernetes.io/name=ai-recognition-frontend -o json | ConvertFrom-Json
if (-not $pods.items -or $pods.items.Count -eq 0) {
    Write-Error "Khong tim thay Pod Frontend nao trong namespace '$Namespace'!"
}

$readyPods = $pods.items | Where-Object {
    $containerReady = $_.status.containerStatuses | Where-Object { $_.ready -eq $true }
    $containerReady.Count -gt 0
}

Write-Host "So luong Pod san sang: $($readyPods.Count)/$($pods.items.Count)" -ForegroundColor Green

# 2. Khoi dong port-forward tam thoi neu can
$baseUrl = "http://127.0.0.1:$LocalPort"
Write-Host "`n2. Kiem tra ket noi qua port $LocalPort..." -ForegroundColor Yellow

$portForwardProcess = $null
try {
    # Thu ket noi san co
    $null = Invoke-WebRequest -Uri "$baseUrl/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
    Write-Host "Port $LocalPort da duoc mo san, su dung $baseUrl de kiem tra." -ForegroundColor Green
} catch {
    Write-Host "Dang mo port-forward kubectl port-forward svc/$FrontendService ${LocalPort}:8080 -n $Namespace..." -ForegroundColor Cyan
    $portForwardProcess = Start-Process -FilePath "kubectl" -ArgumentList "port-forward", "svc/$FrontendService", "${LocalPort}:8080", "-n", $Namespace -PassThru -NoNewWindow
    Start-Sleep -Seconds 3
}

try {
    # 3. Kiem tra endpoint /health
    Write-Host "`n3. Kiem tra healthcheck /health..." -ForegroundColor Yellow
    $healthResp = Invoke-WebRequest -Uri "$baseUrl/health" -UseBasicParsing
    if ($healthResp.StatusCode -eq 200) {
        Write-Host "Healthcheck OK: $($healthResp.Content.Trim())" -ForegroundColor Green
    } else {
        Write-Error "Healthcheck that bai voi ma: $($healthResp.StatusCode)"
    }

    # 4. Kiem tra giao dien SPA (GET /)
    Write-Host "`n4. Kiem tra phuc vu giao dien SPA (GET /)..." -ForegroundColor Yellow
    $indexResp = Invoke-WebRequest -Uri "$baseUrl/" -UseBasicParsing
    if ($indexResp.StatusCode -eq 200 -and $indexResp.Content -match "<div id=`"root`">") {
        Write-Host "SPA HTML duoc tra ve chinh xac." -ForegroundColor Green
    } else {
        Write-Error "Khong nhan duoc HTML SPA hop le tu Nginx."
    }

    # 5. Kiem tra luong upload anh va goi Backend qua proxy /jobs
    Write-Host "`n5. Kiem tra luong upload anh qua reverse-proxy /jobs..." -ForegroundColor Yellow
    $tempFileCreated = $false
    if (-not $ImagePath -or -not (Test-Path $ImagePath)) {
        $ImagePath = Join-Path $env:TEMP "k8s_smoke_test_image.png"
        # Tao file PNG 1x1 hop le
        $pngBytes = [byte[]]@(
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
            0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,
            0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
            0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
            0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,
            0x42, 0x60, 0x82
        )
        [System.IO.File]::WriteAllBytes($ImagePath, $pngBytes)
        $tempFileCreated = $true
        Write-Host "Da tao anh mau PNG: $ImagePath" -ForegroundColor Cyan
    }

    Write-Host "Gui yeu cau POST /jobs toi $baseUrl..."
    $postOutput = curl.exe --silent --show-error --fail-with-body -F "file=@$ImagePath;type=image/png" "$baseUrl/jobs"
    if (-not $postOutput) {
        Write-Error "POST /jobs khong tra ve du lieu."
    }
    $job = $postOutput | ConvertFrom-Json
    Write-Host "Tao job thanh cong: job_id=$($job.job_id), status=$($job.status)" -ForegroundColor Green

    # Poll ket qua
    $statusUrl = "$baseUrl$($job.status_url)"
    Write-Host "Dang polling ket qua tai $statusUrl..." -ForegroundColor Yellow
    $maxAttempts = 30
    $completed = $false

    for ($i = 0; $i -lt $maxAttempts; $i++) {
        Start-Sleep -Seconds 1
        $statusJson = curl.exe --silent --show-error "$statusUrl" | ConvertFrom-Json
        Write-Host "  Lan $i: Trang thai job = $($statusJson.status)" -ForegroundColor Gray
        if ($statusJson.status -eq "completed") {
            Write-Host "Job hoan thanh thanh cong!" -ForegroundColor Green
            Write-Host "Ket qua nhan dien:" -ForegroundColor Cyan
            $statusJson.predictions | ForEach-Object {
                Write-Host "  - $($_.label): $([math]::Round($_.confidence * 100, 2))%" -ForegroundColor White
            }
            if ($statusJson.model_version) {
                Write-Host "Model version: $($statusJson.model_version)" -ForegroundColor Gray
            }
            $completed = $true
            break
        } elseif ($statusJson.status -eq "failed") {
            Write-Error "Job that bai: $($statusJson.error.message)"
        }
    }

    if (-not $completed) {
        Write-Error "Het thoi gian cho job hoan thanh sau $maxAttempts giay."
    }

    Write-Host "`n=== KIEM TRA TOAN BO LUONG THANH CONG! ===" -ForegroundColor Green

    if ($tempFileCreated -and (Test-Path $ImagePath)) {
        Remove-Item $ImagePath -Force -ErrorAction SilentlyContinue
    }
} finally {
    if ($portForwardProcess -and -not $portForwardProcess.HasExited) {
        Stop-Process -Id $portForwardProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Da dong tien trinh port-forward." -ForegroundColor Gray
    }
}
