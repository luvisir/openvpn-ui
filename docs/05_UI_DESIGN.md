# UI Design

## Product Shape

The application opens directly into the management dashboard. It should feel professional, calm, and operationally safe.

## Screens

| Screen | Purpose |
|---|---|
| Dashboard | Online users, traffic, recent events, service health |
| Users | Search, filter, status, and lifecycle actions |
| User detail | Certificate state, connection history, usage, audit events |
| Connections | Live sessions from OpenVPN status |
| Usage | Traffic charts and per-user summaries |
| Logs | OpenVPN logs and admin audit logs |
| Settings | Configured paths and integration capabilities |

## User States

- Active
- Online
- Disabled
- Revoked
- Unknown or unmanaged

## Dangerous Action UX

Revocation must use a high-risk confirmation dialog with:

- Target common name
- Consequence summary
- Required audit reason
- Typed confirmation

Disable can be a lighter confirmation because it should be reversible.
