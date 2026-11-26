import asyncio
import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.config import settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app import models

TEST_DATABASE = "document_intelligence_test_run_20261125"

def prepare_database():
    source_url = make_url(settings.DATABASE_URL)
    connection = psycopg.connect(
        host=source_url.host, port=source_url.port or 5432,
        user=source_url.username, password=source_url.password,
        dbname="postgres", autocommit=True,
    )
    try:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DATABASE,)
        ).fetchone()
        if not exists:
            connection.execute(f'CREATE DATABASE "{TEST_DATABASE}"')
    finally:
        connection.close()

    test_url = source_url.set(database=TEST_DATABASE)
    engine = create_async_engine(test_url, pool_pre_ping=True)

    async def reset_schema():
        async with engine.begin() as connection:
            await connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(reset_schema(), loop_factory=asyncio.SelectorEventLoop)
    return engine

@pytest.fixture(scope="session")
def client():
    engine = prepare_database()
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())
