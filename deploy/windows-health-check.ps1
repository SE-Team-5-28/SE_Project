$ErrorActionPreference = "Continue"

$HealthCheckUrl = "http://127.0.0.1:8000/healthz"
$LogFile = "$PSScriptRoot\health-check.log"

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

try {
    $response = Invoke-WebRequest `
        -Uri $HealthCheckUrl `
        -UseBasicParsing `
        -TimeoutSec 5

    if ($response.StatusCode -eq 200) {
        Add-Content $LogFile "$timestamp | UP | $HealthCheckUrl | HTTP $($response.StatusCode)"
        Write-Host "Health check succeeded: $HealthCheckUrl"
        exit 0
    }
}
catch {
    Add-Content $LogFile "$timestamp | DOWN | $HealthCheckUrl | $($_.Exception.Message)"
}

Write-Host "Health check failed. Attempting Django recovery..."

Add-Content $LogFile "$timestamp | RECOVERY | Attempting to restart Django development server"

# Check whether a Django runserver process exists.
$djangoProcess = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "manage.py runserver"
    }

if ($djangoProcess) {
    foreach ($process in $djangoProcess) {
        try {
            Stop-Process -Id $process.ProcessId -Force
        }
        catch {
            Add-Content $LogFile "$timestamp | RECOVERY-ERROR | Could not stop process $($process.ProcessId)"
        }
    }

    Start-Sleep -Seconds 2
}

# Start Django again in the project directory.
$projectRoot = Split-Path -Parent $PSScriptRoot

Start-Process `
    -FilePath "$projectRoot\.venv\Scripts\python.exe" `
    -ArgumentList "manage.py runserver 127.0.0.1:8000" `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden

Add-Content $LogFile "$timestamp | RECOVERY | Django server restart attempted"

Start-Sleep -Seconds 5

try {
    $response = Invoke-WebRequest `
        -Uri $HealthCheckUrl `
        -UseBasicParsing `
        -TimeoutSec 5

    if ($response.StatusCode -eq 200) {
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content $LogFile "$timestamp | RECOVERED | $HealthCheckUrl | HTTP $($response.StatusCode)"
        Write-Host "Health check recovered after restart."
        exit 0
    }
}
catch {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content $LogFile "$timestamp | FAILED | Health check still failing after restart"
}

Write-Host "Health check still failing after restart."
exit 1