# Zero-Disruption Operations

The target behavior is that routine admin actions should not interrupt other
connected employees.

## What Management Enables

OpenVPN's management interface can be used to inspect current clients and kill a
single client instance. After the management interface is enabled, these actions
do not require restarting the OpenVPN service:

- Read live connections with `status 2`.
- Disconnect one user with `kill <common-name>`.

The UI exposes this through:

- `GET /api/connections`
- `POST /api/connections/{common_name}/kick`

The kick API is disabled unless `features.allow_kick_user` is true.

## Server Config

Add the management listener to the existing OpenVPN server config:

```conf
management 127.0.0.1 7505 /etc/openvpn/management-password
status /var/log/openvpn/status.log 10
status-version 2
```

Use `127.0.0.1`, not `0.0.0.0`. Anyone who can access the management socket can
control the OpenVPN process.

Create the password file:

```bash
install -m 600 -o root -g root /dev/null /etc/openvpn/management-password
```

Put one strong password on the first line.

## UI Config

Configure OpenVPN UI to use the same endpoint:

```yaml
server:
  management_host: 127.0.0.1
  management_port: 7505
  management_password_file: /etc/openvpn/management-password

features:
  allow_kick_user: true
```

Restart OpenVPN once after changing `server.conf`, then restart OpenVPN UI after
changing `openvpn-ui.yaml`.

## Revoke Without Restart

Revocation should update the existing CRL file in place. Do not change the
`crl-verify` path during normal operations.

Recommended flow:

1. Revoke the certificate and regenerate `crl.pem`.
2. Keep the CRL at the same configured `crl-verify` path.
3. If the user is online, disconnect only that user through management.
4. Do not restart OpenVPN unless the server config itself changed.

This prevents unrelated clients from reconnecting or briefly losing traffic
during routine user removal.
