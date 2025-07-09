from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, user_dict):
        self.id = str(user_dict["_id"])  # Required for Flask-Login
        self.username = user_dict.get("username")
        self.email = user_dict.get("email")
        self.password = user_dict.get("password")

        # You can add more attributes as needed
        self.mongo_user = user_dict  # keep full original dict if needed