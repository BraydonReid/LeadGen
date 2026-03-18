#!/usr/bin/env bash
# Quick setup script for LeadGen MVP
set -e

echo "=== LeadGen MVP Setup ==="

# 1. Create .env if it doesn't exist
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — EDIT IT before continuing!"
  echo "  -> Add your POSTGRES_PASSWORD and Stripe keys"
  exit 1
fi

# 2. Create frontend .env.local
if [ ! -f frontend/.env.local ]; then
  cp frontend/.env.local.example frontend/.env.local
  echo "Created frontend/.env.local"
fi

# 3. Start postgres first and run migrations
echo ""
echo "Starting PostgreSQL..."
docker compose up -d postgres

echo "Waiting for PostgreSQL to be ready..."
until docker compose exec postgres pg_isready -U leadgen; do
  sleep 1
done

echo ""
echo "Running database migrations..."
docker compose run --rm backend sh -c "cd /app && alembic upgrade head"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Start all services:  docker compose up"
echo "  2. Run the scraper:     docker compose run --rm -e DATABASE_URL=postgresql://leadgen:PASSWORD@postgres:5432/leadgen scraper python main.py"
echo "  3. Open:                http://localhost:3000"
echo ""
echo "For Stripe webhooks (local testing):"
echo "  stripe listen --forward-to localhost:8000/api/stripe/webhook"
