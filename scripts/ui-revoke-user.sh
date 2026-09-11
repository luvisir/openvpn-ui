#!/usr/bin/env bash
set -euo pipefail

client="${1:-}"
ca_password="${2:-}"
replica_host="${3:-192.168.0.77}"

case "$client" in
  ""|*[!0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_.@-]*)
    echo "invalid client name" >&2
    exit 2
    ;;
esac

if [ -z "$ca_password" ]; then
  echo "CA password is required" >&2
  exit 2
fi

server_ca_dir="/etc/openvpn/easy-rsa/easyrsa3"

cd "$server_ca_dir"
export EASYRSA_BATCH=1
export CA_KEY_PASSWORD="$ca_password"
export EASYRSA_PASSIN="env:CA_KEY_PASSWORD"
./easyrsa --batch revoke "$client"
./easyrsa gen-crl
unset CA_KEY_PASSWORD EASYRSA_PASSIN

rsync -avz --delete --exclude='server.conf' /etc/openvpn/ "root@$replica_host:/etc/openvpn/"
