#!/bin/bash
# ============================================================================
# stb_check.sh — verify + re-apply JioSTB ad/preroll/screensaver config
#
# Usage:  ./stb_check.sh <STB_IP> [adb_port]
#   e.g.  ./stb_check.sh 192.168.29.72
#
# Does everything we check by hand after a reboot / IP change / config push:
#   1. Connect ADB to the STB
#   2. Verify DNS resolves through the Pi/AdGuard
#        acs.oss.jio.com  -> Pi IP            (ACS interception)
#        jtvp.cms.jio.com -> 0.0.0.0/127.*    (blocked)
#        siglyapi.jio.com -> 0.0.0.0/127.*    (blocked)
#   3. Integrity: tr069exec root, ad service gone, OTA pkgs disabled
#   4. (Re-)apply launcher_config  (preroll / ads off)
#   5. (Re-)apply stb_config       (screensaver ads/show off)
#   6. Verify the applied values
#
# Idempotent — safe to run repeatedly. Needs: adb, python3, and the Pi running
# AdGuard + passfront (see restart_services.sh).
# ============================================================================

set -uo pipefail

STB_IP="${1:-}"
ADB_PORT="${2:-5555}"
if [ -z "$STB_IP" ]; then
    echo "Usage: $0 <STB_IP> [adb_port]"; exit 1
fi
DEV="${STB_IP}:${ADB_PORT}"
ADB="adb -s $DEV"
DEX="/data/local/tmp/tr069exec.dex"

GRN='\033[0;32m'; YLW='\033[1;33m'; RED='\033[0;31m'; CYN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "  ${GRN}✓${NC} $*"; }
warn() { echo -e "  ${YLW}!${NC} $*"; }
bad()  { echo -e "  ${RED}✗${NC} $*"; }
hdr()  { echo -e "\n${CYN}== $* ==${NC}"; }

# Pi's own eth0 IP — used to confirm acs.oss.jio.com points back at us
PI_IP=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)

# ── 1. Connect ───────────────────────────────────────────────────────────────
hdr "Connect"
adb connect "$DEV" >/dev/null 2>&1
if [ "$($ADB get-state 2>/dev/null)" != "device" ]; then
    bad "ADB not connected / unauthorized on $DEV"; exit 1
fi
ok "ADB connected: $DEV"

# ── 2. DNS resolution ─────────────────────────────────────────────────────────
hdr "DNS resolution (via router -> Pi/AdGuard)"
resolve() {  # prints the IP the STB resolves $1 to (via ping), or empty
    # ping line: "PING host (1.2.3.4) 56(84) bytes of data." — want the FIRST
    # parenthesized group (the IP), not the "56(84)" payload size.
    $ADB shell "ping -c1 -W2 $1 2>/dev/null" 2>/dev/null \
        | awk -F'[()]' 'NR==1{print $2; exit}'
}
ACS_IP=$(resolve acs.oss.jio.com)
JTVP_IP=$(resolve jtvp.cms.jio.com)
SIGLY_IP=$(resolve siglyapi.jio.com)
GOOG_IP=$(resolve google.com)

[ "$ACS_IP" = "$PI_IP" ] && ok "acs.oss.jio.com -> $ACS_IP (Pi)" \
    || bad "acs.oss.jio.com -> '${ACS_IP:-none}' (expected Pi $PI_IP) — DNS not routed through us!"

is_blocked() { case "$1" in 0.0.0.0|127.*) return 0;; *) return 1;; esac; }
is_blocked "$JTVP_IP"  && ok "jtvp.cms.jio.com -> $JTVP_IP (blocked)" \
    || bad "jtvp.cms.jio.com -> '${JTVP_IP:-none}' (NOT blocked — real IP leaking!)"
is_blocked "$SIGLY_IP" && ok "siglyapi.jio.com -> $SIGLY_IP (blocked)" \
    || bad "siglyapi.jio.com -> '${SIGLY_IP:-none}' (NOT blocked — real IP leaking!)"
[ -n "$GOOG_IP" ] && ! is_blocked "$GOOG_IP" && ok "google.com -> $GOOG_IP (normal)" \
    || warn "google.com -> '${GOOG_IP:-none}' (general DNS may be broken)"

# ── 3. Integrity ──────────────────────────────────────────────────────────────
hdr "Integrity (root / packages)"
ROOT_ID=$($ADB shell "CLASSPATH=$DEX /system/bin/app_process / TR069Exec 'id'" 2>/dev/null | grep -o 'uid=0(root)' | head -1)
[ -n "$ROOT_ID" ] && ok "tr069exec root works (uid=0)" || bad "tr069exec root NOT working — dex missing? ($DEX)"

AD_PKG=$($ADB shell "pm list packages com.jio.stbadservice 2>/dev/null" 2>/dev/null)
[ -z "$AD_PKG" ] && ok "ad service com.jio.stbadservice removed" || warn "ad service still installed: $AD_PKG"

for p in com.iwedia.httpupdate com.iwedia.updateservice com.iwedia.pvodupdateservice com.iwedia.updatercuotaservice; do
    if $ADB shell "pm list packages -d $p 2>/dev/null" 2>/dev/null | grep -q "$p"; then
        ok "OTA pkg disabled: $p"
    else
        if $ADB shell "pm list packages $p 2>/dev/null" 2>/dev/null | grep -q "$p"; then
            warn "OTA pkg ENABLED (expected disabled): $p"
        fi  # not present at all => nothing to do
    fi
done

# ── 4+5. Apply config blobs ───────────────────────────────────────────────────
# $1 = Settings.Global key, $2 = python dict of key:value updates
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
if not raw or raw == 'null':
    sys.exit(3)
d = json.loads(raw)
d.update(updates)
json.dump(d, open(path, 'w'), separators=(',', ':'))
PY
    then
        bad "$key: could not parse/patch (empty or invalid) — skipped"
        rm -f "$tmp"; return 1
    fi
    $ADB push "$tmp" "$rem" >/dev/null 2>&1
    $ADB shell "settings put global $key \"\$(cat $rem)\"" 2>/dev/null
    rm -f "$tmp"
    return 0
}

hdr "Apply launcher_config (preroll / ads off)"
apply_blob launcher_config "{'disable_preroll_video':True,'pre_roll_ads':0,'sigly_event':False,'jio_ads_promotion':0,'other_ads_promotion':0,'isPreroll_info_enabled':False,'disable_preroll_analytics':True}" \
    && ok "launcher_config written"

hdr "Apply stb_config (screensaver ads/show off)"
apply_blob stb_config "{'stb_dream_source_ads':0,'stb_dream_source_show':0}" \
    && ok "stb_config written"

# ── 6. Verify applied values ──────────────────────────────────────────────────
hdr "Verify applied values"
verify_blob() {  # $1 key, $2 space-separated key=expected pairs
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

echo -e "\n${GRN}Done.${NC} If any DNS line is red, fix routing first (STB must use the Pi for DNS),"
echo    "then re-run — the config writes only stick while jtvp.cms.jio.com is blocked."
