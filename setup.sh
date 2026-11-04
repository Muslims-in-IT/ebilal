#!/bin/bash
# eBilal installer.
#
#   curl -fsSL https://raw.githubusercontent.com/Muslims-in-IT/ebilal/main/setup.sh | sudo bash
#
# With options:
#   curl -fsSL .../setup.sh | sudo bash -s -- --pimoroni --hostname ebilal
#
# Works on Raspberry Pi OS, Debian and Ubuntu (any machine with systemd and an
# audio output). Safe to re-run: re-running upgrades the code and refreshes the
# system configuration, and never overwrites your settings.
#
# Options
#   --pimoroni        enable the Pimoroni pHAT BEAT (DAC, buttons, LEDs)
#   --hostname NAME   rename the device, so it is reachable at http://NAME.local/
#   --ref REF         install a branch or tag (default: the latest release)
#   --repo URL        install from another git repository
#   -h, --help        show this help
set -euo pipefail

REPO="https://github.com/Muslims-in-IT/ebilal.git"
REF=""
APP_DIR="/opt/ebilal"
APP_USER="ebilal"
PIMORONI=0
NEW_HOSTNAME=""

# ------------------------------------------------------------------ helpers
STEP=0
TOTAL=9
step() { STEP=$((STEP + 1)); printf '\n\033[1;36m[%d/%d]\033[0m %s\n' "$STEP" "$TOTAL" "$*"; }
info() { printf '      %s\n' "$*"; }
warn() { printf '\033[1;33m      ! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mError: %s\033[0m\n' "$*" >&2; exit 1; }
as_app() { sudo -u "$APP_USER" -H "$@"; }
usage() {
  cat <<'USAGE'
Usage: setup.sh [--pimoroni] [--hostname NAME] [--ref REF] [--repo URL]

  --pimoroni        enable the Pimoroni pHAT BEAT (DAC, buttons, LEDs)
  --hostname NAME   rename the device, so it is reachable at http://NAME.local/
  --ref REF         install a branch or tag (default: the latest release)
  --repo URL        install from another git repository
USAGE
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --pimoroni) PIMORONI=1 ;;
    --hostname) NEW_HOSTNAME="${2:?--hostname needs a name}"; shift ;;
    --ref)      REF="${2:?--ref needs a branch or tag}"; shift ;;
    --repo)     REPO="${2:?--repo needs a URL}"; shift ;;
    -h|--help)  usage ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

# ------------------------------------------------------------------ checks
[ "$(id -u)" -eq 0 ] || die "please run as root, e.g.  curl -fsSL <url>/setup.sh | sudo bash"
[ -f /etc/debian_version ] || die "this installer supports Debian-based systems (Raspberry Pi OS, Debian, Ubuntu)"
command -v systemctl >/dev/null || die "systemd is required"

if [ -n "$NEW_HOSTNAME" ] && ! [[ "$NEW_HOSTNAME" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]]; then
  die "hostname must be lowercase letters, digits and hyphens"
fi

IS_PI=0
grep -qi "raspberry pi" /proc/device-tree/model 2>/dev/null && IS_PI=1
BOOT_CONFIG=""
for f in /boot/firmware/config.txt /boot/config.txt; do
  [ -f "$f" ] && { BOOT_CONFIG="$f"; break; }
done
[ "$PIMORONI" = 1 ] && [ "$IS_PI" = 0 ] && die "--pimoroni needs a Raspberry Pi"

echo "eBilal installer"
info "device:   $( (tr -d '\0' < /proc/device-tree/model) 2>/dev/null || uname -m)"
info "pimoroni: $([ "$PIMORONI" = 1 ] && echo yes || echo no)"

# ------------------------------------------------------------------ 1. packages
step "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q --no-install-recommends \
  git ca-certificates python3 python3-venv python3-dev build-essential \
  libsystemd-dev pkg-config ffmpeg nginx openssl avahi-daemon iw curl

# ------------------------------------------------------------------ 2. hostname
step "Network name"
if [ -n "$NEW_HOSTNAME" ] && [ "$(hostname -s)" != "$NEW_HOSTNAME" ]; then
  OLD="$(hostname -s)"
  hostnamectl set-hostname "$NEW_HOSTNAME"
  sed -i "s/\b${OLD}\b/${NEW_HOSTNAME}/g" /etc/hosts
  grep -q "\b${NEW_HOSTNAME}\b" /etc/hosts || echo "127.0.1.1	${NEW_HOSTNAME}" >> /etc/hosts
  systemctl restart avahi-daemon || true
  info "renamed ${OLD} -> ${NEW_HOSTNAME}"
fi
systemctl enable --now avahi-daemon >/dev/null 2>&1 || true
info "reachable at http://$(hostname -s).local/"

# ------------------------------------------------------------------ 3. user
step "Service user"
id "$APP_USER" >/dev/null 2>&1 || adduser --system --group --home "/home/$APP_USER" --shell /usr/sbin/nologin "$APP_USER"
for g in audio users gpio input; do
  getent group "$g" >/dev/null && usermod -aG "$g" "$APP_USER"
done
info "user $APP_USER in: $(id -nG "$APP_USER")"

# ------------------------------------------------------------------ 4. code
step "Fetching eBilal"
if [ -d "$APP_DIR/.git" ]; then
  chown -R "$APP_USER:$APP_USER" "$APP_DIR"
  as_app git -C "$APP_DIR" fetch --tags --prune -q origin
else
  [ -e "$APP_DIR" ] && die "$APP_DIR exists but is not a git checkout; move it aside first"
  install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR"
  as_app git clone -q "$REPO" "$APP_DIR"
fi
if [ -z "$REF" ]; then
  # Latest release tag, falling back to the default branch if there are none
  REF="$(as_app git -C "$APP_DIR" tag --sort=-v:refname | head -n1)"
  [ -n "$REF" ] || REF="origin/HEAD"
fi
# Prefer a remote branch of that name, so re-runs pick up new commits
if as_app git -C "$APP_DIR" rev-parse -q --verify "origin/$REF" >/dev/null; then
  REF="origin/$REF"
fi
as_app git -C "$APP_DIR" -c advice.detachedHead=false checkout -q --force "$REF"
info "version $(as_app git -C "$APP_DIR" describe --tags --always)"

# ------------------------------------------------------------------ 5. python
step "Python environment (this is slow on a Pi Zero, a few minutes)"
[ -x "$APP_DIR/venv/bin/pip" ] || as_app python3 -m venv "$APP_DIR/venv"
as_app "$APP_DIR/venv/bin/pip" install -q --upgrade pip
as_app "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
if [ "$PIMORONI" = 1 ]; then
  as_app "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements-pimoroni.txt"
fi

# ------------------------------------------------------------------ 6. settings
step "Settings"
SETTINGS="$APP_DIR/settings.toml"
if [ ! -f "$SETTINGS" ]; then
  install -o "$APP_USER" -g "$APP_USER" -m 0644 "$APP_DIR/settings_example.toml" "$SETTINGS"
  info "created $SETTINGS"
else
  info "keeping your existing $SETTINGS"
fi
if [ "$PIMORONI" = 1 ]; then
  if grep -q '^pimoroni' "$SETTINGS"; then
    sed -i 's/^pimoroni *=.*/pimoroni = true/' "$SETTINGS"
  else
    sed -i '/^\[DEFAULT\]/a pimoroni = true' "$SETTINGS"
  fi
  info "pHAT BEAT buttons enabled"
fi

# ------------------------------------------------------------------ 7. services
step "System services"
install -m 0644 "$APP_DIR/other/ebilal.service" /etc/systemd/system/ebilal.service
# The old installer put it under /lib; a stale copy there would shadow nothing,
# but remove it to avoid confusion.
rm -f /lib/systemd/system/ebilal.service
# Lets the in-app updater restart the service without a password
install -m 0440 -o root -g root "$APP_DIR/other/ebilal-sudoers" /etc/sudoers.d/ebilal
visudo -cf /etc/sudoers.d/ebilal >/dev/null || { rm -f /etc/sudoers.d/ebilal; die "sudoers rule failed validation"; }

if [ -e /dev/gpiomem ] || [ "$IS_PI" = 1 ]; then
  install -m 0644 "$APP_DIR/other/99-ebilal-gpio.rules" /etc/udev/rules.d/99-ebilal-gpio.rules
  udevadm control --reload && udevadm trigger --subsystem-match=gpiomem 2>/dev/null || true
fi

if ip link show wlan0 >/dev/null 2>&1; then
  # Pi Zero W Wi-Fi power saving makes the device unreachable; keep it off
  install -m 0644 "$APP_DIR/other/wifi-powersave-off.service" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now wifi-powersave-off.service >/dev/null 2>&1 || warn "could not disable Wi-Fi power save"
fi

if [ "$PIMORONI" = 1 ] && [ -n "$BOOT_CONFIG" ]; then
  # pHAT BEAT audio: the PCM5102a DAC
  if ! grep -q '^dtoverlay=hifiberry-dac' "$BOOT_CONFIG"; then
    echo "dtoverlay=hifiberry-dac" >> "$BOOT_CONFIG"
    NEEDS_REBOOT=1
    info "pHAT BEAT audio overlay added to $BOOT_CONFIG"
  fi
  # pHAT BEAT buttons: let the kernel turn each one into a key press
  # (mapping lives in pimoroni.py, OVERLAYS)
  if ! grep -q '^# eBilal: pHAT BEAT buttons' "$BOOT_CONFIG"; then
    {
      echo ""
      echo "# eBilal: pHAT BEAT buttons (kernel gpio-key; on/off is KEY_PROG1, not KEY_POWER)"
      "$APP_DIR/venv/bin/python3" -c "import sys; sys.path.insert(0, '$APP_DIR'); import pimoroni; print('\n'.join(pimoroni.OVERLAYS))"
    } >> "$BOOT_CONFIG"
    info "pHAT BEAT button overlays added to $BOOT_CONFIG"
  fi
  # Load them now too, so the buttons work without waiting for a reboot
  if command -v dtoverlay >/dev/null && ! dtoverlay -l 2>/dev/null | grep -q gpio-key; then
    "$APP_DIR/venv/bin/python3" -c "import sys; sys.path.insert(0, '$APP_DIR'); import pimoroni; print('\n'.join(pimoroni.OVERLAYS))" |
      while IFS= read -r line; do
        # "dtoverlay=gpio-key,gpio=6,..." -> dtoverlay gpio-key gpio=6 ...
        dtoverlay $(echo "${line#dtoverlay=}" | tr ',' ' ') 2>/dev/null ||
          warn "could not load '$line' now; it will load after a reboot"
      done
    info "pHAT BEAT buttons active"
  fi
fi

systemctl daemon-reload
systemctl enable ebilal.service >/dev/null
systemctl restart ebilal.service

# ------------------------------------------------------------------ 8. https
step "Secure connection (local HTTPS certificate)"
install -m 0755 "$APP_DIR/other/ebilal-tls.sh" /usr/local/sbin/ebilal-tls
install -m 0644 "$APP_DIR/other/ebilal-tls.service" "$APP_DIR/other/ebilal-tls.timer" /etc/systemd/system/
systemctl daemon-reload
EBILAL_TLS_NO_RELOAD=1 /usr/local/sbin/ebilal-tls
systemctl enable ebilal-tls.service ebilal-tls.timer >/dev/null
systemctl start ebilal-tls.timer

# ------------------------------------------------------------------ 9. web
step "Web interface"
install -m 0644 "$APP_DIR/other/ebilal-locations.conf" /etc/nginx/snippets/ebilal-locations.conf
install -m 0644 "$APP_DIR/other/ebilal_site_nginx" /etc/nginx/sites-available/ebilal_site_nginx
ln -sfn /etc/nginx/sites-available/ebilal_site_nginx /etc/nginx/sites-enabled/ebilal_site_nginx
rm -f /etc/nginx/sites-enabled/default
# nginx workers must be able to read the web files
chmod o+rx "$APP_DIR" "$APP_DIR/ebilal_web"
nginx -t -q || die "nginx configuration test failed"
systemctl enable nginx >/dev/null
systemctl restart nginx

# ------------------------------------------------------------------ done
HOST="$(hostname -s).local"
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
printf '\n\033[1;32meBilal is installed.\033[0m\n\n'
echo "  Open on any phone or computer on this Wi-Fi:"
echo "      http://${HOST}/      (or http://${IP}/)"
echo
echo "  For no browser warnings, and to install it as an app, do this once per device:"
echo "      http://${HOST}/trust.html"
echo
echo "  Status:  systemctl status ebilal      Logs:  journalctl -u ebilal -f"
if [ "${NEEDS_REBOOT:-0}" = 1 ]; then
  echo
  warn "Reboot to enable the pHAT BEAT audio output:  sudo reboot"
fi
