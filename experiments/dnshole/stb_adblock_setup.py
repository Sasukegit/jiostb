#!/usr/bin/env python3
"""
stb_adblock_setup.py — Native Windows / Cross-Platform Jio STB Ad-Killer & DNS Verifier

Applies the community Settings.Global patches (killing 15-second pre-roll video ads,
banner promotions, and screensaver ads) and verifies DNS sinkhole status.
"""

import sys
import os
import json
import re
import subprocess
import argparse
from datetime import datetime

# Common paths for adb.exe on Windows
ADB_CANDIDATES = [
    r"C:\Users\krishnasen\Desktop\jiostbdocs\jio-fota-toolkit\bin\adb.exe",
    r"C:\platform-tools\adb.exe",
    "adb"
]

def find_adb():
    for candidate in ADB_CANDIDATES:
        try:
            res = subprocess.run([candidate, "version"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return candidate
        except Exception:
            continue
    return "adb"

def run_adb(adb_bin, target, args, timeout=10):
    cmd = [adb_bin]
    if target:
        cmd.extend(["-s", target])
    cmd.extend(args)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)

def resolve_domain_from_stb(adb_bin, target, domain):
    """Pings domain from STB to check resolved IP."""
    code, out, _ = run_adb(adb_bin, target, ["shell", f"ping -c 1 -W 2 {domain} 2>/dev/null"])
    if code != 0 or not out:
        return None
    match = re.search(r"\(([\d\.]+)\)", out.splitlines()[0])
    return match.group(1) if match else None

def is_sinkholed(ip):
    if not ip:
        return False
    return ip == "0.0.0.0" or ip.startswith("127.") or ip == "::" or ip == "::1"

def patch_json_blob(adb_bin, target, setting_key, updates, backup_dir):
    """Fetches setting, backs it up, patches JSON, and writes it back."""
    code, raw, _ = run_adb(adb_bin, target, ["shell", f"settings get global {setting_key}"])
    raw = raw.strip()
    
    # Save original backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"{setting_key}_backup_{ts}.json")
    with open(backup_file, "w", encoding="utf-8") as f:
        f.write(raw)
    
    data = {}
    if raw and raw != "null":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print(f"  [!] Warning: Existing {setting_key} was not valid JSON. Starting fresh.")
            data = {}
    
    data.update(updates)
    patched_json = json.dumps(data, separators=(',', ':'))
    
    # Push patched JSON to STB temp and write to settings
    remote_tmp = f"/data/local/tmp/{setting_key}_patch.json"
    push_code, _, push_err = run_adb(adb_bin, target, ["shell", f"cat << 'EOF' > {remote_tmp}\n{patched_json}\nEOF"])
    if push_code != 0:
        print(f"  [✗] Failed to push temporary file: {push_err}")
        return False
    
    set_code, _, set_err = run_adb(adb_bin, target, ["shell", f"settings put global {setting_key} \"$(cat {remote_tmp})\""])
    run_adb(adb_bin, target, ["shell", f"rm -f {remote_tmp}"])
    
    return set_code == 0

def verify_json_blob(adb_bin, target, setting_key, expected):
    """Verifies applied key-value pairs."""
    code, raw, _ = run_adb(adb_bin, target, ["shell", f"settings get global {setting_key}"])
    if code != 0 or not raw or raw == "null":
        return False, {}
    try:
        data = json.loads(raw)
    except Exception:
        return False, {}
    
    results = {}
    all_ok = True
    for k, want in expected.items():
        got = data.get(k)
        match = (got == want)
        results[k] = (match, got, want)
        if not match:
            all_ok = False
    return all_ok, results

def main():
    parser = argparse.ArgumentParser(description="Jio STB Ad-Killer & DNS Sinkhole Verifier")
    parser.add_argument("--ip", help="STB IP address (e.g. 192.168.29.10)", default="")
    parser.add_argument("--port", help="ADB TCP Port (default: 5555)", default="5555")
    parser.add_argument("--disable-ota", action="store_true", help="Also disable Iwedia OTA packages")
    args = parser.parse_args()

    adb = find_adb()
    print("=" * 65)
    print("       Jio STB Ad-Killer & DNS Sinkhole Setup (Windows/Cross-Platform)")
    print("=" * 65)
    print(f"Using ADB binary: {adb}")

    # Determine target
    target = ""
    if args.ip:
        target = f"{args.ip}:{args.port}"
        print(f"Connecting to target: {target}...")
        run_adb(adb, "", ["connect", target])
    else:
        # Detect connected device
        _, out, _ = run_adb(adb, "", ["devices"])
        lines = [line.split()[0] for line in out.splitlines()[1:] if "\tdevice" in line]
        if not lines:
            print("[✗] Error: No ADB devices found! Specify --ip <STB_IP> or connect via USB/Wi-Fi.")
            sys.exit(1)
        target = lines[0]
        print(f"Auto-detected connected device: {target}")

    # Verify device authorization
    code, state, _ = run_adb(adb, target, ["get-state"])
    if state != "device":
        print(f"[✗] Device {target} is not in 'device' state (state: {state}). Check authorization on TV.")
        sys.exit(1)

    print(f"[✓] Connected and authorized: {target}\n")

    # 1. Check DNS Sinkhole
    print("── 1. Checking DNS Sinkhole Resolution ─────────────────────────────")
    domains = [
        ("jtvp.cms.jio.com", True, "JioTV+ CMS / Ad Campaign Server"),
        ("siglyapi.jio.com", True, "Sigly User Tracking / Analytics"),
        ("acs.oss.jio.com", False, "TR-069 ACS Provisioning Server"),
        ("google.com", False, "General Internet Connectivity")
    ]

    cms_sinkholed = False
    for domain, should_block, desc in domains:
        resolved = resolve_domain_from_stb(adb, target, domain)
        blocked = is_sinkholed(resolved)
        if domain == "jtvp.cms.jio.com" and blocked:
            cms_sinkholed = True

        if should_block:
            if blocked:
                print(f"  [✓] {domain:<20} -> {resolved:<15} (BLOCKED - {desc})")
            else:
                print(f"  [!] {domain:<20} -> {resolved or 'Unresolved':<15} (LEAKING! {desc})")
        else:
            print(f"  [*] {domain:<20} -> {resolved or 'Unresolved':<15} ({desc})")

    if not cms_sinkholed:
        print("\n  [!] CAUTION: jtvp.cms.jio.com is NOT sinkholed!")
        print("      The ad-free settings will apply now, but Jio will overwrite them in a few hours.")
        print("      Block 'jtvp.cms.jio.com' in NextDNS, AdGuard, Pi-hole, or your router to make it permanent.")

    # Create backup directory
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    # 2. Patch launcher_config (Preroll & Promotions)
    print("\n── 2. Applying launcher_config (Killing Pre-Rolls & Banners) ───────")
    launcher_updates = {
        "disable_preroll_video": True,
        "pre_roll_ads": 0,
        "sigly_event": False,
        "jio_ads_promotion": 0,
        "other_ads_promotion": 0,
        "isPreroll_info_enabled": False,
        "disable_preroll_analytics": True
    }
    if patch_json_blob(adb, target, "launcher_config", launcher_updates, backup_dir):
        print("  [✓] launcher_config patched and written successfully.")
    else:
        print("  [✗] Failed to patch launcher_config.")

    # 3. Patch stb_config (Screensaver ads)
    print("\n── 3. Applying stb_config (Killing Screensaver Ads) ────────────────")
    stb_updates = {
        "stb_dream_source_ads": 0,
        "stb_dream_source_show": 0
    }
    if patch_json_blob(adb, target, "stb_config", stb_updates, backup_dir):
        print("  [✓] stb_config patched and written successfully.")
    else:
        print("  [✗] Failed to patch stb_config.")

    # 4. Optional OTA package disabling
    if args.disable_ota:
        print("\n── 4. Disabling Iwedia OTA Updaters ───────────────────────────────")
        ota_pkgs = [
            "com.iwedia.httpupdate",
            "com.iwedia.updateservice",
            "com.iwedia.pvodupdateservice",
            "com.iwedia.updatercuotaservice"
        ]
        for pkg in ota_pkgs:
            c, out, _ = run_adb(adb, target, ["shell", f"pm disable-user --user 0 {pkg} 2>/dev/null || pm disable {pkg} 2>/dev/null"])
            print(f"  [*] Disabled {pkg}: {out or 'OK'}")

    # 5. Verify Applied Settings
    print("\n── 5. Verifying Applied Settings ──────────────────────────────────")
    l_ok, l_res = verify_json_blob(adb, target, "launcher_config", launcher_updates)
    for k, (ok, got, want) in l_res.items():
        status = "[✓]" if ok else "[✗]"
        print(f"  {status} launcher_config.{k:<25} = {got} (Expected: {want})")

    s_ok, s_res = verify_json_blob(adb, target, "stb_config", stb_updates)
    for k, (ok, got, want) in s_res.items():
        status = "[✓]" if ok else "[✗]"
        print(f"  {status} stb_config.{k:<25} = {got} (Expected: {want})")

    print("\n" + "=" * 65)
    if l_ok and s_ok:
        print("  [SUCCESS] All ad-killing configurations are active on the STB!")
        print("            - JioTV+ Live Channels: ZERO 15s pre-roll video ads.")
        print("            - Home Screen: Clean, no banner promotions.")
        print("            - Screensaver: Clean, no sponsored posters.")
    else:
        print("  [!] Some settings could not be verified. Check ADB permissions.")
    print("=" * 65)

if __name__ == "__main__":
    main()
