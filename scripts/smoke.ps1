param(
    [string]$ApiUrl = 'http://127.0.0.1:8000',
    [string]$WorkerUrl = 'http://127.0.0.1:8001',
    [string]$ImagePath = ''
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Net.Http
$ApiUrl = $ApiUrl.TrimEnd('/')
$WorkerUrl = $WorkerUrl.TrimEnd('/')
$generatedImage = $null
$httpClient = $null
$multipart = $null
$uploadResponse = $null
try {
    foreach ($serviceUrl in @($ApiUrl, $WorkerUrl)) {
        $health = Invoke-WebRequest "$serviceUrl/health" -UseBasicParsing
        if ($health.StatusCode -ne 200 -or ($health.Content | ConvertFrom-Json).status -ne 'ok') {
            throw "Health check failed: $serviceUrl"
        }
        $ready = Invoke-WebRequest "$serviceUrl/ready" -UseBasicParsing
        if ($ready.StatusCode -ne 200) { throw "Service not ready: $serviceUrl" }
    }

    if (-not $ImagePath) {
        Add-Type -AssemblyName System.Drawing
        $generatedImage = Join-Path $env:TEMP ("recognition-smoke-" + [guid]::NewGuid().ToString() + ".png")
        $bitmap = [System.Drawing.Bitmap]::new(320, 240)
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            try { $graphics.Clear([System.Drawing.Color]::Orange) }
            finally { $graphics.Dispose() }
            $bitmap.Save($generatedImage, [System.Drawing.Imaging.ImageFormat]::Png)
        } finally { $bitmap.Dispose() }
        $ImagePath = $generatedImage
    }
    $resolvedImage = (Resolve-Path -LiteralPath $ImagePath).Path
    $extension = [System.IO.Path]::GetExtension($resolvedImage).ToLowerInvariant()
    $mime = switch ($extension) {
        '.png' { 'image/png' }
        '.jpg' { 'image/jpeg' }
        '.jpeg' { 'image/jpeg' }
        default { throw 'Use a .png, .jpg or .jpeg image.' }
    }
    $httpClient = [System.Net.Http.HttpClient]::new()
    $httpClient.Timeout = [TimeSpan]::FromSeconds(30)
    $multipart = [System.Net.Http.MultipartFormDataContent]::new()
    $content = [System.Net.Http.ByteArrayContent]::new([System.IO.File]::ReadAllBytes($resolvedImage))
    $content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::new($mime)
    $multipart.Add($content, 'file', [System.IO.Path]::GetFileName($resolvedImage))
    $uploadResponse = $httpClient.PostAsync("$ApiUrl/jobs", $multipart).GetAwaiter().GetResult()
    $body = $uploadResponse.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    if ([int]$uploadResponse.StatusCode -ne 202) { throw "Upload failed: $body" }
    $accepted = $body | ConvertFrom-Json
    Write-Output ("Accepted job: " + $accepted.job_id)
    $result = $null
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        $result = Invoke-RestMethod "$ApiUrl$($accepted.status_url)"
        if ($result.status -in @('completed', 'failed')) { break }
        Start-Sleep -Milliseconds 250
    }
    if ($result.status -ne 'completed') { throw ("Job did not complete: " + ($result | ConvertTo-Json -Depth 6)) }
    if ($result.predictions.Count -lt 1) { throw 'Model returned no predictions.' }
    foreach ($serviceUrl in @($ApiUrl, $WorkerUrl)) {
        $metrics = Invoke-WebRequest "$serviceUrl/metrics" -UseBasicParsing
        if ($metrics.StatusCode -ne 200 -or $metrics.Content -notmatch 'http_requests_total') {
            throw "Metrics check failed: $serviceUrl"
        }
    }
    $result | ConvertTo-Json -Depth 6
    Write-Output 'PASS: API + worker health, readiness, upload, Redis job, ONNX result and metrics.'
} finally {
    if ($null -ne $uploadResponse) { $uploadResponse.Dispose() }
    if ($null -ne $multipart) { $multipart.Dispose() }
    if ($null -ne $httpClient) { $httpClient.Dispose() }
    if ($generatedImage -and (Test-Path -LiteralPath $generatedImage)) {
        Remove-Item -LiteralPath $generatedImage
    }
}
