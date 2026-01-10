# Ziskin Field Systems

Professional field surveillance platform for investigation operations.

## Overview

Ziskin Field Systems (ZFS) is a complete surveillance platform consisting of:

- **Edge Devices**: Mini PCs deployed at surveillance sites handling stream capture, continuous recording, and PTZ camera control
- **Cloud Platform**: Digital Ocean infrastructure for authentication, stream relay, and management
- **Web Interface**: Mobile-responsive application for live viewing and PTZ control

## Architecture

```
[PTZ Camera] ──RTSP──► [Mini PC] ──5G/WAN──► [Digital Ocean] ◄──HTTPS── [Browser]
      ▲                    │                        │
      │                    │                        │
      └──── ONVIF PTZ ─────┴────── WireGuard ───────┘
```

## Project Structure

```
ziskin-field-systems/
├── edge/                    # Edge device software
│   ├── orchestrator/        # Python daemon
│   ├── systemd/             # Service files
│   ├── config.example.yaml  # Configuration template
│   └── install.sh           # Installation script
│
├── cloud/                   # Cloud platform
│   ├── api/                 # FastAPI backend
│   ├── web/                 # React frontend
│   ├── nginx/               # Nginx configuration
│   ├── docker-compose.yml   # Docker orchestration
│   └── Dockerfile.*         # Container builds
│
└── docs/                    # Documentation
```

## Quick Start

### Cloud Platform

1. Clone the repository:
   ```bash
   git clone https://github.com/ziskin-field-systems/zfs.git
   cd zfs/cloud
   ```

2. Copy environment file and configure:
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

3. Start with Docker Compose:
   ```bash
   docker-compose up -d
   ```

4. Access the application at `http://localhost`

### Edge Device

1. Install on Ubuntu Server 22.04:
   ```bash
   cd edge
   sudo ./install.sh
   ```

2. Configure the device:
   ```bash
   sudo nano /opt/ziskin/config.yaml
   ```

3. Start the service:
   ```bash
   sudo systemctl start zfs-orchestrator
   ```

## Features

### Live Streaming
- HLS streaming with 3-8 second latency
- 1080p sub-stream for cloud viewing
- 4K main stream for local recording
- Auto-reconnection on interruption

### PTZ Control
- Real-time pan/tilt/zoom via ONVIF
- Preset positions
- Rate limiting (10 commands/second)
- Permission-based access

### Recording
- Continuous 4K recording with burned-in timestamps
- 30-minute segments
- Configurable retention (up to 90 days)
- Remote clip export

### Security
- WireGuard encrypted tunnels
- Clerk authentication with JWT
- Role-based access control
- Audit logging

## Technology Stack

### Edge Device
- Ubuntu Server 22.04 LTS
- Python 3.11+ with asyncio
- MediaMTX for RTSP/HLS
- FFmpeg for recording
- onvif-zeep for PTZ
- WireGuard for VPN

### Cloud Platform
- FastAPI (Python)
- PostgreSQL
- React with Tailwind CSS
- hls.js video player
- Clerk authentication
- Nginx reverse proxy
- Docker

## API Documentation

When running in development mode, API documentation is available at:
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

## Configuration

### Edge Device (config.yaml)

```yaml
site_id: "site-abc123"
site_name: "Example Site"

cloud:
  api_endpoint: "https://api.zfs.example.com"
  wireguard_endpoint: "wg.zfs.example.com:51820"

cameras:
  - id: cam-01
    name: "Front Gate"
    ip: 192.168.1.101
    ptz: true
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Application secret for JWT signing |
| `DATABASE_URL` | PostgreSQL connection string |
| `CLERK_SECRET_KEY` | Clerk authentication secret |
| `RESEND_API_KEY` | Email service API key |

## License

Proprietary - Ziskin Field Systems

## Support

For support, contact: support@zfs.example.com
