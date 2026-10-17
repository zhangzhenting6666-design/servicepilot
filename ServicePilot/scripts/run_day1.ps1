param([switch]$ConfigureKey)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Project Python environment is missing.' }
$oldKey = $env:OPENAI_API_KEY
$oldEncoding = $env:PYTHONIOENCODING
try {
    $env:PYTHONIOENCODING = 'utf-8'
    if ($ConfigureKey) {
        Write-Host 'Enter the API key locally. It will be masked, used for this run only, and never saved to a file.'
        $secureKey = Read-Host 'OPENAI_API_KEY' -AsSecureString
        $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        try { $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer).Trim() }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer); $secureKey.Dispose() }
    } elseif ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
        $env:OPENAI_API_KEY = [Environment]::GetEnvironmentVariable('OPENAI_API_KEY', 'User')
    }
    & $pythonExe (Join-Path $PSScriptRoot 'minimal_agent.py')
    $minimalExit = $LASTEXITCODE
    # Import and report credential blockers for both targets. For a failed real call,
    # stop before making more billable calls in the official example.
    if ($minimalExit -eq 0 -or $minimalExit -eq 2) {
        & $pythonExe (Join-Path $PSScriptRoot 'run_official_customer_service.py')
        $officialExit = $LASTEXITCODE
    } else {
        Write-Host 'Minimal call did not pass. Official live run deferred; inspect minimal-agent-latest.json.'
        $officialExit = 1
    }
} finally {
    $env:OPENAI_API_KEY = $oldKey
    $env:PYTHONIOENCODING = $oldEncoding
}
if ($minimalExit -eq 2 -or $officialExit -eq 2) { exit 2 }
if ($minimalExit -ne 0 -or $officialExit -ne 0) { exit 1 }
exit 0
