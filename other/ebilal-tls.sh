#!/bin/bash
# eBilal local HTTPS certificates.
#
# Browsers only treat a page as a "secure context" (needed for the installable
# PWA, and to avoid the "Not secure" warning) over trusted HTTPS. eBilal lives on
# a home LAN with no public domain, so each device gets its OWN small
# certificate authority:
#
#   ca.crt      generated once, 10 years. Users trust it once per phone/laptop
#               via the setup page (http://<host>.local/trust.html).
#   server.crt  signed by that CA for <host>.local + the device's LAN IPs.
#               Re-issued automatically when it nears expiry or the IP/hostname
#               changes. Users never notice.
#
# Safety: the CA is NAME-CONSTRAINED (critical) to .local / localhost and the
# private IPv4 ranges. Even if this device's CA key were stolen, it could not be
# used to impersonate any public website to the phones that trust it.
#
# Usage: ebilal-tls [--force]          (run as root; idempotent)
#   EBILAL_TLS_DIR    private output directory (default /var/lib/ebilal/tls)
#   EBILAL_TLS_PUBLIC public files for the setup page (default /var/lib/ebilal/ca-public)
set -euo pipefail

DIR="${EBILAL_TLS_DIR:-/var/lib/ebilal/tls}"      # private: root only
# Public bits served at /ca/. Kept OUTSIDE $DIR because nginx workers (www-data)
# cannot traverse the root-only private directory.
PUB="${EBILAL_TLS_PUBLIC:-$(dirname "$DIR")/ca-public}"
HOST="$(hostname -s)"
FQDN="${HOST}.local"
LEAF_DAYS=397                  # within every browser's maximum for leaf certs
RENEW_DAYS=30
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

log() { echo "ebilal-tls: $*"; }

mkdir -p "$DIR" "$PUB"
chmod 755 "$(dirname "$DIR")"
chmod 700 "$DIR"
chmod 755 "$PUB"
umask 077

# Private LAN IPv4 addresses only (the CA cannot sign anything else anyway)
lan_ips() {
  hostname -I 2>/dev/null | tr ' ' '\n' |
    grep -E '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)[0-9.]+$' | sort -u || true
}

# ------------------------------------------------------------------ the CA
if [ ! -s "$DIR/ca.key" ] || [ ! -s "$DIR/ca.crt" ]; then
  log "creating local certificate authority for $FQDN"
  cat > "$DIR/ca.cnf" <<EOF
[req]
distinguished_name = dn
prompt = no
[dn]
CN = eBilal local CA ($HOST)
O = eBilal
[v3_ca]
basicConstraints = critical, CA:TRUE, pathlen:0
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
nameConstraints = critical, permitted;DNS:local, permitted;DNS:localhost, permitted;IP:10.0.0.0/255.0.0.0, permitted;IP:172.16.0.0/255.240.0.0, permitted;IP:192.168.0.0/255.255.0.0, permitted;IP:127.0.0.0/255.0.0.0
EOF
  openssl ecparam -name prime256v1 -genkey -noout -out "$DIR/ca.key"
  openssl req -x509 -new -sha256 -days 3650 -key "$DIR/ca.key" \
    -config "$DIR/ca.cnf" -extensions v3_ca -out "$DIR/ca.crt"
  FORCE=1  # a new CA needs a new leaf
fi

# ------------------------------------------- does the server cert need (re)issuing?
SANS="DNS:${FQDN},DNS:localhost,IP:127.0.0.1"
for ip in $(lan_ips); do SANS="${SANS},IP:${ip}"; done

need=0
if [ "$FORCE" = 1 ] || [ ! -s "$DIR/server.crt" ] || [ ! -s "$DIR/server.key" ]; then
  need=1
elif [ "$(cat "$DIR/server.sans" 2>/dev/null)" != "$SANS" ]; then
  log "hostname or IP changed"
  need=1
elif ! openssl x509 -checkend $((RENEW_DAYS * 86400)) -noout -in "$DIR/server.crt" >/dev/null; then
  log "certificate expires within $RENEW_DAYS days"
  need=1
fi

if [ "$need" = 1 ]; then
  log "issuing server certificate for $SANS"
  cat > "$DIR/server.ext" <<EOF
basicConstraints = critical, CA:FALSE
keyUsage = critical, digitalSignature
extendedKeyUsage = serverAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid
subjectAltName = $SANS
EOF
  openssl ecparam -name prime256v1 -genkey -noout -out "$DIR/server.key.new"
  openssl req -new -sha256 -key "$DIR/server.key.new" -subj "/CN=${FQDN}/O=eBilal" -out "$DIR/server.csr"
  openssl x509 -req -sha256 -days "$LEAF_DAYS" -in "$DIR/server.csr" \
    -CA "$DIR/ca.crt" -CAkey "$DIR/ca.key" -CAcreateserial -CAserial "$DIR/ca.srl" \
    -extfile "$DIR/server.ext" -out "$DIR/server.crt.new" 2>/dev/null
  openssl verify -CAfile "$DIR/ca.crt" "$DIR/server.crt.new" >/dev/null
  mv "$DIR/server.key.new" "$DIR/server.key"
  # nginx wants the chain: leaf first, then the CA
  cat "$DIR/server.crt.new" "$DIR/ca.crt" > "$DIR/server.crt"
  rm -f "$DIR/server.crt.new" "$DIR/server.csr"
  echo "$SANS" > "$DIR/server.sans"
  changed=1
else
  changed=0
fi

# ------------------------------------------- public files for the setup page
umask 022
install -m 0644 "$DIR/ca.crt" "$PUB/ebilal-ca.crt"  # Android, Windows, macOS, Linux
openssl x509 -in "$DIR/ca.crt" -outform der -out "$PUB/ebilal-ca.cer"
chmod 0644 "$PUB"/*
FP="$(openssl x509 -in "$DIR/ca.crt" -noout -fingerprint -sha256 | cut -d= -f2)"
echo "$FP" > "$PUB/fingerprint.txt"

# iOS/iPadOS configuration profile containing just the CA
if [ ! -s "$PUB/ebilal.mobileconfig" ] || [ "$PUB/ebilal.mobileconfig" -ot "$DIR/ca.crt" ]; then
  uuid() { cat /proc/sys/kernel/random/uuid 2>/dev/null || uuidgen; }
  DER_B64="$(openssl x509 -in "$DIR/ca.crt" -outform der | base64 | tr -d '\n')"
  cat > "$PUB/ebilal.mobileconfig" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>PayloadContent</key>
  <array>
    <dict>
      <key>PayloadCertificateFileName</key><string>ebilal-ca.cer</string>
      <key>PayloadContent</key><data>${DER_B64}</data>
      <key>PayloadDisplayName</key><string>eBilal local CA (${HOST})</string>
      <key>PayloadIdentifier</key><string>local.ebilal.${HOST}.ca</string>
      <key>PayloadType</key><string>com.apple.security.root</string>
      <key>PayloadUUID</key><string>$(uuid)</string>
      <key>PayloadVersion</key><integer>1</integer>
    </dict>
  </array>
  <key>PayloadDescription</key><string>Lets this device open your eBilal player at https://${FQDN} without a security warning. It can only vouch for local network addresses.</string>
  <key>PayloadDisplayName</key><string>eBilal (${HOST})</string>
  <key>PayloadIdentifier</key><string>local.ebilal.${HOST}</string>
  <key>PayloadType</key><string>Configuration</string>
  <key>PayloadUUID</key><string>$(uuid)</string>
  <key>PayloadVersion</key><integer>1</integer>
</dict>
</plist>
EOF
fi
chmod 0644 "$PUB"/*

if [ "$changed" = 1 ] && [ "${EBILAL_TLS_NO_RELOAD:-0}" = 0 ] && systemctl is-active --quiet nginx 2>/dev/null; then
  systemctl reload nginx
  log "nginx reloaded"
fi
log "ok ($FQDN, CA fingerprint $FP)"
