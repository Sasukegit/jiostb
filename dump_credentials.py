"""
Dump Jio STB TR-069 Credentials via ADB
Extracts device Serial Number and ro.acsdata, derives the CPE Digest password,
and writes device_credentials.json for standalone PC-to-ACS querying.

Supports all 3 hardware vendors (SDMC, Bluebank, Skyworth) using their
proprietary manufacturer secret keys (sk).
"""

import subprocess
import hashlib
import base64
import json
import os
import sys

MANUFACTURER_KEYS = {
    "SDMC": "DahWaethuL9xoo3e",      # JHSD200, JMSD200, etc.
    "Bluebank": "Hee4Xeigaethaeye",  # JHSB200, JMSB200, etc.
    "Skyworth": "Rov5Ifozoobeeth8",  # JHSC200, JMSC200, etc.
}

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

def detect_vendor(model, device, manufacturer):
    combined = f"{model} {device} {manufacturer}".upper()
    if any(k in combined for k in ["JHSD", "JMSD", "SDMC"]):
        return "SDMC"
    elif any(k in combined for k in ["JHSC", "JMSC", "SKYWORTH"]):
        return "Skyworth"
    elif any(k in combined for k in ["JHSB", "JMSB", "BLUEBANK"]):
        return "Bluebank"
    return "SDMC"

def derive_cpe_password(acsdata, secret_key):
    combined = (acsdata + secret_key).encode("utf-8")
    sha_hash = hashlib.sha256(combined).digest()
    return base64.b64encode(sha_hash[:16]).decode("utf-8").strip()

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
    manufacturer = run_adb("getprop ro.product.manufacturer")
    sw_version = run_adb("getprop ro.build.display.id")
    acsdata = run_adb("getprop ro.acsdata")

    vendor = detect_vendor(model, device, manufacturer)
    secret_key = MANUFACTURER_KEYS.get(vendor, MANUFACTURER_KEYS["SDMC"])

    print(f"[+] Device Serial:   {serial}")
    print(f"[+] Product Model:   {model} ({device})")
    print(f"[+] Manufacturer:    {manufacturer} -> Detected: {vendor}")
    print(f"[+] Current Version: {sw_version}")
    print(f"[+] ro.acsdata:      {acsdata}")
    print(f"[+] Secret Key (sk): {secret_key}")

    if not acsdata:
        print("[!] ro.acsdata is empty via getprop. Using default prepassword.")
        acsdata = "9e434fa86d4f6ac7"

    cpe_password = derive_cpe_password(acsdata, secret_key)
    print(f"[+] Derived CPE PW:  {cpe_password}")

    # Compute passwords for all vendors for reference
    all_passwords = {v: derive_cpe_password(acsdata, k) for v, k in MANUFACTURER_KEYS.items()}

    creds = {
        "serial_number": serial,
        "ro_acsdata": acsdata,
        "vendor": vendor,
        "secret_key": secret_key,
        "cpe_password": cpe_password,
        "all_vendor_passwords": all_passwords,
        "model": model,
        "device": device,
        "manufacturer": manufacturer,
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
