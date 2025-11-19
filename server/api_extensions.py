"""
API Extensions for Pi Fleet Manager V2

Additional API endpoints for:
- Device grouping and tagging
- Alert management
- User management
- Scheduled tasks
- Command templates
- Export functionality

Add these routes to your Flask app:
    from server.api_extensions import register_v2_endpoints
    register_v2_endpoints(app, db)
"""

from flask import request, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import json
import io
import csv


def register_v2_endpoints(app, db):
    """Register V2 API endpoints with Flask app.

    Args:
        app: Flask application instance
        db: SQLAlchemy database instance
    """

    # Import models (assuming they exist in main file or are imported)
    from pi_fleet_manager_enhanced import (
        Device, DeviceGroup, Tag, AlertRule, AlertNotification,
        ScheduledTask, CommandTemplate, User
    )

    # ========== Device Groups ==========

    @app.route('/api/v2/groups', methods=['GET'])
    def list_groups():
        """List all device groups."""
        try:
            groups = DeviceGroup.query.all()
            return jsonify({
                'groups': [g.to_dict() for g in groups],
                'count': len(groups)
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/v2/groups', methods=['POST'])
    @login_required
    def create_group():
        """Create a new device group."""
        try:
            data = request.json
            group = DeviceGroup(
                name=data['name'],
                description=data.get('description', '')
            )
            db.session.add(group)
            db.session.commit()
            return jsonify(group.to_dict()), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/v2/groups/<int:group_id>/devices', methods=['POST'])
    @login_required
    def add_device_to_group(group_id):
        """Add device to group."""
        try:
            data = request.json
            group = DeviceGroup.query.get_or_404(group_id)
            device = Device.query.filter_by(device_id=data['device_id']).first_or_404()

            if device not in group.devices:
                group.devices.append(device)
                db.session.commit()

            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    # ========== Tags ==========

    @app.route('/api/v2/tags', methods=['GET'])
    def list_tags():
        """List all tags."""
        try:
            tags = Tag.query.all()
            return jsonify({
                'tags': [t.to_dict() for t in tags],
                'count': len(tags)
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/v2/tags', methods=['POST'])
    @login_required
    def create_tag():
        """Create a new tag."""
        try:
            data = request.json
            tag = Tag(
                name=data['name'],
                color=data.get('color', '#3B82F6')
            )
            db.session.add(tag)
            db.session.commit()
            return jsonify(tag.to_dict()), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/v2/devices/<device_id>/tags', methods=['POST'])
    @login_required
    def add_tag_to_device(device_id):
        """Add tag to device."""
        try:
            data = request.json
            device = Device.query.filter_by(device_id=device_id).first_or_404()
            tag = Tag.query.get_or_404(data['tag_id'])

            if tag not in device.tags:
                device.tags.append(tag)
                db.session.commit()

            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    # ========== Alert Rules ==========

    @app.route('/api/v2/alerts/rules', methods=['GET'])
    def list_alert_rules():
        """List all alert rules."""
        try:
            rules = AlertRule.query.all()
            return jsonify({
                'rules': [r.to_dict() for r in rules],
                'count': len(rules)
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/v2/alerts/rules', methods=['POST'])
    @login_required
    def create_alert_rule():
        """Create a new alert rule."""
        try:
            data = request.json
            rule = AlertRule(
                name=data['name'],
                description=data.get('description'),
                metric_type=data['metric_type'],
                condition=data['condition'],
                threshold=data.get('threshold'),
                duration=data.get('duration', 60),
                severity=data.get('severity', 'warning'),
                enabled=data.get('enabled', True),
                notify_email=data.get('notify_email', True),
                email_addresses=json.dumps(data.get('email_addresses', [])),
                device_filter=json.dumps(data.get('device_filter', {}))
            )
            db.session.add(rule)
            db.session.commit()
            return jsonify(rule.to_dict()), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/v2/alerts/rules/<int:rule_id>', methods=['PUT'])
    @login_required
    def update_alert_rule(rule_id):
        """Update an alert rule."""
        try:
            rule = AlertRule.query.get_or_404(rule_id)
            data = request.json

            for key in ['name', 'description', 'metric_type', 'condition',
                       'threshold', 'duration', 'severity', 'enabled', 'notify_email']:
                if key in data:
                    setattr(rule, key, data[key])

            if 'email_addresses' in data:
                rule.email_addresses = json.dumps(data['email_addresses'])
            if 'device_filter' in data:
                rule.device_filter = json.dumps(data['device_filter'])

            db.session.commit()
            return jsonify(rule.to_dict())
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    # ========== Alert Notifications ==========

    @app.route('/api/v2/alerts/notifications', methods=['GET'])
    def list_alerts():
        """List alert notifications."""
        try:
            acknowledged = request.args.get('acknowledged', 'false').lower() == 'true'
            limit = request.args.get('limit', 50, type=int)

            query = AlertNotification.query
            if not acknowledged:
                query = query.filter_by(acknowledged=False)

            notifications = query.order_by(
                AlertNotification.created_at.desc()
            ).limit(limit).all()

            return jsonify({
                'notifications': [n.to_dict() for n in notifications],
                'count': len(notifications)
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/v2/alerts/notifications/<int:alert_id>/acknowledge', methods=['POST'])
    @login_required
    def acknowledge_alert(alert_id):
        """Acknowledge an alert."""
        try:
            alert = AlertNotification.query.get_or_404(alert_id)
            alert.acknowledged = True
            alert.acknowledged_by = current_user.id
            alert.acknowledged_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    # ========== Command Templates ==========

    @app.route('/api/v2/templates', methods=['GET'])
    def list_templates():
        """List command templates."""
        try:
            templates = CommandTemplate.query.filter_by(is_public=True).all()
            return jsonify({
                'templates': [t.to_dict() for t in templates],
                'count': len(templates)
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/v2/templates', methods=['POST'])
    @login_required
    def create_template():
        """Create command template."""
        try:
            data = request.json
            template = CommandTemplate(
                name=data['name'],
                description=data.get('description'),
                category=data.get('category'),
                steps=json.dumps(data['steps']),
                created_by=current_user.id,
                is_public=data.get('is_public', True)
            )
            db.session.add(template)
            db.session.commit()
            return jsonify(template.to_dict()), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/v2/templates/<int:template_id>/execute', methods=['POST'])
    @login_required
    def execute_template(template_id):
        """Execute template on devices."""
        try:
            template = CommandTemplate.query.get_or_404(template_id)
            data = request.json
            device_ids = data.get('device_ids', [])

            steps = json.loads(template.steps)
            results = []

            for device_id in device_ids:
                device = Device.query.filter_by(device_id=device_id).first()
                if not device:
                    continue

                # Execute each step
                for step in steps:
                    from pi_fleet_manager_enhanced import Command
                    command = Command(
                        device_id=device_id,
                        command_type=step['type'],
                        payload=json.dumps(step.get('payload', {})),
                        created_by=current_user.id
                    )
                    db.session.add(command)

            db.session.commit()
            return jsonify({'success': True, 'message': 'Template executed'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    # ========== Export ==========

    @app.route('/api/v2/export/metrics', methods=['GET'])
    @login_required
    def export_metrics_api():
        """Export metrics as CSV."""
        try:
            from pi_fleet_manager_enhanced import Metric

            device_id = request.args.get('device_id')
            days = request.args.get('days', type=int)

            query = Metric.query.join(Device)

            if device_id:
                query = query.filter(Metric.device_id == device_id)
            if days:
                cutoff = datetime.utcnow() - timedelta(days=days)
                query = query.filter(Metric.timestamp >= cutoff)

            metrics = query.order_by(Metric.timestamp.desc()).limit(10000).all()

            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow(['timestamp', 'device_id', 'device_name', 'cpu_percent',
                           'memory_percent', 'temperature', 'uptime'])

            # Data
            for m in metrics:
                writer.writerow([
                    m.timestamp.isoformat() if m.timestamp else '',
                    m.device_id,
                    m.device.device_name if m.device else '',
                    m.cpu_percent or '',
                    m.memory_percent or '',
                    m.temperature or '',
                    m.uptime or ''
                ])

            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode()),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'metrics_{datetime.now().strftime("%Y%m%d")}.csv'
            )

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ========== Statistics ==========

    @app.route('/api/v2/stats/devices', methods=['GET'])
    def device_stats():
        """Get device statistics."""
        try:
            stats = {
                'by_status': {},
                'by_model': {},
                'by_os': {},
                'total': Device.query.count()
            }

            # Group by status
            from sqlalchemy import func
            status_counts = db.session.query(
                Device.status,
                func.count(Device.id)
            ).group_by(Device.status).all()

            stats['by_status'] = {status: count for status, count in status_counts}

            # Group by model
            model_counts = db.session.query(
                Device.model,
                func.count(Device.id)
            ).group_by(Device.model).all()

            stats['by_model'] = {model or 'Unknown': count for model, count in model_counts}

            return jsonify(stats)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/v2/stats/alerts', methods=['GET'])
    def alert_stats():
        """Get alert statistics."""
        try:
            from sqlalchemy import func

            total = AlertNotification.query.count()
            unacknowledged = AlertNotification.query.filter_by(acknowledged=False).count()

            # Group by severity
            severity_counts = db.session.query(
                AlertNotification.severity,
                func.count(AlertNotification.id)
            ).group_by(AlertNotification.severity).all()

            return jsonify({
                'total': total,
                'unacknowledged': unacknowledged,
                'by_severity': {sev: count for sev, count in severity_counts}
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return app
