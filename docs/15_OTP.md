# OTP deployment and rollback

This feature adds TOTP to the existing certificate authentication. It never edits
OpenVPN configuration, restarts OpenVPN, moves certificates or changes rsync jobs.
It uses PyOTP for TOTP, Fernet for encrypted secrets and SQLite transactions for
shared replay protection. The independent verifier and panel run on vpn-1 and
share the OTP data directory. Both VPN nodes use this one verifier.

## 1. Update the panel without changing OpenVPN

Run from the existing project on vpn-1. Use the project's supported Python (3.9+),
not the operating system's Python 3.6. Do not replace the system Python.

```bash
cd /opt/openvpn-ui
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install .
cd frontend
npm ci
npm run build
cd ..
```

Add this top-level section to your existing `config/openvpn-ui.yaml`. Keep all
existing server, certificate, lifecycle and replica settings.

```yaml
otp:
  enabled: true
  issuer: Company VPN
  data_dir: /var/lib/openvpn-ui/otp
  nodes: [vpn-1, vpn-2]
```

The module switch is not the enforcement switch. `enabled: true` permits OTP
management and starting the verifier; first initialization still defaults to
enforcement OFF. Do not set `enabled: false` while OpenVPN relies on the verifier.
Configuration changes require restarting the panel and verifier processes.

Explicitly initialize once (creates only the new OTP directory and files):

```bash
cd /opt/openvpn-ui
OPENVPN_UI_CONFIG=/opt/openvpn-ui/config/openvpn-ui.yaml .venv/bin/python -m backend.otp_store init
```

This refuses to overwrite existing credentials or a partially initialized store.
It generates `encryption.key`, `admin.token`, `vpn-1.token`, `vpn-2.token` and
`otp.db`. Directory permissions must be 0700; credentials and database must be
0600. The panel and verifier must run as the same trusted OS account. The sample
matches your existing root deployment; it does not add Linux employee accounts.

Back up the whole OTP directory together with `openvpn-ui.db`. The encryption
key is essential for restoring OTP bindings. Never put tokens, key, database or
binding QR codes in Git, logs, shared screenshots or third-party QR websites.
Stop the verifier briefly for a consistent file backup or use SQLite's backup
API; a plain live database copy is not a guaranteed consistent backup.

## 2. Start the independent OTP service with one command

```bash
cd /opt/openvpn-ui
OPENVPN_UI_CONFIG=/opt/openvpn-ui/config/openvpn-ui.yaml .venv/bin/python -m uvicorn backend.otp_service:app --host 127.0.0.1 --port 8001 --no-access-log
```

Use a free port if 8001 is occupied. Keep it on loopback. This is independent of
the existing panel process (usually port 8000). Check it in a second terminal:

```bash
curl --fail http://127.0.0.1:8001/health
```

For autostart, inspect the sample before installing it. These commands affect
only the newly added OTP service, not `openvpn.service`:

```bash
cp config/openvpn-ui-otp.service.example /etc/systemd/system/openvpn-ui-otp.service
systemctl daemon-reload
systemctl enable --now openvpn-ui-otp.service
systemctl status openvpn-ui-otp.service
```

Restart only the existing panel to load the new backend/frontend, using your
existing panel startup procedure. Open the new OTP tab. Read the generated
`admin.token` locally with an authorized administrator and enter it in the
masked management credential field. It is kept only in page memory and cleared
when locking or leaving the tab. Management must be accessed via HTTPS or an SSH
tunnel; don't send the credential or QR codes over an exposed HTTP panel.

The OTP endpoints require this credential even though the old panel has no
built-in administrator login. Protect the entire old panel separately, because
its existing lifecycle endpoints are still privileged.

## 3. Prepare the local OpenVPN authentication hook

Keep hook configuration outside `/etc/openvpn/` so your existing recursive
`rsync --delete` does not overwrite node-specific settings.

```bash
install -d -m 700 /var/lib/openvpn-ui/otp-client
install -m 755 scripts/otp-verify.py /var/lib/openvpn-ui/otp-client/verify.py
install -m 600 config/otp-node.example.json /var/lib/openvpn-ui/otp-client/node.json
```

For vpn-1 the installed JSON is:

```json
{
  "url": "http://127.0.0.1:8001/verify",
  "node": "vpn-1",
  "token_file": "/var/lib/openvpn-ui/otp/vpn-1.token"
}
```

The hook uses only Python's standard library and also works on Python 3.6 on
vpn-2. Ensure `/usr/bin/python3` exists. With the root deployment, the private
files can remain root-only. If OpenVPN uses `user`, `group`, `chroot`, SELinux or
systemd filesystem restrictions, adapt access and test under the actual daemon
identity; don't make secrets world-readable or disable SELinux globally.

## 4. Test with an isolated OpenVPN instance first

Before choosing exact flags, collect on both nodes:

```bash
openvpn --version
systemctl cat openvpn.service
```

Also identify each employee client application/version. The following example
targets OpenVPN 2.4+; do not paste unsupported options into older installations.

Prepare a separate test config with another port (for example TCP 7000), a
distinct TUN device and an unused address pool. Use absolute paths for existing
CA/server certificate/key/DH/CRL files. Give the test instance its own status,
log, PID and pool-persistence files. Do not let it reuse `10.8.0.0/24` or existing
state files. Check routing, firewall forwarding/NAT, pushed routes, `local`,
daemon settings and management port conflicts before starting. Test network
rules must be narrowly scoped; don't flush existing rules.

Append the following authentication settings to the TEST configuration only:

```conf
verify-client-cert require
script-security 2
auth-user-pass-verify "/usr/bin/python3 /var/lib/openvpn-ui/otp-client/verify.py /var/lib/openvpn-ui/otp-client/node.json" via-file
auth-gen-token 3600
```

Keep `crl-verify` and existing certificate authentication. Do not add
`verify-client-cert none`, `client-cert-not-required` or
`username-as-common-name`. The hook requires the submitted username to match the
certificate's original CN. It reads the code from OpenVPN's temporary file,
never a command-line password. Ensure OpenVPN's temporary directory is private.
The synchronous hook has a five-second network timeout; test realistic login
bursts, since synchronous authentication can delay the OpenVPN event loop.

`auth-gen-token` allows later renegotiations to use an OpenVPN session token
instead of replaying an expired TOTP. Do NOT add `external-auth` to it: this
verifier accepts OTPs, not OpenVPN's internal tokens. Internal token validation
bypasses the OTP hook during token-authenticated renegotiation. Thus policy
changes and resets apply on the next full OTP authentication, not instantly to
existing/token-authenticated sessions. The example limits token lifetime to
one hour; test expiration, reconnect and client prompting across that boundary.
Do not disable key renegotiation as an OTP workaround.

Start only the isolated instance using the absolute test config path. Never
use `systemctl restart openvpn.service` during this stage. Review its routing
effects before starting it on a production machine.

## 5. Bind a test employee and update the client

1. Select an active certificate user in the OTP tab and choose Bind.
2. Let that employee scan the locally generated QR code in an authenticator app.
   Deliver it through a trusted channel. Anyone with the QR can clone the OTP.
3. Enter the employee's six-digit code to confirm. Unconfirmed QR codes expire
   after ten minutes. Confirmation consumes that code: wait for the next code
   before connecting.
4. Switch enforcement ON, entering `ENABLE` in the confirmation field.
5. Copy the employee's existing client profile, change its remote port to the
   test port, retain the separate `ca`, `cert` and `key` file references and add:

```conf
auth-user-pass
auth-retry interact
```

Client applications differ; check whether they support these directives before
distribution. Remove an old `auth-user-pass` credentials file reference if one
exists; don't store a rotating OTP as a fixed password. Re-import the edited
profile where the application requires it. Enter the original private-key
password to unlock the key; use the certificate CN as username and the current
six-digit OTP as the login password. The CA signing password is never needed
for VPN login or OTP binding. Not every reconnect needs a new OTP while a valid
session token is in use. Do not save the OTP in the client password manager.

New OTP features do not change certificate creation or require reissuing old
certificates. Reset requires confirming the username; the previous OTP remains
valid until the new binding is confirmed. Resetting does not kick active VPN
sessions or invalidate OpenVPN session tokens; use the existing kick operation
when immediate disconnection is required.

## 6. Connect vpn-2 through an SSH tunnel

Only one verifier is required. Do not rsync its live database or secrets to
vpn-2. Instead, install `verify.py` and a private node JSON on vpn-2 outside the
existing certificate sync tree. Securely deliver ONLY `vpn-2.token`, never
`admin.token`, `encryption.key` or vpn-1's token, to:

```text
/var/lib/openvpn-ui/otp-client/vpn-2.token
```

Use an SSH identity dedicated to forwarding and pin vpn-1's host key after
checking its fingerprint through a trusted channel. Restrict that identity on
vpn-1 to forwarding to `127.0.0.1:8001`, with no shell/PTY. Establish a persistent
local forward from vpn-2 (replace `VPN1_INTERNAL_IP` and identity path):

```bash
ssh -NT -o BatchMode=yes -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -i /path/to/otp-tunnel-key -L 127.0.0.1:18001:127.0.0.1:8001 root@VPN1_INTERNAL_IP
```

Configure vpn-2's JSON:

```json
{
  "url": "http://127.0.0.1:18001/verify",
  "node": "vpn-2",
  "token_file": "/var/lib/openvpn-ui/otp-client/vpn-2.token"
}
```

Supervise the tunnel via systemd with `Restart=always`, using the provided
`config/openvpn-ui-otp-tunnel.service.example` after filling its placeholders.
The transport between hosts is SSH encrypted; the HTTP endpoint remains on
loopback at both ends. Alternatively use HTTPS with verified certificates and
`ca_file` in the hook JSON. LAN plain HTTP and HTTP redirects are rejected.
Do not expose port 8001 publicly. Avoid connecting the tunnel through the very
VPN it is authenticating, which would create a circular dependency.

Repeat isolated VPN tests on vpn-2 before connecting its production service.
Same certificate paths and existing certificate rsync are compatible; each node
must keep its own hook JSON and node token outside that rsync tree.

## 7. Verification and production cutover

Test both nodes against the same service:

- Valid certificate + next valid OTP succeeds; wrong/expired/missing OTP fails.
- Alice's certificate + Bob's username/OTP fails; unknown, revoked or disabled
  users fail even with enforcement OFF. OpenVPN still validates expiry and CRL.
- Using the same OTP on the other node fails (including simultaneous attempts).
  Wait for the next code when rapidly switching nodes. Five failed code attempts
  lock that user for 60 seconds across nodes; do not widen the time window to
  compensate for broken server clocks. Keep clocks synchronized on vpn-1/phones.
- Rebinding, cancellation and expired QR codes preserve the old binding until
  a new one is confirmed; old codes stop working after confirmation.
- Test renegotiation, the one-hour token expiration, reconnect and node failover
  with actual clients. Nodes don't share OpenVPN session-token signing secrets
  by default; a node switch can require a fresh OTP, which is expected.
- Stop the verifier or SSH tunnel: new full authentications fail closed even
  with enforcement OFF; existing sessions may continue until reauthentication.
  Restarting just the panel must not stop the independent verifier.
- Run the original create/disable/enable/revoke and certificate rsync workflows;
  ensure OTP directory and node-specific settings survive.
- Verify central audit has no passwords, TOTP seeds or QR contents.

Before formal cutover, back up each server config and prepare client profiles,
enroll users, verify firewall/tunnel autostart, backup/restore and resource use.
Install the tested auth settings by hand into each production `server.conf`.
Restart only the selected node during an agreed maintenance window:

```bash
systemctl restart openvpn.service
```

This interrupts that node's active connections. Migrate one node at a time.
The untouched node remains a certificate-only bypass until it too is migrated.
With the central service on vpn-1, a vpn-1 outage blocks new full authentication
on both nodes: this first version is not a highly available authentication
cluster. It also has no self-service recovery codes; a trusted administrator
must verify identity and reset bindings when employees lose their phones.

## 8. Switches and full rollback

- Panel OTP checkbox: persisted in the OTP database and read on each full
  authentication by both nodes. OFF skips the OTP check but still requires a
  valid known active certificate and matching username. No VPN restart or kick.
- OFF is not a service shutdown switch. Clients still need to supply matching
  usernames and a nonempty placeholder password, since OpenVPN still requires
  username/password exchange; the code is ignored by the verifier in OFF mode.
- Module `otp.enabled: false`: disables OTP management and prevents starting
  the verifier; it does not remove OpenVPN's dependency on its hook.
- Full removal: restore the original `server.conf` on each node (removing only
  the added OTP auth settings) and restart each node in a maintenance window.
  Once neither node uses the hook, stop/disable the OTP service and tunnel.
  Restore client profiles without the added authentication directives. Original
  certificates, private keys, routes and key passwords stay unchanged.

Official references:
- https://openvpn.net/community-docs/using-alternative-authentication-methods/
- https://openvpn.net/community-docs/community-articles/openvpn-2-6-manual/
