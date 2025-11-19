# Quick Start Guide

Get your Pi Fleet up and running in 10 minutes!

## Prerequisites

- One server machine (can be a Pi, laptop, or cloud server) for the fleet manager
- One or more Raspberry Pi devices
- All devices on the same network

## Step 1: Start the Fleet Manager (5 minutes)

On your server machine:

```bash
# Clone the repository
git clone <repository-url>
cd pi-fleet

# Install dependencies
pip3 install -r requirements.txt

# Start the fleet manager
python3 pi-fleet-manager.py --host 0.0.0.0 --port 5000
```

The dashboard will be available at: `http://<server-ip>:5000`

## Step 2: Install Agent on Your Pi Devices (5 minutes)

### Option A: Automated Installation (Recommended)

On each Raspberry Pi:

```bash
# Download the agent file
scp user@server:/path/to/pi-fleet/pi-agent.py ~/
scp user@server:/path/to/pi-fleet/install-agent.sh ~/

# Run the installer
chmod +x install-agent.sh
./install-agent.sh http://<server-ip>:5000
```

The installer will:
- Install dependencies
- Set up the agent
- Create a systemd service
- Start the agent automatically

### Option B: Manual Installation

On each Raspberry Pi:

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y python3 python3-pip
pip3 install psutil requests

# Copy the agent
scp user@server:/path/to/pi-fleet/pi-agent.py ~/

# Run the agent
python3 pi-agent.py --server http://<server-ip>:5000 --name my-pi-device
```

## Step 3: Verify in Dashboard

1. Open your browser to `http://<server-ip>:5000`
2. You should see your devices appear in the dashboard
3. Click on a device to view detailed metrics

## What's Next?

### Set Up Automated Updates

```bash
# On the server
./update-fleet.sh --server http://localhost:5000 --dry-run
```

### Configure SSH Key Management

```bash
# Generate and distribute SSH keys
./tools/ssh/manage-keys.sh generate
./tools/ssh/manage-keys.sh distribute
```

### Set Up Backups

```bash
# Create device list
cat > config/devices.txt <<EOF
pi@device1.local
pi@device2.local
EOF

# Run backup
./tools/backup/backup-fleet.sh
```

### Deploy Configurations

```bash
# Create a deployment spec
cat > my-deployment.yaml <<EOF
deployments:
  - template: config/templates/mqtt-config.conf.j2
    target: /etc/mqtt/mqtt.conf
    mode: "0644"
    variables:
      mqtt_broker: "192.168.1.10"
      mqtt_port: 1883
EOF

# Deploy to fleet
python3 tools/config/deploy-config.py \
  --server http://localhost:5000 \
  --config my-deployment.yaml
```

## Troubleshooting

### Can't connect to server

```bash
# Test connectivity
ping <server-ip>
curl http://<server-ip>:5000/api/status
```

### Agent not appearing in dashboard

```bash
# Check if agent is running
sudo systemctl status pi-fleet-agent

# View agent logs
sudo journalctl -u pi-fleet-agent -f
```

### Dashboard not loading

```bash
# Check if server is running
curl http://localhost:5000/api/status

# View server logs
python3 pi-fleet-manager.py --debug
```

## Common Commands

### Server Management

```bash
# Start server
python3 pi-fleet-manager.py --host 0.0.0.0 --port 5000

# Start with debug logging
python3 pi-fleet-manager.py --debug

# Run as systemd service (production)
sudo systemctl start pi-fleet-server
```

### Agent Management

```bash
# Start agent
python3 pi-agent.py --server http://<server-ip>:5000

# Start with custom name
python3 pi-agent.py --server http://<server-ip>:5000 --name my-device

# Check agent status
sudo systemctl status pi-fleet-agent

# View agent logs
sudo journalctl -u pi-fleet-agent -f

# Restart agent
sudo systemctl restart pi-fleet-agent
```

### Fleet Operations

```bash
# Update all devices
./update-fleet.sh --server http://<server-ip>:5000

# Update specific devices
./update-fleet.sh --filter "living-room"

# Backup all devices
./tools/backup/backup-fleet.sh

# Restore a device
./tools/backup/restore-device.sh latest pi@device.local
```

## Production Deployment Tips

1. **Use HTTPS**: Set up a reverse proxy (nginx/apache) with SSL
2. **Set up systemd services**: For automatic startup on boot
3. **Configure firewall**: Restrict access to port 5000
4. **Regular backups**: Schedule daily backups with cron
5. **Monitor disk space**: The database can grow with historical metrics
6. **Use a dedicated server**: For reliability, run the manager on a dedicated machine

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the dashboard features
- Set up automated monitoring and alerts
- Create custom configuration templates
- Integrate with your existing home automation

## Getting Help

If you run into issues:
1. Check the troubleshooting section above
2. Review the logs for error messages
3. Ensure all devices are on the same network
4. Verify firewall rules allow communication
5. Check the full README for more details

Happy fleet managing! 🍓
