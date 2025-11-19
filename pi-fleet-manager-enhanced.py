#!/usr/bin/env python3
"""
Raspberry Pi Fleet Management Server - Enhanced Version

Central management server with authentication, alerting, scheduling,
device grouping, and advanced monitoring capabilities.

Usage:
    python3 pi-fleet-manager-enhanced.py --host 0.0.0.0 --port 5000
"""

import argparse
import json
import logging
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from functools import wraps

from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import desc, and_, or_
from sqlalchemy.exc import SQLAlchemyError
from apscheduler.schedulers.background import BackgroundScheduler

# Configuration
SERVER_VERSION = "2.0.0"
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
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['JWT_SECRET_KEY'] = secrets.token_hex(32)

# Email configuration (configure these via environment variables in production)
app.config['MAIL_SERVER'] = 'localhost'
app.config['MAIL_PORT'] = 25
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = None
app.config['MAIL_PASSWORD'] = None
app.config['MAIL_DEFAULT_SENDER'] = 'pi-fleet@localhost'

CORS(app)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
jwt = JWTManager(app)
mail = Mail(app)
scheduler = BackgroundScheduler()


# Database Models
class User(UserMixin, db.Model):
    """User model for authentication."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')  # admin, user, viewer
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active,
        }


class DeviceGroup(db.Model):
    """Device group for organizing devices."""
    __tablename__ = 'device_groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# Association table for device-group many-to-many relationship
device_group_association = db.Table('device_group_association',
    db.Column('device_id', db.String(100), db.ForeignKey('devices.device_id')),
    db.Column('group_id', db.Integer, db.ForeignKey('device_groups.id'))
)

# Association table for device-tag many-to-many relationship
device_tag_association = db.Table('device_tag_association',
    db.Column('device_id', db.String(100), db.ForeignKey('devices.device_id')),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'))
)


class Tag(db.Model):
    """Tags for devices."""
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    color = db.Column(db.String(7), default='#3B82F6')  # Hex color

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
        }


class Device(db.Model):
    """Device model for fleet inventory."""
    __tablename__ = 'devices'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    device_name = db.Column(db.String(100), nullable=False)
    agent_version = db.Column(db.String(20))
    notes = db.Column(db.Text)  # User notes about the device

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
    health_score = db.Column(db.Integer, default=100)  # 0-100
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    metrics = db.relationship('Metric', backref='device', lazy='dynamic',
                            cascade='all, delete-orphan')
    commands = db.relationship('Command', backref='device', lazy='dynamic',
                             cascade='all, delete-orphan')
    groups = db.relationship('DeviceGroup', secondary=device_group_association,
                           backref='devices')
    tags = db.relationship('Tag', secondary=device_tag_association,
                         backref='devices')

    def to_dict(self) -> Dict[str, Any]:
        """Convert device to dictionary."""
        return {
            'id': self.id,
            'device_id': self.device_id,
            'device_name': self.device_name,
            'agent_version': self.agent_version,
            'notes': self.notes,
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
            'health_score': self.health_score,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'groups': [g.to_dict() for g in self.groups],
            'tags': [t.to_dict() for t in self.tags],
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
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
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
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class AlertRule(db.Model):
    """Alert rules for monitoring."""
    __tablename__ = 'alert_rules'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    metric_type = db.Column(db.String(50), nullable=False)  # cpu, memory, temperature, disk, offline
    condition = db.Column(db.String(20), nullable=False)  # gt, lt, eq
    threshold = db.Column(db.Float)
    duration = db.Column(db.Integer, default=60)  # seconds
    severity = db.Column(db.String(20), default='warning')  # info, warning, critical
    enabled = db.Column(db.Boolean, default=True)
    notify_email = db.Column(db.Boolean, default=True)
    email_addresses = db.Column(db.Text)  # JSON list
    device_filter = db.Column(db.Text)  # JSON: {"groups": [], "tags": [], "devices": []}
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'metric_type': self.metric_type,
            'condition': self.condition,
            'threshold': self.threshold,
            'duration': self.duration,
            'severity': self.severity,
            'enabled': self.enabled,
            'notify_email': self.notify_email,
            'email_addresses': json.loads(self.email_addresses) if self.email_addresses else [],
            'device_filter': json.loads(self.device_filter) if self.device_filter else {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AlertNotification(db.Model):
    """Alert notification history."""
    __tablename__ = 'alert_notifications'

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('alert_rules.id'))
    device_id = db.Column(db.String(100), db.ForeignKey('devices.device_id'))
    message = db.Column(db.Text)
    severity = db.Column(db.String(20))
    acknowledged = db.Column(db.Boolean, default=False)
    acknowledged_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    acknowledged_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    rule = db.relationship('AlertRule', backref='notifications')
    device = db.relationship('Device')

    def to_dict(self):
        return {
            'id': self.id,
            'rule_id': self.rule_id,
            'device_id': self.device_id,
            'device_name': self.device.device_name if self.device else None,
            'message': self.message,
            'severity': self.severity,
            'acknowledged': self.acknowledged,
            'acknowledged_by': self.acknowledged_by,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ScheduledTask(db.Model):
    """Scheduled tasks."""
    __tablename__ = 'scheduled_tasks'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    task_type = db.Column(db.String(50), nullable=False)  # command, update, backup
    schedule_type = db.Column(db.String(20), nullable=False)  # cron, interval, once
    schedule_config = db.Column(db.Text)  # JSON cron or interval config
    task_payload = db.Column(db.Text)  # JSON
    device_filter = db.Column(db.Text)  # JSON
    enabled = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime)
    next_run = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'task_type': self.task_type,
            'schedule_type': self.schedule_type,
            'schedule_config': json.loads(self.schedule_config) if self.schedule_config else {},
            'task_payload': json.loads(self.task_payload) if self.task_payload else {},
            'device_filter': json.loads(self.device_filter) if self.device_filter else {},
            'enabled': self.enabled,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class CommandTemplate(db.Model):
    """Reusable command templates."""
    __tablename__ = 'command_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    steps = db.Column(db.Text, nullable=False)  # JSON array of command steps
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'steps': json.loads(self.steps) if self.steps else [],
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_public': self.is_public,
        }


# Authentication
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(f):
    """Decorator for admin-only routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


# Continue in next message due to length...
