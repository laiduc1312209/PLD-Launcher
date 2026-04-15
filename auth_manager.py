"""
PLD Launcher — Authentication & Session Manager (MongoDB Edition)
Handles secure authentication using MongoDB Atlas and Bcrypt.
"""
import os
import json
import hashlib
import secrets
from pymongo import MongoClient
from config import MONGODB_URI, DB_NAME

SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_session.json")

class AuthManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuthManager, cls).__new__(cls)
            cls._instance.session = cls._instance._load_session()
            cls._instance.client = None
            cls._instance.db = None
            cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        """Initializes MongoDB connection."""
        if MONGODB_URI == "REPLACE_WITH_YOUR_MONGODB_URI":
            print("MongoDB URI not configured.")
            return

        try:
            self.client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            self.db = self.client[DB_NAME]
            # Verify connection
            self.client.server_info()
        except Exception as e:
            print(f"MongoDB Connection Error: {e}")
            self.client = None
            self.db = None

    def _load_session(self):
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return None

    def _save_session(self, session_data):
        self.session = session_data
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)

    def is_logged_in(self) -> bool:
        return self.session is not None

    def _hash_password(self, password, salt=None):
        """Hashes password using PBKDF2 with SHA256."""
        if salt is None:
            salt = secrets.token_hex(16)
        
        # iterations=100000 is robust enough
        phash = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt.encode('utf-8'), 
            100000
        ).hex()
        return f"pbkdf2_sha256$100000${salt}${phash}"

    def _verify_password(self, password, stored_value):
        """Verifies a password against the stored string format."""
        try:
            if not stored_value or "$" not in str(stored_value):
                return False
            
            # For backward compatibility or if we stored as bytes
            if isinstance(stored_value, bytes):
                stored_value = stored_value.decode('utf-8')

            parts = stored_value.split('$')
            if len(parts) != 4:
                return False
            
            _, iterations, salt, _ = parts
            return self._hash_password(password, salt) == stored_value
        except Exception:
            return False

    def login(self, email, password):
        """Authenticates user via MongoDB."""
        if self.db is None:
            return False, "Database chưa được cấu hình hoặc lỗi kết nối. Vui lòng kiểm tra config.py."

        try:
            users = self.db.users
            user = users.find_one({"email": email.lower()})

            if not user:
                return False, "Email không tồn tại."

            # Check password
            stored_val = user.get("password_hash")
            if self._verify_password(password, stored_val):
                session_data = {
                    "email": user["email"],
                    "id": str(user["_id"]),
                    "registered_at": user.get("created_at", "")
                }
                self._save_session(session_data)
                return True, "Đăng nhập thành công!"
            else:
                return False, "Mật khẩu không chính xác."
        except Exception as e:
            return False, f"Lỗi đăng nhập: {str(e)}"

    def register(self, email, password):
        """Registers a new user in MongoDB with hashed password."""
        if self.db is None:
            return False, "Database chưa được cấu hình hoặc lỗi kết nối. Vui lòng kiểm tra config.py."

        try:
            users = self.db.users
            email_lower = email.lower()
            
            # Check if user already exists
            if users.find_one({"email": email_lower}):
                return False, "Email đã được đăng ký."

            # Create secure hash
            pw_hash = self._hash_password(password)

            import datetime
            new_user = {
                "email": email_lower,
                "password_hash": pw_hash,
                "created_at": datetime.datetime.utcnow().isoformat()
            }
            
            res = users.insert_one(new_user)
            if res.inserted_id:
                return True, "Đăng ký thành công! Quay lại Đăng nhập ngay."
            return False, "Đăng ký thất bại."
        except Exception as e:
            return False, f"Lỗi đăng ký: {str(e)}"

    def logout(self):
        """Clears session and wipes local settings cache."""
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        
        # Clear local settings cache to prevent library leak
        from settings import SETTINGS_FILE
        if os.path.exists(SETTINGS_FILE):
            os.remove(SETTINGS_FILE)

        self.session = None

    def get_cloud_library(self):
        """Fetches the game library array from MongoDB for the current user."""
        if self.db is None or self.session is None:
            return None
        
        try:
            from bson.objectid import ObjectId
            user_id = self.session.get("id")
            user = self.db.users.find_one({"_id": ObjectId(user_id)})
            return user.get("library") if user else None
        except Exception as e:
            print(f"Error fetching cloud library: {e}")
            return None

    def update_cloud_library(self, library_dict):
        """Pushes the entire games dictionary to MongoDB as an array for the current user."""
        if self.db is None or self.session is None:
            return False, "Not connected or not logged in."

        try:
            from bson.objectid import ObjectId
            user_id = self.session.get("id")
            
            # Convert dictionary {gid: data} to list of objects for MongoDB storage
            library_list = []
            for gid, gdata in library_dict.items():
                gdata["gid"] = gid # Ensure gid is inside the object
                library_list.append(gdata)

            res = self.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"library": library_list}}
            )
            return True, "Cloud Sync thành công!"
        except Exception as e:
            return False, f"Cloud Sync lỗi: {str(e)}"

    def setup_buckets(self):
        """No longer used for MongoDB."""
        pass
