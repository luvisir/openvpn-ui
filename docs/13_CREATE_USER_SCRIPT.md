# Create User Script

The UI calls a non-interactive script. It should accept:

```text
ui-create-user.sh <common_name> <client_key_password> <ca_key_password> [replica_host]
```

The repository includes a ready-to-copy script at `scripts/ui-create-user.sh`.
It uses the existing paths from the current deployment:

- `/etc/openvpn/client/easyrsa3`
- `/etc/openvpn/easy-rsa/easyrsa3`
- `/etc/openvpn/client/<common_name>`

Example:

```bash
#!/usr/bin/env bash
set -euo pipefail

client="$1"
client_password="$2"
ca_password="$3"
replica_host="${4:-192.168.0.77}"

case "$client" in
  ""|*[!0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_.@-]*)
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

mkdir -p "/etc/openvpn/client/$client"

cd /etc/openvpn/client/easyrsa3
export EASYRSA_BATCH=1
export CLIENT_KEY_PASSWORD="$client_password"
export EASYRSA_PASSOUT="env:CLIENT_KEY_PASSWORD"
./easyrsa gen-req "$client"
unset CLIENT_KEY_PASSWORD EASYRSA_PASSOUT

cd /etc/openvpn/easy-rsa/easyrsa3
export EASYRSA_BATCH=1
./easyrsa import-req "/etc/openvpn/client/easyrsa3/pki/reqs/$client.req" "$client"
export CA_KEY_PASSWORD="$ca_password"
export EASYRSA_PASSIN="env:CA_KEY_PASSWORD"
./easyrsa --batch sign client "$client"
unset CA_KEY_PASSWORD EASYRSA_PASSIN

cp /etc/openvpn/easy-rsa/easyrsa3/pki/ca.crt "/etc/openvpn/client/$client/"
cp "/etc/openvpn/easy-rsa/easyrsa3/pki/issued/$client.crt" "/etc/openvpn/client/$client/"
cp "/etc/openvpn/client/easyrsa3/pki/private/$client.key" "/etc/openvpn/client/$client/"

rsync -avz --delete --exclude='server.conf' /etc/openvpn/ "root@$replica_host:/etc/openvpn/"
```

Config:

```yaml
lifecycle:
  command_timeout_seconds: 600
  create_user_command:
    - /etc/openvpn/scripts/ui-create-user.sh
    - "{common_name}"
    - "{password}"
    - "{ca_password}"
    - 192.168.0.77

features:
  allow_create_user: true
```

Do not reload or restart OpenVPN in this script. New client certificates do not
require restarting the server.

Some Easy-RSA versions reject setting `EASYRSA_REQ_CN` or `--req-cn` while
running `gen-req`. The script intentionally passes the client name only as the
`gen-req "$client"` argument so it works with those versions.
