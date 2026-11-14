# AGENTS.md — DNS Sinkhole & Ad-Killer Experiment Guidelines

## 1. Scope & Objective
This directory (`experiments/dnshole/`) manages tools and documentation for analyzing, verifying, and applying the community DNS sinkhole and `Settings.Global` ad-blocking configuration for Reliance Jio Set-Top Boxes (`JHSD200`, `JHSC200`, `JMSB200A`, etc.).

---

## 2. Invariants & Safety Rules

1. **JSON Integrity Invariant:**
   * Never blindly overwrite `Settings.Global.launcher_config` or `Settings.Global.stb_config` with arbitrary strings.
   * Always fetch existing JSON first, parse with `json.loads()`, apply dictionary updates with `update()`, re-serialize, and verify with `json.dumps()`. Writing malformed JSON into `launcher_config` can crash `com.jio.media.stb.launcher` into a restart loop.
2. **Automatic Backup Invariant:**
   * Every write to `Settings.Global` must write a timestamped backup copy of the raw pre-modification value into `experiments/dnshole/backups/`.
3. **Zero Bootloader Interference:**
   * This directory operates strictly within standard Android userspace APIs (`adb shell settings`, `adb shell pm`, and network DNS).
   * Do not touch `/dev/block/env`, bootloader partitions, or U-Boot variables.

---

## 3. Operational CLI Reference

### A. Run Setup on Windows (Default Execution)
```powershell
python "C:\Users\krishnasen\Desktop\jiostbdocs\experiments\dnshole\stb_adblock_setup.py" --ip <STB_IP> --disable-ota
```
*(If `--ip` is omitted, the script automatically queries `adb devices` and binds to the first connected device).*

### B. Verify Settings Over Raw ADB
```powershell
adb -s <STB_IP>:5555 shell "settings get global launcher_config"
adb -s <STB_IP>:5555 shell "settings get global stb_config"
```

### C. Verify DNS Sinkhole Resolution on STB
```powershell
adb -s <STB_IP>:5555 shell "ping -c 1 -W 2 jtvp.cms.jio.com"
adb -s <STB_IP>:5555 shell "ping -c 1 -W 2 siglyapi.jio.com"
```
* **Success:** Returns `0.0.0.0` or `127.0.0.1` or fails to resolve.
* **Failure (Leaking):** Returns a public Jio IP address (e.g. `49.44.x.x` or `103.x.x.x`).

---

## 4. Key Domains Reference

| Domain | Role | Target Resolution |
| :--- | :--- | :--- |
| **`jtvp.cms.jio.com`** | JioTV+ Cloud CMS (overwrites launcher settings) | `0.0.0.0` (BLOCKED) |
| **`siglyapi.jio.com`** | Jio Sigly Analytics & Telemetry | `0.0.0.0` (BLOCKED) |
| **`acs.oss.jio.com`** | TR-069 CWMP Management Server | Local ACS Proxy or `0.0.0.0` |
| **`connectivitycheck.gstatic.com`** | Android Captive Portal check | Public Google IP (HTTP 204) |

---

## 5. Troubleshooting & Remediation

* **Issue: Settings reset after a few hours / after reboot:**
  * **Cause:** `jtvp.cms.jio.com` was not properly sinkholed. The STB contacted Jio's cloud CMS on schedule and reverted `launcher_config`.
  * **Fix:** Add `jtvp.cms.jio.com` to NextDNS / AdGuard Home / router blocklist, then re-run `stb_adblock_setup.py`.
* **Issue: JioTV+ app shows network error when opening channels:**
  * **Cause:** Aggressive adblock lists blocked legitimate media streaming CDNs (`*.jiocinema.com`, `*.jio.com` media endpoints).
  * **Fix:** Ensure only `jtvp.cms.jio.com` and `siglyapi.jio.com` are sinkholed. Do not wildcard block `*.jio.com`.
