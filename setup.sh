#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing dependencies..."
uv pip install --python /home/ubuntu/.venv/bin/python "$SCRIPT_DIR" --quiet

echo "Building chat UI..."
docker build -t deep-agents-ui "$SCRIPT_DIR/deep-agents-ui" > /dev/null 2>&1

echo "Starting chat UI..."
if docker ps -a --format '{{.Names}}' | grep -q '^deep-agents-ui$'; then
    docker start deep-agents-ui > /dev/null 2>&1
else
    docker run -d --network host --name deep-agents-ui --restart unless-stopped deep-agents-ui > /dev/null 2>&1
fi

echo "Done!"
