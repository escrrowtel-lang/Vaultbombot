import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))

# Files
USER_DATA_FILE   = os.path.join(BASE_DIR, "data", "users.json")
ADMIN_DATA_FILE  = os.path.join(BASE_DIR, "data", "admin.json")
PAYMENTS_FILE    = os.path.join(BASE_DIR, "data", "payments.json")
LOOKUP_DATA_FILE = os.path.join(BASE_DIR, "data", "lookups.json")

# Credits
DEFAULT_CREDITS  = 10
REFERRAL_CREDITS = 25
REFERRED_CREDITS = 10

# Bomber credit defaults
BOMBER_CREDITS_DEFAULT = {
    "api_bomb":    10,
    "custom_bomb": 5,
}
BOMBER_QUANTITY_DEFAULT = {
    "api_bomb":    1,
    "custom_bomb": 50,
}

# Lookup costs (credits)
LOOKUP_COSTS = {
    "phone_lookup":    5,
    "ip_lookup":       3,
    "email_lookup":    5,
    "username_lookup": 4,
    "address_lookup":  8,
    "plate_lookup":    6,
    "social_lookup":   5,
    "name_lookup":     4,
}

DEFAULT_CUSTOM_SMS_CREDITS  = 5
DEFAULT_DIRECT_BOMB_CREDITS = 3
DEFAULT_CUSTOM_SMS_QTY      = 1
DEFAULT_DIRECT_BOMB_QTY     = 1
