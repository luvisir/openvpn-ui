# Configuration

The app is configured by a YAML file that describes the existing OpenVPN
deployment. The UI must adapt to this file instead of moving OpenVPN files.

## Runtime File

1. Copy `config/openvpn-ui.example.yaml` to `config/openvpn-ui.yaml`.
2. Fill in the real paths from the existing server.
3. Start or restart the backend service.

The backend reads the config once per process. After changing the config file,
restart the service to apply changes.

## Environment Variable

By default the backend reads:

```bash
config/openvpn-ui.yaml
```

For production, set:

```bash
OPENVPN_UI_CONFIG=/etc/openvpn-ui/openvpn-ui.yaml
```

## Path Groups

`server` describes the OpenVPN runtime:

- `config_path`: existing OpenVPN server config.
- `service_name`: existing systemd service name.
- `status_file`: OpenVPN status file, if configured.
- `log_file`: OpenVPN log file, if file logging is used.
- `management_host` and `management_port`: optional management interface.
- `management_password_file`: optional password file for the management interface.

`certificates` describes the existing certificate layout:

- `ca_dir`
- `easy_rsa_dir`
- `issued_dir`
- `private_dir`
- `crl_path`
- `client_profiles_dir`

`lifecycle` describes optional command integrations:

- `client_config_dir`
- `command_timeout_seconds`
- `create_user_command`
- `generate_profile_command`
- `disable_user_command`
- `enable_user_command`
- `revoke_user_command`
- `reload_command`

Commands must be argv arrays, not shell strings. This keeps later privileged
execution narrow and avoids unsafe shell interpolation.

Supported command placeholders:

- `{common_name}`
- `{reason}`
- `{password}` for create-user commands only
- `{ca_password}` for create-user signing and revoke/gen-crl operations

Do not echo `{password}` or `{ca_password}` in scripts. The UI passes them only
to the configured create-user command and does not write them to audit logs.

## Feature Gates

All mutating operations are disabled by default:

- `allow_create_user`
- `allow_disable_user`
- `allow_kick_user`
- `allow_revoke_user`
- `allow_openvpn_reload`

Enable them only after the related paths and commands are verified on the
server.

## User Discovery

The Users screen reads existing users from:

- `certificates.ca_dir/index.txt`
- `certificates.issued_dir/*.crt`
- `certificates.client_profiles_dir/<common_name>.ovpn`

The panel does not move or rewrite those files during discovery.

## Audit Database

Admin actions are recorded in the configured SQLite database. With the default
development config, the file is created at:

```bash
./openvpn-ui.db
```

In production, prefer an absolute path:

```yaml
app:
  database_url: sqlite:////var/lib/openvpn-ui/openvpn-ui.db
```
