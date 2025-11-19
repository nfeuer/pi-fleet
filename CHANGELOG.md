# Changelog

All notable changes to Pi Fleet Manager will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2024

### Added

#### Authentication & Access Control
- User authentication system with login/logout
- Role-based access control (Admin, User, Viewer)
- JWT token support for API authentication
- Session management
- Default admin account creation

#### Device Organization
- Device grouping functionality
- Tag system for flexible device categorization
- Many-to-many relationships for groups and tags
- Group and tag management via API
- Filter devices by group or tag

#### Alerting System
- Alert rule engine for proactive monitoring
- Support for CPU, memory, temperature, disk, and offline alerts
- Customizable thresholds and conditions (>, <, =)
- Severity levels (info, warning, critical)
- Email notification support
- Alert notification history
- Alert acknowledgment system
- Device-specific and group-based alert rules
- Standalone alert monitor service (`services/alert-monitor.py`)
- Pre-configured sample alert rules

#### Scheduled Tasks
- Task scheduling system (cron, interval, one-time)
- Automated fleet updates
- Recurring maintenance windows
- Task execution history
- Device filtering for scheduled tasks

#### Command Templates & Playbooks
- Reusable command sequence templates
- Multi-step command execution
- Template categories and organization
- Public/private template sharing
- Execute templates across multiple devices
- Pre-built maintenance templates

#### Enhanced Monitoring
- Device health scores (0-100)
- Historical metrics retention
- Device notes/documentation field
- Enhanced metrics API with time-based filtering
- Improved device status tracking

#### Export & Reporting
- Export metrics to CSV format
- Export metrics to JSON format
- Comprehensive fleet reports
- Device inventory exports
- Alert history exports
- Command history exports
- Export tool (`tools/export-metrics.py`)
- API endpoint for metric exports

#### Analytics & Visualization
- Enhanced dashboard with Chart.js integration
- Historical CPU usage charts
- Historical memory usage charts
- Device status pie charts
- Alert severity distribution charts
- Fleet statistics dashboard
- Time-range selection for analytics

#### API Extensions
- `/api/v2/groups` - Group management endpoints
- `/api/v2/tags` - Tag management endpoints
- `/api/v2/alerts/rules` - Alert rule management
- `/api/v2/alerts/notifications` - Alert notification management
- `/api/v2/templates` - Command template management
- `/api/v2/stats/*` - Fleet statistics endpoints
- `/api/v2/export/*` - Data export endpoints
- Backward compatible with V1 API

#### Tools & Utilities
- Database upgrade script (`upgrade-to-v2.py`)
- Alert monitoring service
- Metrics export utility
- Sample data creation
- Database backup during upgrade

#### Documentation
- Comprehensive V2 features guide (`docs/V2_FEATURES.md`)
- Quick reference card (`docs/QUICK_REFERENCE.md`)
- API extensions documentation
- Migration guide from V1 to V2
- Best practices guide
- Troubleshooting guide for V2 features

### Changed

#### Database Schema
- Added `users` table for authentication
- Added `device_groups` table
- Added `tags` table
- Added `alert_rules` table
- Added `alert_notifications` table
- Added `scheduled_tasks` table
- Added `command_templates` table
- Added `device_group_association` junction table
- Added `device_tag_association` junction table
- Extended `devices` table with `notes` and `health_score` columns
- Extended `commands` table with `created_by` column

#### Dependencies
- Added `flask-login` for session management
- Added `flask-jwt-extended` for JWT authentication
- Added `flask-mail` for email notifications
- Added `bcrypt` and `werkzeug` for password hashing
- Added `apscheduler` for task scheduling

#### Server
- Updated server version to 2.0.0
- Enhanced API with V2 endpoints
- Improved error handling
- Added authentication middleware

### Fixed
- Improved error handling in alert system
- Better database connection management
- Enhanced logging throughout the system

### Security
- Password hashing with bcrypt
- JWT token-based API authentication
- Session management
- Role-based access control
- SQL injection protection via SQLAlchemy ORM

## [1.0.0] - 2024

### Added

#### Core Functionality
- Central fleet management server
- Device agent for Raspberry Pi
- REST API for device management
- Web dashboard for monitoring
- Device auto-discovery and registration
- Real-time metrics collection
- Remote command execution

#### Monitoring
- CPU usage monitoring
- Memory usage monitoring
- Temperature monitoring
- Disk space monitoring
- Uptime tracking
- Service health checks
- Network connectivity monitoring

#### Management Features
- Remote command execution (shell, update, service, reboot)
- SSH key management tools
- Configuration deployment
- Backup and restore capabilities
- Fleet-wide update orchestration

#### Dashboard
- Real-time device status
- Fleet summary statistics
- Device detail views
- Command execution interface
- Command history tracking

#### Tools
- `pi-fleet-manager.py` - Main server
- `pi-agent.py` - Device agent
- `update-fleet.sh` - Fleet update orchestration
- `tools/ssh/manage-keys.sh` - SSH key management
- `tools/backup/backup-fleet.sh` - Fleet backup
- `tools/backup/restore-device.sh` - Device restoration
- `tools/config/deploy-config.py` - Configuration deployment
- `install-agent.sh` - Agent installation script

#### Documentation
- Comprehensive README
- Quick start guide
- API reference
- Setup instructions
- Troubleshooting guide

### Supported Platforms
- Raspberry Pi 5
- Raspberry Pi 4
- Raspberry Pi 3
- Raspberry Pi Zero W/2W
- Raspberry Pi OS (Bullseye, Bookworm)
- Ubuntu Server for Raspberry Pi

## Migration Guide

### Upgrading from V1 to V2

1. **Backup your database:**
   ```bash
   cp fleet.db fleet_backup.db
   ```

2. **Install new dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Run upgrade script:**
   ```bash
   python3 upgrade-to-v2.py
   ```

4. **Start new services (optional):**
   ```bash
   python3 services/alert-monitor.py &
   ```

5. **Log in to dashboard:**
   - Username: admin
   - Password: admin123
   - **Change password immediately!**

### Breaking Changes

**None** - V2 is fully backward compatible with V1. All existing devices, metrics, and functionality remain intact.

### New Requirements

- Python 3.7+ (same as V1)
- Additional Python packages (automatically installed)
- Optional: SMTP server for email notifications

## Roadmap

### Planned for V2.1
- [ ] PostgreSQL support for large fleets
- [ ] Mobile-responsive dashboard improvements
- [ ] Webhook support for alerts
- [ ] Slack/Discord integration
- [ ] Advanced role permissions

### Planned for V2.2
- [ ] Container monitoring (Docker)
- [ ] Kubernetes integration
- [ ] Metrics aggregation and downsampling
- [ ] Advanced analytics and ML-based predictions
- [ ] Multi-tenancy support

### Planned for V3.0
- [ ] Native mobile apps (iOS/Android)
- [ ] Grafana integration
- [ ] Prometheus exporter
- [ ] Advanced automation engine
- [ ] Device provisioning system

## Contributors

This project is developed and maintained for home infrastructure and IoT project management.

## License

This project is provided as-is for educational and personal use.

---

For more information, see:
- [README.md](README.md) - Main documentation
- [docs/V2_FEATURES.md](docs/V2_FEATURES.md) - V2 features guide
- [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md) - Quick reference
