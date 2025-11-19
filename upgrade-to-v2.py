#!/usr/bin/env python3
"""
Pi Fleet Manager - Upgrade to V2 Script

This script upgrades your Pi Fleet Manager installation from v1.0 to v2.0,
adding new features including:
- User authentication and RBAC
- Device grouping and tagging
- Alert rules and notifications
- Scheduled tasks
- Command templates
- Enhanced monitoring

Usage:
    python3 upgrade-to-v2.py
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

try:
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import sessionmaker
except ImportError:
    print("Error: SQLAlchemy is required. Install with: pip3 install sqlalchemy")
    sys.exit(1)

DATABASE_FILE = "fleet.db"


def backup_database():
    """Create backup of existing database."""
    db_path = Path(DATABASE_FILE)
    if not db_path.exists():
        print(f"Database {DATABASE_FILE} not found. Starting fresh installation.")
        return None

    backup_name = f"fleet_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_path = Path(backup_name)

    print(f"Creating backup: {backup_name}")
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"✓ Backup created: {backup_path}")
    return backup_path


def create_tables(engine):
    """Create new database tables."""
    print("\nCreating new tables...")

    tables_sql = {
        'users': """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """,

        'device_groups': """
            CREATE TABLE IF NOT EXISTS device_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,

        'tags': """
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(50) UNIQUE NOT NULL,
                color VARCHAR(7) DEFAULT '#3B82F6'
            )
        """,

        'device_group_association': """
            CREATE TABLE IF NOT EXISTS device_group_association (
                device_id VARCHAR(100),
                group_id INTEGER,
                FOREIGN KEY (device_id) REFERENCES devices(device_id),
                FOREIGN KEY (group_id) REFERENCES device_groups(id)
            )
        """,

        'device_tag_association': """
            CREATE TABLE IF NOT EXISTS device_tag_association (
                device_id VARCHAR(100),
                tag_id INTEGER,
                FOREIGN KEY (device_id) REFERENCES devices(device_id),
                FOREIGN KEY (tag_id) REFERENCES tags(id)
            )
        """,

        'alert_rules': """
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                metric_type VARCHAR(50) NOT NULL,
                condition VARCHAR(20) NOT NULL,
                threshold REAL,
                duration INTEGER DEFAULT 60,
                severity VARCHAR(20) DEFAULT 'warning',
                enabled BOOLEAN DEFAULT 1,
                notify_email BOOLEAN DEFAULT 1,
                email_addresses TEXT,
                device_filter TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,

        'alert_notifications': """
            CREATE TABLE IF NOT EXISTS alert_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER,
                device_id VARCHAR(100),
                message TEXT,
                severity VARCHAR(20),
                acknowledged BOOLEAN DEFAULT 0,
                acknowledged_by INTEGER,
                acknowledged_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rule_id) REFERENCES alert_rules(id),
                FOREIGN KEY (device_id) REFERENCES devices(device_id),
                FOREIGN KEY (acknowledged_by) REFERENCES users(id)
            )
        """,

        'scheduled_tasks': """
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                task_type VARCHAR(50) NOT NULL,
                schedule_type VARCHAR(20) NOT NULL,
                schedule_config TEXT,
                task_payload TEXT,
                device_filter TEXT,
                enabled BOOLEAN DEFAULT 1,
                last_run TIMESTAMP,
                next_run TIMESTAMP,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """,

        'command_templates': """
            CREATE TABLE IF NOT EXISTS command_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                category VARCHAR(50),
                steps TEXT NOT NULL,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_public BOOLEAN DEFAULT 1,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """
    }

    with engine.connect() as conn:
        for table_name, sql in tables_sql.items():
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"✓ Created table: {table_name}")
            except Exception as e:
                print(f"✗ Error creating {table_name}: {e}")


def update_existing_tables(engine):
    """Add new columns to existing tables."""
    print("\nUpdating existing tables...")

    updates = {
        'devices': [
            ("notes", "ALTER TABLE devices ADD COLUMN notes TEXT"),
            ("health_score", "ALTER TABLE devices ADD COLUMN health_score INTEGER DEFAULT 100"),
        ],
        'commands': [
            ("created_by", "ALTER TABLE commands ADD COLUMN created_by INTEGER REFERENCES users(id)"),
        ]
    }

    with engine.connect() as conn:
        inspector = inspect(engine)

        for table_name, columns in updates.items():
            if table_name not in inspector.get_table_names():
                print(f"⚠ Table {table_name} doesn't exist, skipping...")
                continue

            existing_columns = [col['name'] for col in inspector.get_columns(table_name)]

            for col_name, sql in columns:
                if col_name not in existing_columns:
                    try:
                        conn.execute(text(sql))
                        conn.commit()
                        print(f"✓ Added column {table_name}.{col_name}")
                    except Exception as e:
                        print(f"✗ Error adding {table_name}.{col_name}: {e}")
                else:
                    print(f"- Column {table_name}.{col_name} already exists")


def create_default_admin(engine):
    """Create default admin user."""
    print("\nCreating default admin user...")

    from werkzeug.security import generate_password_hash

    default_password = "admin123"
    hashed = generate_password_hash(default_password)

    sql = text("""
        INSERT INTO users (username, email, password_hash, role)
        VALUES (:username, :email, :password, :role)
    """)

    try:
        with engine.connect() as conn:
            # Check if admin exists
            result = conn.execute(text("SELECT COUNT(*) as count FROM users WHERE username = 'admin'"))
            row = result.fetchone()

            if row and row.count == 0:
                conn.execute(sql, {
                    'username': 'admin',
                    'email': 'admin@localhost',
                    'password': hashed,
                    'role': 'admin'
                })
                conn.commit()
                print("✓ Created admin user")
                print(f"  Username: admin")
                print(f"  Password: {default_password}")
                print("  ⚠ IMPORTANT: Change this password immediately!")
            else:
                print("- Admin user already exists")
    except Exception as e:
        print(f"✗ Error creating admin user: {e}")


def create_sample_data(engine):
    """Create sample alert rules and templates."""
    print("\nCreating sample data...")

    samples = {
        'alert_rules': [
            {
                'name': 'High CPU Usage',
                'description': 'Alert when CPU usage exceeds 90%',
                'metric_type': 'cpu',
                'condition': 'gt',
                'threshold': 90.0,
                'severity': 'warning'
            },
            {
                'name': 'High Temperature',
                'description': 'Alert when temperature exceeds 80°C',
                'metric_type': 'temperature',
                'condition': 'gt',
                'threshold': 80.0,
                'severity': 'critical'
            },
            {
                'name': 'Low Disk Space',
                'description': 'Alert when disk usage exceeds 90%',
                'metric_type': 'disk',
                'condition': 'gt',
                'threshold': 90.0,
                'severity': 'warning'
            },
            {
                'name': 'Device Offline',
                'description': 'Alert when device goes offline',
                'metric_type': 'offline',
                'condition': 'eq',
                'threshold': 1.0,
                'severity': 'critical'
            }
        ],
        'tags': [
            {'name': 'production', 'color': '#EF4444'},
            {'name': 'development', 'color': '#3B82F6'},
            {'name': 'iot-sensor', 'color': '#10B981'},
            {'name': 'media', 'color': '#F59E0B'},
        ],
        'device_groups': [
            {'name': 'Production', 'description': 'Production devices'},
            {'name': 'Development', 'description': 'Development and testing devices'},
            {'name': 'IoT Sensors', 'description': 'IoT sensor nodes'},
        ]
    }

    with engine.connect() as conn:
        # Create alert rules
        for rule in samples['alert_rules']:
            try:
                conn.execute(text("""
                    INSERT OR IGNORE INTO alert_rules
                    (name, description, metric_type, condition, threshold, severity, enabled)
                    VALUES (:name, :description, :metric_type, :condition, :threshold, :severity, 1)
                """), rule)
                conn.commit()
                print(f"✓ Created alert rule: {rule['name']}")
            except Exception as e:
                print(f"✗ Error creating alert rule: {e}")

        # Create tags
        for tag in samples['tags']:
            try:
                conn.execute(text("""
                    INSERT OR IGNORE INTO tags (name, color)
                    VALUES (:name, :color)
                """), tag)
                conn.commit()
                print(f"✓ Created tag: {tag['name']}")
            except Exception as e:
                print(f"✗ Error creating tag: {e}")

        # Create device groups
        for group in samples['device_groups']:
            try:
                conn.execute(text("""
                    INSERT OR IGNORE INTO device_groups (name, description)
                    VALUES (:name, :description)
                """), group)
                conn.commit()
                print(f"✓ Created group: {group['name']}")
            except Exception as e:
                print(f"✗ Error creating group: {e}")


def main():
    """Main upgrade process."""
    parser = argparse.ArgumentParser(description='Upgrade Pi Fleet Manager to V2')
    parser.add_argument('--skip-backup', action='store_true',
                       help='Skip database backup (not recommended)')
    parser.add_argument('--sample-data', action='store_true', default=True,
                       help='Create sample alert rules and tags')

    args = parser.parse_args()

    print("=" * 60)
    print("Pi Fleet Manager - Upgrade to V2.0")
    print("=" * 60)

    # Create backup
    if not args.skip_backup:
        backup_path = backup_database()
    else:
        print("⚠ Skipping backup (--skip-backup flag)")
        backup_path = None

    # Connect to database
    print(f"\nConnecting to database: {DATABASE_FILE}")
    engine = create_engine(f'sqlite:///{DATABASE_FILE}')

    try:
        # Create new tables
        create_tables(engine)

        # Update existing tables
        update_existing_tables(engine)

        # Create default admin
        create_default_admin(engine)

        # Create sample data
        if args.sample_data:
            create_sample_data(engine)

        print("\n" + "=" * 60)
        print("✓ Upgrade completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Install new dependencies:")
        print("   pip3 install -r requirements.txt")
        print("\n2. Start the enhanced manager (optional - v1 still works):")
        print("   python3 pi-fleet-manager.py")
        print("\n3. Access the dashboard and log in:")
        print("   Username: admin")
        print("   Password: admin123")
        print("   ⚠ Change the admin password immediately!")
        print("\n4. Start the alerting daemon:")
        print("   python3 services/alert-monitor.py")
        print("\n5. Optionally start the scheduler:")
        print("   python3 services/task-scheduler.py")

        if backup_path:
            print(f"\n📦 Backup saved to: {backup_path}")

        print("\nFor more information, see docs/UPGRADE_GUIDE.md")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Upgrade failed: {e}")
        if backup_path:
            print(f"\n📦 Your data is safe in: {backup_path}")
            print("To restore: cp {backup_path} {DATABASE_FILE}")
        sys.exit(1)


if __name__ == '__main__':
    main()
