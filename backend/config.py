"""Backend configuration — reads from environment / project-root .env."""

import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BASE_DIR, ".env"))

DATABASE_URL = os.environ.get(
    "AGRISMART_DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'agrismart.db')}"
)

JWT_SECRET = os.environ.get("AGRISMART_JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get("AGRISMART_TOKEN_EXPIRE_MINUTES", 60 * 24 * 14)
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

CORS_ORIGINS = os.environ.get("AGRISMART_CORS_ORIGINS", "*").split(",")
