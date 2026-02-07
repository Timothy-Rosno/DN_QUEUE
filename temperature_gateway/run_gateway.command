#!/bin/bash
# Temperature Gateway Launcher
# Uses virtual environment Python directly for Automator compatibility

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Lock file to prevent multiple instances
LOCK_FILE="$SCRIPT_DIR/.gateway.lock"
PID_FILE="$SCRIPT_DIR/.gateway.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Temperature Gateway is already running (PID: $OLD_PID)"
        echo "To stop it, run: kill $OLD_PID"
        read -p "Press Enter to exit..."
        exit 1
    else
        # Stale PID file, clean up
        rm -f "$PID_FILE" "$LOCK_FILE"
    fi
fi

# Check if gateway_config.json exists
if [ ! -f "gateway_config.json" ]; then
    echo "ERROR: gateway_config.json not found!"
    echo "Copy gateway_config.json.example to gateway_config.json and configure it."
    read -p "Press Enter to exit..."
    exit 1
fi

# Use venv Python directly (absolute path for Automator compatibility)
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
elif [ -f "$SCRIPT_DIR/../.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/../.venv/bin/python"
elif [ -f "$SCRIPT_DIR/../venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/../venv/bin/python"
else
    echo "ERROR: No virtual environment found!"
    echo "Create one with: python3 -m venv .venv && .venv/bin/pip install requests"
    read -p "Press Enter to exit..."
    exit 1
fi

# Write PID file
echo $$ > "$PID_FILE"

# Cleanup on exit
cleanup() {
    rm -f "$PID_FILE" "$LOCK_FILE"
}
trap cleanup EXIT

echo "Using Python: $PYTHON"
echo "Starting Temperature Gateway..."
"$PYTHON" temperature_gateway.py