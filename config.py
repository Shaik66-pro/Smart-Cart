import os
from dotenv import load_dotenv

load_dotenv()

# Application Secret Key
SECRET_KEY = os.environ.get("SECRET_KEY", "smartcart_super_secret_session_key_2026")

# MySQL Database Configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "S@m123")
DB_NAME = os.environ.get("DB_NAME", "smartcart")
DB_PORT = int(os.environ.get("DB_PORT", 3306))

# Mail Settings
MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() in ("true", "1")
MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "sameernawab66@gmail.com")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "mhny obil rhir pcbx")

# Upload Folders
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "static/uploads/product_images")
ADMIN_UPLOAD_FOLDER = os.environ.get("ADMIN_UPLOAD_FOLDER", "static/uploads/admin_profile")

# Razorpay credentials
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_TOPt85iWSRKCAh")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "3D5Hf0kDymTetX6DwCqkDKzq")
