import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")  # service_role key (not anon)

# Files
USER_DATA_FILE = os.path.join(BASE_DIR, "data", "users.json")
ADMIN_DATA_FILE = os.path.join(BASE_DIR, "data", "admin.json")
PAYMENTS_FILE = os.path.join(BASE_DIR, "data", "payments.json")
LOOKUP_DATA_FILE = os.path.join(BASE_DIR, "data", "lookups.json")

# Credits
DEFAULT_CREDITS = 10          # Credits on /start
REFERRAL_CREDITS = 25         # Per referral
REFERRED_CREDITS = 10         # Bonus for being referred

# Bomber credit defaults (admin can override via admin_settings table)
BOMBER_CREDITS_DEFAULT = {
    "api_bomb":    10,   # credits per API bomb run
    "custom_bomb": 5,    # credits per custom message bomb run
}
BOMBER_QUANTITY_DEFAULT = {
    "api_bomb":    1,    # how many full API cycles per run
    "custom_bomb": 50,   # how many custom messages per run
}

# Lookup costs (credits)
LOOKUP_COSTS = {
    "phone_lookup": 5,
    "ip_lookup": 3,
    "email_lookup": 5,
    "username_lookup": 4,
    "address_lookup": 8,
    "plate_lookup": 6,
    "social_lookup": 5,
    "name_lookup": 4,
}

# Bomber defaults (admin can override via admin panel)
DEFAULT_CUSTOM_SMS_CREDITS = 5    # credits per custom SMS bomb use
DEFAULT_DIRECT_BOMB_CREDITS = 3   # credits per direct API bomb use
DEFAULT_CUSTOM_SMS_QTY = 1        # default firebase sends
DEFAULT_DIRECT_BOMB_QTY = 1       # how many API cycles (1 = all 1000+ APIs once)
