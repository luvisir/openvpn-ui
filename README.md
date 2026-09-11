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

For no-restart connection management and single-user disconnect behavior, see
`docs/10_ZERO_DISRUPTION.md`.

For two-node or multi-node connection visibility, see `docs/11_REPLICAS.md`.

## Current Framework

The repository now contains a minimal backend and frontend skeleton:

- `backend/`: FastAPI API service
- `frontend/`: React/Vite dashboard shell
- `config/openvpn-ui.example.yaml`: configuration template for the existing server layout

## Configuration-First Workflow

The application is designed to be configured for an already deployed OpenVPN
server.

1. Copy the example config:

   ```bash
   cp config/openvpn-ui.example.yaml config/openvpn-ui.yaml
   ```

2. Fill in the real OpenVPN paths and service name.
3. Start or restart the backend.
4. Open the dashboard and check `/api/system/health` results.

The backend reads configuration once per process. If the config changes, restart
the service for the new paths and feature gates to take effect.

For production, keep the real config outside the repository and point the
backend at it:

```bash
OPENVPN_UI_CONFIG=/etc/openvpn-ui/openvpn-ui.yaml uvicorn backend.main:app
```

## Development Run

Backend:

```bash
uvicorn backend.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```
