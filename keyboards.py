from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# ─────────────────────────── Main Menu ───────────────────────────

def main_menu_kb():
    return InlineKeyboardMarkup([
        # Row 1 — Primary action (full width, bold green feel)
        [InlineKeyboardButton("💣 BOMBER",              callback_data="menu_bomber")],
        # Row 2 — Credits actions (blue row)
        [
            InlineKeyboardButton("💳 Buy Credits",      callback_data="menu_buy"),
            InlineKeyboardButton("🎁 Redeem Code",      callback_data="menu_redeem"),
        ],
        # Row 3 — Profile & social (blue row)
        [
            InlineKeyboardButton("👤 My Profile",       callback_data="menu_profile"),
            InlineKeyboardButton("👥 Referral",         callback_data="menu_referral"),
        ],
        # Row 4 — History & support (olive/dark row)
        [
            InlineKeyboardButton("📜 History",          callback_data="menu_history"),
            InlineKeyboardButton("💬 Support",          callback_data="menu_support"),
        ],
    ])

def back_to_main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ])

def back_kb(target: str = "menu_main", label: str = "⬅️ Back"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=target)],
    ])

# ─────────────────────────── Lookups Menu ───────────────────────────

def lookups_menu_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Phone Lookup",    callback_data="lookup_phone"),
            InlineKeyboardButton("🌐 IP Lookup",       callback_data="lookup_ip"),
        ],
        [
            InlineKeyboardButton("📧 Email Lookup",    callback_data="lookup_email"),
            InlineKeyboardButton("🔎 Username Lookup", callback_data="lookup_username"),
        ],
        [
            InlineKeyboardButton("🏠 Address Lookup",  callback_data="lookup_address"),
            InlineKeyboardButton("🚘 Plate Lookup",    callback_data="lookup_plate"),
        ],
        [
            InlineKeyboardButton("📱 Social Lookup",   callback_data="lookup_social"),
            InlineKeyboardButton("👤 Name Lookup",     callback_data="lookup_name"),
        ],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ])

def lookup_confirm_kb(lookup_type: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm",   callback_data=f"lookup_confirm_{lookup_type}"),
            InlineKeyboardButton("❌ Cancel",    callback_data="menu_lookups"),
        ],
    ])

# ─────────────────────────── Buy Credits ───────────────────────────

def buy_credits_kb(packages: list):
    rows = []
    for pkg in packages:
        rows.append([InlineKeyboardButton(
            f"{'⭐' if pkg['label']=='Popular' else '💎' if pkg['label']=='Elite' else '📦'} "
            f"{pkg['label']} — {pkg['credits']} credits @ ₹{pkg['price']}",
            callback_data=f"buy_pkg_{pkg['id']}"
        )])
    rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)

def payment_flow_kb(pay_id: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I've Paid — Submit UTR & Screenshot", callback_data=f"pay_done_{pay_id}")],
        [InlineKeyboardButton("❌ Cancel Payment", callback_data=f"pay_cancel_{pay_id}")],
    ])

def payment_confirm_kb(pay_id: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{pay_id}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"admin_reject_{pay_id}"),
        ],
    ])

# ─────────────────────────── Admin Panel ───────────────────────────

def admin_panel_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 Payment Setup",   callback_data="admin_payment_setup"),
            InlineKeyboardButton("📦 Credit Packages", callback_data="admin_packages"),
        ],
        [
            InlineKeyboardButton("👥 Manage Users",    callback_data="admin_users"),
            InlineKeyboardButton("🎟️ Redeem Codes",    callback_data="admin_codes"),
        ],
        [
            InlineKeyboardButton("📊 Statistics",      callback_data="admin_stats"),
            InlineKeyboardButton("📋 Pending Payments",callback_data="admin_pending"),
        ],
        [
            InlineKeyboardButton("💣 Bomber Settings", callback_data="admin_bomber_settings"),
            InlineKeyboardButton("🔧 Maintenance",     callback_data="admin_maintenance"),
        ],
        [
            InlineKeyboardButton("👑 Manage Admins",   callback_data="admin_admins"),
        ],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ])

def admin_payment_setup_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Set UPI ID",         callback_data="admin_set_upi")],
        [InlineKeyboardButton("🖼️ Set QR Image",       callback_data="admin_set_qr")],
        [InlineKeyboardButton("💬 Set Payment Group",  callback_data="admin_set_group")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")],
    ])

def admin_users_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Find User",      callback_data="admin_find_user")],
        [InlineKeyboardButton("➕ Add Credits",    callback_data="admin_add_credits")],
        [InlineKeyboardButton("✏️ Set Credits",    callback_data="admin_set_credits")],
        [InlineKeyboardButton("🚫 Ban User",       callback_data="admin_ban_user")],
        [InlineKeyboardButton("✅ Unban User",     callback_data="admin_unban_user")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")],
    ])

def admin_codes_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Create Code",   callback_data="admin_create_code")],
        [InlineKeyboardButton("📋 List Codes",    callback_data="admin_list_codes")],
        [InlineKeyboardButton("🗑️ Delete Code",   callback_data="admin_delete_code")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")],
    ])

def cancel_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")],
    ])
