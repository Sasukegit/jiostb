# AI Agent Guidelines & Technical Operational Manual: Jio STB Toolkit

This document defines technical specifications, architectural boundaries, and actionable protocols for autonomous AI agents (Antigravity, Claude Code, Cursor, Gemini CLI) operating or maintaining this repository.

---

## 1. System Architecture

```
+---------------------------------------------------------------------------------+
|                                 STANDALONE MODE                                 |
|                                                                                 |
|  [ PC (query_acs_direct.py) ]  ==== HTTPS:8443 (Digest Auth) ====>  [ Jio ACS ] |
|   - Serial: <STB_SERIAL_NUMBER>                                   (49.40.134.113)
|   - Password: <DERIVED_CPE_PASSWORD>                                            |
+---------------------------------------------------------------------------------+

+---------------------------------------------------------------------------------+
|                                ADB UNLOCK LAB                                   |
|                                                                                 |
|  [ Physical Jio STB ] <==== P2P / Wi-Fi ====> [ captive_lab / mock_acs ]         |
|   - Port 67 (DHCP) -> Assigns IP                                                |
|   - Port 53 (DNS)  -> Spoofs acs.oss.jio.com                                    |
|   - Port 80 (204)  -> Satisfies Android Captive Portal                          |
|   - Port 8443(TLS) -> Injects USBDebugging = true & DowngradeEnable = true      |
+---------------------------------------------------------------------------------+

+---------------------------------------------------------------------------------+
|                            FIRMWARE MITM CAPTURE                                |
|                                                                                 |
|  [ Physical Jio STB ] ---- Port 8443 (TLS) ---> [ fota_monitor_acs.py ]          |
|                                                       |                         |
|                                            (Spoofs Firmware Version)            |
|                                                       |                         |
|                                                       +--> [ Real Jio ACS ]     |
|                                                             (49.40.134.113)     |
+---------------------------------------------------------------------------------+
```

---

## 2. Core Operational Protocols for Agents

### Protocol A: Standalone ACS Firmware Query (No Hardware Needed)
When asked to query Jio ACS for updates or test a new version:
1. Do **NOT** require the physical STB to be connected or turned on.
2. If querying for a specific physical STB for the first time, run `python dump_credentials.py` while connected via ADB to save `device_credentials.json`.
3. Execute `query_acs_direct.py` directly on the host machine:
   ```bash
   python query_acs_direct.py <VERSION_STRING>
   ```
4. `query_acs_direct.py` automatically loads `device_credentials.json` if available, or prompts for device details if run standalone without configured credentials.
5. To compute credentials manually for a different serial number $S$ and $ro.acsdata$ $A$:
   $$\text{Password} = \text{Base64}\Big(\text{SHA-256}(A + \text{"Hee4Xeigaethaeye"})[0:16]\Big).\text{strip}()$$
6. Analyze the SOAP response:
   - Status `200` with `204 No Content`: Device is authenticated; no pending tasks on ACS.
   - Status `200` with `<cwmp:SetParameterValues>`: ACS is configuring device parameters. Respond with `<cwmp:SetParameterValuesResponse><Status>0</Status></cwmp:SetParameterValuesResponse>`.
   - Status `200` with `<cwmp:Download>`: **FIRMWARE FOUND!** Extract `<URL>`, `<FileSize>`, and `<TargetFileName>`. Automatically saved to `fota_firmware_url.txt` and `fota_update_found.json`.
7. Discovered URLs can be shared to the catalog using `python share_firmware.py`.

---

### Protocol B: Permanent ADB Unlock (Ethernet or Wi-Fi)
1. **Determine Connection Mode:**
   - If PC has Ethernet $\to$ Execute `UNLOCK_ADB_ETHERNET.bat` (or `powershell -File scripts\start-adb-ethernet.ps1`).
   - If PC is Wi-Fi only $\to$ Ensure Windows Mobile Hotspot is ON (2.4 GHz, SSID `JioSTB-Setup`, password `password123`), then execute `UNLOCK_ADB_WIFI.bat`.
2. **Cold Power-Cycle the STB:** Instruct the user or wait for cold-reboot.
3. **Monitor Log Tail:**
   - Look for `[ACS] Sending SetParameterValues: Device.JioSTB.USB.USBDebugging = true`.
   - Confirm `SetParameterValuesResponse: Status = 0`.
4. **Connect via ADB:**
   ```powershell
   adb connect 192.168.50.2:5555   # (Ethernet)
   adb connect 192.168.137.x:5555  # (Wi-Fi)
   ```

---

### Protocol C: Real-Time Firmware Capture (Ethernet or Wi-Fi MITM)
When capturing live traffic from a physical STB:
1. Ensure `com.iwedia.updateservice` is stopped from flashing payloads:
   ```bash
   adb shell pm disable-user --user 0 com.iwedia.updateservice
   ```
2. Set the target spoofed version in `spoofed_version.txt` (e.g. `STB-JHSD200-11.1.0`).
3. Run `CAPTURE_FIRMWARE_ETHERNET.bat` or `CAPTURE_FIRMWARE_WIFI.bat`.
4. On the STB, navigate to **Settings** $\to$ **System Settings** $\to$ **Software Update**.
5. When `cwmp:Download` is intercepted, verify URL on public Akamai CDN via HTTP Range request.

---

### Protocol D: Post-Unlock Debloating & Launcher Setup
Follow [`DEBLOAT_GUIDE.md`](DEBLOAT_GUIDE.md):
1. Disable stock launcher:
   ```bash
   pm disable-user --user 0 com.iwedia.ui.rjio.launcher.reliance
   ```
2. Disable all ads and background schedulers:
   ```bash
   pm disable-user --user 0 com.jio.stbadservice
   pm disable-user --user 0 com.jio.bioscopecontentservice
   pm disable-user --user 0 com.jio.jiobackgroundscheduler
   pm disable-user --user 0 com.jio.appoptimizer
   ```
3. Install Projectivy Launcher and CleanYourTV accessibility service.

---

## 3. Failure Modes & Automated Recovery

| Failure / Exception | Root Cause | Automated Recovery Action |
| :--- | :--- | :--- |
| **`PermissionDenied` on UDP 53** | Windows DNS Client cache (`Dnscache`) or ICS holds UDP 53. | Execute: `Stop-Service -Name "SharedAccess" -ErrorAction SilentlyContinue`. |
| **`OSError: [WinError 10048] address already in use: 123`** | Windows Time Service (`w32time`) owns UDP 123. | Execute: `Stop-Service w32time -Force`. |
| **`FaultCode 9005` (Invalid Parameter)** | STB runs Android 9 firmware where `Device.JioSTB` does not exist. | `mock_acs_universal.py` automatically retries with legacy `Device.JSTB.USB.USBDebugging`. |
| **`FaultCode 9003` (Atomic Reject)** | Multi-parameter RPC array failed schema verification. | `mock_acs_universal.py` automatically injects parameters in individual discrete transactions. |
| **Port 8443 TLS Handshake Failure** | STB rejects untrusted certificate chain. | Verify `forged_chain.pem` is loaded. Do not replace with arbitrary self-signed certificates. |

---

## 4. Teardown Protocol
When finished, always call:
```cmd
STOP_ALL_LABS.bat
```
This kills all lingering Python processes on ports `53, 67, 80, 123, 443, 7443, 8443, 9443` and restores `w32time`.
