import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('CREATOROS_TESTING', '1')
    from app.main import app
    from app.db import Base, get_db
    from fastapi.testclient import TestClient
    import app.content as content
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    def db_override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(content, 'UPLOAD_DIR', tmp_path)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
