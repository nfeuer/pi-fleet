# Raspberry Pi Fleet Management System

A comprehensive, centralized management system for fleets of Raspberry Pi devices. Monitor, update, configure, and manage multiple Pi devices from a single control point.

> **🎉 Version 2.0 Available!** Now with user authentication, alerting, device grouping, scheduled tasks, and more!
> See [V2_FEATURES.md](docs/V2_FEATURES.md) for details and [upgrade instructions](#upgrading-to-v2).

## Features

### Fleet Management
- **Auto-discovery and Registration**: Devices automatically register with the central server
- **Device Inventory**: Track hardware specs, OS versions, and installed packages
- **Real-time Monitoring**: CPU, RAM, temperature, disk space, and service health
- **Remote Management**: Execute commands, deploy files, manage services
- **Centralized Updates**: Coordinate OS and package updates across the fleet

### Monitoring & Analytics
- **Web Dashboard**: Real-time visualization of fleet status and metrics
- **Historical Data**: Track performance and health trends over time
- **Alert Capable**: Monitor for offline devices and resource issues
- **Fleet-wide Statistics**: Aggregate metrics across all devices

### Configuration Management
- **Template-based Deployment**: Use Jinja2 templates for flexible configurations
- **Group Management**: Apply configurations to device groups
- **Version Control Ready**: Track configuration changes over time
- **Rollback Support**: Restore previous configurations

### Security & Maintenance
- **SSH Key Management**: Centralized key distribution and rotation
- **Backup & Restore**: Automated configuration backups
- **Secure Communication**: HTTPS/SSH for all remote operations
- **Low Overhead**: Minimal resource usage on Pi devices

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 Fleet Manager Server                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   REST API   │  │   Database   │  │  Dashboard   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
    ┌──────────────┐┌──────────────┐┌──────────────┐
    │   Pi Agent   ││   Pi Agent   ││   Pi Agent   │
    │  (Device 1)  ││  (Device 2)  ││  (Device 3)  │
    └──────────────┘└──────────────┘└──────────────┘
```

## Quick Start

### Prerequisites

**Fleet Manager Server:**
- Python 3.7+
- Linux/macOS/Windows

**Raspberry Pi Devices:**
- Raspberry Pi 3, 4, 5, or Zero
- Raspberry Pi OS (Bullseye or later recommended)
- Python 3.7+
- Network connectivity to the fleet manager

### Installation

#### 1. Set Up Fleet Manager Server

```bash
# Clone the repository
git clone <repository-url>
cd pi-fleet

# Install dependencies
pip3 install -r requirements.txt

# Start the fleet manager
python3 pi-fleet-manager.py --host 0.0.0.0 --port 5000
```

The dashboard will be available at `http://<server-ip>:5000`

#### 2. Install Agent on Raspberry Pi Devices

Copy the agent to each Pi device:

```bash
# On each Pi device
scp pi-agent.py pi@<pi-hostname>:~/
scp requirements.txt pi@<pi-hostname>:~/

# SSH into the Pi
ssh pi@<pi-hostname>

# Install dependencies
pip3 install -r requirements.txt

# Run the agent
python3 pi-agent.py --server http://<server-ip>:5000 --name my-pi-device
```

#### 3. Set Up as a Service (Recommended)

Create a systemd service to run the agent automatically:

```bash
sudo nano /etc/systemd/system/pi-fleet-agent.service
```

Add the following content:

```ini
[Unit]
Description=Pi Fleet Agent
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python3 /home/pi/pi-agent.py --server http://<server-ip>:5000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pi-fleet-agent
sudo systemctl start pi-fleet-agent
sudo systemctl status pi-fleet-agent
```

## Usage

### Web Dashboard

Access the dashboard at `http://<server-ip>:5000` to:
- View all registered devices
- Monitor real-time metrics
- Send commands to devices
- View command history
- Check fleet-wide statistics

### Update Fleet

Update all devices or specific groups:

```bash
# Update all devices
./update-fleet.sh --server http://<server-ip>:5000

# Update specific devices
./update-fleet.sh --filter "livingroom"

# Update in smaller batches with longer delays
./update-fleet.sh --batch 3 --delay 120

# Dry run to see what would be updated
./update-fleet.sh --dry-run
```

### SSH Key Management

Manage SSH keys across your fleet:

```bash
# Generate new SSH key pair
./tools/ssh/manage-keys.sh generate

# Distribute key to all devices
./tools/ssh/manage-keys.sh distribute

# Audit key deployment
./tools/ssh/manage-keys.sh audit

# Rotate keys
./tools/ssh/manage-keys.sh rotate
```

### Configuration Deployment

Deploy configurations using templates:

```bash
# Create deployment specification (YAML)
cat > deploy-spec.yaml <<EOF
filter: ""  # All devices
deployments:
  - template: config/templates/nginx.conf.j2
    target: /etc/nginx/nginx.conf
    mode: "0644"
    variables:
      server_name: example.com
      port: 80
EOF

# Deploy configuration
python3 tools/config/deploy-config.py --server http://<server-ip>:5000 --config deploy-spec.yaml
```

### Backup & Restore

Backup device configurations:

```bash
# Setup devices list
cat > config/devices.txt <<EOF
pi@raspberrypi-1.local
pi@192.168.1.100
pi@192.168.1.101
EOF

# Backup all devices
./tools/backup/backup-fleet.sh

# Restore a device from backup
./tools/backup/restore-device.sh latest pi@raspberrypi-1.local

# Restore from specific backup
./tools/backup/restore-device.sh 20240101-120000 pi@192.168.1.100
```

## API Reference

### Device Registration

```bash
POST /api/devices/register
```

Register a new device or update existing device information.

### Send Heartbeat

```bash
POST /api/devices/heartbeat
```

Send device metrics and update status.

### List Devices

```bash
GET /api/devices
```

Get list of all registered devices.

### Get Device Details

```bash
GET /api/devices/{device_id}
```

Get detailed information about a specific device.

### Send Command

```bash
POST /api/devices/{device_id}/commands
```

Send a command to a device. Supported command types:
- `shell`: Execute shell command
- `update`: Run system updates
- `deploy_config`: Deploy configuration file
- `service`: Manage systemd service
- `reboot`: Schedule device reboot

Example:

```bash
curl -X POST http://localhost:5000/api/devices/{device_id}/commands \
  -H "Content-Type: application/json" \
  -d '{
    "type": "shell",
    "payload": {
      "command": "uptime",
      "timeout": 30
    }
  }'
```

### Fleet Summary

```bash
GET /api/fleet/summary
```

Get fleet-wide statistics and health summary.

## Configuration

### Agent Configuration

Create `/etc/pi-fleet/agent.conf` for persistent configuration:

```ini
[server]
url = http://192.168.1.100:5000

[agent]
name = my-pi-device
interval = 60

[logging]
level = INFO
```

### Server Configuration

Environment variables:
- `DATABASE_FILE`: Path to SQLite database (default: `fleet.db`)
- `SERVER_VERSION`: Server version identifier

### Custom Backup Paths

Create `config/backup-paths.txt` to specify additional paths to backup:

```
/home/pi/.config
/opt/myapp/config
/etc/custom-service
```

## Supported Devices

- Raspberry Pi 5
- Raspberry Pi 4 Model B
- Raspberry Pi 3 Model B/B+
- Raspberry Pi Zero W/2W
- Raspberry Pi 400

Tested with:
- Raspberry Pi OS (Bullseye, Bookworm)
- Ubuntu Server for Raspberry Pi
- Debian-based distributions

## Troubleshooting

### Agent Can't Connect to Server

1. Check network connectivity:
   ```bash
   ping <server-ip>
   curl http://<server-ip>:5000/api/status
   ```

2. Verify firewall rules allow port 5000

3. Check server logs for errors

### Device Shows as Offline

1. Check if agent is running:
   ```bash
   sudo systemctl status pi-fleet-agent
   ```

2. Check agent logs:
   ```bash
   tail -f /etc/pi-fleet/agent.log
   ```

3. Verify network connectivity to server

### High CPU/Memory Usage

The agent is designed to be lightweight. If you're experiencing high resource usage:

1. Increase the check interval:
   ```bash
   python3 pi-agent.py --server <url> --interval 120
   ```

2. Check for pending commands that might be resource-intensive

### Temperature Warnings

If temperature readings are not available:
- Ensure you have permissions to read `/sys/class/thermal/thermal_zone0/temp`
- Try installing `vcgencmd` tool: `sudo apt-get install libraspberrypi-bin`

## Security Considerations

1. **Use HTTPS**: Configure the server with SSL/TLS in production
2. **Firewall**: Restrict access to the fleet manager port
3. **SSH Keys**: Use SSH key authentication instead of passwords
4. **Network Isolation**: Run on a private network or VPN
5. **Regular Updates**: Keep all devices and the server updated
6. **Backup Encryption**: Encrypt backup files containing sensitive data

## Performance

- **Agent overhead**: ~10-20MB RAM, <1% CPU
- **Check interval**: Default 60 seconds (configurable)
- **Database**: SQLite for up to 100 devices (PostgreSQL recommended for larger fleets)
- **Metrics retention**: 7 days by default (configurable)

## Development

### Running Tests

```bash
# Install dev dependencies
pip3 install pytest pytest-cov

# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

### Project Structure

```
pi-fleet/
├── pi-agent.py              # Agent that runs on each Pi
├── pi-fleet-manager.py      # Central management server
├── update-fleet.sh          # Fleet update orchestration
├── requirements.txt         # Python dependencies
├── dashboard/               # Web dashboard
│   ├── index.html
│   └── static/
│       ├── css/
│       └── js/
├── tools/
│   ├── ssh/                 # SSH key management
│   ├── backup/              # Backup/restore tools
│   └── config/              # Configuration deployment
└── config/                  # Configuration templates
    └── templates/
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is provided as-is for educational and personal use.

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check existing documentation
- Review troubleshooting section

## Upgrading to V2

Version 2.0 adds powerful new features while maintaining full backward compatibility.

### What's New in V2

✅ **User Authentication & RBAC** - Multi-user support with admin/user/viewer roles
✅ **Device Grouping & Tagging** - Organize devices logically
✅ **Alerting System** - Proactive monitoring with email notifications
✅ **Scheduled Tasks** - Automate maintenance with cron-like scheduling
✅ **Command Templates** - Reusable command sequences
✅ **Enhanced Analytics** - Historical charts and advanced reporting
✅ **Export Tools** - Export metrics to CSV/JSON for analysis

### Upgrade Process

```bash
# 1. Backup your database
cp fleet.db fleet_backup.db

# 2. Install new dependencies
pip3 install -r requirements.txt

# 3. Run upgrade script
python3 upgrade-to-v2.py

# 4. Start alert monitor (optional)
python3 services/alert-monitor.py &

# 5. Log in to dashboard
# Username: admin
# Password: admin123 (change immediately!)
```

### Documentation

- **[V2 Features Guide](docs/V2_FEATURES.md)** - Complete guide to all V2 features
- **[Quick Reference](docs/QUICK_REFERENCE.md)** - Command cheat sheet
- **[CHANGELOG](CHANGELOG.md)** - Detailed change log

## Roadmap

### Completed in V2.0
- [x] Email/Slack notifications
- [x] Device grouping and tagging
- [x] Role-based access control
- [x] Advanced alerting system
- [x] Scheduled task automation
- [x] Command templates/playbooks

### Planned for Future Releases
- [ ] Ansible playbook integration
- [ ] Docker container monitoring
- [ ] Prometheus/Grafana integration
- [ ] PostgreSQL support for large fleets (>100 devices)
- [ ] Mobile app for monitoring
- [ ] Kubernetes cluster support
- [ ] Advanced ML-based predictions

## Acknowledgments

Built for home infrastructure and IoT project management.
