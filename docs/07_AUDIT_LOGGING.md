# Audit Logging

## Events

- `admin.login`
- `admin.logout`
- `user.created`
- `user.disabled`
- `user.enabled`
- `user.revoked`
- `user.kicked`
- `profile.downloaded`
- `openvpn.reload_requested`
- `openvpn.reload_succeeded`
- `openvpn.reload_failed`

## Fields

| Field | Purpose |
|---|---|
| id | Unique event id |
| timestamp | Event time |
| actor | Admin identity |
| action | Event name |
| target | User, service, or resource |
| request_ip | Admin request source |
| user_agent | Browser or client |
| reason | Admin-provided reason for risky actions |
| result | Success or failure |
| error | Error message if failed |

## Retention

Initial recommendation:

- Keep admin audit logs indefinitely unless storage policy says otherwise.
- Keep OpenVPN imported logs according to operational retention requirements.
