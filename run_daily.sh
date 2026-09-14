#!/bin/bash
# ------------------------------------------------------------------------------
# Daily runner script for Bluesky auto-poster
# Can be run manually or invoked by crontab / launchd
# ------------------------------------------------------------------------------
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Activate python or virtualenv if present
if [ -d "venv" ]; then
    source venv/bin/activate
fi

python3 bsky_poster.py "$@"
