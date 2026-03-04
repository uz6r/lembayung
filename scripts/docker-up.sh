#!/bin/bash
set -e

# Ensure data directory exists for persistent sqlite storage
mkdir -p data

echo "🚀 Starting Lembayung stack (Monitor + Telegram Bot)..."
docker compose up -d

echo "📊 Current status:"
docker compose ps
