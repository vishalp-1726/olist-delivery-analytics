"""Project settings and folder paths, used by every script and notebook."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]      # the project folder
load_dotenv(ROOT / ".env")                      # database login

with open(ROOT / "config" / "settings.yaml") as f:
    SETTINGS = yaml.safe_load(f)

RAW = ROOT / "data" / "raw"                     # the Kaggle files, unzipped
PROCESSED = ROOT / "data" / "processed"         # files for Tableau and the business teams
FIGURES = ROOT / "reports" / "figures"
SQL = ROOT / "sql"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://localhost:5432/olist")
