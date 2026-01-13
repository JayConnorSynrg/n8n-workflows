# Docker & Hostinger Deployment Guide

## Option 1: Docker (Local or Any VPS)

### Quick Start

```bash
cd voice-agent-poc

# Create environment file
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Build and start
docker-compose up -d

# Check logs
docker-compose logs -f
```

**Access:**
- Voice Agent Webpage: `http://localhost:8080`
- Relay Server WebSocket: `ws://localhost:3000`
- Health Check: `http://localhost:3001/health`

### Production with SSL (Traefik)

For production, you need SSL for WebSocket (wss://) and HTTPS. Add Traefik:

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    container_name: traefik
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=your@email.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt
    restart: unless-stopped

  relay-server:
    build: ./relay-server
    container_name: voice-agent-relay
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - PORT=3000
      - HEALTH_PORT=3001
      - LOG_LEVEL=INFO
    labels:
      - "traefik.enable=true"
      # WebSocket route
      - "traefik.http.routers.relay.rule=Host(`relay.yourdomain.com`)"
      - "traefik.http.routers.relay.entrypoints=websecure"
      - "traefik.http.routers.relay.tls.certresolver=letsencrypt"
      - "traefik.http.services.relay.loadbalancer.server.port=3000"
    restart: unless-stopped

  client:
    image: nginx:alpine
    container_name: voice-agent-client
    volumes:
      - ./client:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.client.rule=Host(`voice.yourdomain.com`)"
      - "traefik.http.routers.client.entrypoints=websecure"
      - "traefik.http.routers.client.tls.certresolver=letsencrypt"
      - "traefik.http.services.client.loadbalancer.server.port=80"
    restart: unless-stopped
```

Deploy:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## Option 2: Hostinger VPS

Hostinger VPS plans support Docker. Here's how to deploy:

### Step 1: Set Up VPS

1. Purchase Hostinger VPS (KVM 1 or higher recommended)
2. Choose Ubuntu 22.04 LTS
3. Note your VPS IP address

### Step 2: Connect and Install Docker

```bash
# SSH into your VPS
ssh root@YOUR_VPS_IP

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
apt install docker-compose-plugin -y

# Verify
docker --version
docker compose version
```

### Step 3: Clone and Configure

```bash
# Create directory
mkdir -p /opt/voice-agent
cd /opt/voice-agent

# Clone or upload your files
# Option A: Git clone
git clone https://github.com/your-repo/voice-agent-poc.git .

# Option B: SCP upload
# (from your local machine)
# scp -r voice-agent-poc/* root@YOUR_VPS_IP:/opt/voice-agent/

# Create environment file
cp .env.example .env
nano .env  # Add your OPENAI_API_KEY
```

### Step 4: Configure Domain (Hostinger DNS)

1. In Hostinger hPanel, go to **DNS Zone**
2. Add A records:
   - `voice.yourdomain.com` → Your VPS IP
   - `relay.yourdomain.com` → Your VPS IP

### Step 5: Deploy with SSL

```bash
cd /opt/voice-agent

# Use production compose with Traefik
# First, edit docker-compose.prod.yml to set your domain and email

# Deploy
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

### Step 6: Verify Deployment

```bash
# Test health endpoint
curl https://relay.yourdomain.com/health

# Expected: {"status":"healthy","activeConnections":0,"uptime":...}
```

**Your URLs:**
- Voice Agent: `https://voice.yourdomain.com`
- Relay WebSocket: `wss://relay.yourdomain.com`

---

## Option 3: Hostinger Node.js Hosting (Shared)

If you don't want to manage a VPS, Hostinger's Node.js hosting works for the relay server only (client needs separate static hosting).

### Relay Server on Hostinger Node.js

1. In hPanel, enable **Node.js** for your hosting
2. Set Node.js version to 18+
3. Upload relay-server files via File Manager:
   ```
   public_html/
   ├── index.js
   ├── package.json
   └── .env
   ```
4. In Node.js settings:
   - Entry point: `index.js`
   - Environment variables: Add `OPENAI_API_KEY`
5. Click "Restart"

**Note:** Shared hosting may have WebSocket limitations. VPS is recommended for production.

### Client on Hostinger Static Hosting

1. Upload `client/` contents to a subdomain
2. Or use Hostinger's Website Builder static hosting
3. Configure URL parameters to point to your relay server

---

## Firewall Configuration (VPS)

```bash
# Allow HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# If not using Traefik, allow direct ports
ufw allow 3000/tcp  # WebSocket
ufw allow 3001/tcp  # Health check

# Enable firewall
ufw enable
```

---

## Monitoring & Logs

```bash
# View all logs
docker compose logs -f

# View specific service
docker compose logs -f relay-server

# Check resource usage
docker stats

# Restart services
docker compose restart

# Update and redeploy
git pull
docker compose build --no-cache
docker compose up -d
```

---

## Troubleshooting

### WebSocket Connection Fails

```bash
# Check if relay is running
docker compose ps
docker compose logs relay-server

# Test locally inside container
docker compose exec relay-server wget -q -O- http://localhost:3001/health
```

### SSL Certificate Issues

```bash
# Check Traefik logs
docker compose logs traefik

# Verify DNS propagation
dig voice.yourdomain.com

# Force certificate renewal
docker compose exec traefik rm /letsencrypt/acme.json
docker compose restart traefik
```

### Port Already in Use

```bash
# Find what's using the port
lsof -i :3000
netstat -tulpn | grep 3000

# Kill process or change port in docker-compose.yml
```

---

## Quick Reference

| Deployment | Client URL | Relay URL | SSL |
|------------|------------|-----------|-----|
| Local Docker | http://localhost:8080 | ws://localhost:3000 | No |
| VPS + Traefik | https://voice.domain.com | wss://relay.domain.com | Yes |
| Hostinger VPS | https://voice.domain.com | wss://relay.domain.com | Yes |
| Hostinger Shared | (separate static host) | wss://relay.domain.com | Maybe |

**Full Voice Agent URL (production):**
```
https://voice.yourdomain.com?wss=wss://relay.yourdomain.com&calendar_webhook=https://your-n8n.app.n8n.cloud/webhook/calendar&webhook_secret=YOUR_SECRET
```
