#!/usr/bin/env python3
"""
Configuration Deployment Tool

Deploy configuration files and templates to Pi devices in the fleet.
Supports Jinja2 templating, variable substitution, and group-based deployments.

Usage:
    python3 deploy-config.py --server <url> --config <file> [options]
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('deploy-config')


class ConfigDeployer:
    """Deploy configurations to fleet devices."""

    def __init__(self, server_url: str):
        """Initialize the deployer.

        Args:
            server_url: Fleet manager server URL
        """
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()

    def get_devices(self, filter_pattern: Optional[str] = None,
                   group: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of devices to deploy to.

        Args:
            filter_pattern: Filter devices by name pattern
            group: Filter devices by group

        Returns:
            List of device dictionaries
        """
        response = self.session.get(f"{self.server_url}/api/devices")
        response.raise_for_status()

        devices = response.json()['devices']

        # Filter by pattern
        if filter_pattern:
            devices = [d for d in devices
                      if filter_pattern.lower() in d['device_name'].lower()]

        # Only online devices
        devices = [d for d in devices if d['status'] == 'online']

        return devices

    def render_template(self, template_path: Path,
                       variables: Dict[str, Any]) -> str:
        """Render a configuration template.

        Args:
            template_path: Path to template file
            variables: Variables for template rendering

        Returns:
            Rendered template content
        """
        try:
            from jinja2 import Template
        except ImportError:
            # If Jinja2 not available, do simple variable substitution
            content = template_path.read_text()
            for key, value in variables.items():
                content = content.replace(f"{{{{{key}}}}}", str(value))
            return content

        # Use Jinja2 for advanced templating
        template = Template(template_path.read_text())
        return template.render(**variables)

    def deploy_config(self, device_id: str, device_name: str,
                     target_path: str, content: str,
                     mode: str = "0644") -> bool:
        """Deploy configuration to a device.

        Args:
            device_id: Device ID
            device_name: Device name (for logging)
            target_path: Target path on device
            content: Configuration content
            mode: File permissions (octal string)

        Returns:
            True if successful
        """
        logger.info(f"Deploying config to {device_name}: {target_path}")

        payload = {
            "type": "deploy_config",
            "payload": {
                "path": target_path,
                "content": content,
                "mode": mode,
            }
        }

        try:
            response = self.session.post(
                f"{self.server_url}/api/devices/{device_id}/commands",
                json=payload
            )
            response.raise_for_status()
            logger.info(f"✓ Config deployed to {device_name}")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to deploy to {device_name}: {e}")
            return False

    def deploy_to_fleet(self, config_spec: Dict[str, Any],
                       dry_run: bool = False) -> None:
        """Deploy configuration based on specification.

        Args:
            config_spec: Configuration specification
            dry_run: If True, only show what would be deployed
        """
        # Get target devices
        devices = self.get_devices(
            filter_pattern=config_spec.get('filter'),
            group=config_spec.get('group')
        )

        if not devices:
            logger.warning("No devices match the specified criteria")
            return

        logger.info(f"Deploying to {len(devices)} device(s)")

        # Process each deployment
        for deployment in config_spec.get('deployments', []):
            template_path = Path(deployment['template'])
            target_path = deployment['target']
            mode = deployment.get('mode', '0644')
            variables = deployment.get('variables', {})

            logger.info(f"\nDeploying: {template_path} -> {target_path}")

            # Render template
            try:
                content = self.render_template(template_path, variables)
            except Exception as e:
                logger.error(f"Failed to render template: {e}")
                continue

            if dry_run:
                logger.info("[DRY RUN] Would deploy to:")
                for device in devices:
                    logger.info(f"  - {device['device_name']}")
                continue

            # Deploy to each device
            success_count = 0
            for device in devices:
                # Merge device-specific variables
                device_vars = {
                    **variables,
                    'device_id': device['device_id'],
                    'device_name': device['device_name'],
                    'hostname': device['network']['hostname'],
                }

                # Re-render with device-specific vars
                device_content = self.render_template(template_path, device_vars)

                if self.deploy_config(
                    device['device_id'],
                    device['device_name'],
                    target_path,
                    device_content,
                    mode
                ):
                    success_count += 1

            logger.info(f"\nDeployment complete: {success_count}/{len(devices)} successful")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Deploy configurations to Pi fleet'
    )
    parser.add_argument(
        '--server',
        required=True,
        help='Fleet manager server URL'
    )
    parser.add_argument(
        '--config',
        required=True,
        help='Configuration specification file (YAML)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deployed without executing'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    # Load configuration specification
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    try:
        with open(config_path) as f:
            config_spec = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Deploy configurations
    deployer = ConfigDeployer(args.server)

    try:
        deployer.deploy_to_fleet(config_spec, dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
