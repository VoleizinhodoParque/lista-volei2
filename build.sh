#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Create the /data directory if it doesn't exist
mkdir -p /data