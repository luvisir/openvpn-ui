#!/usr/bin/env bash
set -euo pipefail

client="${1:-}"
client_password="${2:-}"
ca_password="${3:-}"

case "$client" in
  ""|*[!0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-]*)
    echo "invalid client name" >&2
    exit 2
    ;;
esac

if [ -z "$client_password" ]; then
  echo "client password is required" >&2
  exit 2
fi

if [ -z "$ca_password" ]; then
  echo "CA password is required" >&2
  exit 2
fi

client_req_dir="/etc/openvpn/client/easyrsa3"
server_ca_dir="/etc/openvpn/easy-rsa/easyrsa3"
client_dir="/etc/openvpn/client/$client"
replica_host="192.168.0.77"

mkdir -p "$client_dir"

cd "$client_req_dir"
export EASYRSA_BATCH=1
export EASYRSA_REQ_CN="$client"
export CLIENT_KEY_PASSWORD="$client_password"
export EASYRSA_PASSOUT="env:CLIENT_KEY_PASSWORD"
./easyrsa gen-req "$client"
unset CLIENT_KEY_PASSWORD EASYRSA_PASSOUT

cd "$server_ca_dir"
export EASYRSA_BATCH=1
./easyrsa import-req "$client_req_dir/pki/reqs/$client.req" "$client"
export CA_KEY_PASSWORD="$ca_password"
export EASYRSA_PASSIN="env:CA_KEY_PASSWORD"
./easyrsa --batch sign client "$client"
unset CA_KEY_PASSWORD EASYRSA_PASSIN

cp "$server_ca_dir/pki/ca.crt" "$client_dir/"
cp "$server_ca_dir/pki/issued/$client.crt" "$client_dir/"
cp "$client_req_dir/pki/private/$client.key" "$client_dir/"

rsync -avz --delete --exclude='server.conf' /etc/openvpn/ "root@$replica_host:/etc/openvpn/"
