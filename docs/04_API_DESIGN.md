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
| POST | `/api/connections/{common_name}/kick` | Disconnect one active client through OpenVPN management |

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

## Command Placeholders

Configured lifecycle commands are argv arrays and may use:

- `{common_name}`
- `{reason}`
- `{password}` for create-user commands only; never store it in audit logs.
- `{ca_password}` for create-user signing and revoke/gen-crl operations; never
  store it in audit logs.

## Request Requirements

- Mutating endpoints must require an authenticated admin.
- Dangerous endpoints must accept an audit reason.
- Revocation should require a confirmation token or typed common name.
