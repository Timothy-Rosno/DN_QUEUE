#!/usr/bin/env python3
"""
Temperature Gateway Service for Lab Equipment Scheduler

This script runs on a computer within the university network that has access
to the lab machines' local IP addresses. It periodically reads temperature
data from each machine and sends it to the Django app hosted on Render.

Requirements:
    - Python 3.6+
    - requests library (pip install requests)
    - gateway_config.json file with configuration

Usage:
    python temperature_gateway.py

The script will run continuously, updating temperatures every N seconds
(configured in gateway_config.json).
"""

import json
import time
import requests
import sys
from datetime import datetime
from pathlib import Path


class TemperatureGateway:
    """Gateway service for reading and forwarding machine temperatures."""

    def __init__(self, config_path='gateway_config.json'):
        """Initialize the gateway with configuration."""
        self.config_path = Path(config_path)
        self.load_config()

    def load_config(self):
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)

            # Validate required fields
            required = ['api_url', 'api_key', 'machines']
            for field in required:
                if field not in self.config:
                    raise ValueError(f"Missing required config field: {field}")

            self.api_url = self.config['api_url']
            self.api_key = self.config['api_key']
            self.machines = self.config['machines']
            self.update_interval = self.config.get('update_interval', 15)

            print(f"✅ Loaded config for {len(self.machines)} machines")
            print(f"   API: {self.api_url}")
            print(f"   Update interval: {self.update_interval} seconds")

        except FileNotFoundError:
            print(f"❌ Config file not found: {self.config_path}")
            print("   Create gateway_config.json from gateway_config.json.example")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in config file: {e}")
            sys.exit(1)
        except ValueError as e:
            print(f"❌ Config error: {e}")
            sys.exit(1)

    def read_temperature(self, machine):
        """
        Read temperature from a single machine's API.

        Args:
            machine (dict): Machine configuration with id, name, ip, api_type, etc.

        Returns:
            dict: {id, temperature, online} or None if error
        """
        machine_id = machine['id']
        machine_name = machine['name']
        ip = machine['ip']
        api_type = machine['api_type']

        try:
            if api_type == 'port5001':
                # Hidalgo/Griffin style API
                url = f'http://{ip}:5001/channel/measurement/latest'
                response = requests.get(url, timeout=3)
                response.raise_for_status()
                data = response.json()
                temperature = data.get('temperature')

                return {
                    'id': machine_id,
                    'temperature': temperature,
                    'online': True
                }

            elif api_type == 'quantum_design':
                # Quantum Design (OptiCool/CryoCore) API
                port = machine.get('api_port', 47101)
                url = f'http://{ip}:{port}/v1/sampleChamber/temperatureControllers/user1/thermometer/properties/sample'
                response = requests.get(url, timeout=3)
                response.raise_for_status()
                data = response.json()
                temperature = data.get('sample', {}).get('temperature')

                return {
                    'id': machine_id,
                    'temperature': temperature,
                    'online': True
                }

            elif api_type == 'none':
                # No API - skip
                return {
                    'id': machine_id,
                    'temperature': None,
                    'online': True  # Assume available if no monitoring
                }

            else:
                print(f"⚠️  {machine_name}: Unknown API type '{api_type}'")
                return {
                    'id': machine_id,
                    'temperature': None,
                    'online': False
                }

        except requests.Timeout:
            print(f"⚠️  {machine_name}: Timeout (machine may be off or network issue)")
            return {
                'id': machine_id,
                'temperature': None,
                'online': False
            }
        except requests.RequestException as e:
            print(f"⚠️  {machine_name}: Connection error - {e}")
            return {
                'id': machine_id,
                'temperature': None,
                'online': False
            }
        except (KeyError, TypeError, json.JSONDecodeError) as e:
            print(f"⚠️  {machine_name}: Invalid response format - {e}")
            return {
                'id': machine_id,
                'temperature': None,
                'online': False
            }

    def send_to_api(self, machine_data):
        """
        Send temperature data to the Django API on Render.

        Args:
            machine_data (list): List of {id, temperature, online} dicts

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            headers = {
                'X-API-Key': self.api_key,
                'Content-Type': 'application/json'
            }

            payload = {
                'machines': machine_data
            }

            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=10
            )

            response.raise_for_status()
            result = response.json()

            if result.get('success'):
                updated = result.get('updated', 0)
                errors = result.get('errors', [])

                if errors:
                    print(f"⚠️  API reported errors:")
                    for error in errors:
                        print(f"     {error}")

                return True
            else:
                print(f"❌ API returned success=false: {result.get('error', 'Unknown error')}")
                return False

        except requests.Timeout:
            print(f"❌ API timeout - server may be sleeping (Render free tier)")
            print("   Will retry on next cycle...")
            return False
        except requests.RequestException as e:
            print(f"❌ API request failed: {e}")
            return False
        except (KeyError, TypeError, json.JSONDecodeError) as e:
            print(f"❌ Invalid API response: {e}")
            return False

    def run_once(self):
        """Run one update cycle."""
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Reading temperatures...")

        # Read from all machines
        machine_data = []
        for machine in self.machines:
            result = self.read_temperature(machine)
            if result:
                machine_data.append(result)
                temp_str = f"{result['temperature']:.2f}K" if result['temperature'] else "N/A"
                status = "✅" if result['online'] else "❌"
                print(f"  {status} {machine['name']}: {temp_str}")

        # Send to API
        if machine_data:
            print(f"  Sending {len(machine_data)} readings to API...")
            if self.send_to_api(machine_data):
                print(f"  ✅ Successfully updated {len(machine_data)} machines")
            else:
                print(f"  ❌ Failed to send to API")
        else:
            print(f"  ⚠️  No data to send")

    def run(self):
        """Run the gateway service continuously."""
        print("=" * 60)
        print("Temperature Gateway Service")
        print("=" * 60)
        print(f"Monitoring {len(self.machines)} machines")
        print(f"Update interval: {self.update_interval} seconds")
        print(f"API endpoint: {self.api_url}")
        print("\nPress Ctrl+C to stop\n")
        print("=" * 60)

        try:
            while True:
                self.run_once()
                print(f"\nWaiting {self.update_interval} seconds until next update...")
                time.sleep(self.update_interval)

        except KeyboardInterrupt:
            print("\n\n✅ Gateway service stopped by user")
            sys.exit(0)
        except Exception as e:
            print(f"\n\n❌ Unexpected error: {e}")
            sys.exit(1)


if __name__ == '__main__':
    gateway = TemperatureGateway()
    gateway.run()
