#!/usr/bin/env bash
set -e

echo "========================================================"
echo "  Starting Frontdesk (Arvo Systems Support Management)"
echo "========================================================"

echo "Installing Python dependencies..."
pip install -r backend/requirements.txt

echo "Starting application on http://127.0.0.1:8000 ..."
python run_local.py
