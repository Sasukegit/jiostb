#Requires -RunAsAdministrator
$ErrorActionPreference = 'SilentlyContinue'
$base = Split-Path -Parent $PSScriptRoot

Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host "         STOPPING JIO STB RESEARCH LAB SERVERS             " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow

# 1. Kill listening processes on lab ports
$ports = 53, 67, 80, 443, 7443, 8080, 8443, 9443
Get-NetTCPConnection -LocalPort $ports -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}

# 2. Kill python scripts by name
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match 'fota_captive_lab|fota_monitor_acs|captive_wifi_lab|mock_acs'
} | Stop-Process -Force -ErrorAction SilentlyContinue

# 3. Clean pid files
Get-ChildItem -Path $base -Filter "*.pid" | Remove-Item -Force -ErrorAction SilentlyContinue

# 4. Clean up firewall rules
Get-NetFirewallRule -DisplayName 'Jio-FOTA-Lab*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule

# 5. Restart w32time
Start-Service w32time -ErrorAction SilentlyContinue

Write-Host "[+] All lab processes stopped and ports freed." -ForegroundColor Green
