# OpenVPN Layout

This file is the source of truth for paths discovered on the server.

## Paths

| Purpose | Path | Access | Notes |
|---|---|---|---|
| Server config | TBD | Read only | Do not rewrite automatically |
| Status file | TBD | Read only | Used for live connections |
| OpenVPN log | TBD | Read only | File or journald |
| CA directory | TBD | Restricted | Existing path |
| Easy-RSA directory | TBD | Restricted | If used |
| Issued certs | TBD | Restricted | Existing path |
| Private keys | TBD | Restricted | Existing path |
| CRL file | TBD | Restricted | Existing path |
| Client profiles | TBD | Restricted | Existing path |
| CCD directory | TBD | Read/write if approved | Used for soft disable if available |

## Integration Rules

- The app must use these paths instead of inventing a parallel OpenVPN layout.
- Only configured paths may be read or written.
- Backend startup should fail clearly if required paths are missing.
- Mutating operations must create backups where appropriate.
