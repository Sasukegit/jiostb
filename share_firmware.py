"""
Helper script to share newly discovered firmware download URLs to the catalog.
Ensures zero personal information or device serials are ever shared.
"""

import os
import json
import urllib.parse
import webbrowser

BASE = os.path.dirname(os.path.abspath(__file__))
FOUND_JSON = os.path.join(BASE, "fota_update_found.json")
FOUND_TXT = os.path.join(BASE, "fota_firmware_url.txt")

def main():
    print("=" * 60)
    print("  JIO STB FIRMWARE CATALOG SUBMISSION HELPER")
    print("=" * 60)

    url = None
    size = None
    target_name = None

    if os.path.exists(FOUND_JSON):
        try:
            with open(FOUND_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                url = data.get("url")
                size = data.get("file_size")
                target_name = data.get("target_name")
        except Exception:
            pass

    if not url and os.path.exists(FOUND_TXT):
        try:
            with open(FOUND_TXT, "r", encoding="utf-8") as f:
                url = f.read().strip()
        except Exception:
            pass

    if not url:
        print("[-] No newly captured firmware update found yet.")
        print("    Run CAPTURE_FIRMWARE_ETHERNET.bat or QUERY_JIO_ACS.bat first to discover a URL!")
        url_input = input("\nOr manually paste a Jio FOTA URL to format a report: ").strip()
        if not url_input:
            input("\nPress Enter to exit...")
            return
        url = url_input

    print(f"\n[+] Discovered Firmware URL:\n    {url}")
    if size:
        print(f"[+] Reported File Size: {size} bytes ({int(size)/1024/1024:.2f} MB)")
    if target_name:
        print(f"[+] Target File Name:   {target_name}")

    print("\n" + "-" * 60)
    print("PRIVACY & DISCLOSURE NOTICE:")
    print("Only the public Akamai download URL, file size, and target model will be")
    print("included in the report. Your device serial number and personal credentials")
    print("are NEVER transmitted or shared.")
    print("-" * 60)

    title = f"[New Firmware Discovered] {url.split('/')[-1]}"
    body = f"""### New Jio Firmware Discovery

* **Firmware URL:** `{url}`
* **File Size:** `{size if size else 'Unknown'}` bytes
* **Target File:** `{target_name if target_name else 'Unknown'}`

*Submitted via Jio STB Master Toolkit.*
"""

    confirm = input("\nWould you like to open GitHub in your browser to submit this URL? (y/n): ").strip().lower()
    if confirm == "y":
        repo_url = "https://github.com/krishnasen/jio-fota-toolkit/issues/new"
        params = urllib.parse.urlencode({
            "title": title,
            "body": body
        })
        full_url = f"{repo_url}?{params}"
        print(f"\n[+] Opening web browser: {full_url}")
        webbrowser.open(full_url)
    else:
        print("\nSubmission cancelled. The report details are printed above.")

    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
