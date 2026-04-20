# Security Model

## Threat Model

The management panel can affect VPN access. A compromised panel can create or revoke access, so the backend must be treated as a privileged administration surface.

## Required Controls

- Admin authentication
- CSRF protection if using cookie sessions
- Strict username validation
- No raw shell command interpolation
- Least-privilege sudo rules
- Audit logs for all write operations
- Typed confirmation for revocation
- Backups before certificate index or CRL changes

## Privileged Operations

| Operation | Risk | Guardrail |
|---|---|---|
| Create user | Medium | Validate common name and check duplicates |
| Disable user | Medium | Prefer reversible method |
| Enable user | Medium | Verify user is not revoked |
| Revoke user | High | Confirmation, backup, audit reason |
| Reload OpenVPN | High | Explicit approval and health check |

## Username Rules

Initial recommendation:

- Allow letters, numbers, dot, dash, and underscore.
- Reject spaces, slashes, shell metacharacters, and empty names.
- Enforce a maximum length.
- Treat certificate common names as immutable identifiers.
