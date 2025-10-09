#!/bin/bash
#
# Reload Doorman configuration without restart
#
# Usage:
#   ./scripts/reload-config.sh
#   ./scripts/reload-config.sh --check

set -e

PID_FILE="doorman.pid"
CONFIG_FILE="config.yaml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${YELLOW}Warning: $CONFIG_FILE not found${NC}"
    echo "Using environment variables only"
fi

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo -e "${RED}Error: $PID_FILE not found${NC}"
    echo "Is Doorman running?"
    exit 1
fi

# Read PID
PID=$(cat "$PID_FILE")

# Check if process is running
if ! kill -0 "$PID" 2>/dev/null; then
    echo -e "${RED}Error: Doorman process (PID: $PID) not running${NC}"
    echo "Stale PID file detected, please remove $PID_FILE"
    exit 1
fi

# Check mode
if [ "$1" == "--check" ]; then
    echo "Doorman Configuration Check"
    echo "============================"
    echo
    echo "Process:"
    echo "  PID: $PID"
    echo "  Status: Running"
    echo
    echo "Configuration:"
    if [ -f "$CONFIG_FILE" ]; then
        echo "  File: $CONFIG_FILE (exists)"
        echo
        echo "Current values:"
        grep -E '^[a-z_]+:' "$CONFIG_FILE" | head -20
    else
        echo "  File: Not configured (using environment variables)"
    fi
    echo
    echo "To reload configuration:"
    echo "  $0"
    exit 0
fi

# Send SIGHUP signal
echo -e "${GREEN}Reloading Doorman configuration...${NC}"
echo "  PID: $PID"
echo "  Signal: SIGHUP"

if kill -HUP "$PID"; then
    echo -e "${GREEN}✓ Configuration reload signal sent${NC}"
    echo
    echo "Check logs for reload status:"
    echo "  tail -f logs/doorman.log | grep -i 'sighup\|reload'"
    echo
    echo "Verify configuration changes:"
    echo "  curl http://localhost:8000/config/current"
else
    echo -e "${RED}✗ Failed to send reload signal${NC}"
    exit 1
fi
