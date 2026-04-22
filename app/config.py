import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./facturation.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "facturation@example.com")
PDF_STORAGE_PATH = os.getenv("PDF_STORAGE_PATH", "./storage/bdl")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

ALERT_SEUIL_30 = 0.30
ALERT_SEUIL_10 = 0.10
