#!/usr/bin/env bash
set -euo pipefail

client="${1:-}"
ccd_dir="${2:-/etc/openvpn/ccd}"
replica_host="${3:-192.168.0.77}"

case "$client" in
  ""|.|..|-*|*[!0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_.@-]*)
    echo "invalid client name" >&2
    exit 2
    ;;
esac

ccd_file="$ccd_dir/$client"

if [ -e "$ccd_file" ] && ! grep -q '^# managed-by openvpn-ui$' "$ccd_file"; then
  echo "refusing to remove unmanaged CCD file: $ccd_file" >&2
  exit 3
fi

rm -f "$ccd_file"
# Delete only this panel-managed CCD on the replica, including on a retried enable.
printf -v remote_command 'bash -s -- %q %q' "$ccd_dir" "$client"
ssh "root@$replica_host" "$remote_command" <<'EOF'
set -euo pipefail
ccd_file="$1/$2"
if [ -e "$ccd_file" ]; then
  if ! grep -q '^# managed-by openvpn-ui$' "$ccd_file"; then
    echo "refusing to remove unmanaged remote CCD file" >&2
    exit 3
  fi
  rm -f "$ccd_file"
fi
EOF
rsync -avz --exclude='server.conf' /etc/openvpn/ "root@$replica_host:/etc/openvpn/"
