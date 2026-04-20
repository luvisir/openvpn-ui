# Discovery

This file records the existing OpenVPN server layout. Discovery must be read-only.

## Rules

- Do not modify OpenVPN configuration during discovery.
- Do not move or rename existing certificate files.
- Do not run revoke, clean, init, or rebuild commands.
- Do not restart or reload OpenVPN unless explicitly approved.

## OpenVPN Runtime

| Item | Value | Notes |
|---|---|---|
| Server config path | TBD | Example: `/etc/openvpn/server/server.conf` |
| Service name | TBD | Example: `openvpn-server@server` |
| Status file | TBD | Usually configured by `status` |
| Log file | TBD | Could be file log or journald |
| Management interface | TBD | Optional |
| Client config dir | TBD | Usually configured by `client-config-dir` |

## Certificate Layout

| Item | Value | Notes |
|---|---|---|
| CA path | TBD | Existing CA only |
| Easy-RSA path | TBD | If used |
| Issued certs path | TBD | Existing path |
| Private keys path | TBD | Existing path |
| CRL path | TBD | Existing path |
| Client profile directory | TBD | Existing path |

## Existing User Flow

Document the current manual process.

### Create User

- TBD

### Disable User

- TBD

### Revoke User

- TBD

### Generate Client Profile

- TBD

## Risks

- Certificate revocation is destructive and must require confirmation.
- Incorrect CRL generation can affect all clients.
- Shell command construction must avoid string interpolation.
- Backend service permissions must be least-privilege.
