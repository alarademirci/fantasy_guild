from flask_login import UserMixin
class User(UserMixin):
    def __init__(self, id, email, password_hash, role):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.role = role

    def is_adventurer(self):
        return self.role == "adventurer"

    def is_guild_master(self):
        return self.role == "guild_master"

    def is_guild_council(self):
        return self.role == "guild_council"