"""
Standalone Jio ACS Query Tool
Allows checking Jio TR-069 ACS for firmware updates and RPC commands
completely from the PC without requiring the physical STB.

CPE Credentials derived via reverse engineering of libtr069client & TR069ClientService:
- Username: Device Serial Number (e.g. from `getprop ro.serialno`)
- Prepassword: Device ro.acsdata (from `getprop ro.acsdata`)
- Native Secret Key (libcpe): Hee4Xeigaethaeye
- Derived Password: Base64(SHA256(prepassword + secret)[:16])

Run EXTRACT_CREDENTIALS.bat once while connected via ADB to generate device_credentials.json!
"""

import os
import json
import sys
import hashlib
import base64
import requests
from requests.auth import HTTPDigestAuth
import urllib3
urllib3.disable_warnings()

REAL_ACS_URL = "https://49.40.134.113:8443/ftacs-digest/ACS"
REAL_ACS_HOST = "acs.oss.jio.com:8443"
SERIAL_NUMBER = None
CPE_PASSWORD = None
PRODUCT_CLASS = "JHSD200"

# Check for local device credentials file
creds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "device_credentials.json")
if os.path.exists(creds_path):
    try:
        with open(creds_path, "r", encoding="utf-8") as f:
            creds = json.load(f)
            SERIAL_NUMBER = creds.get("serial_number")
            CPE_PASSWORD = creds.get("cpe_password")
            PRODUCT_CLASS = creds.get("model", PRODUCT_CLASS)
            print(f"[i] Loaded credentials from device_credentials.json for {SERIAL_NUMBER} ({PRODUCT_CLASS})")
    except Exception as e:
        print(f"[!] Warning reading device_credentials.json: {e}")

if not SERIAL_NUMBER or not CPE_PASSWORD:
    print("=" * 60)
    print("  NO SAVED DEVICE CREDENTIALS FOUND (device_credentials.json)")
    print("  You can generate it automatically by connecting your STB via ADB")
    print("  and running: EXTRACT_CREDENTIALS.bat")
    print("=" * 60)
    s_input = input("Enter your STB Serial Number (or press Enter to exit): ").strip()
    if not s_input:
        sys.exit(0)
    acs_input = input("Enter ro.acsdata (press Enter for default '9e434fa86d4f6ac7'): ").strip()
    if not acs_input:
        acs_input = "9e434fa86d4f6ac7"
    SERIAL_NUMBER = s_input
    # Derive password
    combined = (acs_input + "Hee4Xeigaethaeye").encode("utf-8")
    CPE_PASSWORD = base64.b64encode(hashlib.sha256(combined).digest()[:16]).decode("utf-8").strip()
    print(f"[+] Computed CPE Digest Password: {CPE_PASSWORD}")

HEADERS = {
    "Host": REAL_ACS_HOST,
    "User-Agent": "curl/7.69.1",
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": '""'
}

def query_acs(software_version="STB-JHSD200-11.1.0"):
    print("=" * 60)
    print("  JIO STB STANDALONE ACS QUERY")
    print(f"  Target Serial:   {SERIAL_NUMBER}")
    print(f"  Product Class:   {PRODUCT_CLASS}")
    print(f"  Spoofed Version: {software_version}")
    print(f"  ACS Endpoint:    {REAL_ACS_URL}")
    print("=" * 60)

    inform_body = f"""<soap-env:Envelope xmlns:soap-enc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
<soap-env:Header><cwmp:ID soap-env:mustUnderstand="1">0</cwmp:ID></soap-env:Header>
<soap-env:Body><cwmp:Inform>
<DeviceId><Manufacturer>Reliance Jio</Manufacturer><OUI>000000</OUI><ProductClass>{PRODUCT_CLASS}</ProductClass><SerialNumber>{SERIAL_NUMBER}</SerialNumber></DeviceId>
<Event soap-enc:arrayType="cwmp:EventStruct[1]"><EventStruct><EventCode>6 CONNECTION REQUEST</EventCode><CommandKey/></EventStruct></Event>
<MaxEnvelopes>1</MaxEnvelopes><CurrentTime>2026-11-13T23:00:00+05:30</CurrentTime><RetryCount>0</RetryCount>
<ParameterList soap-enc:arrayType="cwmp:ParameterValueStruct[4]">
<ParameterValueStruct><Name>Device.DeviceInfo.HardwareVersion</Name><Value xsi:type="xsd:string">amlogic</Value></ParameterValueStruct>
<ParameterValueStruct><Name>Device.DeviceInfo.SoftwareVersion</Name><Value xsi:type="xsd:string">{software_version}</Value></ParameterValueStruct>
<ParameterValueStruct><Name>Device.ManagementServer.ConnectionRequestURL</Name><Value xsi:type="xsd:string">http://192.168.50.2:7547/641D93D0F90DCE99.html</Value></ParameterValueStruct>
<ParameterValueStruct><Name>Device.ManagementServer.ParameterKey</Name><Value xsi:type="xsd:string">7174098644</Value></ParameterValueStruct>
</ParameterList></cwmp:Inform></soap-env:Body></soap-env:Envelope>"""

    auth = HTTPDigestAuth(SERIAL_NUMBER, CPE_PASSWORD)
    session = requests.Session()

    print("[1] Sending cwmp:Inform to Real Jio ACS...")
    try:
        r = session.post(REAL_ACS_URL, data=inform_body, headers=HEADERS, auth=auth, verify=False, timeout=12)
    except Exception as e:
        print(f"[-] Connection Error: {e}")
        return

    print(f"    ACS Response Code: {r.status_code}")
    if r.status_code != 200:
        print(f"[-] Authentication/Server Failed: {r.text[:300]}")
        return

    print("[+] Digest Authentication Successful! cwmp:InformResponse received.")

    next_body = ""
    step = 2
    while True:
        try:
            r = session.post(REAL_ACS_URL, data=next_body, headers=HEADERS, auth=auth, verify=False, timeout=12)
        except Exception as e:
            print(f"[-] Session error: {e}")
            break

        print(f"[{step}] ACS Response Code: {r.status_code}")
        if r.status_code == 204:
            print("[+] ACS returned 204 No Content -> Session ended cleanly (No further RPCs).")
            break
        elif r.status_code == 200:
            resp_xml = r.text
            print(f"    Payload Received ({len(resp_xml)} bytes):")
            print(resp_xml)

            if "Download" in resp_xml:
                print("\n" + "!" * 60)
                print(">>> [ALERT] FIRMWARE DOWNLOAD RPC (cwmp:Download) FOUND!")
                print("!" * 60 + "\n")

            cwmp_id = "0"
            if "<cwmp:ID" in resp_xml:
                try:
                    cwmp_id = resp_xml.split("<cwmp:ID")[1].split(">")[1].split("</cwmp:ID>")[0]
                except Exception:
                    pass

            if "SetParameterValues" in resp_xml:
                next_body = f"""<soap-env:Envelope xmlns:soap-enc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
<soap-env:Header><cwmp:ID soap-env:mustUnderstand="1">{cwmp_id}</cwmp:ID></soap-env:Header>
<soap-env:Body><cwmp:SetParameterValuesResponse><Status>0</Status></cwmp:SetParameterValuesResponse></soap-env:Body></soap-env:Envelope>"""
            elif "GetParameterValues" in resp_xml:
                next_body = f"""<soap-env:Envelope xmlns:soap-enc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
<soap-env:Header><cwmp:ID soap-env:mustUnderstand="1">{cwmp_id}</cwmp:ID></soap-env:Header>
<soap-env:Body><cwmp:GetParameterValuesResponse><ParameterList soap-enc:arrayType="cwmp:ParameterValueStruct[0]"/></cwmp:GetParameterValuesResponse></soap-env:Body></soap-env:Envelope>"""
            else:
                next_body = ""
            step += 1
        else:
            print(f"[-] Unexpected Status: {r.status_code}")
            break

if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else "STB-JHSD200-11.1.0"
    query_acs(version)
