import pytest
from sqlalchemy.pool import StaticPool

from app import create_app
from app.extensions import db
from app.models.user import User
from app.services.clinic_status_service import ensure_default_clinic_status


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
            "SERVER_NAME": "localhost",
        }
    )

    with app.app_context():
        db.create_all()
        ensure_default_clinic_status()

        doctor = User(name="Test Doctor", email="doctor@test.com", role="doctor")
        doctor.set_password("password")
        receptionist = User(name="Test Receptionist", email="receptionist@test.com", role="receptionist")
        receptionist.set_password("password")
        db.session.add_all([doctor, receptionist])
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
