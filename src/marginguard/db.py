import os
from dotenv import load_dotenv
from sqlalchemy import create_engine


def get_engine():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Copy .env.example to .env and configure DATABASE_URL.")
    return create_engine(url, pool_pre_ping=True)
