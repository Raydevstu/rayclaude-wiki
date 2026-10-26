param(
  [int]$ApiPort = 8000,
  [int]$UiPort = 8001,
  [switch]$Ollama
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if ($Ollama) {
  $env:TIER1_PROVIDER = 'ollama'
  $env:TIER1_PROVIDER_BASE_URL = 'http://127.0.0.1:11434/v1'
  $env:TIER1_MODEL_SMALL = if ($env:TIER1_MODEL_SMALL) { $env:TIER1_MODEL_SMALL } else { 'llama3.2' }
  $env:TIER1_MODEL_MEDIUM = if ($env:TIER1_MODEL_MEDIUM) { $env:TIER1_MODEL_MEDIUM } else { 'llama3.2' }
  $env:TIER1_MODEL_LARGE = if ($env:TIER1_MODEL_LARGE) { $env:TIER1_MODEL_LARGE } else { 'llama3.2' }
}

Write-Host "Starting Tier-1 API on http://127.0.0.1:$ApiPort"
$api = Start-Process -FilePath 'python' -ArgumentList '-m','tier1','serve','--host','127.0.0.1','--port',$ApiPort -WorkingDirectory $root -PassThru
$env:VITE_TIER1_API_ORIGIN = "http://127.0.0.1:$ApiPort"
Write-Host "Starting UI on http://127.0.0.1:$UiPort"
Start-Process -FilePath 'npm' -ArgumentList 'run','dev','--','--port',$UiPort -WorkingDirectory $root
Write-Host "API PID: $($api.Id)"
Write-Host "Press Ctrl+C to stop this launcher; stop the API process with Stop-Process -Id $($api.Id)."
