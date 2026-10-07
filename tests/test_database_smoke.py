from sqlalchemy import create_engine, text

from app.config import Settings


def test_tests_service_can_reach_test_database():
    settings = Settings()
    engine = create_engine(settings.database_url)

    with engine.connect() as connection:
        database = connection.execute(text("SELECT current_database()")).scalar_one()

    engine.dispose()
    assert database == settings.postgres_db
