# Architecture

## Goal

Build a local OpenVPN management panel on top of an existing manual OpenVPN deployment.

## Principles

- Preserve the current OpenVPN layout.
- Read existing state before adding write operations.
- Keep privileged operations behind a narrow adapter layer.
- Record every mutating action in an audit log.
- Make dangerous operations explicit and confirmable.
- Prefer reversible disable operations before certificate revocation.

## Components

| Component | Responsibility |
|---|---|
| Web frontend | Admin dashboard and workflow UI |
| Backend API | Authenticated management API |
| OpenVPN status reader | Parses status file or management interface |
| Certificate adapter | Calls existing certificate workflow safely |
| User lifecycle service | Create, disable, enable, revoke users |
| Audit logger | Records admin actions and results |
| Usage collector | Stores traffic snapshots and sessions |

## Suggested Stack

- Backend: FastAPI
- Database: SQLite for initial deployment
- Frontend: React, Vite, TypeScript
- UI: Tailwind CSS plus a component system
- Deployment: systemd service behind a local reverse proxy or direct bind

## Data Flow

1. Frontend calls backend API.
2. Backend validates admin session and request payload.
3. Backend uses adapters to read OpenVPN state or perform approved operations.
4. Mutating actions write audit records.
5. UI refreshes user, connection, usage, and log state.
