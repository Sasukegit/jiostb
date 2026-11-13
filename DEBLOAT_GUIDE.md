# Reliance Jio STB Complete Debloating, Lockdown & Customization Guide

This guide details how to permanently lock down the Reliance Jio STB (JHS D200 v2 / JHS C200 / franklin) once ADB is enabled. It eliminates all Jio ads, telemetry, and background updaters while setting up a clean Android TV launcher (Projectivy), native Android TV Settings, and custom remote hotkeys.

---

## 1. Quick One-Line Debloat Script

Once connected via ADB (`adb connect <STB_IP>:5555`), execute the following shell commands to disable and uninstall bloatware for user `0`:

### A. Disable All OTA Updaters & TR-069 Daemons
```bash
# Disable background services
pm disable-user --user 0 com.jio.tr069client
pm disable-user --user 0 insight.tr069.client
pm disable-user --user 0 com.iwedia.updateservice
pm disable-user --user 0 com.iwedia.httpupdate
pm disable-user --user 0 com.iwedia.pvodupdateservice
pm disable-user --user 0 com.iwedia.updatercuotaservice

# Uninstall for user 0 (keeps system partition intact)
pm uninstall -k --user 0 com.jio.tr069client
pm uninstall -k --user 0 insight.tr069.client
pm uninstall -k --user 0 com.iwedia.updateservice
pm uninstall -k --user 0 com.iwedia.httpupdate
```

### B. Disable Jio Ads, Telemetry & Diagnostics
```bash
# Ads & Content Injection
pm disable-user --user 0 com.jio.stbadservice
pm disable-user --user 0 com.jio.bioscopecontentservice
pm disable-user --user 0 com.jio.screensaver

# Telemetry & Background Schedulers
pm disable-user --user 0 com.jio.jiobackgroundscheduler
pm disable-user --user 0 com.jio.appoptimizer
pm disable-user --user 0 com.jio.adc.embedded
pm disable-user --user 0 com.jio.adc.aka
pm disable-user --user 0 com.jio.systemstats
pm disable-user --user 0 com.rjil.jiostblogservice
pm disable-user --user 0 com.jio.stb.remotediagnose
pm disable-user --user 0 com.jio.store
pm disable-user --user 0 com.jio.universalsetup
pm disable-user --user 0 com.netflix.partnertoken
```

### C. Replace Stock Launcher with Projectivy Launcher
1. Sideload Projectivy Launcher:
   ```bash
   adb install Projectivy_Launcher.apk
   ```
2. Disable the bloated Reliance Stock Launcher:
   ```bash
   pm disable-user --user 0 com.iwedia.ui.rjio.launcher.reliance
   pm uninstall -k --user 0 com.iwedia.ui.rjio.launcher.reliance
   ```
3. Press the Home button on the remote. Android TV will immediately make Projectivy the default Home screen.

---

## 2. Restoring Native Android TV Settings vs. Jio Settings

On stock Jio firmware, Jio hardcodes their proprietary settings app (`com.rjil.jiostbsetting`) with an intent filter `priority="999"` for `android.settings.SETTINGS`. This forcefully hijacks all settings clicks and hides standard Android TV options (such as developer options, accessibility services, app permissions, and storage).

When `com.rjil.jiostbsetting` is disabled, the standard "Settings" icon may fail to open in custom launchers.

### The Solution: Bundled Settings Shortcut APKs
Inside [`apks/`](apks/), we provide two dedicated lightweight launcher shortcuts:

1. **`AndroidSettingsShortcut.apk` (`com.user.androidsettings`)**:
   - Opens the genuine, native **Android TV Settings** (`com.android.tv.settings/.MainSettings`).
   - Gives direct access to: Apps, Permissions, Display & Sound, Developer Options, Accessibility, and Account Management.
   - Install via ADB:
     ```bash
     adb install apks/AndroidSettingsShortcut.apk
     ```
   - Manual ADB launch command:
     ```bash
     adb shell am start -n com.android.tv.settings/.MainSettings
     ```

2. **`JioSettingsShortcut.apk` (`com.user.jiosettings`)**:
   - Opens **Jio Settings** (`com.rjil.jiostbsetting/.MainActivity`) as a standalone app without letting it hijack system-wide settings.
   - Useful if you need to pair Bluetooth remotes, scan DVB-C cable channels, or check Jio subscription diagnostics.
   - Install via ADB:
     ```bash
     adb install apks/JioSettingsShortcut.apk
     ```

---

## 3. Remote Control Key Remapping (CleanYourTV)

Jio remotes feature dedicated shortcut buttons that normally force-launch Jio apps or stay dead when stock apps are uninstalled.

Using **CleanYourTV** ([`apks/TVHome.apk`](apks/TVHome.apk)), these keys can be routed to your preferred media apps:

### Key Event Mapping Reference
| Button Name | Linux Keycode | Android Keycode Constant | Recommended Target Application | Target Package Name |
| :--- | :---: | :--- | :--- | :--- |
| **Netflix** | `137` | `KEYCODE_F7` | Netflix | `com.netflix.ninja` |
| **Disney+ Hotstar** | `138` | `KEYCODE_F8` | Disney+ Hotstar | `in.startv.hotstar` |
| **JioCinema** | `139` | `KEYCODE_F9` | JioCinema | `com.jio.media.ondemand` |
| **Custom / Apps** | `140` | `KEYCODE_F10` | SmartTube | `org.smarttube.stable` |
| **JioTV+ / Guide** | `131`, `136`, `170`, `172` | `KEYCODE_TV`, `KEYCODE_GUIDE` | JioTV+ (Live TV) | `com.jio.media.jiotvplus` |
| **Mic / Voice** | `231` | `KEYCODE_VOICE_ASSIST` | Jio Voice Assistant | `com.android.app.jio.voiceassist` |

### Configuration File Setup
CleanYourTV stores key bindings in `/sdcard/Android/data/com.gathin.tvhome/files/config.json`:
```json
{
  "keyMappings": [
    {"keyCode": 137, "action": "launch_app", "packageName": "com.netflix.ninja"},
    {"keyCode": 138, "action": "launch_app", "packageName": "in.startv.hotstar"},
    {"keyCode": 139, "action": "launch_app", "packageName": "com.jio.media.ondemand"},
    {"keyCode": 140, "action": "launch_app", "packageName": "org.smarttube.stable"},
    {"keyCode": 131, "action": "launch_app", "packageName": "com.jio.media.jiotvplus"}
  ]
}
```
Ensure the Accessibility Service is enabled:
```bash
settings put secure enabled_accessibility_services com.gathin.tvhome/.InputKeyService
```

---

## 4. Low-Level Network Discoveries & System Mechanics

### A. NTP Time Synchronization (UDP Port 123)
* **The Mechanism:** Upon boot, TeleOS verifies real-world time before attempting any TLS handshake with Jio ACS or Google servers.
* **The Bottleneck:** Windows Host runs the Windows Time Service (`w32time`), which binds exclusively to UDP port 123.
* **Our Fix:** The lab launcher scripts automatically stop `w32time` (`Stop-Service w32time -Force`) so Python's high-precision RFC 5905 NTP server can answer the STB with 64-bit real-world timestamps.

### B. Private DNS / DoT (TCP Port 853) Dropping
* **The Mechanism:** On Android 11, the operating system attempts to establish encrypted DNS connections (DNS-over-TLS) to Google or Cloudflare DNS servers on TCP port 853. If successful, this bypasses local DNS spoofing on port 53.
* **Our Fix:** The captive lab (`captive_lab.py`) opens TCP port 853 and immediately terminates or drops connections, forcing Android TV to fall back to unencrypted local DNS queries on UDP port 53.

### C. Captive Portal Detection (HTTP Port 80)
* **The Mechanism:** Android TV sends `GET http://connectivitycheck.gstatic.com/generate_204` on TCP port 80. If it receives a redirect, timeout, or non-204 status, it marks the network connection as `NO_INTERNET` and disables background cloud services.
* **Our Fix:** The captive responder listens on port 80 and returns an immediate `HTTP/1.1 204 No Content` reply with zero body, clearing the Android network validation check instantly.

---

## 5. Firmware Downgrading Mechanics (`DowngradeEnable`)

Jio STBs normally block flashing older firmware using anti-rollback timestamp checks. However, Jio engineers embedded a TR-181 override parameter:
* **`Device.JioSTB.FOTA.DowngradeEnable`** (`true`)
* **`Device.JioSTB.FOTA.DowngradeValidityDate`** (`2037-12-31T23:59:59.000Z`)

### How it Works:
1. When `DowngradeEnable = true` is injected via our mock ACS (`mock_acs_universal.py`), the internal FOTA service (`com.iwedia.updateservice`) disables the version timestamp check:
   $$\text{AllowUpdate} = (\text{TargetVersion} > \text{CurrentVersion}) \lor (\text{DowngradeEnable} == \text{true})$$
2. The STB can then accept an older full block OTA package (e.g. downgrading from `11.3.46` to `11.1.0` or `11.3.24`) provided via our local captive responder.

---

## 6. Reversing / Restoring Stock State

Because all debloating is performed under `--user 0`, the modifications are **100% reversible**:
* **To re-enable any specific app:**
  ```bash
  pm enable <package_name>
  ```
* **Full Factory Reset:**
  Settings $\to$ Device Preferences $\to$ Reset, or booting into Recovery (`adb reboot recovery`) restores the box to untouched factory defaults.
