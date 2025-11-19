"""
Alerting module for Pi Fleet Manager

Monitors devices and sends notifications based on alert rules.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from flask import current_app
from flask_mail import Message

logger = logging.getLogger('alerting')


class AlertingSystem:
    """Alert monitoring and notification system."""

    def __init__(self, db, mail):
        """Initialize alerting system.

        Args:
            db: SQLAlchemy database instance
            mail: Flask-Mail instance
        """
        self.db = db
        self.mail = mail

    def check_alerts(self):
        """Check all alert rules against current device metrics."""
        from pi_fleet_manager_enhanced import AlertRule, Device, Metric, AlertNotification

        rules = AlertRule.query.filter_by(enabled=True).all()

        for rule in rules:
            try:
                self._check_rule(rule)
            except Exception as e:
                logger.error(f"Error checking alert rule {rule.id}: {e}")

    def _check_rule(self, rule):
        """Check a specific alert rule.

        Args:
            rule: AlertRule instance
        """
        from pi_fleet_manager_enhanced import Device, Metric, AlertNotification

        # Get devices matching the filter
        devices = self._get_filtered_devices(rule.device_filter)

        for device in devices:
            # Check if rule applies to this device
            violated = False
            metric_value = None

            if rule.metric_type == 'offline':
                # Check if device is offline
                if device.status == 'offline':
                    violated = True
                    metric_value = 'offline'

            elif rule.metric_type in ['cpu', 'memory', 'temperature', 'disk']:
                # Get latest metric
                latest_metric = Metric.query.filter_by(
                    device_id=device.device_id
                ).order_by(Metric.timestamp.desc()).first()

                if latest_metric:
                    metric_value = self._get_metric_value(latest_metric, rule.metric_type)

                    if metric_value is not None:
                        violated = self._evaluate_condition(
                            metric_value,
                            rule.condition,
                            rule.threshold
                        )

            # If violated, check if we should send notification
            if violated:
                self._handle_violation(rule, device, metric_value)

    def _get_filtered_devices(self, device_filter_json):
        """Get devices matching the filter criteria.

        Args:
            device_filter_json: JSON string with filter criteria

        Returns:
            List of Device instances
        """
        from pi_fleet_manager_enhanced import Device
        import json

        if not device_filter_json:
            return Device.query.all()

        try:
            filter_config = json.loads(device_filter_json)
        except:
            return Device.query.all()

        query = Device.query

        # Filter by specific devices
        if filter_config.get('devices'):
            query = query.filter(Device.device_id.in_(filter_config['devices']))

        # Filter by groups
        if filter_config.get('groups'):
            query = query.join(Device.groups).filter(
                DeviceGroup.id.in_(filter_config['groups'])
            )

        # Filter by tags
        if filter_config.get('tags'):
            query = query.join(Device.tags).filter(
                Tag.id.in_(filter_config['tags'])
            )

        return query.all()

    def _get_metric_value(self, metric, metric_type):
        """Extract specific metric value from Metric instance.

        Args:
            metric: Metric instance
            metric_type: Type of metric to extract

        Returns:
            Metric value or None
        """
        if metric_type == 'cpu':
            return metric.cpu_percent
        elif metric_type == 'memory':
            return metric.memory_percent
        elif metric_type == 'temperature':
            return metric.temperature
        elif metric_type == 'disk':
            # Get worst disk usage
            import json
            if metric.disk_info:
                disk_data = json.loads(metric.disk_info)
                if disk_data:
                    return max(d.get('percent', 0) for d in disk_data.values())
        return None

    def _evaluate_condition(self, value, condition, threshold):
        """Evaluate if condition is met.

        Args:
            value: Current metric value
            condition: Condition type (gt, lt, eq)
            threshold: Threshold value

        Returns:
            True if condition is violated
        """
        if condition == 'gt':
            return value > threshold
        elif condition == 'lt':
            return value < threshold
        elif condition == 'eq':
            return value == threshold
        return False

    def _handle_violation(self, rule, device, metric_value):
        """Handle alert rule violation.

        Args:
            rule: AlertRule instance
            device: Device instance
            metric_value: Current metric value
        """
        from pi_fleet_manager_enhanced import AlertNotification

        # Check if we recently sent an alert for this (avoid spam)
        recent_cutoff = datetime.utcnow() - timedelta(minutes=rule.duration / 60)
        recent_alert = AlertNotification.query.filter_by(
            rule_id=rule.id,
            device_id=device.device_id,
            acknowledged=False
        ).filter(
            AlertNotification.created_at > recent_cutoff
        ).first()

        if recent_alert:
            # Already notified recently
            return

        # Create alert notification
        message = self._format_alert_message(rule, device, metric_value)

        notification = AlertNotification(
            rule_id=rule.id,
            device_id=device.device_id,
            message=message,
            severity=rule.severity
        )

        self.db.session.add(notification)
        self.db.session.commit()

        # Send email if configured
        if rule.notify_email and rule.email_addresses:
            self._send_email_notification(rule, device, message)

        logger.info(f"Alert triggered: {rule.name} for device {device.device_name}")

    def _format_alert_message(self, rule, device, metric_value):
        """Format alert message.

        Args:
            rule: AlertRule instance
            device: Device instance
            metric_value: Current metric value

        Returns:
            Formatted message string
        """
        if rule.metric_type == 'offline':
            return f"Device '{device.device_name}' is offline"

        return (f"Alert: {rule.name}\n"
                f"Device: {device.device_name}\n"
                f"Metric: {rule.metric_type}\n"
                f"Current value: {metric_value}\n"
                f"Threshold: {rule.threshold}\n"
                f"Severity: {rule.severity}")

    def _send_email_notification(self, rule, device, message):
        """Send email notification.

        Args:
            rule: AlertRule instance
            device: Device instance
            message: Alert message
        """
        import json

        try:
            email_list = json.loads(rule.email_addresses)

            msg = Message(
                subject=f"Pi Fleet Alert: {rule.name}",
                recipients=email_list,
                body=message
            )

            self.mail.send(msg)
            logger.info(f"Email notification sent for alert {rule.id}")

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")

    def get_active_alerts(self, acknowledged=False):
        """Get list of active alerts.

        Args:
            acknowledged: Include acknowledged alerts if True

        Returns:
            List of AlertNotification instances
        """
        from pi_fleet_manager_enhanced import AlertNotification

        query = AlertNotification.query

        if not acknowledged:
            query = query.filter_by(acknowledged=False)

        return query.order_by(AlertNotification.created_at.desc()).all()

    def acknowledge_alert(self, alert_id, user_id):
        """Acknowledge an alert.

        Args:
            alert_id: Alert notification ID
            user_id: User ID acknowledging the alert

        Returns:
            True if successful
        """
        from pi_fleet_manager_enhanced import AlertNotification

        alert = AlertNotification.query.get(alert_id)
        if not alert:
            return False

        alert.acknowledged = True
        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.utcnow()

        self.db.session.commit()
        return True
