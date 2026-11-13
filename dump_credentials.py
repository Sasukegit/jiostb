"""
Dump Jio STB TR-069 Credentials via ADB
Extracts device Serial Number and ro.acsdata, derives the CPE Digest password,
and writes device_credentials.json for standalone PC-to-ACS querying.
"""

import subprocess
import hashlib
import base64
import json
import os
import sys

SECRET_KEY = "Hee4Xeigaethaeye"

def get_adb_binary():
    local_adb = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "adb.exe")
    if os.path.exists(local_adb):
        return local_adb
    return "adb"

ADB_BIN = get_adb_binary()

def run_adb(cmd):
    try:
        res = subprocess.run([ADB_BIN, "shell", cmd], capture_output=True, text=True, timeout=8)
        return res.stdout.strip()
    except Exception as e:
        return ""

def main():
    print("=" * 60)
    print("  Jio STB Device Credentials Extractor")
    print(f"  Using ADB: {ADB_BIN}")
    print("=" * 60)

    # Check adb devices
    try:
        devs = subprocess.run([ADB_BIN, "devices"], capture_output=True, text=True).stdout
        print(devs)
        if "device\n" not in devs and "\tdevice" not in devs:
            print("[-] No active ADB device found. Ensure STB is connected via ADB:")
            print("    adb connect <STB_IP>:5555")
            input("\nPress Enter to exit...")
            sys.exit(1)
    except Exception as e:
        print(f"[-] ADB error: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)

    serial = run_adb("getprop ro.serialno")
    if not serial:
        serial = subprocess.run([ADB_BIN, "get-serialno"], capture_output=True, text=True).stdout.strip()

    model = run_adb("getprop ro.product.model")
    device = run_adb("getprop ro.product.device")
    sw_version = run_adb("getprop ro.build.display.id")
    acsdata = run_adb("getprop ro.acsdata")

    print(f"[+] Device Serial:   {serial}")
    print(f"[+] Product Model:   {model} ({device})")
    print(f"[+] Current Version: {sw_version}")
    print(f"[+] ro.acsdata:      {acsdata}")

    if not acsdata:
        print("[!] ro.acsdata is empty via getprop. Using default prepassword.")
        acsdata = "9e434fa86d4f6ac7"

    combined = (acsdata + SECRET_KEY).encode("utf-8")
    sha_hash = hashlib.sha256(combined).digest()
    cpe_password = base64.b64encode(sha_hash[:16]).decode("utf-8").strip()

    print(f"[+] Derived CPE PW:  {cpe_password}")

    creds = {
        "serial_number": serial,
        "ro_acsdata": acsdata,
        "cpe_password": cpe_password,
        "model": model,
        "device": device,
        "software_version": sw_version
    }

    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "device_credentials.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(creds, f, indent=2)

    print(f"\n[+] Credentials saved to: {out_file}")
    print("[+] Standalone PC tool (query_acs_direct.py) will now use this device's profile!")
    print("=" * 60)

if __name__ == "__main__":
    main()
