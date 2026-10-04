# SAMANVAY Deployment Guide

SAMANVAY is an offline-first, single-process mission-orchestration system. It bundles the FastAPI backend, PMTiles vector map server (HTTP 206), real-time WebSocket broker, and the compiled 3D React/MapLibre console into one unified service.

---

## 1. Quick Deploy: Docker Container

The fastest way to deploy anywhere (local machine, ruggedized field edge node, or cloud VM):

### Build the Image
```bash
docker build -t samanvay:latest .
```

### Run the Container
```bash
docker run -d \
  --name samanvay-console \
  --restart unless-stopped \
  -p 8000:8000 \
  samanvay:latest
```

Open `http://localhost:8000` (or `http://<server-ip>:8000`).

---

## 2. Air-Gapped Field Laptop Deployment (Native)

For search and rescue deployments where internet and external registry access are strictly prohibited:

### Prerequisites (Prepared before going to field)
- Python 3.11 with `.venv` installed via `pip install -r requirements.lock`
- Pre-cached vector tiles in `public/mumbai.pmtiles`
- Pre-cached district scenarios in `public/zones/*.json`
- Pre-built frontend bundle in `dist/`

### Build Step (One-time on prep machine)
```powershell
npm ci
npm run build
node scripts/copy-maplibre.cjs
```

### Production Run
```powershell
# Windows PowerShell
.\.venv\Scripts\python -m uvicorn samanvay.server.app:app --host 0.0.0.0 --port 8000 --workers 1

# Linux / macOS
./.venv/bin/python -m uvicorn samanvay.server.app:app --host 0.0.0.0 --port 8000 --workers 1
```

---

## 3. Production Linux Server (Systemd + Nginx)

### A. Systemd Service Unit (`/etc/systemd/system/samanvay.service`)

```ini
[Unit]
Description=SAMANVAY Mission Console
After=network.target

[Service]
Type=simple
User=samanvay
WorkingDirectory=/opt/samanvay
ExecStart=/opt/samanvay/.venv/bin/python -m uvicorn samanvay.server.app:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now samanvay
```

### B. Nginx Reverse Proxy Configuration

> [!IMPORTANT]
> The Nginx configuration **must** support WebSocket upgrades (`/ws`) and HTTP 206 Partial Content Range requests (`/mumbai.pmtiles`).

```nginx
server {
    listen 80;
    server_name console.samanvay.local;

    # Pass Range headers for PMTiles streaming
    proxy_set_header Range $http_range;
    proxy_set_header If-Range $http_if_range;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket endpoint
    location /ws {
        proxy_pass http://127.0.0.1:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
```

---

## 4. Verification & Health Check

After deploying, verify the endpoints:

```bash
# 1. Check health / pre-cached zones library
curl http://127.0.0.1:8000/api/zones

# 2. Check PMTiles range request (HTTP 206 Partial Content)
curl -I -H "Range: bytes=0-1023" http://127.0.0.1:8000/mumbai.pmtiles

# 3. Check offline audit self-test
python -m samanvay.cli doctor --offline
```
