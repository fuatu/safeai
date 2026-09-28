#!/usr/bin/env bash
# ==============================================================================
# SafeAI - Local Gateway & Governance Portal Runner
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "🛡️  Starting SafeAI Local Gateway on host..."

# 1. Setup / activate virtual environment
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment (.venv)..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r backend/requirements.txt
else
    source .venv/bin/activate
fi

# 2. Check if frontend build exists
if [ ! -d "frontend/dist" ]; then
    echo "⚡ Building frontend assets..."
    cd frontend
    npm install
    npm run build
    cd ..
fi

# 3. Create local data directory for SQLite audit logs
mkdir -p data

echo "🚀 Launching SafeAI Core Gateway at http://localhost:8080"
echo "   - Dashboard UI: http://localhost:8080"
echo "   - MCP Endpoint: http://localhost:8080/mcp?client_name=<ClientName>"
echo "   - SQLite DB:    ./data/safeai.db"
echo ""

exec python -m backend.main
