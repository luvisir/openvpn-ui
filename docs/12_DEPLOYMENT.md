# Deployment

OpenVPN UI can run as a single FastAPI process in production. Build the frontend
once, then FastAPI serves `frontend/dist`.

## Build

```bash
cd /opt/openvpn-ui/frontend
npm install
npm run build
```

## Configure

Keep the real config outside the repository:

```bash
mkdir -p /etc/openvpn-ui /var/lib/openvpn-ui
cp /opt/openvpn-ui/config/openvpn-ui.example.yaml /etc/openvpn-ui/openvpn-ui.yaml
```

Edit `/etc/openvpn-ui/openvpn-ui.yaml` and fill the existing OpenVPN paths.

## Run

```bash
cd /opt/openvpn-ui
python3 -m venv .venv
.venv/bin/pip install .
OPENVPN_UI_CONFIG=/etc/openvpn-ui/openvpn-ui.yaml \
  .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Visit through an SSH tunnel or a protected reverse proxy:

```bash
ssh -L 8000:127.0.0.1:8000 root@vpn-1
```

Then open:

```text
http://127.0.0.1:8000
```

## Notes

- Do not run `npm run dev` in production.
- The app does not modify OpenVPN during startup.
- Mutating VPN actions require explicit feature gates and configured commands.
- Restart OpenVPN UI after changing `openvpn-ui.yaml`.
