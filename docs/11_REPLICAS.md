# Replicas

Replicas are optional. If `replicas` is empty, the app behaves like a single-node
panel and uses `server.management_host`, `server.management_port`, and
`server.status_file`.

When replicas are configured, the Connections screen reads every node and shows
which node each connection belongs to.

## Example

```yaml
replicas:
  - name: vpn-1
    role: local
    management_host: 127.0.0.1
    management_port: 7505
    management_password_file: /etc/openvpn/management-password

  - name: vpn-2
    role: ssh
    ssh_host: 192.168.0.77
    ssh_user: root
    ssh_port: 22
    management_host: 127.0.0.1
    management_port: 7505
    management_password_file: /etc/openvpn/management-password
```

## OpenVPN Config On Each Node

Each OpenVPN server should expose management only on localhost:

```conf
management 127.0.0.1 7505 /etc/openvpn/management-password
status /var/log/openvpn/status.log 10
status-version 2
```

The panel connects to `vpn-2` with SSH and then connects to `127.0.0.1:7505`
from inside that server. Do not expose the management port publicly.

## User Lifecycle

Certificate lifecycle operations still run on the node where the panel is
deployed. Use the configured lifecycle scripts to create, revoke, and sync files
to other nodes.

Creating a new user should not reload or restart OpenVPN on either node.

Revoking a user should:

1. Update the existing CRL path.
2. Sync the changed OpenVPN files to replicas.
3. Kick only that common name on each node through management.
4. Avoid `systemctl restart`, `systemctl reload`, and broad `SIGHUP` during
   routine user removal.
