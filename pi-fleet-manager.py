#!/usr/bin/env python3
"""
Raspberry Pi Fleet Management Server

Central management server for controlling and monitoring a fleet of
Raspberry Pi devices. Provides REST API and web dashboard.

Usage:
    python3 pi-fleet-manager.py --host 0.0.0.0 --port 5000
"""

import argparse
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, and_
from sqlalchemy.exc import SQLAlchemyError

# Configuration
SERVER_VERSION = "1.0.0"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5000
DATABASE_FILE = "fleet.db"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('pi-fleet-manager')

# Flask app initialization
app = Flask(__name__,
            static_folder='dashboard/static',
            template_folder='dashboard')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DATABASE_FILE}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_SORT_KEYS'] = False

CORS(app)
db = SQLAlchemy(app)


# Database Models
class Device(db.Model):
    """Device model for fleet inventory."""
    __tablename__ = 'devices'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    device_name = db.Column(db.String(100), nullable=False)
    agent_version = db.Column(db.String(20))

    # Hardware info
    model = db.Column(db.String(200))
    revision = db.Column(db.String(50))
    cpu_count = db.Column(db.Integer)
    total_memory = db.Column(db.BigInteger)

    # OS info
    os_system = db.Column(db.String(50))
    os_release = db.Column(db.String(100))
    os_distribution = db.Column(db.String(200))
    architecture = db.Column(db.String(50))

    # Network info
    hostname = db.Column(db.String(100))
    ip_addresses = db.Column(db.Text)  # JSON

    # Status
    status = db.Column(db.String(20), default='online')  # online, offline, warning, error
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    metrics = db.relationship('Metric', backref='device', lazy='dynamic',
                            cascade='all, delete-orphan')
    commands = db.relationship('Command', backref='device', lazy='dynamic',
                             cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        """Convert device to dictionary."""
        return {
            'id': self.id,
            'device_id': self.device_id,
            'device_name': self.device_name,
            'agent_version': self.agent_version,
            'hardware': {
                'model': self.model,
                'revision': self.revision,
                'cpu_count': self.cpu_count,
                'total_memory': self.total_memory,
            },
            'os': {
                'system': self.os_system,
                'release': self.os_release,
                'distribution': self.os_distribution,
                'architecture': self.architecture,
            },
            'network': {
                'hostname': self.hostname,
                'ip_addresses': json.loads(self.ip_addresses) if self.ip_addresses else {},
            },
            'status': self.status,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
        }


class Metric(db.Model):
    """Metrics model for device telemetry."""
    __tablename__ = 'metrics'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), db.ForeignKey('devices.device_id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # CPU metrics
    cpu_percent = db.Column(db.Float)
    cpu_per_core = db.Column(db.Text)  # JSON

    # Memory metrics
    memory_total = db.Column(db.BigInteger)
    memory_available = db.Column(db.BigInteger)
    memory_percent = db.Column(db.Float)
    memory_used = db.Column(db.BigInteger)

    # Disk metrics
    disk_info = db.Column(db.Text)  # JSON

    # Temperature
    temperature = db.Column(db.Float)

    # Uptime
    uptime = db.Column(db.Float)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary."""
        return {
            'id': self.id,
            'device_id': self.device_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'cpu': {
                'percent': self.cpu_percent,
                'per_core': json.loads(self.cpu_per_core) if self.cpu_per_core else [],
            },
            'memory': {
                'total': self.memory_total,
                'available': self.memory_available,
                'percent': self.memory_percent,
                'used': self.memory_used,
            },
            'disk': json.loads(self.disk_info) if self.disk_info else {},
            'temperature': self.temperature,
            'uptime': self.uptime,
        }


class Command(db.Model):
    """Command model for remote execution."""
    __tablename__ = 'commands'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), db.ForeignKey('devices.device_id'), nullable=False, index=True)
    command_type = db.Column(db.String(50), nullable=False)
    payload = db.Column(db.Text)  # JSON
    status = db.Column(db.String(20), default='pending')  # pending, sent, completed, error
    result = db.Column(db.Text)  # JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    def to_dict(self) -> Dict[str, Any]:
        """Convert command to dictionary."""
        return {
            'id': self.id,
            'device_id': self.device_id,
            'type': self.command_type,
            'payload': json.loads(self.payload) if self.payload else {},
            'status': self.status,
            'result': json.loads(self.result) if self.result else {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


# API Routes
@app.route('/')
def index():
    """Serve the dashboard."""
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """Get server status."""
    return jsonify({
        'status': 'online',
        'version': SERVER_VERSION,
        'timestamp': datetime.utcnow().isoformat(),
    })


@app.route('/api/devices', methods=['GET'])
def list_devices():
    """List all devices."""
    try:
        devices = Device.query.all()
        return jsonify({
            'devices': [d.to_dict() for d in devices],
            'count': len(devices),
        })
    except Exception as e:
        logger.error(f"Error listing devices: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/devices/<device_id>', methods=['GET'])
def get_device(device_id):
    """Get specific device details."""
    try:
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            return jsonify({'error': 'Device not found'}), 404

        return jsonify(device.to_dict())
    except Exception as e:
        logger.error(f"Error getting device: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/devices/register', methods=['POST'])
def register_device():
    """Register a new device or update existing one."""
    try:
        data = request.json
        device_id = data.get('device_id')

        if not device_id:
            return jsonify({'error': 'device_id is required'}), 400

        # Check if device exists
        device = Device.query.filter_by(device_id=device_id).first()

        if device:
            # Update existing device
            logger.info(f"Updating device: {device_id}")
        else:
            # Create new device
            device = Device(device_id=device_id)
            logger.info(f"Registering new device: {device_id}")

        # Update device info
        device.device_name = data.get('device_name', device_id)
        device.agent_version = data.get('agent_version')

        # Hardware info
        hw = data.get('hardware', {})
        device.model = hw.get('model')
        device.revision = hw.get('revision')
        device.cpu_count = hw.get('cpu_count')
        device.total_memory = hw.get('total_memory')

        # OS info
        os_info = data.get('os', {})
        device.os_system = os_info.get('system')
        device.os_release = os_info.get('release')
        device.os_distribution = os_info.get('distribution')
        device.architecture = os_info.get('architecture')

        # Network info
        network = data.get('network', {})
        device.hostname = network.get('hostname')
        device.ip_addresses = json.dumps(network.get('interfaces', {}))

        # Update status
        device.status = 'online'
        device.last_seen = datetime.utcnow()

        if device.id is None:
            db.session.add(device)

        db.session.commit()

        return jsonify({
            'status': 'success',
            'device': device.to_dict(),
        }), 201

    except Exception as e:
        logger.error(f"Error registering device: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/devices/heartbeat', methods=['POST'])
def device_heartbeat():
    """Receive device heartbeat with metrics."""
    try:
        data = request.json
        device_id = data.get('device_id')

        if not device_id:
            return jsonify({'error': 'device_id is required'}), 400

        # Update device last_seen
        device = Device.query.filter_by(device_id=device_id).first()
        if device:
            device.last_seen = datetime.utcnow()
            device.status = 'online'

        # Store metrics
        metrics_data = data.get('metrics', {})
        metric = Metric(
            device_id=device_id,
            cpu_percent=metrics_data.get('cpu_percent'),
            cpu_per_core=json.dumps(metrics_data.get('cpu_per_core', [])),
            memory_total=metrics_data.get('memory', {}).get('total'),
            memory_available=metrics_data.get('memory', {}).get('available'),
            memory_percent=metrics_data.get('memory', {}).get('percent'),
            memory_used=metrics_data.get('memory', {}).get('used'),
            disk_info=json.dumps(metrics_data.get('disk', {})),
            temperature=metrics_data.get('temperature'),
            uptime=metrics_data.get('uptime'),
        )

        db.session.add(metric)
        db.session.commit()

        return jsonify({'status': 'success'})

    except Exception as e:
        logger.error(f"Error processing heartbeat: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/devices/<device_id>/metrics', methods=['GET'])
def get_device_metrics(device_id):
    """Get metrics for a device."""
    try:
        # Get query parameters
        limit = request.args.get('limit', 100, type=int)
        hours = request.args.get('hours', type=int)

        query = Metric.query.filter_by(device_id=device_id)

        # Filter by time if specified
        if hours:
            since = datetime.utcnow() - timedelta(hours=hours)
            query = query.filter(Metric.timestamp >= since)

        metrics = query.order_by(desc(Metric.timestamp)).limit(limit).all()

        return jsonify({
            'device_id': device_id,
            'metrics': [m.to_dict() for m in metrics],
            'count': len(metrics),
        })

    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/devices/<device_id>/commands', methods=['GET'])
def get_device_commands(device_id):
    """Get pending commands for a device."""
    try:
        commands = Command.query.filter_by(
            device_id=device_id,
            status='pending'
        ).all()

        # Mark commands as sent
        for cmd in commands:
            cmd.status = 'sent'

        db.session.commit()

        return jsonify([cmd.to_dict() for cmd in commands])

    except Exception as e:
        logger.error(f"Error getting commands: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/devices/<device_id>/commands', methods=['POST'])
def create_command(device_id):
    """Create a new command for a device."""
    try:
        data = request.json
        command_type = data.get('type')
        payload = data.get('payload', {})

        if not command_type:
            return jsonify({'error': 'command type is required'}), 400

        # Verify device exists
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            return jsonify({'error': 'Device not found'}), 404

        # Create command
        command = Command(
            device_id=device_id,
            command_type=command_type,
            payload=json.dumps(payload),
            status='pending',
        )

        db.session.add(command)
        db.session.commit()

        logger.info(f"Command created for {device_id}: {command_type}")

        return jsonify({
            'status': 'success',
            'command': command.to_dict(),
        }), 201

    except Exception as e:
        logger.error(f"Error creating command: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/devices/<device_id>/commands/<int:command_id>/result', methods=['POST'])
def command_result(device_id, command_id):
    """Receive command execution result."""
    try:
        data = request.json

        command = Command.query.filter_by(
            id=command_id,
            device_id=device_id
        ).first()

        if not command:
            return jsonify({'error': 'Command not found'}), 404

        command.status = data.get('status', 'completed')
        command.result = json.dumps(data)
        command.completed_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Command {command_id} completed: {command.status}")

        return jsonify({'status': 'success'})

    except Exception as e:
        logger.error(f"Error updating command result: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/devices/<device_id>/commands/history', methods=['GET'])
def command_history(device_id):
    """Get command history for a device."""
    try:
        limit = request.args.get('limit', 50, type=int)

        commands = Command.query.filter_by(
            device_id=device_id
        ).order_by(desc(Command.created_at)).limit(limit).all()

        return jsonify({
            'device_id': device_id,
            'commands': [cmd.to_dict() for cmd in commands],
            'count': len(commands),
        })

    except Exception as e:
        logger.error(f"Error getting command history: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/fleet/summary', methods=['GET'])
def fleet_summary():
    """Get fleet-wide summary statistics."""
    try:
        total_devices = Device.query.count()

        # Count devices by status
        online_devices = Device.query.filter_by(status='online').count()

        # Devices offline (not seen in last 5 minutes)
        offline_threshold = datetime.utcnow() - timedelta(minutes=5)
        offline_devices = Device.query.filter(
            Device.last_seen < offline_threshold
        ).count()

        # Get latest metrics for aggregation
        latest_metrics = []
        for device in Device.query.all():
            metric = Metric.query.filter_by(
                device_id=device.device_id
            ).order_by(desc(Metric.timestamp)).first()
            if metric:
                latest_metrics.append(metric)

        # Calculate averages
        avg_cpu = sum(m.cpu_percent or 0 for m in latest_metrics) / len(latest_metrics) if latest_metrics else 0
        avg_memory = sum(m.memory_percent or 0 for m in latest_metrics) / len(latest_metrics) if latest_metrics else 0
        avg_temp = sum(m.temperature or 0 for m in latest_metrics if m.temperature) / len([m for m in latest_metrics if m.temperature]) if any(m.temperature for m in latest_metrics) else 0

        return jsonify({
            'total_devices': total_devices,
            'online_devices': online_devices,
            'offline_devices': offline_devices,
            'averages': {
                'cpu_percent': round(avg_cpu, 2),
                'memory_percent': round(avg_memory, 2),
                'temperature': round(avg_temp, 2) if avg_temp else None,
            },
            'timestamp': datetime.utcnow().isoformat(),
        })

    except Exception as e:
        logger.error(f"Error getting fleet summary: {e}")
        return jsonify({'error': str(e)}), 500


# Maintenance tasks
def cleanup_old_metrics(days=7):
    """Clean up metrics older than specified days."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = Metric.query.filter(Metric.timestamp < cutoff).delete()
        db.session.commit()
        logger.info(f"Cleaned up {deleted} old metrics")
        return deleted
    except Exception as e:
        logger.error(f"Error cleaning up metrics: {e}")
        db.session.rollback()
        return 0


def update_device_status():
    """Update device status based on last_seen."""
    try:
        offline_threshold = datetime.utcnow() - timedelta(minutes=5)

        # Mark devices as offline
        offline_count = Device.query.filter(
            Device.last_seen < offline_threshold,
            Device.status != 'offline'
        ).update({'status': 'offline'})

        db.session.commit()

        if offline_count > 0:
            logger.info(f"Marked {offline_count} devices as offline")

        return offline_count
    except Exception as e:
        logger.error(f"Error updating device status: {e}")
        db.session.rollback()
        return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Raspberry Pi Fleet Management Server'
    )
    parser.add_argument(
        '--host',
        default=DEFAULT_HOST,
        help=f'Host to bind to (default: {DEFAULT_HOST})'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=DEFAULT_PORT,
        help=f'Port to bind to (default: {DEFAULT_PORT})'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        app.config['DEBUG'] = True

    # Create database tables
    with app.app_context():
        db.create_all()
        logger.info("Database initialized")

    logger.info(f"Starting Pi Fleet Manager v{SERVER_VERSION}")
    logger.info(f"Server: http://{args.host}:{args.port}")

    # Run the Flask app
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
