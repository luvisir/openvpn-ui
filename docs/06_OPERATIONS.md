# Operations

## Deployment

Recommended production shape:

- Backend runs as a dedicated system user.
- Backend is managed by systemd.
- Frontend is served by the backend or a reverse proxy.
- Privileged commands are delegated through limited scripts or sudo rules.

## Backups

Before certificate mutations:

- Backup Easy-RSA index files if present.
- Backup CRL file before regeneration.
- Backup generated client profile before overwriting.

## Reload Strategy

Reload OpenVPN only when required by the selected operation.

After reload:

- Check service status.
- Re-read OpenVPN status.
- Record result in audit log.

## Rollback Notes

Document rollback for:

- Failed user creation
- Failed profile generation
- Failed disable
- Failed revoke
- Failed CRL update
- Failed OpenVPN reload
