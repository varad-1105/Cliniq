from app import create_app
from app.extensions import db
from app.models.user import User

app = create_app()

with app.app_context():
    users = [
        {
            "name": "Admin Doctor",
            "email": "doctor@cliniq.com",
            "password": "123456",
            "role": "doctor",
        },
        {
            "name": "Front Desk",
            "email": "receptionist@cliniq.com",
            "password": "123456",
            "role": "receptionist",
        },
    ]

    for user_data in users:
        user = User.query.filter_by(email=user_data["email"]).first()

        if user is None:
            user = User(
                name=user_data["name"],
                email=user_data["email"],
                role=user_data["role"],
            )
            db.session.add(user)
        else:
            user.name = user_data["name"]
            user.role = user_data["role"]

        user.set_password(user_data["password"])

    db.session.commit()

    print("Demo users created successfully!")
