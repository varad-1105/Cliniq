from flask import Flask, jsonify, render_template
from config import Config
from app.extensions import db, login_manager
from app.models.appointment import Appointment, ensure_queue_columns
from app.models.clinic_status import ClinicStatus
from app.models.notification import Notification
from app.models.prescription import Prescription
from app.models.user import User
from app.routes.auth import auth
from app.routes.dashboard import dashboard
from app.routes.patient import patient


def ensure_demo_users():
    demo_users = (
        ("Admin Doctor", "doctor@cliniq.com", "123456", "doctor"),
        ("Front Desk", "receptionist@cliniq.com", "123456", "receptionist"),
    )
    users_created = False

    for name, email, password, role in demo_users:
        if User.query.filter_by(email=email).first() is None:
            user = User(name=name, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            users_created = True

    if users_created:
        db.session.commit()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(patient)

    @app.route("/")
    def home():
        from app.services.clinic_status_service import get_current_clinic_status

        return render_template(
            "home.html",
            clinic_status=get_current_clinic_status(),
        )

    @app.get("/health")
    def health():
        return jsonify(status="ok"), 200

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("500.html"), 500

    with app.app_context():
        db.create_all()
        ensure_queue_columns()
        from app.services.clinic_status_service import ensure_default_clinic_status

        ensure_default_clinic_status()
        ensure_demo_users()

    return app
