#!/usr/bin/env bash
# Build a clean deployment bundle (no .venv, __pycache__, .env, .DS_Store).
# Usage: ./scripts/build_deploy_bundle.sh [output.zip]

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-deploy-bundle.zip}"
cd "$ROOT"

echo "Creating deploy bundle: $OUT"
zip -r "$OUT" . \
  -x "*.pyc" \
  -x "*__pycache__*" \
  -x ".venv/*" \
  -x "venv/*" \
  -x "env/*" \
  -x ".env" \
  -x ".env.*" \
  -x ".git/*" \
  -x ".DS_Store" \
  -x "*.log" \
  -x "data/*" \
  -x "deploy-bundle.zip" \
  -x ".idea/*" \
  -x ".vscode/*"

echo "Done. Unzip and run: pip install -r requirements.txt && gunicorn app:app"
