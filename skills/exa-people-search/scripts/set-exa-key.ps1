# Store an Exa API key for the people-search skill — safely, with no editing.
#
# Run this in YOUR OWN PowerShell window (not through the AI):
#   powershell -ExecutionPolicy Bypass -File set-exa-key.ps1
#
# It prompts once for your key (hidden as you type/paste), writes it to a private
# credentials file (%USERPROFILE%\.config\exa\key), and verifies it against the
# Exa API. The key never appears on screen and never passes through the AI.
#
# The skill reads the key from $env:EXA_API_KEY first, then from this file — so
# you do NOT need to edit any profile or restart your terminal.

$ErrorActionPreference = 'Stop'

$keyfile = if ($env:EXA_KEY_FILE) { $env:EXA_KEY_FILE } else { Join-Path $HOME '.config\exa\key' }

Write-Host "Paste your Exa API key at the prompt, then press Enter."
Write-Host "(You will NOT see anything as you paste — that is intentional.)"

$secure = Read-Host -AsSecureString "Exa API key"
$bstr   = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $key = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
} finally {
  [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

# Strip all whitespace (keys never contain spaces; paste often adds trailing newlines).
$key = ($key -replace '\s', '')

if ([string]::IsNullOrEmpty($key)) {
  Write-Host "No key entered. Nothing was saved. Run the command again."
  exit 1
}

# Double-paste guard: exact doubling of the real key (e.g. 36 chars became 72).
if ($key.Length -gt 8 -and $key.Length % 2 -eq 0) {
  $half = $key.Length / 2
  if ($key.Substring(0, $half) -eq $key.Substring($half)) {
    Write-Host "That looks like the key was pasted twice (its length is exactly doubled)."
    Write-Host "Nothing was saved. Run the command again and paste it just once."
    exit 1
  }
}

# Idempotent whole-file write to the private credentials file.
$dir = Split-Path -Parent $keyfile
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Set-Content -Path $keyfile -Value $key -NoNewline -Encoding ascii
Write-Host "Saved to $keyfile"

# Best-effort live verification — never prints the key, only the HTTP status.
Write-Host -NoNewline "Verifying against the Exa API... "
try {
  $resp = Invoke-WebRequest -Method Post -Uri 'https://api.exa.ai/agent/runs' `
    -Headers @{ 'x-api-key' = $key; 'Content-Type' = 'application/json' } `
    -Body '{"query":"hi","effort":"low"}' -UseBasicParsing
  if ($resp.StatusCode -eq 200) {
    Write-Host "OK (HTTP 200). Key saved and verified — you are all set."
  } else {
    Write-Host "HTTP $($resp.StatusCode) — key saved, but verification was inconclusive."
  }
} catch {
  $code = $null
  if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
  if ($code -eq 401 -or $code -eq 403) {
    Write-Host "HTTP $code — the key was saved but the API rejected it. Double-check you copied the whole key (with Agent API access), then run this again."
  } else {
    Write-Host "couldn't verify (network issue or blocked). Key was saved; it will be used next time you run the skill."
  }
}
