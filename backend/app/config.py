"""Configuration from environment (never commit a real .env)."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing. Configure backend/.env or the Docker Compose environment.")
FRONTEND_ORIGINS = [origin.strip() for origin in os.getenv(
    "FRONTEND_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",") if origin.strip()]
SESSION_HOURS = max(1, int(os.getenv("SESSION_HOURS", "12")))
MAX_QUANTITY = 1_000_000
