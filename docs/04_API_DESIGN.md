# API Design

## System

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/system/health` | Backend, database, and OpenVPN status |
| GET | `/api/system/config` | Sanitized configured paths and capabilities |

## Users

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/users` | List users and certificate state |
| POST | `/api/users` | Create user |
| GET | `/api/users/{common_name}` | User detail |
| POST | `/api/users/{common_name}/disable` | Disable user |
| POST | `/api/users/{common_name}/enable` | Enable user |
| POST | `/api/users/{common_name}/revoke` | Revoke certificate |

## Connections

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/connections` | Current OpenVPN client list |
| GET | `/api/connections/{common_name}` | Current connection for one user |

## Usage

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/usage` | Aggregate traffic |
| GET | `/api/usage/users/{common_name}` | User traffic history |

## Logs

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/logs/openvpn` | OpenVPN runtime logs |
| GET | `/api/logs/audit` | Admin audit logs |

## Request Requirements

- Mutating endpoints must require an authenticated admin.
- Dangerous endpoints must accept an audit reason.
- Revocation should require a confirmation token or typed common name.
