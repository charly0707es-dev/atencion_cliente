#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -d backend/.venv ]]; then
  python3 -m venv backend/.venv
fi
backend/.venv/bin/python -m pip install -r backend/requirements.txt

cd frontend
npm install
npm run build
cd "$ROOT_DIR"

exec backend/.venv/bin/python backend/app.py

