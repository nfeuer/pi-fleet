#!/usr/bin/env python3
"""
Export Fleet Metrics to CSV/JSON

Export device metrics and fleet data for analysis, reporting, or backup.

Usage:
    python3 export-metrics.py --format csv --output fleet-metrics.csv
    python3 export-metrics.py --format json --device pi-001 --days 7
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
except ImportError:
    print("Error: SQLAlchemy required. Install with: pip3 install sqlalchemy")
    sys.exit(1)

DATABASE_FILE = "fleet.db"


class MetricsExporter:
    """Export fleet metrics to various formats."""

    def __init__(self, db_path=DATABASE_FILE):
        """Initialize exporter."""
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.Session = sessionmaker(bind=self.engine)

    def export_metrics(self, output_file, format='csv', device_id=None,
                      days=None, include_devices=True):
        """Export metrics to file.

        Args:
            output_file: Output file path
            format: Export format (csv, json)
            device_id: Specific device ID (None for all)
            days: Number of days to export (None for all)
            include_devices: Include device information
        """
        session = self.Session()

        try:
            # Build query
            query = "SELECT m.*, d.device_name FROM metrics m JOIN devices d ON m.device_id = d.device_id"
            conditions = []
            params = {}

            if device_id:
                conditions.append("m.device_id = :device_id")
                params['device_id'] = device_id

            if days:
                cutoff = datetime.utcnow() - timedelta(days=days)
                conditions.append("m.timestamp >= :cutoff")
                params['cutoff'] = cutoff

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY m.timestamp DESC"

            # Execute query
            result = session.execute(query, params)
            rows = [dict(row._mapping) for row in result]

            print(f"Exporting {len(rows)} metric records...")

            # Export based on format
            if format == 'csv':
                self._export_csv(rows, output_file)
            elif format == 'json':
                self._export_json(rows, output_file, include_devices)
            else:
                print(f"Unknown format: {format}")
                return

            print(f"✓ Exported to: {output_file}")

        finally:
            session.close()

    def _export_csv(self, rows, output_file):
        """Export to CSV format."""
        if not rows:
            print("No data to export")
            return

        with open(output_file, 'w', newline='') as f:
            # Get all unique keys
            fieldnames = set()
            for row in rows:
                fieldnames.update(row.keys())

            writer = csv.DictWriter(f, fieldnames=sorted(fieldnames))
            writer.writeheader()

            for row in rows:
                # Convert timestamp to string
                if 'timestamp' in row and row['timestamp']:
                    row['timestamp'] = str(row['timestamp'])
                writer.writerow(row)

    def _export_json(self, rows, output_file, include_devices):
        """Export to JSON format."""
        # Convert timestamps to strings
        for row in rows:
            if 'timestamp' in row and row['timestamp']:
                row['timestamp'] = str(row['timestamp'])

        output = {
            'exported_at': datetime.utcnow().isoformat(),
            'record_count': len(rows),
            'metrics': rows
        }

        if include_devices:
            output['devices'] = self._get_devices()

        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)

    def _get_devices(self):
        """Get all devices."""
        session = self.Session()
        try:
            result = session.execute("SELECT * FROM devices")
            devices = []
            for row in result:
                device = dict(row._mapping)
                if 'registered_at' in device and device['registered_at']:
                    device['registered_at'] = str(device['registered_at'])
                if 'last_seen' in device and device['last_seen']:
                    device['last_seen'] = str(device['last_seen'])
                devices.append(device)
            return devices
        finally:
            session.close()

    def export_report(self, output_file):
        """Generate comprehensive fleet report.

        Args:
            output_file: Output file path (JSON)
        """
        session = self.Session()

        try:
            report = {
                'generated_at': datetime.utcnow().isoformat(),
                'fleet_summary': self._get_fleet_summary(session),
                'devices': self._get_device_details(session),
                'alerts': self._get_recent_alerts(session),
                'commands': self._get_recent_commands(session),
            }

            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)

            print(f"✓ Report generated: {output_file}")

        finally:
            session.close()

    def _get_fleet_summary(self, session):
        """Get fleet summary statistics."""
        result = session.execute("""
            SELECT
                COUNT(*) as total_devices,
                SUM(CASE WHEN status = 'online' THEN 1 ELSE 0 END) as online_devices,
                SUM(CASE WHEN status = 'offline' THEN 1 ELSE 0 END) as offline_devices,
                AVG(health_score) as avg_health_score
            FROM devices
        """)
        row = result.fetchone()
        return dict(row._mapping) if row else {}

    def _get_device_details(self, session):
        """Get detailed device information."""
        result = session.execute("SELECT * FROM devices")
        devices = []
        for row in result:
            device = dict(row._mapping)
            if 'registered_at' in device and device['registered_at']:
                device['registered_at'] = str(device['registered_at'])
            if 'last_seen' in device and device['last_seen']:
                device['last_seen'] = str(device['last_seen'])
            devices.append(device)
        return devices

    def _get_recent_alerts(self, session, days=7):
        """Get recent alerts."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = session.execute("""
            SELECT * FROM alert_notifications
            WHERE created_at >= :cutoff
            ORDER BY created_at DESC
            LIMIT 100
        """, {'cutoff': cutoff})

        alerts = []
        for row in result:
            alert = dict(row._mapping)
            if 'created_at' in alert and alert['created_at']:
                alert['created_at'] = str(alert['created_at'])
            alerts.append(alert)
        return alerts

    def _get_recent_commands(self, session, days=7):
        """Get recent commands."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = session.execute("""
            SELECT * FROM commands
            WHERE created_at >= :cutoff
            ORDER BY created_at DESC
            LIMIT 100
        """, {'cutoff': cutoff})

        commands = []
        for row in result:
            cmd = dict(row._mapping)
            if 'created_at' in cmd and cmd['created_at']:
                cmd['created_at'] = str(cmd['created_at'])
            if 'completed_at' in cmd and cmd['completed_at']:
                cmd['completed_at'] = str(cmd['completed_at'])
            commands.append(cmd)
        return commands


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Export Pi Fleet Metrics')
    parser.add_argument('--format', choices=['csv', 'json'], default='csv',
                       help='Export format')
    parser.add_argument('--output', required=True,
                       help='Output file path')
    parser.add_argument('--device', help='Device ID (export specific device only)')
    parser.add_argument('--days', type=int,
                       help='Number of days to export (default: all)')
    parser.add_argument('--report', action='store_true',
                       help='Generate comprehensive fleet report (JSON only)')

    args = parser.parse_args()

    exporter = MetricsExporter()

    if args.report:
        exporter.export_report(args.output)
    else:
        exporter.export_metrics(
            args.output,
            format=args.format,
            device_id=args.device,
            days=args.days
        )


if __name__ == '__main__':
    main()
