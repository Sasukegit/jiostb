# Jio STB DNS Sinkhole & Ad-Killer Experiment

This folder contains the complete toolset and architectural documentation for eliminating pre-roll video ads, banner promotions, and screensaver advertisements on Jio Set-Top Boxes, enabling an ad-free stock launcher experience.

---

## Quick Start (Windows)

1. Make sure your STB is connected over Wi-Fi or Ethernet with ADB enabled.
2. Double-click [`stb_adblock_setup.bat`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/stb_adblock_setup.bat).
3. Enter your STB IP (or press ENTER to auto-detect).
4. The tool will:
   - Check if `jtvp.cms.jio.com` and `siglyapi.jio.com` are blocked.
   - Automatically back up existing Android settings.
   - Inject the ad-killing JSON blobs into `launcher_config` and `stb_config`.
   - Disable Iwedia background OTA updaters.
   - Verify all settings in real-time.

---

## Detailed Documentation

* Read the full architectural analysis: [`ANALYSIS.md`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/ANALYSIS.md)
* AI Agent instructions & invariants: [`AGENTS.md`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/AGENTS.md)

---

## Script Manifest

* [`stb_adblock_setup.py`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/stb_adblock_setup.py): Cross-platform Python setup & verification script.
* [`stb_adblock_setup.bat`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/stb_adblock_setup.bat): 1-click Windows launcher.
* [`stb_check_modded.sh`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/stb_check_modded.sh): Enhanced Linux/Raspberry Pi bash auditor.
* [`stb_check_original.sh`](file:///C:/Users/krishnasen/Desktop/jiostbdocs/experiments/dnshole/stb_check_original.sh): Unmodified community reference script from Pastebin `mZrMHXXC`.
