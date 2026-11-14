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

### C. Replace Stock Launcher (Projectivy or Monet)
Choose your preferred clean launcher:
* **Option 1: Monet Launcher** (Lightweight Material You launcher bundled in `apks/`):
  ```bash
  adb install apks/monet-launcher.apk
  ```
* **Option 2: Projectivy Launcher** (Highly customizable Android TV launcher):
  ```bash
  adb install Projectivy_Launcher.apk
  ```

Disable the bloated Reliance Stock Launcher:
```bash
pm disable-user --user 0 com.iwedia.ui.rjio.launcher.reliance
pm uninstall -k --user 0 com.iwedia.ui.rjio.launcher.reliance
```
Press the Home button on the remote. Android TV will immediately prompt or default to your new launcher.

---

## 2. On-Device Shell & App Management (No PC Needed Afterward)

### A. Shevery (`apks/shevery-release.apk`) — On-Device Shizuku Shell
* **What it is:** **Shevery** (`com.hamondev.shevery`) is a standalone, on-device **Shizuku API provider**.
* **Why use it:** Once ADB is unlocked, installing Shevery gives you persistent `uid=2000(shell)` privileges directly on the TV. You can install APKs silently, freeze/unfreeze apps, and grant runtime permissions directly from the TV without plugging in a PC!
* **Installation:**
  ```bash
  adb install apks/shevery-release.apk
  ```

### B. Aurora Store (`apks/AuroraStore_4.8.4.apk`) — Open-Source Play Store
* **What it is:** An open-source, privacy-friendly Google Play Store client for Android TV.
* **Why use it:** Allows downloading, installing, and updating any Android TV application without Google Play Services or logging into a personal Google account.
* **Installation:**
  ```bash
  adb install apks/AuroraStore_4.8.4.apk
  ```

---

## 3. Upgrading the Google Cast (Chromecast Built-In) Stub

### The Problem: Hollow Stub
On stock Jio firmware, casting from YouTube, Chrome, or smartphones fails. Inspection of the system partition reveals:
* Jio ships `com.google.android.apps.mediashell` as an empty **0 MB stub** (`v0.0`, versionCode `1`) in `/product/priv-app/AndroidMediaShell`.
* Because it is only a placeholder stub, the Chromecast receiver service does not run.

### The Fix: Official Production Update (`apks/mediashell.apk`)
We captured the genuine production Google Cast receiver update (`v3.72.446070`, versionCode `446070112`) and bundled it in [`apks/mediashell.apk`](apks/mediashell.apk):

1. **Install the Production Cast Receiver:**
   ```bash
   adb install -r apks/mediashell.apk
   ```
2. **Verify Cast Service Activation:**
   ```bash
   adb shell dumpsys activity services com.google.android.apps.mediashell
   ```
   * The STB registers `CastReceiverService` with Google Cast client ID.
   * Your TV immediately begins broadcasting as a genuine **Chromecast built-in** receiver (e.g. "Living Room TV") across your local Wi-Fi network!
3. **DIAL Protocol Casting (`com.jio.dialserver`):**
   * Keep `com.jio.dialserver` enabled. It provides the **DIAL (Discovery And Launch)** protocol created by Netflix and YouTube, allowing apps on your phone to launch and stream directly to your TV.

---

## 4. Important Notice: JioTV+ & Jio SSO (`com.media.jio.sso.stb`)

> [!WARNING]
> **DO NOT DISABLE `com.media.jio.sso.stb` if you plan to use JioTV+ or LiveTV!**

* **Why:** All Jio media apps (`com.jio.media.jiotvplus`, `com.jio.media.livetv`, `com.jio.myjiotv`) rely on Jio's Single Sign-On service via intent `app://open.sso.app`.
* If `com.media.jio.sso.stb` is uninstalled or disabled, launching JioTV+ triggers a fatal `ActivityNotFoundException` crash.
* **If you accidentally disabled it, restore it via:**
  ```bash
  cmd package install-existing com.media.jio.sso.stb
  pm enable com.media.jio.sso.stb
  ```

## 5. Restoring Native Android TV Settings vs. Jio Settings

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

## 6. Remote Control Key Remapping (CleanYourTV)

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

## 7. Low-Level Network Discoveries & System Mechanics

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

## 8. Firmware Downgrading Mechanics (`DowngradeEnable`)

Jio STBs normally block flashing older firmware using anti-rollback timestamp checks. However, Jio engineers embedded a TR-181 override parameter:
* **`Device.JioSTB.FOTA.DowngradeEnable`** (`true`)
* **`Device.JioSTB.FOTA.DowngradeValidityDate`** (`2037-12-31T23:59:59.000Z`)

### How it Works:
1. When `DowngradeEnable = true` is injected via our mock ACS (`mock_acs_universal.py`), the internal FOTA service (`com.iwedia.updateservice`) disables the version timestamp check:
   $$\text{AllowUpdate} = (\text{TargetVersion} > \text{CurrentVersion}) \lor (\text{DowngradeEnable} == \text{true})$$
2. The STB can then accept an older full block OTA package (e.g. downgrading from `11.3.46` to `11.1.0` or `11.3.24`) provided via our local captive responder.

---

## 9. Reversing / Restoring Stock State

Because all debloating is performed under `--user 0`, the modifications are **100% reversible**:
* **To re-enable any specific app:**
  ```bash
  pm enable <package_name>
  ```
* **Full Factory Reset:**
  Settings $\to$ Device Preferences $\to$ Reset, or booting into Recovery (`adb reboot recovery`) restores the box to untouched factory defaults.
