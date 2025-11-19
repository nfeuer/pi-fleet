#!/usr/bin/env python3
"""
Pi Fleet Alert Monitor Service

Continuously monitors devices and triggers alerts based on configured rules.

Usage:
    python3 alert-monitor.py [--interval 60]
"""

import argparse
import logging
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from sqlalchemy import create_engine, desc
    from sqlalchemy.orm import sessionmaker, scoped_session
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
except ImportError as e:
    print(f"Error: Required package not installed: {e}")
    print("Install with: pip3 install sqlalchemy")
    sys.exit(1)

# Configuration
DATABASE_FILE = "fleet.db"
CHECK_INTERVAL = 60  # seconds
ALERT_COOLDOWN = 300  # 5 minutes between same alerts

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('alert-monitor')


class AlertMonitor:
    """Monitor devices and send alerts."""

    def __init__(self, db_path=DATABASE_FILE):
        """Initialize alert monitor."""
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        self.last_check = {}  # Track last alert time per device/rule

    def run(self, interval=CHECK_INTERVAL):
        """Main monitoring loop."""
        logger.info("Starting Alert Monitor Service")
        logger.info(f"Check interval: {interval} seconds")

        while True:
            try:
                self.check_all_rules()
                time.sleep(interval)
            except KeyboardInterrupt:
                logger.info("Shutting down Alert Monitor")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(interval)

    def check_all_rules(self):
        """Check all enabled alert rules."""
        session = self.Session()

        try:
            # Get all enabled rules
            result = session.execute(
                "SELECT * FROM alert_rules WHERE enabled = 1"
            )

            rules = [dict(row._mapping) for row in result]

            logger.debug(f"Checking {len(rules)} alert rules")

            for rule in rules:
                try:
                    self.check_rule(session, rule)
                except Exception as e:
                    logger.error(f"Error checking rule {rule['id']}: {e}")

            session.commit()

        except Exception as e:
            logger.error(f"Error checking rules: {e}")
            session.rollback()
        finally:
            session.close()

    def check_rule(self, session, rule):
        """Check a specific alert rule.

        Args:
            session: Database session
            rule: Rule dictionary
        """
        import json

        # Get devices to check
        devices = self.get_filtered_devices(session, rule.get('device_filter'))

        for device in devices:
            violated, metric_value = self.evaluate_rule(session, rule, device)

            if violated:
                self.trigger_alert(session, rule, device, metric_value)

    def get_filtered_devices(self, session, filter_json):
        """Get devices matching filter criteria.

        Args:
            session: Database session
            filter_json: JSON filter config

        Returns:
            List of device dictionaries
        """
        import json

        # Base query
        query = "SELECT * FROM devices WHERE status = 'online' OR :check_offline = 1"
        params = {'check_offline': 1}

        # Apply filters if specified
        if filter_json:
            try:
                filter_config = json.loads(filter_json)

                # Filter by specific devices
                if filter_config.get('devices'):
                    device_list = ','.join([f"'{d}'" for d in filter_config['devices']])
                    query += f" AND device_id IN ({device_list})"

            except:
                pass

        result = session.execute(query, params)
        return [dict(row._mapping) for row in result]

    def evaluate_rule(self, session, rule, device):
        """Evaluate if rule is violated for device.

        Args:
            session: Database session
            rule: Rule dictionary
            device: Device dictionary

        Returns:
            Tuple of (violated: bool, metric_value)
        """
        metric_type = rule['metric_type']

        # Check offline status
        if metric_type == 'offline':
            return (device['status'] == 'offline', 'offline')

        # Get latest metric
        result = session.execute(
            """
            SELECT * FROM metrics
            WHERE device_id = :device_id
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            {'device_id': device['device_id']}
        )

        metric = result.fetchone()
        if not metric:
            return (False, None)

        metric_dict = dict(metric._mapping)

        # Extract metric value
        metric_value = None
        if metric_type == 'cpu':
            metric_value = metric_dict.get('cpu_percent')
        elif metric_type == 'memory':
            metric_value = metric_dict.get('memory_percent')
        elif metric_type == 'temperature':
            metric_value = metric_dict.get('temperature')
        elif metric_type == 'disk':
            import json
            disk_info = metric_dict.get('disk_info')
            if disk_info:
                disk_data = json.loads(disk_info)
                if disk_data:
                    metric_value = max(d.get('percent', 0) for d in disk_data.values())

        if metric_value is None:
            return (False, None)

        # Evaluate condition
        condition = rule['condition']
        threshold = rule['threshold']
        violated = False

        if condition == 'gt':
            violated = metric_value > threshold
        elif condition == 'lt':
            violated = metric_value < threshold
        elif condition == 'eq':
            violated = metric_value == threshold

        return (violated, metric_value)

    def trigger_alert(self, session, rule, device, metric_value):
        """Trigger an alert.

        Args:
            session: Database session
            rule: Rule dictionary
            device: Device dictionary
            metric_value: Current metric value
        """
        # Check cooldown
        alert_key = f"{rule['id']}:{device['device_id']}"
        last_alert = self.last_check.get(alert_key)

        if last_alert:
            time_since = (datetime.utcnow() - last_alert).total_seconds()
            if time_since < ALERT_COOLDOWN:
                logger.debug(f"Alert cooldown active for {alert_key}")
                return

        # Format message
        message = self.format_alert_message(rule, device, metric_value)

        # Create alert notification
        try:
            session.execute(
                """
                INSERT INTO alert_notifications
                (rule_id, device_id, message, severity, created_at)
                VALUES (:rule_id, :device_id, :message, :severity, :created_at)
                """,
                {
                    'rule_id': rule['id'],
                    'device_id': device['device_id'],
                    'message': message,
                    'severity': rule['severity'],
                    'created_at': datetime.utcnow()
                }
            )

            session.commit()
            logger.info(f"Alert triggered: {rule['name']} for {device['device_name']}")

            # Update last check time
            self.last_check[alert_key] = datetime.utcnow()

            # Send email if configured
            if rule.get('notify_email') and rule.get('email_addresses'):
                self.send_email(rule, device, message)

        except Exception as e:
            logger.error(f"Error creating alert notification: {e}")
            session.rollback()

    def format_alert_message(self, rule, device, metric_value):
        """Format alert message.

        Args:
            rule: Rule dictionary
            device: Device dictionary
            metric_value: Current metric value

        Returns:
            Formatted message
        """
        if rule['metric_type'] == 'offline':
            return f"Device '{device['device_name']}' is offline"

        return (f"Alert: {rule['name']}\n"
                f"Device: {device['device_name']}\n"
                f"Metric: {rule['metric_type']}\n"
                f"Current value: {metric_value}\n"
                f"Threshold: {rule['threshold']}\n"
                f"Severity: {rule['severity']}")

    def send_email(self, rule, device, message):
        """Send email notification.

        Args:
            rule: Rule dictionary
            device: Device dictionary
            message: Alert message
        """
        import json

        try:
            email_list = json.loads(rule['email_addresses'])

            # Create email (basic SMTP - configure as needed)
            msg = MIMEMultipart()
            msg['From'] = 'pi-fleet@localhost'
            msg['To'] = ', '.join(email_list)
            msg['Subject'] = f"Pi Fleet Alert: {rule['name']}"

            body = message
            msg.attach(MIMEText(body, 'plain'))

            # Send email (requires SMTP server configuration)
            # This is a basic example - configure for your SMTP server
            try:
                server = smtplib.SMTP('localhost', 25)
                server.send_message(msg)
                server.quit()
                logger.info(f"Email sent for alert {rule['id']}")
            except Exception as e:
                logger.warning(f"Email sending not configured or failed: {e}")
                logger.info("Configure SMTP settings to enable email notifications")

        except Exception as e:
            logger.error(f"Error sending email: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Pi Fleet Alert Monitor Service')
    parser.add_argument('--interval', type=int, default=CHECK_INTERVAL,
                       help=f'Check interval in seconds (default: {CHECK_INTERVAL})')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    monitor = AlertMonitor()
    monitor.run(interval=args.interval)


if __name__ == '__main__':
    main()
