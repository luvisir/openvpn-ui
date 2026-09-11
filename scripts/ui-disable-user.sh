#!/usr/bin/env bash
set -euo pipefail

client="${1:-}"
ccd_dir="${2:-/etc/openvpn/ccd}"
replica_host="${3:-192.168.0.77}"

case "$client" in
  ""|*[!0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_.@-]*)
    echo "invalid client name" >&2
    exit 2
    ;;
esac

mkdir -p "$ccd_dir"
ccd_file="$ccd_dir/$client"

if [ -e "$ccd_file" ] && ! grep -q '^# managed-by openvpn-ui$' "$ccd_file"; then
  echo "refusing to overwrite unmanaged CCD file: $ccd_file" >&2
  exit 3
fi

cat > "$ccd_file" <<'EOF'
# managed-by openvpn-ui
disable
EOF

rsync -avz --delete --exclude='server.conf' /etc/openvpn/ "root@$replica_host:/etc/openvpn/"
