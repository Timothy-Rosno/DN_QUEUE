#!/usr/bin/env python
"""
Run Django development server on an available port.
Automatically finds the next available port starting from 8000.
Also ensures Redis is running for Django Channels.
"""
import socket
import subprocess
import sys
import shutil
import platform

def is_port_available(port):
    """Check if a port is available."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', port))
        sock.close()
        return True
    except OSError:
        return False

def find_available_port(start_port=8000, max_attempts=10):
    """Find the first available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port):
            return port
    return None

def is_redis_installed():
    """Check if Redis is installed."""
    return shutil.which("redis-server") is not None

def is_redis_running():
    """Check if Redis is running by attempting to ping it."""
    try:
        result = subprocess.run(
            ["redis-cli", "ping"],
            capture_output=True,
            text=True,
            timeout=2
        )
        return result.returncode == 0 and "PONG" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def start_redis():
    """Attempt to start Redis server."""
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            # Try using Homebrew services first
            result = subprocess.run(
                ["brew", "services", "start", "redis"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True

            # Fallback to direct redis-server
            subprocess.Popen(
                ["redis-server", "--daemonize", "yes"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        elif system == "Linux":
            # Try systemctl first
            result = subprocess.run(
                ["sudo", "systemctl", "start", "redis"],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                return True

            # Fallback to direct redis-server
            subprocess.Popen(
                ["redis-server", "--daemonize", "yes"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        else:
            # Windows or other
            subprocess.Popen(
                ["redis-server"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
    except Exception as e:
        print(f"Warning: Failed to start Redis automatically: {e}")
        return False

def check_redis():
    """Check Redis installation and status, start if needed."""
    if not is_redis_installed():
        print("ERROR: Redis is not installed!")
        print("-" * 60)
        print("Redis is required for Django Channels WebSocket support.")
        print("\nInstallation instructions:")
        print("-" * 60)

        system = platform.system()
        if system == "Darwin":  # macOS
            print("macOS (using Homebrew):")
            print("  brew install redis")
            print("  brew services start redis")
        elif system == "Linux":
            print("Linux (Ubuntu/Debian):")
            print("  sudo apt-get update")
            print("  sudo apt-get install redis-server")
            print("  sudo systemctl start redis")
            print("\nLinux (Fedora/CentOS/RHEL):")
            print("  sudo yum install redis")
            print("  sudo systemctl start redis")
        else:
            print("Windows:")
            print("  Download from: https://redis.io/download")
            print("  Or use WSL and follow Linux instructions")

        print("-" * 60)
        sys.exit(1)

    if not is_redis_running():
        print("Redis is not running. Attempting to start...")
        if start_redis():
            # Wait a moment for Redis to start
            import time
            time.sleep(1)

            if is_redis_running():
                print("Redis started successfully!")
            else:
                print("Warning: Redis may not have started properly.")
                print("You may need to start it manually with: redis-server")
        else:
            print("Warning: Could not start Redis automatically.")
            print("Please start Redis manually with: redis-server")
    else:
        print("Redis is running")

if __name__ == "__main__":
    # Check Redis before starting
    check_redis()
    print()

    # Find available port
    port = find_available_port()

    if port is None:
        print("Error: Could not find an available port in range 8000-8010")
        sys.exit(1)

    print(f"Starting Django development server on port {port}...")
    print(f"Server will be available at: http://127.0.0.1:{port}/")
    print("-" * 60)

    # Run the Django development server
    try:
        subprocess.run([sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}"])
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)
