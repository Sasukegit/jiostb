#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$base = Split-Path -Parent $PSScriptRoot
$adapterName = 'Ethernet'
$labAddress = '192.168.50.1'
$labPrefix = 24

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       JIO STB FOTA & TR-069 ETHERNET RESEARCH LAB         " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Clean up old processes & ports
Write-Host "`n[1/5] Cleaning up old processes & freeing ports..." -ForegroundColor Yellow
Get-NetTCPConnection -LocalPort 53,80,443,7443,8443,9443 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
@('fota-lab.pid', 'captive-lab.pid') | ForEach-Object {
    $pidFile = Join-Path $base $_
    if (Test-Path $pidFile) {
        $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($oldPid) { Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}

# 2. Stop w32time for NTP port 123
Write-Host "[2/5] Stopping Windows Time Service (w32time)..." -ForegroundColor Yellow
Stop-Service w32time -ErrorAction SilentlyContinue

# 3. Configure Ethernet Interface
Write-Host "[3/5] Configuring Ethernet Adapter ($adapterName) to $labAddress..." -ForegroundColor Yellow
$adapter = Get-NetAdapter -Name $adapterName -ErrorAction SilentlyContinue
if (-not $adapter) {
    # Try finding any physical ethernet adapter
    $adapter = Get-NetAdapter | Where-Object { $_.InterfaceDescription -notmatch 'Virtual|Hyper-V|Loopback|TAP' -and $_.Status -ne 'Disabled' } | Select-Object -First 1
}

if ($adapter) {
    Set-NetIPInterface -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -Forwarding Disabled -ErrorAction SilentlyContinue
    Set-NetIPInterface -InterfaceIndex $adapter.ifIndex -AddressFamily IPv6 -Forwarding Disabled -ErrorAction SilentlyContinue
    & netsh.exe interface portproxy reset | Out-Null
    Get-NetRoute -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue
    Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -ne '127.0.0.1' } | Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
    Set-NetIPInterface -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -Dhcp Disabled -ErrorAction SilentlyContinue

    New-NetIPAddress -InterfaceIndex $adapter.ifIndex -IPAddress $labAddress -PrefixLength $labPrefix -ErrorAction SilentlyContinue | Out-Null
    New-NetIPAddress -InterfaceIndex $adapter.ifIndex -IPAddress '8.8.8.8' -PrefixLength 32 -ErrorAction SilentlyContinue | Out-Null
    New-NetIPAddress -InterfaceIndex $adapter.ifIndex -IPAddress '142.250.190.46' -PrefixLength 32 -ErrorAction SilentlyContinue | Out-Null
    New-NetIPAddress -InterfaceIndex $adapter.ifIndex -IPAddress '49.44.112.10' -PrefixLength 32 -ErrorAction SilentlyContinue | Out-Null
} else {
    Write-Host "[!] Warning: Ethernet adapter not found. Binding to local sockets only." -ForegroundColor Yellow
}

# 4. Windows Firewall Rules
Write-Host "[4/5] Updating Windows Firewall rules for Lab..." -ForegroundColor Yellow
Get-NetFirewallRule -DisplayName 'Jio-FOTA-Lab*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule

New-NetFirewallRule -DisplayName 'Jio-FOTA-Lab-Allow-UDP' -Group 'Jio-FOTA-Lab' -Direction Inbound -Action Allow -Protocol UDP -LocalPort 53,67,123 -LocalAddress Any -RemoteAddress Any -Profile Any | Out-Null
New-NetFirewallRule -DisplayName 'Jio-FOTA-Lab-Allow-TCP' -Group 'Jio-FOTA-Lab' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 53,80,443,7443,8080,8443,9443 -LocalAddress Any -RemoteAddress Any -Profile Any | Out-Null
New-NetFirewallRule -DisplayName 'Jio-FOTA-Lab-Allow-ICMP' -Group 'Jio-FOTA-Lab' -Direction Inbound -Action Allow -Protocol ICMPv4 -LocalAddress Any -RemoteAddress Any -Profile Any | Out-Null

# 5. Launch Services
Write-Host "[5/5] Launching FOTA Monitor ACS and Captive Responder..." -ForegroundColor Green
$python = (Get-Command python -ErrorAction Stop).Source

# Start monitor ACS in a separate console window for live logging
Start-Process -FilePath $python -ArgumentList (Join-Path $base 'fota_monitor_acs.py') -WorkingDirectory $base

Write-Host "`n>>> Starting Universal Captive Responder on Ethernet..." -ForegroundColor Cyan
& $python (Join-Path $base 'fota_captive_lab.py') --mode ethernet
