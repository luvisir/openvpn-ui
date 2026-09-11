# User Lifecycle Scripts

The repository includes operation scripts for the existing vpn-1/vpn-2 layout:

- `scripts/ui-create-user.sh` creates a password-protected client key, signs the
  certificate, copies files into `/etc/openvpn/client/<common_name>/`, and syncs
  `/etc/openvpn/` to vpn-2 while excluding `server.conf`.
- `scripts/ui-disable-user.sh` writes a managed CCD file with `disable`.
- `scripts/ui-enable-user.sh` removes only CCD files created by OpenVPN UI.
- `scripts/ui-revoke-user.sh` revokes a certificate, regenerates `crl.pem`, and
  syncs the changed OpenVPN files to vpn-2 while excluding `server.conf`.

The ready-to-adapt config is `config/openvpn-ui.server-example.yaml`.

## OpenVPN Server Lines

For kick and no-restart disconnect actions:

```conf
management 127.0.0.1 7505 /etc/openvpn/management-password
status /data/log/openvpn/openvpn-status.log 10
status-version 2
```

For reversible disable/enable:

```conf
client-config-dir /etc/openvpn/ccd
```

These server config lines require one manual OpenVPN restart. Routine UI actions
after that should not use a broad restart, except when the admin intentionally
clicks the OpenVPN restart action.

## Management Password File

The management password file must contain one password line and should be owned
by root:

```bash
install -m 600 -o root -g root /dev/null /etc/openvpn/management-password
```

Put the password on the first line, then configure the same path in
`openvpn-ui.yaml`.
