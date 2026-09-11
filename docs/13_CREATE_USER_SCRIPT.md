# Create User Script

The UI calls a non-interactive script. It should accept:

```text
ui-create-user.sh <common_name> <client_key_password> [reason]
```

Example:

```bash
#!/usr/bin/env bash
set -euo pipefail

client="$1"
client_password="$2"
reason="${3:-}"

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
./easyrsa --batch sign client "$client"

cp /etc/openvpn/easy-rsa/easyrsa3/pki/ca.crt "/etc/openvpn/client/$client/"
cp "/etc/openvpn/easy-rsa/easyrsa3/pki/issued/$client.crt" "/etc/openvpn/client/$client/"
cp "/etc/openvpn/client/easyrsa3/pki/private/$client.key" "/etc/openvpn/client/$client/"

rsync -avz --delete --exclude='server.conf' /etc/openvpn/ root@192.168.0.77:/etc/openvpn/
```

Config:

```yaml
lifecycle:
  create_user_command:
    - /etc/openvpn/scripts/ui-create-user.sh
    - "{common_name}"
    - "{password}"

features:
  allow_create_user: true
```

Do not reload or restart OpenVPN in this script. New client certificates do not
require restarting the server.
