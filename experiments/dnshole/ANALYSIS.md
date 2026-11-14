# Jio STB Ad-Killer & DNS Sinkhole Architecture Analysis

## 1. Overview & Context

This directory documents and implements the community **DNS Sinkhole + Settings.Global Configuration Exploit** for Reliance Jio Set-Top Boxes (`JHSD200`, `JHSC200`, `JMSB200A`, etc.).

The original script (`stb_check.sh`), surfaced via [Pastebin mZrMHXXC](https://pastebin.com/mZrMHXXC), is an idempotent maintenance script designed for home setups where a **Raspberry Pi running AdGuard Home / Pi-hole + mock ACS proxy** manages the STB over the local network.

This analysis evaluates:
1. **The Exact Mechanism:** How Jio serves pre-roll and home screen ads, and how hidden JSON config keys disable them.
2. **The Cloud Lock Problem:** Why blocking `jtvp.cms.jio.com` is mandatory for the ad-free settings to persist.
3. **Execution Options:** How to run this **with a Raspberry Pi** or **without any extra hardware** (using free Cloud DNS like NextDNS or on-device local filters).

---

## 2. File Index

| File | Platform | Description |
| :--- | :--- | :--- |
| [`stb_check_original.sh`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/stb_check_original.sh) | Linux / Pi | Raw, unmodified bash script from the community Pastebin. |
| [`stb_adblock_setup.py`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/stb_adblock_setup.py) | **Windows** / Cross-Platform | Native Python script with automatic ADB detection, JSON backup, and colorized status reporting. |
| [`stb_adblock_setup.bat`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/stb_adblock_setup.bat) | **Windows** | 1-Click launcher for Windows users (prompts for IP or auto-detects connected ADB device). |
| [`stb_check_modded.sh`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/stb_check_modded.sh) | Linux / Pi / macOS | Enhanced bash script with auto-interface detection, non-fatal root fallback, and robust error recovery. |
| [`AGENTS.md`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/AGENTS.md) | Agent Guide | Operating instructions, invariants, and troubleshooting guidelines for AI assistants. |

---

## 3. The Technical Mechanism: How Ads Work on Jio STB

Even if third-party launchers (like Monet Launcher) are installed, users who launch the official **JioTV+** app to watch live channels experience **15-second unskippable video ads (pre-roll)** before the live video stream starts, alongside sponsored home screen carousels and idle screensaver posters.

### The Ad Delivery Architecture:
```
                      ┌───────────────────────────────────────────┐
                      │    Jio Cloud Ad & CMS Infrastructure     │
                      └─────────────────────┬─────────────────────┘
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
          jtvp.cms.jio.com                              siglyapi.jio.com
     (Ad Campaigns & Config Sync)                   (User Telemetry & Tracking)
                     │                                             │
                     ▼                                             ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ Jio STB Client (com.jio.media.stb.launcher / com.jio.stbadservice)        │
 │                                                                           │
 │  1. Queries jtvp.cms.jio.com ──► Pulls ad schedule & campaign IDs         │
 │  2. Overwrites local Settings.Global ──► launcher_config (ads ON)         │
 │  3. Plays 15s pre-roll video before launching Live TV HLS stream          │
 │  4. Reports viewing habits ──► siglyapi.jio.com                           │
 └───────────────────────────────────────────────────────────────────────────┘
```

### The Solution: A Two-Pillar Defense

To permanently kill ads, two distinct actions must happen simultaneously:

```
Pillar 1: Patch Settings.Global (Local Killswitch)
   - disable_preroll_video = true
   - pre_roll_ads = 0
   - jio_ads_promotion = 0
   - stb_dream_source_ads = 0

                              +

Pillar 2: Sinkhole jtvp.cms.jio.com (Cloud Lock)
   - Route jtvp.cms.jio.com -> 0.0.0.0
   - STB cannot contact CMS to revert your settings
   - Settings become PERMANENT
```

---

## 4. Deep-Dive: The Settings.Global JSON Keys

The stock Jio launcher stores its operational feature flags inside Android's system database under `Settings.Global`:

### A. `launcher_config` (Live TV Pre-Rolls & Banners)

```json
{
  "disable_preroll_video": true,
  "pre_roll_ads": 0,
  "jio_ads_promotion": 0,
  "other_ads_promotion": 0,
  "isPreroll_info_enabled": false,
  "sigly_event": false,
  "disable_preroll_analytics": true
}
```

* **`disable_preroll_video: true`**: Tells the JioTV+ player engine to completely bypass the 15-second video ad buffer and directly load the live TV HLS stream URL.
* **`pre_roll_ads: 0`**: Sets the allowed pre-roll count to zero.
* **`jio_ads_promotion: 0` & `other_ads_promotion: 0`**: Hides sponsored promotional tiles and banner carousels on the main navigation screen.
* **`sigly_event: false` & `disable_preroll_analytics: true`**: Disables analytics event reporting back to Reliance servers.

### B. `stb_config` (Screensaver / Daydream Ads)

```json
{
  "stb_dream_source_ads": 0,
  "stb_dream_source_show": 0
}
```

* **`stb_dream_source_ads: 0`**: Prevents the daydream screensaver service from fetching and displaying commercial advertisements when the STB is idle.
* **`stb_dream_source_show: 0`**: Prevents promotional show trailers from looping in screensaver mode.

---

## 5. The DNS Sinkhole Requirements

| Domain | Recommended Action | Technical Reason |
| :--- | :--- | :--- |
| **`jtvp.cms.jio.com`** | **Block (`0.0.0.0`)** | **Mandatory.** If this domain is reachable, the STB launcher checks in every few hours, detects modified settings, and overwrites `launcher_config` with cloud defaults. Blocking this makes the ad-free state permanent. |
| **`siglyapi.jio.com`** | **Block (`0.0.0.0`)** | Sigly analytics and behavioral tracking collector. |
| **`acs.oss.jio.com`** | Redirect or Block | TR-069 ACS management server. In a full lab setup, redirected to local ACS proxy (`mock_acs.py`). In a standalone setup, blocked or disabled via TR-181 persistent storage (`FOTA.Disable = true`). |
| **`google.com` / `connectivitycheck.gstatic.com`** | Allow normally | Standard Android network validation check (HTTP 204 portal). |

---

## 6. How to Implement: With vs Without a Raspberry Pi

### Option A: With a Dedicated Raspberry Pi
1. Run **AdGuard Home** or **Pi-hole** on the Raspberry Pi.
2. Under DNS Blocklists / Custom Filtering Rules, add:
   ```text
   0.0.0.0 jtvp.cms.jio.com
   0.0.0.0 siglyapi.jio.com
   ```
3. Set the STB's primary DNS to the Pi's IP address.
4. Run [`stb_check_modded.sh`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/stb_check_modded.sh) from the Pi on boot or via cron.

---

### Option B: Without a Raspberry Pi (Zero Extra Hardware)

You do **not** need a separate physical computer or Raspberry Pi:

#### Step 1: Push Settings via Windows PC (Takes 10 Seconds)
Double-click [`stb_adblock_setup.bat`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/stb_adblock_setup.bat) or run:
```powershell
python stb_adblock_setup.py --ip 192.168.29.10 --disable-ota
```
This immediately applies the JSON patches to `launcher_config` and `stb_config`.

#### Step 2: Sinkhole `jtvp.cms.jio.com` Using Free Cloud DNS
Choose one of these 3 free methods:

1. **NextDNS (Recommended - 100% Free Cloud Sinkhole):**
   - Create a free account at [nextdns.io](https://nextdns.io).
   - Go to **Denylist** $\to$ Add `jtvp.cms.jio.com` and `siglyapi.jio.com`.
   - On the STB: Set your DNS to your NextDNS IPv4 endpoints (or set Private DNS hostname in Android settings).
2. **On-Device Local App (`personalDNSfilter`):**
   - Sideload `personalDNSfilter` APK onto the STB over ADB:
     ```cmd
     adb install personalDNSfilter.apk
     ```
   - In the app, add `jtvp.cms.jio.com` to the local blocklist. It runs as a lightweight local VPN service entirely on the STB with zero battery/CPU overhead.
3. **Home Wi-Fi Router Domain Filter:**
   - Log into your home router's admin portal (e.g. `192.168.29.1`).
   - Go to **Security / Parental Controls / Domain Blocking**.
   - Add `jtvp.cms.jio.com` and `siglyapi.jio.com`.

---

## 7. Reversibility & Factory Defaults

If you ever want to revert back to default Jio settings:
1. Backups of the original JSON blobs are automatically saved in [`experiments/dnshole/backups/`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/backups/).
2. Alternatively, unblock `jtvp.cms.jio.com` in your DNS; within 12 hours, the stock Jio launcher will automatically re-download cloud defaults and restore original settings.
3. A standard factory reset in Android settings completely restores all system properties to factory state.
