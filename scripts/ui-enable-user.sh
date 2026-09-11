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

ccd_file="$ccd_dir/$client"

if [ ! -e "$ccd_file" ]; then
  exit 0
fi

if ! grep -q '^# managed-by openvpn-ui$' "$ccd_file"; then
  echo "refusing to remove unmanaged CCD file: $ccd_file" >&2
  exit 3
fi

rm -f "$ccd_file"
rsync -avz --delete --exclude='server.conf' /etc/openvpn/ "root@$replica_host:/etc/openvpn/"
