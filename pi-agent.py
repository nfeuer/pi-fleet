#!/usr/bin/env python3
"""
Raspberry Pi Fleet Management Agent

This agent runs on each Raspberry Pi device and communicates with
the central fleet manager. It provides system metrics, executes
commands, and manages configurations.

Usage:
    python3 pi-agent.py --server <server_url> --name <device_name>
"""

import argparse
import json
import logging
import os
import platform
import psutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuration
DEFAULT_PORT = 5000
CHECK_INTERVAL = 60  # seconds
AGENT_VERSION = "1.0.0"
CONFIG_DIR = Path("/etc/pi-fleet")
STATE_FILE = CONFIG_DIR / "agent-state.json"
LOG_FILE = CONFIG_DIR / "agent.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE) if CONFIG_DIR.exists() else logging.StreamHandler(),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('pi-agent')


class PiAgent:
    """Main agent class for Pi fleet management."""

    def __init__(self, server_url: str, device_name: Optional[str] = None):
        """Initialize the Pi agent.

        Args:
            server_url: URL of the fleet manager server
            device_name: Optional custom name for this device
        """
        self.server_url = server_url.rstrip('/')
        self.device_name = device_name or socket.gethostname()
        self.device_id = self._get_device_id()
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def _get_device_id(self) -> str:
        """Get unique device identifier."""
        # Try to get CPU serial (works on most Pi models)
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        return line.split(':')[1].strip()
        except Exception:
            pass

        # Fallback to MAC address
        try:
            import uuid
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                          for elements in range(0, 2*6, 2)][::-1])
            return mac
        except Exception:
            return socket.gethostname()

    def get_system_info(self) -> Dict[str, Any]:
        """Collect comprehensive system information."""
        info = {
            'device_id': self.device_id,
            'device_name': self.device_name,
            'agent_version': AGENT_VERSION,
            'timestamp': datetime.utcnow().isoformat(),
            'hardware': self._get_hardware_info(),
            'os': self._get_os_info(),
            'metrics': self._get_metrics(),
            'network': self._get_network_info(),
            'services': self._get_services_info(),
            'packages': self._get_installed_packages()
        }
        return info

    def _get_hardware_info(self) -> Dict[str, Any]:
        """Get hardware information."""
        hw_info = {
            'model': 'Unknown',
            'revision': 'Unknown',
            'cpu_count': psutil.cpu_count(),
            'total_memory': psutil.virtual_memory().total,
        }

        # Try to get Pi model from device tree
        try:
            with open('/proc/device-tree/model', 'r') as f:
                hw_info['model'] = f.read().strip('\x00').strip()
        except Exception:
            pass

        # Try to get revision
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Revision'):
                        hw_info['revision'] = line.split(':')[1].strip()
                        break
        except Exception:
            pass

        return hw_info

    def _get_os_info(self) -> Dict[str, Any]:
        """Get OS information."""
        os_info = {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'architecture': platform.machine(),
        }

        # Try to get OS release info
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME'):
                        os_info['distribution'] = line.split('=')[1].strip().strip('"')
                        break
        except Exception:
            pass

        return os_info

    def _get_metrics(self) -> Dict[str, Any]:
        """Collect current system metrics."""
        metrics = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'cpu_per_core': psutil.cpu_percent(interval=1, percpu=True),
            'memory': {
                'total': psutil.virtual_memory().total,
                'available': psutil.virtual_memory().available,
                'percent': psutil.virtual_memory().percent,
                'used': psutil.virtual_memory().used,
            },
            'disk': {},
            'temperature': self._get_temperature(),
            'uptime': time.time() - psutil.boot_time(),
        }

        # Get disk usage for all partitions
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                metrics['disk'][partition.mountpoint] = {
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent,
                }
            except Exception:
                continue

        return metrics

    def _get_temperature(self) -> Optional[float]:
        """Get CPU temperature."""
        try:
            # Try thermal zone (most Pi models)
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read().strip()) / 1000.0
                return round(temp, 2)
        except Exception:
            pass

        # Try vcgencmd (alternative method)
        try:
            result = subprocess.run(
                ['vcgencmd', 'measure_temp'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                temp_str = result.stdout.strip().replace("temp=", "").replace("'C", "")
                return round(float(temp_str), 2)
        except Exception:
            pass

        return None

    def _get_network_info(self) -> Dict[str, Any]:
        """Get network information."""
        network = {
            'hostname': socket.gethostname(),
            'interfaces': {}
        }

        # Get network interfaces
        for interface, addrs in psutil.net_if_addrs().items():
            network['interfaces'][interface] = []
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    network['interfaces'][interface].append({
                        'type': 'IPv4',
                        'address': addr.address,
                        'netmask': addr.netmask,
                    })
                elif addr.family == socket.AF_INET6:
                    network['interfaces'][interface].append({
                        'type': 'IPv6',
                        'address': addr.address,
                    })

        return network

    def _get_services_info(self) -> Dict[str, str]:
        """Get status of common services."""
        services = {}
        common_services = ['ssh', 'docker', 'nginx', 'apache2', 'mosquitto', 'influxdb']

        for service in common_services:
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', service],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                services[service] = result.stdout.strip()
            except Exception:
                services[service] = 'unknown'

        return services

    def _get_installed_packages(self) -> Dict[str, Any]:
        """Get list of installed packages (summary only to keep it lightweight)."""
        packages = {
            'count': 0,
            'last_updated': None,
        }

        try:
            # Count installed packages
            result = subprocess.run(
                ['dpkg', '-l'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # Count lines starting with 'ii' (installed packages)
                packages['count'] = len([l for l in result.stdout.split('\n')
                                       if l.startswith('ii')])
        except Exception:
            pass

        return packages

    def register_device(self) -> bool:
        """Register this device with the fleet manager."""
        try:
            info = self.get_system_info()
            response = self.session.post(
                f"{self.server_url}/api/devices/register",
                json=info,
                timeout=10
            )

            if response.status_code in [200, 201]:
                logger.info(f"Device registered successfully: {self.device_name}")
                return True
            else:
                logger.error(f"Registration failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to register device: {e}")
            return False

    def send_heartbeat(self) -> bool:
        """Send heartbeat with current metrics to the server."""
        try:
            metrics = {
                'device_id': self.device_id,
                'device_name': self.device_name,
                'timestamp': datetime.utcnow().isoformat(),
                'metrics': self._get_metrics(),
            }

            response = self.session.post(
                f"{self.server_url}/api/devices/heartbeat",
                json=metrics,
                timeout=10
            )

            if response.status_code == 200:
                logger.debug(f"Heartbeat sent successfully")
                return True
            else:
                logger.warning(f"Heartbeat failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
            return False

    def check_for_commands(self) -> None:
        """Check for pending commands from the server."""
        try:
            response = self.session.get(
                f"{self.server_url}/api/devices/{self.device_id}/commands",
                timeout=10
            )

            if response.status_code == 200:
                commands = response.json()
                for cmd in commands:
                    self.execute_command(cmd)

        except Exception as e:
            logger.error(f"Failed to check for commands: {e}")

    def execute_command(self, command: Dict[str, Any]) -> None:
        """Execute a command from the server.

        Args:
            command: Command dictionary with 'id', 'type', and 'payload'
        """
        cmd_id = command.get('id')
        cmd_type = command.get('type')
        payload = command.get('payload', {})

        logger.info(f"Executing command {cmd_id}: {cmd_type}")

        result = {
            'command_id': cmd_id,
            'status': 'unknown',
            'output': '',
            'error': '',
        }

        try:
            if cmd_type == 'shell':
                result = self._execute_shell_command(payload)
            elif cmd_type == 'update':
                result = self._execute_update(payload)
            elif cmd_type == 'deploy_config':
                result = self._deploy_config(payload)
            elif cmd_type == 'service':
                result = self._manage_service(payload)
            elif cmd_type == 'reboot':
                result = self._schedule_reboot(payload)
            else:
                result['status'] = 'error'
                result['error'] = f"Unknown command type: {cmd_type}"

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            logger.error(f"Command execution failed: {e}")

        # Send result back to server
        try:
            self.session.post(
                f"{self.server_url}/api/devices/{self.device_id}/commands/{cmd_id}/result",
                json=result,
                timeout=10
            )
        except Exception as e:
            logger.error(f"Failed to send command result: {e}")

    def _execute_shell_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a shell command."""
        cmd = payload.get('command', '')
        timeout = payload.get('timeout', 300)

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        return {
            'status': 'success' if result.returncode == 0 else 'error',
            'output': result.stdout,
            'error': result.stderr,
            'return_code': result.returncode,
        }

    def _execute_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute system update."""
        update_type = payload.get('update_type', 'packages')

        if update_type == 'packages':
            # Update package lists
            subprocess.run(['apt-get', 'update'], check=True)

            # Upgrade packages
            result = subprocess.run(
                ['apt-get', 'upgrade', '-y'],
                capture_output=True,
                text=True,
                timeout=600
            )

            return {
                'status': 'success' if result.returncode == 0 else 'error',
                'output': result.stdout,
                'error': result.stderr,
            }
        else:
            return {
                'status': 'error',
                'error': f"Unknown update type: {update_type}",
            }

    def _deploy_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy configuration file."""
        file_path = payload.get('path')
        content = payload.get('content')
        mode = payload.get('mode', '0644')

        if not file_path or not content:
            return {
                'status': 'error',
                'error': 'Missing path or content',
            }

        # Write file
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

        # Set permissions
        os.chmod(file_path, int(mode, 8))

        return {
            'status': 'success',
            'output': f"Config deployed to {file_path}",
        }

    def _manage_service(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Manage systemd service."""
        service = payload.get('service')
        action = payload.get('action', 'status')

        result = subprocess.run(
            ['systemctl', action, service],
            capture_output=True,
            text=True,
            timeout=30
        )

        return {
            'status': 'success' if result.returncode == 0 else 'error',
            'output': result.stdout,
            'error': result.stderr,
        }

    def _schedule_reboot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule system reboot."""
        delay = payload.get('delay', 1)  # minutes

        subprocess.run(['shutdown', '-r', f'+{delay}'])

        return {
            'status': 'success',
            'output': f"Reboot scheduled in {delay} minutes",
        }

    def run(self) -> None:
        """Main agent loop."""
        logger.info(f"Starting Pi Fleet Agent v{AGENT_VERSION}")
        logger.info(f"Device: {self.device_name} (ID: {self.device_id})")
        logger.info(f"Server: {self.server_url}")

        # Initial registration
        if not self.register_device():
            logger.warning("Initial registration failed, will retry...")

        # Main loop
        while True:
            try:
                # Send heartbeat
                self.send_heartbeat()

                # Check for commands
                self.check_for_commands()

                # Sleep until next check
                time.sleep(CHECK_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Agent stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(CHECK_INTERVAL)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Raspberry Pi Fleet Management Agent'
    )
    parser.add_argument(
        '--server',
        required=True,
        help='Fleet manager server URL (e.g., http://192.168.1.100:5000)'
    )
    parser.add_argument(
        '--name',
        help='Custom device name (default: hostname)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=CHECK_INTERVAL,
        help=f'Check interval in seconds (default: {CHECK_INTERVAL})'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    # Update check interval
    global CHECK_INTERVAL
    CHECK_INTERVAL = args.interval

    # Create config directory if needed
    if not CONFIG_DIR.exists():
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            logger.warning(f"Cannot create {CONFIG_DIR}, using current directory")

    # Create and run agent
    agent = PiAgent(args.server, args.name)
    agent.run()


if __name__ == '__main__':
    main()
