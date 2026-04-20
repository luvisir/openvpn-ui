# OpenVPN UI

OpenVPN UI is a management interface designed to sit on top of an existing manually deployed OpenVPN server.

The project must preserve the current OpenVPN installation:

- Do not reinstall OpenVPN.
- Do not move existing server configuration.
- Do not move CA, certificate, client profile, or user directories.
- Do not regenerate an existing CA.
- Prefer read-only discovery before adding any write operation.

## Initial Goal

Build a clean administrative dashboard for:

- Creating VPN users
- Disabling users
- Enabling users
- Revoking users
- Viewing connection status
- Viewing traffic usage
- Reviewing OpenVPN and admin audit logs

## Project Phases

1. Discovery and architecture documentation
2. Read-only dashboard
3. User lifecycle operations
4. Audit logging and permission hardening
5. UI polish and deployment packaging

## Documentation

Start with the files in `docs/` before writing production code. They define the operating boundaries for integrating with the existing OpenVPN server.
