import pytest

from app import create_app
from app.cli import bootstrap_database
from app.extensions import db
from config import TestConfig


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        bootstrap_database(application)
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
