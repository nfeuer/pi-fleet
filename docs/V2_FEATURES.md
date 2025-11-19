# Pi Fleet Manager V2 - New Features Guide

This guide covers all the new features added in Version 2.0 of Pi Fleet Manager.

## Table of Contents

1. [Overview](#overview)
2. [User Authentication & RBAC](#user-authentication--rbac)
3. [Device Grouping & Tagging](#device-grouping--tagging)
4. [Alerting System](#alerting-system)
5. [Scheduled Tasks](#scheduled-tasks)
6. [Command Templates](#command-templates)
7. [Enhanced Monitoring](#enhanced-monitoring)
8. [Export & Reporting](#export--reporting)
9. [API Extensions](#api-extensions)

## Overview

Version 2.0 adds enterprise-grade features to Pi Fleet Manager:

- **Multi-user support** with role-based access control
- **Device organization** through groups and tags
- **Proactive monitoring** with customizable alerts
- **Automation** via scheduled tasks and templates
- **Advanced analytics** and export capabilities

### Upgrading from V1

```bash
# 1. Backup your database
cp fleet.db fleet_backup.db

# 2. Install new dependencies
pip3 install -r requirements.txt

# 3. Run upgrade script
python3 upgrade-to-v2.py

# 4. Start enhanced services
python3 services/alert-monitor.py &
```

## User Authentication & RBAC

### Roles

- **Admin**: Full access to all features
- **User**: Can view and manage devices, execute commands
- **Viewer**: Read-only access to dashboard and metrics

### Default Credentials

After upgrade, log in with:
- Username: `admin`
- Password: `admin123`

**⚠️ Change immediately in production!**

### Managing Users

```python
# Via Python API
from pi_fleet_manager_enhanced import User, db

# Create new user
user = User(
    username='john',
    email='john@example.com',
    role='user'
)
user.set_password('secure_password')
db.session.add(user)
db.session.commit()

# Update user role
user = User.query.filter_by(username='john').first()
user.role = 'admin'
db.session.commit()
```

### API Authentication

Use JWT tokens for API access:

```bash
# Get token
curl -X POST http://localhost:5000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Use token
curl -H "Authorization: Bearer <token>" \
  http://localhost:5000/api/v2/devices
```

## Device Grouping & Tagging

### Device Groups

Organize devices by function, location, or any logical grouping.

```bash
# Create group via API
curl -X POST http://localhost:5000/api/v2/groups \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Servers",
    "description": "Production IoT devices"
  }'

# Add device to group
curl -X POST http://localhost:5000/api/v2/groups/1/devices \
  -H "Content-Type: application/json" \
  -d '{"device_id": "pi-001"}'
```

### Tags

Tag devices for flexible filtering and bulk operations.

```bash
# Create tag
curl -X POST http://localhost:5000/api/v2/tags \
  -H "Content-Type: application/json" \
  -d '{
    "name": "production",
    "color": "#EF4444"
  }'

# Add tag to device
curl -X POST http://localhost:5000/api/v2/devices/pi-001/tags \
  -H "Content-Type: application/json" \
  -d '{"tag_id": 1}'
```

### Use Cases

**Location-based groups:**
- `Living Room`
- `Kitchen`
- `Garage`

**Function-based tags:**
- `camera` - Security cameras
- `sensor` - Environmental sensors
- `media` - Media players
- `automation` - Home automation controllers

## Alerting System

### Alert Rules

Create rules to monitor device health and trigger notifications.

#### Pre-configured Rules

After upgrade, these rules are automatically created:

1. **High CPU Usage** - Alert when CPU > 90%
2. **High Temperature** - Alert when temp > 80°C
3. **Low Disk Space** - Alert when disk > 90%
4. **Device Offline** - Alert when device goes offline

#### Creating Custom Rules

```bash
curl -X POST http://localhost:5000/api/v2/alerts/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Memory Usage",
    "description": "Alert when memory exceeds 85%",
    "metric_type": "memory",
    "condition": "gt",
    "threshold": 85.0,
    "duration": 60,
    "severity": "warning",
    "notify_email": true,
    "email_addresses": ["admin@example.com"],
    "device_filter": {
      "groups": [1],
      "tags": ["production"]
    }
  }'
```

#### Metric Types

- `cpu` - CPU usage percentage
- `memory` - Memory usage percentage
- `temperature` - CPU temperature (°C)
- `disk` - Disk usage percentage
- `offline` - Device offline status

#### Conditions

- `gt` - Greater than
- `lt` - Less than
- `eq` - Equal to

#### Severities

- `info` - Informational
- `warning` - Warning condition
- `critical` - Critical condition

### Alert Notifications

View and manage alert notifications:

```bash
# Get unacknowledged alerts
curl http://localhost:5000/api/v2/alerts/notifications

# Acknowledge alert
curl -X POST http://localhost:5000/api/v2/alerts/notifications/1/acknowledge
```

### Email Configuration

Configure email in the main manager file or via environment variables:

```python
# Email settings
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your-app-password'
app.config['MAIL_DEFAULT_SENDER'] = 'pi-fleet@example.com'
```

### Alert Monitor Service

The alert monitor runs as a separate service:

```bash
# Start alert monitor
python3 services/alert-monitor.py

# Run with custom interval (default: 60 seconds)
python3 services/alert-monitor.py --interval 30

# Enable debug logging
python3 services/alert-monitor.py --debug
```

#### Running as systemd Service

```ini
[Unit]
Description=Pi Fleet Alert Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/pi-fleet
ExecStart=/usr/bin/python3 services/alert-monitor.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Scheduled Tasks

Automate recurring operations across your fleet.

### Creating Scheduled Tasks

```bash
curl -X POST http://localhost:5000/api/v2/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Nightly Updates",
    "description": "Update packages every night at 2 AM",
    "task_type": "update",
    "schedule_type": "cron",
    "schedule_config": {
      "hour": 2,
      "minute": 0
    },
    "device_filter": {
      "groups": [1]
    },
    "task_payload": {
      "update_type": "packages"
    }
  }'
```

### Schedule Types

#### Cron Schedule

```json
{
  "schedule_type": "cron",
  "schedule_config": {
    "minute": 0,
    "hour": 2,
    "day_of_week": "*"
  }
}
```

#### Interval Schedule

```json
{
  "schedule_type": "interval",
  "schedule_config": {
    "hours": 6
  }
}
```

#### One-time Schedule

```json
{
  "schedule_type": "once",
  "schedule_config": {
    "run_at": "2024-12-31T23:59:00"
  }
}
```

### Task Types

- `command` - Execute shell command
- `update` - Run system updates
- `backup` - Create backups
- `reboot` - Restart devices

## Command Templates

Reusable command sequences for common operations.

### Creating Templates

```bash
curl -X POST http://localhost:5000/api/v2/templates \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Full System Maintenance",
    "description": "Complete maintenance routine",
    "category": "maintenance",
    "steps": [
      {
        "type": "update",
        "payload": {"update_type": "packages"}
      },
      {
        "type": "shell",
        "payload": {"command": "apt-get autoremove -y"}
      },
      {
        "type": "shell",
        "payload": {"command": "apt-get clean"}
      }
    ]
  }'
```

### Example Templates

#### Deploy IoT Sensor

```json
{
  "name": "Deploy IoT Sensor",
  "category": "deployment",
  "steps": [
    {
      "type": "shell",
      "payload": {"command": "pip3 install paho-mqtt"}
    },
    {
      "type": "deploy_config",
      "payload": {
        "path": "/etc/sensor/config.yaml",
        "content": "..."
      }
    },
    {
      "type": "service",
      "payload": {"service": "sensor", "action": "restart"}
    }
  ]
}
```

#### Security Hardening

```json
{
  "name": "Basic Security Hardening",
  "category": "security",
  "steps": [
    {
      "type": "shell",
      "payload": {"command": "ufw enable"}
    },
    {
      "type": "shell",
      "payload": {"command": "ufw allow 22/tcp"}
    },
    {
      "type": "shell",
      "payload": {"command": "apt-get install -y fail2ban"}
    }
  ]
}
```

### Executing Templates

```bash
# Execute on specific devices
curl -X POST http://localhost:5000/api/v2/templates/1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "device_ids": ["pi-001", "pi-002"]
  }'
```

## Enhanced Monitoring

### Health Scores

Devices now have health scores (0-100) based on:
- CPU usage
- Memory usage
- Temperature
- Disk space
- Uptime stability
- Command success rate

### Historical Data

V2 stores historical metrics for trend analysis:

```bash
# Get metrics for last 7 days
curl "http://localhost:5000/api/devices/pi-001/metrics?hours=168"
```

### Device Notes

Add notes to devices for documentation:

```bash
curl -X PATCH http://localhost:5000/api/devices/pi-001 \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Living room Pi. Running Home Assistant. Do not reboot during evenings."
  }'
```

## Export & Reporting

### Export Metrics

Export fleet data for external analysis:

```bash
# Export all metrics to CSV
python3 tools/export-metrics.py \
  --format csv \
  --output fleet-metrics.csv

# Export specific device
python3 tools/export-metrics.py \
  --format json \
  --device pi-001 \
  --days 7 \
  --output pi-001-metrics.json

# Generate comprehensive report
python3 tools/export-metrics.py \
  --report \
  --output fleet-report.json
```

### Export via API

```bash
# Export metrics as CSV
curl "http://localhost:5000/api/v2/export/metrics?days=7" \
  -o metrics.csv
```

### Report Contents

Comprehensive reports include:
- Fleet summary statistics
- Device inventory
- Recent alerts
- Command history
- Performance trends

## API Extensions

### New Endpoints

#### Groups

- `GET /api/v2/groups` - List all groups
- `POST /api/v2/groups` - Create group
- `POST /api/v2/groups/{id}/devices` - Add device to group

#### Tags

- `GET /api/v2/tags` - List all tags
- `POST /api/v2/tags` - Create tag
- `POST /api/v2/devices/{id}/tags` - Add tag to device

#### Alerts

- `GET /api/v2/alerts/rules` - List alert rules
- `POST /api/v2/alerts/rules` - Create alert rule
- `PUT /api/v2/alerts/rules/{id}` - Update alert rule
- `GET /api/v2/alerts/notifications` - List notifications
- `POST /api/v2/alerts/notifications/{id}/acknowledge` - Acknowledge alert

#### Templates

- `GET /api/v2/templates` - List templates
- `POST /api/v2/templates` - Create template
- `POST /api/v2/templates/{id}/execute` - Execute template

#### Statistics

- `GET /api/v2/stats/devices` - Device statistics
- `GET /api/v2/stats/alerts` - Alert statistics

#### Export

- `GET /api/v2/export/metrics` - Export metrics as CSV

### Complete API Documentation

For full API documentation, see [API_REFERENCE.md](API_REFERENCE.md)

## Best Practices

### Alert Configuration

1. **Start conservative** - Set higher thresholds initially
2. **Monitor alert volume** - Adjust to avoid alert fatigue
3. **Use severity levels** - Reserve critical for urgent issues
4. **Test notifications** - Verify email delivery works
5. **Document rules** - Add clear descriptions

### Device Organization

1. **Use groups for hierarchy** - Location or function-based
2. **Use tags for attributes** - Multiple tags per device
3. **Consistent naming** - Use clear, descriptive names
4. **Regular cleanup** - Remove obsolete tags/groups

### Scheduled Tasks

1. **Test first** - Run manually before scheduling
2. **Stagger timing** - Avoid all devices updating simultaneously
3. **Maintenance windows** - Schedule during low-usage periods
4. **Monitor execution** - Check task history regularly

### Security

1. **Change default password** - Immediately after upgrade
2. **Use strong passwords** - For all user accounts
3. **Enable HTTPS** - In production deployments
4. **Limit API access** - Use firewall rules
5. **Regular updates** - Keep dependencies updated

## Troubleshooting

### Alert Monitor Not Running

```bash
# Check if running
ps aux | grep alert-monitor

# View logs
tail -f /var/log/pi-fleet/alert-monitor.log

# Restart service
sudo systemctl restart pi-fleet-alert-monitor
```

### Email Notifications Not Sending

1. Check SMTP configuration
2. Verify firewall allows SMTP traffic
3. Test email settings manually
4. Check alert-monitor logs

### Missing Features After Upgrade

Run upgrade script again:

```bash
python3 upgrade-to-v2.py
```

### Database Issues

Restore from backup:

```bash
cp fleet_backup_YYYYMMDD_HHMMSS.db fleet.db
```

## Migration from V1

All V1 features remain fully functional. V2 adds new capabilities without breaking existing functionality.

### What's Preserved

- All devices and their history
- All metrics
- Command history
- Dashboard functionality

### What's New

- User accounts and authentication
- Groups and tags (empty after upgrade)
- Alert rules (sample rules created)
- Templates (empty after upgrade)
- Enhanced API endpoints

## Next Steps

1. **Configure alerts** - Set up rules for your fleet
2. **Organize devices** - Create groups and apply tags
3. **Create templates** - Build reusable command sequences
4. **Schedule tasks** - Automate routine maintenance
5. **Export data** - Generate reports for analysis

## Support

For issues or questions:
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review [API_REFERENCE.md](API_REFERENCE.md)
- Open an issue on GitHub

## Version History

- **V2.0.0** - Initial release with auth, alerting, grouping, scheduling
- **V1.0.0** - Original release with basic fleet management
