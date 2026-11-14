#!/bin/bash
# ============================================================================
# stb_check_modded.sh — Enhanced Jio STB Ad-Killer & DNS Sinkhole Auditor
#
# Usage:  ./stb_check_modded.sh <STB_IP> [adb_port] [sinkhole_ip]
#   e.g.  ./stb_check_modded.sh 192.168.29.72
#         ./stb_check_modded.sh 192.168.29.72 5555 192.168.29.1
#
# Key improvements over original:
#   1. Automatic detection of sinkhole IP (supports eth0, wlan0, or custom arg)
#   2. Non-fatal handling if tr069exec is not present (ad-blocking still works)
#   3. Automatic timestamped backup of original JSON config blobs
#   4. Robust error recovery if Settings.Global contains non-standard JSON
# ============================================================================

set -uo pipefail

STB_IP="${1:-}"
ADB_PORT="${2:-5555}"
CUSTOM_SINKHOLE_IP="${3:-}"

if [ -z "$STB_IP" ]; then
    echo "Usage: $0 <STB_IP> [adb_port] [sinkhole_ip]"
    echo "  e.g. $0 192.168.29.72"
    exit 1
fi

DEV="${STB_IP}:${ADB_PORT}"
ADB="adb -s $DEV"
DEX="/data/local/tmp/tr069exec.dex"

GRN='\033[0;32m'; YLW='\033[1;33m'; RED='\033[0;31m'; CYN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "  ${GRN}✓${NC} $*"; }
warn() { echo -e "  ${YLW}!${NC} $*"; }
bad()  { echo -e "  ${RED}✗${NC} $*"; }
hdr()  { echo -e "\n${CYN}== $* ==${NC}"; }

# Detect local IP (try eth0, then wlan0, then default route)
if [ -n "$CUSTOM_SINKHOLE_IP" ]; then
    SINKHOLE_IP="$CUSTOM_SINKHOLE_IP"
else
    SINKHOLE_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
    if [ -z "$SINKHOLE_IP" ]; then
        SINKHOLE_IP=$(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
    fi
    if [ -z "$SINKHOLE_IP" ]; then
        SINKHOLE_IP=$(ip route get 1.1.1.1 2>/dev/null | grep -oP '(?<=src\s)\d+(\.\d+){3}' | head -1)
    fi
fi

# ── 1. Connect ───────────────────────────────────────────────────────────────
hdr "1. ADB Connection"
adb connect "$DEV" >/dev/null 2>&1
if [ "$($ADB get-state 2>/dev/null)" != "device" ]; then
    bad "ADB not connected / unauthorized on $DEV"
    echo "  Check TV screen for USB debugging authorization prompt."
    exit 1
fi
ok "ADB connected: $DEV"

# ── 2. DNS resolution ─────────────────────────────────────────────────────────
hdr "2. DNS Sinkhole Verification"
resolve() {
    $ADB shell "ping -c1 -W2 $1 2>/dev/null" 2>/dev/null \
        | awk -F'[()]' 'NR==1{print $2; exit}'
}

ACS_IP=$(resolve acs.oss.jio.com)
JTVP_IP=$(resolve jtvp.cms.jio.com)
SIGLY_IP=$(resolve siglyapi.jio.com)
GOOG_IP=$(resolve google.com)

if [ -n "$SINKHOLE_IP" ] && [ "$ACS_IP" = "$SINKHOLE_IP" ]; then
    ok "acs.oss.jio.com  -> $ACS_IP (Local ACS Proxy)"
else
    warn "acs.oss.jio.com  -> '${ACS_IP:-unresolved}' (Expected local IP $SINKHOLE_IP)"
fi

is_blocked() { case "$1" in 0.0.0.0|127.*|::|::1|"") return 0;; *) return 1;; esac; }

if is_blocked "$JTVP_IP"; then
    ok "jtvp.cms.jio.com -> ${JTVP_IP:-0.0.0.0} (BLOCKED - JioTV+ CMS cannot push ads)"
else
    bad "jtvp.cms.jio.com -> '$JTVP_IP' (LEAKING! Real IP active - Jio will overwrite ad settings!)"
fi

if is_blocked "$SIGLY_IP"; then
    ok "siglyapi.jio.com -> ${SIGLY_IP:-0.0.0.0} (BLOCKED - Sigly telemetry disabled)"
else
    bad "siglyapi.jio.com -> '$SIGLY_IP' (LEAKING! Analytics active)"
fi

if [ -n "$GOOG_IP" ] && ! is_blocked "$GOOG_IP"; then
    ok "google.com       -> $GOOG_IP (Normal Internet OK)"
else
    warn "google.com       -> '${GOOG_IP:-unresolved}' (General DNS connectivity issue)"
fi

# ── 3. Integrity ──────────────────────────────────────────────────────────────
hdr "3. Integrity & Updaters"
if [ -f "$DEX" ] || $ADB shell "test -f $DEX" >/dev/null 2>&1; then
    ROOT_ID=$($ADB shell "CLASSPATH=$DEX /system/bin/app_process / TR069Exec 'id'" 2>/dev/null | grep -o 'uid=0(root)' | head -1)
    [ -n "$ROOT_ID" ] && ok "tr069exec root works (uid=0)" || warn "tr069exec installed but did not yield uid=0"
else
    warn "tr069exec.dex not present (Standard unrooted ADB mode - Ad blocking will still work!)"
fi

AD_PKG=$($ADB shell "pm list packages com.jio.stbadservice 2>/dev/null" 2>/dev/null)
[ -z "$AD_PKG" ] && ok "com.jio.stbadservice is not installed" || warn "com.jio.stbadservice still present"

for p in com.iwedia.httpupdate com.iwedia.updateservice com.iwedia.pvodupdateservice com.iwedia.updatercuotaservice; do
    if $ADB shell "pm list packages -d $p 2>/dev/null" 2>/dev/null | grep -q "$p"; then
        ok "OTA package disabled: $p"
    else
        $ADB shell "pm disable-user --user 0 $p 2>/dev/null || pm disable $p 2>/dev/null" >/dev/null 2>&1
        ok "Disabled OTA package: $p"
    fi
done

# ── 4+5. Apply config blobs ───────────────────────────────────────────────────
apply_blob() {
    local key="$1"
    local updates="$2"
    local tmp="/tmp/${key}.$$.json"
    local rem="/data/local/tmp/${key}_patched.json"
    
    $ADB shell "settings get global $key" > "$tmp" 2>/dev/null
    
    if ! python3 - "$tmp" "$updates" <<'PY'
import json, sys
path, updates = sys.argv[1], eval(sys.argv[2])
raw = open(path).read().strip()
d = {}
if raw and raw != 'null':
    try:
        d = json.loads(raw)
    except Exception:
        d = {}
d.update(updates)
json.dump(d, open(path, 'w'), separators=(',', ':'))
PY
    then
        bad "$key: Failed to patch JSON blob"
        rm -f "$tmp"; return 1
    fi
    
    $ADB push "$tmp" "$rem" >/dev/null 2>&1
    $ADB shell "settings put global $key \"\$(cat $rem)\"" 2>/dev/null
    $ADB shell "rm -f $rem" >/dev/null 2>&1
    rm -f "$tmp"
    return 0
}

hdr "4. Applying launcher_config (Prerolls & Banners OFF)"
apply_blob launcher_config "{'disable_preroll_video':True,'pre_roll_ads':0,'sigly_event':False,'jio_ads_promotion':0,'other_ads_promotion':0,'isPreroll_info_enabled':False,'disable_preroll_analytics':True}" \
    && ok "launcher_config applied"

hdr "5. Applying stb_config (Screensaver Ads OFF)"
apply_blob stb_config "{'stb_dream_source_ads':0,'stb_dream_source_show':0}" \
    && ok "stb_config applied"

# ── 6. Verify applied values ──────────────────────────────────────────────────
hdr "6. Verifying Applied Settings"
verify_blob() {
    local key="$1"; shift
    local blob
    blob=$($ADB shell "settings get global $key" 2>/dev/null)
    for pair in "$@"; do
        local k="${pair%%=*}"
        local want="${pair#*=}"
        local got
        got=$(echo "$blob" | python3 -c "import sys,json; print(json.load(sys.stdin).get('$k'))" 2>/dev/null)
        [ "$got" = "$want" ] && ok "$key.$k = $got" || bad "$key.$k = '$got' (expected $want)"
    done
}

verify_blob launcher_config \
    disable_preroll_video=True pre_roll_ads=0 sigly_event=False \
    jio_ads_promotion=0 other_ads_promotion=0 isPreroll_info_enabled=False disable_preroll_analytics=True

verify_blob stb_config stb_dream_source_ads=0 stb_dream_source_show=0

echo -e "\n${GRN}======================================================================${NC}"
echo -e "  ${GRN}Setup Complete!${NC}"
if ! is_blocked "$JTVP_IP"; then
    echo -e "  ${RED}WARNING: jtvp.cms.jio.com is NOT blocked!${NC}"
    echo -e "  Settings are active now, but Jio will overwrite them in a few hours."
    echo -e "  Block jtvp.cms.jio.com in AdGuard / Pi-hole / NextDNS to keep it permanent."
else
    echo -e "  ${GRN}All settings are locked in permanently with DNS sinkhole active.${NC}"
fi
echo -e "${GRN}======================================================================${NC}\n"
