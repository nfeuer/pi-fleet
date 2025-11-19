# Pi Fleet Manager - Quick Reference Card

## Essential Commands

### Server Management

```bash
# Start fleet manager (V1)
python3 pi-fleet-manager.py --host 0.0.0.0 --port 5000

# Start alert monitor (V2)
python3 services/alert-monitor.py

# Upgrade to V2
python3 upgrade-to-v2.py
```

### Agent Management

```bash
# Start agent manually
python3 pi-agent.py --server http://SERVER_IP:5000 --name DEVICE_NAME

# Install as service
sudo ./install-agent.sh http://SERVER_IP:5000

# Check agent status
sudo systemctl status pi-fleet-agent

# View agent logs
sudo journalctl -u pi-fleet-agent -f
```

### Fleet Operations

```bash
# Update all devices
./update-fleet.sh --server http://SERVER_IP:5000

# Update specific devices
./update-fleet.sh --filter "PATTERN"

# Dry run (preview only)
./update-fleet.sh --dry-run

# Backup fleet
./tools/backup/backup-fleet.sh

# Restore device
./tools/backup/restore-device.sh latest pi@DEVICE

# Export metrics
python3 tools/export-metrics.py --format csv --output metrics.csv
```

### SSH Key Management

```bash
# Generate keys
./tools/ssh/manage-keys.sh generate

# Distribute to fleet
./tools/ssh/manage-keys.sh distribute

# Audit deployment
./tools/ssh/manage-keys.sh audit

# Rotate keys
./tools/ssh/manage-keys.sh rotate
```

## API Endpoints

### V1 Core Endpoints

```bash
# Server status
GET /api/status

# List devices
GET /api/devices

# Device details
GET /api/devices/{device_id}

# Device metrics
GET /api/devices/{device_id}/metrics?hours=24

# Send command
POST /api/devices/{device_id}/commands
{
  "type": "shell|update|service|reboot",
  "payload": {...}
}

# Fleet summary
GET /api/fleet/summary
```

### V2 Extended Endpoints

```bash
# Groups
GET    /api/v2/groups
POST   /api/v2/groups
POST   /api/v2/groups/{id}/devices

# Tags
GET    /api/v2/tags
POST   /api/v2/tags
POST   /api/v2/devices/{id}/tags

# Alerts
GET    /api/v2/alerts/rules
POST   /api/v2/alerts/rules
GET    /api/v2/alerts/notifications
POST   /api/v2/alerts/notifications/{id}/acknowledge

# Templates
GET    /api/v2/templates
POST   /api/v2/templates
POST   /api/v2/templates/{id}/execute

# Export
GET    /api/v2/export/metrics?days=7

# Stats
GET    /api/v2/stats/devices
GET    /api/v2/stats/alerts
```

## Command Payloads

### Shell Command
```json
{
  "type": "shell",
  "payload": {
    "command": "uptime",
    "timeout": 30
  }
}
```

### System Update
```json
{
  "type": "update",
  "payload": {
    "update_type": "packages"
  }
}
```

### Service Management
```json
{
  "type": "service",
  "payload": {
    "service": "nginx",
    "action": "restart"
  }
}
```

### Deploy Config
```json
{
  "type": "deploy_config",
  "payload": {
    "path": "/etc/app/config.yaml",
    "content": "...",
    "mode": "0644"
  }
}
```

### Reboot
```json
{
  "type": "reboot",
  "payload": {
    "delay": 1
  }
}
```

## Configuration Files

### Agent Service
`/etc/systemd/system/pi-fleet-agent.service`

### Server Service
`/etc/systemd/system/pi-fleet-server.service`

### Devices List
`config/devices.txt`

### Backup Paths
`config/backup-paths.txt`

### SSH Keys
`.ssh-keys/`

## Default Credentials (V2)

**Username:** admin
**Password:** admin123

⚠️ **Change immediately!**

## Port Usage

- **5000** - Fleet Manager Web/API
- **22** - SSH (for remote management)
- **25** - SMTP (for email alerts)

## File Locations

```
pi-fleet/
├── pi-fleet-manager.py      # Main server
├── pi-agent.py               # Device agent
├── upgrade-to-v2.py          # V2 upgrade script
├── update-fleet.sh           # Fleet updater
├── fleet.db                  # Database
├── config/                   # Configuration
│   ├── devices.txt
│   ├── backup-paths.txt
│   └── templates/
├── tools/
│   ├── ssh/manage-keys.sh
│   ├── backup/
│   │   ├── backup-fleet.sh
│   │   └── restore-device.sh
│   └── export-metrics.py
├── services/
│   └── alert-monitor.py
└── dashboard/                # Web UI
```

## Troubleshooting

### Agent Won't Connect
```bash
# Test connectivity
ping SERVER_IP
curl http://SERVER_IP:5000/api/status

# Check firewall
sudo ufw status
sudo ufw allow 5000/tcp

# Check agent logs
sudo journalctl -u pi-fleet-agent -n 50
```

### No Metrics Showing
```bash
# Check agent is running
sudo systemctl status pi-fleet-agent

# Verify agent can reach server
curl http://SERVER_IP:5000/api/status

# Check server logs
grep ERROR pi-fleet-manager.log
```

### Alerts Not Working
```bash
# Check alert monitor is running
ps aux | grep alert-monitor

# Start alert monitor
python3 services/alert-monitor.py &

# Check alert rules
curl http://SERVER_IP:5000/api/v2/alerts/rules
```

## Quick Setup (New Installation)

```bash
# 1. Server Setup
git clone <repo>
cd pi-fleet
pip3 install -r requirements.txt
python3 pi-fleet-manager.py &

# 2. Agent Setup (on each Pi)
scp server:/path/to/pi-agent.py .
python3 pi-agent.py --server http://SERVER_IP:5000 &

# 3. Access Dashboard
open http://SERVER_IP:5000
```

## Emergency Recovery

### Restore Database
```bash
cp fleet_backup_TIMESTAMP.db fleet.db
python3 pi-fleet-manager.py
```

### Reset Admin Password
```python
from pi_fleet_manager_enhanced import User, db
user = User.query.filter_by(username='admin').first()
user.set_password('newpassword')
db.session.commit()
```

### Clear Old Metrics
```python
from datetime import datetime, timedelta
from pi_fleet_manager_enhanced import Metric, db
cutoff = datetime.utcnow() - timedelta(days=30)
Metric.query.filter(Metric.timestamp < cutoff).delete()
db.session.commit()
```

## Performance Tuning

### For Large Fleets (>50 devices)

1. **Increase check intervals:**
   ```bash
   python3 pi-agent.py --interval 120
   ```

2. **Clean old metrics:**
   ```bash
   # Keep only 7 days
   python3 -c "from pi_fleet_manager import cleanup_old_metrics; cleanup_old_metrics(7)"
   ```

3. **Use PostgreSQL:**
   ```python
   app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:pass@localhost/fleet'
   ```

## Support Resources

- **Documentation:** `docs/`
- **V2 Features:** `docs/V2_FEATURES.md`
- **Troubleshooting:** `docs/TROUBLESHOOTING.md`
- **Examples:** `config/`

## Useful Snippets

### Bulk Tag Assignment
```python
from pi_fleet_manager_enhanced import Device, Tag, db
tag = Tag.query.filter_by(name='production').first()
devices = Device.query.filter(Device.device_name.like('%prod%')).all()
for device in devices:
    if tag not in device.tags:
        device.tags.append(tag)
db.session.commit()
```

### Custom Alert Rule
```bash
curl -X POST http://localhost:5000/api/v2/alerts/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Load",
    "metric_type": "cpu",
    "condition": "gt",
    "threshold": 80,
    "severity": "warning",
    "email_addresses": ["admin@example.com"]
  }'
```

### Batch Command Execution
```bash
for device in $(curl -s http://localhost:5000/api/devices | jq -r '.devices[].device_id'); do
  curl -X POST "http://localhost:5000/api/devices/$device/commands" \
    -H "Content-Type: application/json" \
    -d '{"type":"shell","payload":{"command":"uptime"}}'
done
```

---

**Version:** 2.0.0
**Last Updated:** 2024
