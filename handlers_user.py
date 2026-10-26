import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from data_manager import (
    get_user, add_credits, deduct_credits, apply_referral,
    use_redeem_code, add_lookup_history, get_all_users, load_admin_data,
    get_user_history
)
from keyboards import (
    main_menu_kb, lookups_menu_kb, back_to_main_kb, back_kb,
    lookup_confirm_kb
)
from config import LOOKUP_COSTS, OWNER_ID

logger = logging.getLogger(__name__)

# ─────────────────────────── Helpers ───────────────────────────

async def safe_edit(query, text, reply_markup=None, parse_mode=ParseMode.HTML):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        try:
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"safe_edit failed: {e}")

def _credits_bar(credits: int, max_credits: int = 500) -> str:
    pct = min(credits / max_credits, 1.0)
    filled = int(pct * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {credits}"

# ─────────────────────────── /start ───────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    # Register / get user
    u = await get_user(user.id, user.username or "", user.full_name)

    # Handle referral
    referral_msg = ""
    if args and args[0].startswith("ref_"):
        code = args[0][4:]
        success = await apply_referral(user.id, code)
        if success:
            referral_msg = "\n\n🎁 <b>Referral applied!</b> Bonus credits added!"

    text = (
        f"🛡️ <b>WELCOME TO VAULT BOT ⚡</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👋 Hello, <b>{user.full_name}</b>!\n\n"
        f"🚀 <b>Powerful • Fast • Reliable</b>\n"
        f"🔍 Quick & Easy Lookups\n"
        f"💳 Your Credits: <code>{u['credits']}</code>\n"
        f"👥 Refer & Earn Rewards\n"
        f"🎟️ Redeem Codes & More\n"
        f"{referral_msg}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ <i>Select an option below to get started.</i>"
    )

    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)
    else:
        await safe_edit(update.callback_query, text, main_menu_kb())

# ─────────────────────────── Main Menu Callback ───────────────────────────

async def menu_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    u = await get_user(user.id, user.username or "", user.full_name)

    text = (
        f"🛡️ <b>VAULT BOT — Main Menu</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👋 <b>{user.full_name}</b>\n"
        f"💳 Credits: <code>{u['credits']}</code>\n"
        f"🔍 Lookups done: <code>{u['lookups_done']}</code>\n\n"
        f"✨ <i>Choose an option below.</i>"
    )
    await safe_edit(query, text, main_menu_kb())

# ─────────────────────────── Profile ───────────────────────────

async def menu_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    u = await get_user(user.id)

    joined = u.get("joined_at", "N/A")[:10]
    ref_count = len(u.get("referrals", []))

    text = (
        f"👤 <b>MY PROFILE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 User ID: <code>{user.id}</code>\n"
        f"📛 Name: <b>{user.full_name}</b>\n"
        f"🔗 Username: @{user.username or 'N/A'}\n\n"
        f"💳 <b>Credits:</b> <code>{u['credits']}</code>\n"
        f"   {_credits_bar(u['credits'])}\n\n"
        f"📊 <b>Stats</b>\n"
        f"  • Total Earned: <code>{u.get('total_earned', 0)}</code>\n"
        f"  • Total Spent:  <code>{u.get('total_spent', 0)}</code>\n"
        f"  • Lookups Done: <code>{u.get('lookups_done', 0)}</code>\n"
        f"  • Referrals:    <code>{ref_count}</code>\n\n"
        f"📅 Joined: <code>{joined}</code>\n"
        f"🎫 Referral Code: <code>{u.get('referral_code', 'N/A')}</code>"
    )
    await safe_edit(query, text, back_to_main_kb())

# ─────────────────────────── Lookups ───────────────────────────

LOOKUP_LABELS = {
    "phone":    ("📱 Phone Lookup",    "Enter the 10-digit phone number:"),
    "ip":       ("🌐 IP Lookup",       "Enter the IP address:"),
    "email":    ("📧 Email Lookup",    "Enter the email address:"),
    "username": ("🔎 Username Lookup", "Enter the username (without @):"),
    "address":  ("🏠 Address Lookup",  "Enter the full address:"),
    "plate":    ("🚘 Plate Lookup",    "Enter the vehicle plate number:"),
    "social":   ("📱 Social Lookup",   "Enter the profile URL or username:"),
    "name":     ("👤 Name Lookup",     "Enter the full name:"),
}

async def menu_lookups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    u = await get_user(user.id)

    # Build cost table
    cost_lines = "\n".join(
        f"  • {LOOKUP_LABELS[k][0]}: <b>{v} credits</b>"
        for k, v in {
            "phone": LOOKUP_COSTS["phone_lookup"],
            "ip": LOOKUP_COSTS["ip_lookup"],
            "email": LOOKUP_COSTS["email_lookup"],
            "username": LOOKUP_COSTS["username_lookup"],
        }.items()
    )

    text = (
        f"🔍 <b>LOOKUPS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💳 Your credits: <code>{u['credits']}</code>\n\n"
        f"<b>Lookup Costs:</b>\n{cost_lines}\n\n"
        f"<i>Select a lookup type below:</i>"
    )
    await safe_edit(query, text, lookups_menu_kb())

async def handle_lookup_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called when user picks a lookup type."""
    query = update.callback_query
    await query.answer()
    lookup_type = query.data.replace("lookup_", "")

    if lookup_type not in LOOKUP_LABELS:
        return

    label, prompt = LOOKUP_LABELS[lookup_type]
    cost_key = f"{lookup_type}_lookup"
    cost = LOOKUP_COSTS.get(cost_key, 5)

    user = query.from_user
    u = await get_user(user.id)

    if u["credits"] < cost:
        text = (
            f"❌ <b>Insufficient Credits</b>\n\n"
            f"You need <code>{cost}</code> credits for {label}.\n"
            f"Your balance: <code>{u['credits']}</code>\n\n"
            f"<i>Buy more credits to continue.</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Buy Credits", callback_data="menu_buy")],
            [InlineKeyboardButton("🏠 Main Menu",   callback_data="menu_main")],
        ])
        await safe_edit(query, text, kb)
        return

    context.user_data["pending_lookup"] = lookup_type
    text = (
        f"🔍 <b>{label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💳 Cost: <code>{cost}</code> credits\n"
        f"Your balance: <code>{u['credits']}</code>\n\n"
        f"📝 {prompt}\n\n"
        f"<i>Type your query in the chat below:</i>"
    )
    await safe_edit(query, text, back_kb("menu_lookups", "⬅️ Back to Lookups"))

async def handle_lookup_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives text input for a pending lookup."""
    if "pending_lookup" not in context.user_data:
        return

    lookup_type = context.user_data.pop("pending_lookup")
    query_text = update.message.text.strip()
    user = update.effective_user
    u = await get_user(user.id)

    cost_key = f"{lookup_type}_lookup"
    cost = LOOKUP_COSTS.get(cost_key, 5)
    label = LOOKUP_LABELS[lookup_type][0]

    if u["credits"] < cost:
        await update.message.reply_text(
            f"❌ Not enough credits ({u['credits']}/{cost}). Buy more with /buy.",
            parse_mode=ParseMode.HTML
        )
        return

    # Store query for confirmation
    context.user_data["lookup_confirm"] = {
        "type": lookup_type,
        "query": query_text,
        "cost": cost,
    }

    text = (
        f"🔍 <b>Confirm Lookup</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Type: <b>{label}</b>\n"
        f"Query: <code>{query_text}</code>\n"
        f"Cost: <code>{cost}</code> credits\n"
        f"Balance after: <code>{u['credits'] - cost}</code>\n\n"
        f"<i>Confirm to proceed?</i>"
    )
    await update.message.reply_text(text, reply_markup=lookup_confirm_kb(lookup_type), parse_mode=ParseMode.HTML)

async def handle_lookup_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Processing...")

    confirm_data = context.user_data.pop("lookup_confirm", None)
    if not confirm_data:
        await safe_edit(query, "⚠️ Session expired. Please start again.", back_to_main_kb())
        return

    user = query.from_user
    lookup_type = confirm_data["type"]
    query_text = confirm_data["query"]
    cost = confirm_data["cost"]
    label = LOOKUP_LABELS[lookup_type][0]

    # Deduct credits
    success = await deduct_credits(user.id, cost, f"{label}: {query_text}")
    if not success:
        await safe_edit(query, "❌ Insufficient credits. Please buy more.", back_to_main_kb())
        return

    # ── LOOKUP EXECUTION ──
    # This is the stub where you plug in real lookup APIs.
    # Replace the block below with actual API calls per lookup_type.
    result = await _execute_lookup(lookup_type, query_text)

    await add_lookup_history(user.id, lookup_type, query_text, result[:100])

    u = await get_user(user.id)
    text = (
        f"✅ <b>{label} Result</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔎 Query: <code>{query_text}</code>\n\n"
        f"{result}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 Credits remaining: <code>{u['credits']}</code>"
    )
    await safe_edit(query, text, back_kb("menu_lookups", "🔍 More Lookups"))

async def _execute_lookup(lookup_type: str, query: str) -> str:
    """
    Plug your real lookup APIs here per type.
    Returns formatted HTML result string.
    """
    # Placeholder — replace each block with real API integration
    stubs = {
        "phone":    f"📱 <b>Phone:</b> <code>{query}</code>\n🏙️ Carrier: <i>Demo Carrier</i>\n📍 Region: <i>Demo State</i>\n⚠️ <i>Connect a real lookup API to get live results.</i>",
        "ip":       f"🌐 <b>IP:</b> <code>{query}</code>\n🌍 Country: <i>Demo Country</i>\n🏙️ City: <i>Demo City</i>\n🔧 ISP: <i>Demo ISP</i>\n⚠️ <i>Connect a real lookup API to get live results.</i>",
        "email":    f"📧 <b>Email:</b> <code>{query}</code>\n✅ Valid: <i>Yes</i>\n🏢 Domain: <i>{query.split('@')[-1] if '@' in query else 'N/A'}</i>\n⚠️ <i>Connect a real lookup API to get live results.</i>",
        "username": f"🔎 <b>Username:</b> <code>{query}</code>\n📱 Platforms found: <i>Checking...</i>\n⚠️ <i>Connect a real lookup API to get live results.</i>",
        "address":  f"🏠 <b>Address:</b> <code>{query}</code>\n📍 Geocode: <i>Demo Lat/Long</i>\n⚠️ <i>Connect a real lookup API to get live results.</i>",
        "plate":    f"🚘 <b>Plate:</b> <code>{query}</code>\n🚗 Vehicle: <i>Demo Vehicle</i>\n⚠️ <i>Connect a real lookup API to get live results.</i>",
        "social":   f"📱 <b>Profile:</b> <code>{query}</code>\n👤 Name: <i>Demo Name</i>\n⚠️ <i>Connect a real lookup API to get live results.</i>",
        "name":     f"👤 <b>Name:</b> <code>{query}</code>\n🔎 Records: <i>Demo Records</i>\n⚠️ <i>Connect a real lookup API to get live results.</i>",
    }
    return stubs.get(lookup_type, "⚠️ Lookup type not found.")

# ─────────────────────────── Referral ───────────────────────────

async def menu_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    u = await get_user(user.id)

    from config import REFERRAL_CREDITS, REFERRED_CREDITS
    bot_info = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{u['referral_code']}"
    ref_count = len(u.get("referrals", []))

    text = (
        f"👥 <b>REFERRAL PROGRAM</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎁 <b>Earn {REFERRAL_CREDITS} credits</b> for every friend you refer!\n"
        f"🤝 Your friend gets <b>{REFERRED_CREDITS} bonus credits</b> too!\n\n"
        f"🔗 <b>Your Referral Link:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"📊 Total Referrals: <code>{ref_count}</code>\n"
        f"💳 Credits Earned from Referrals: <code>{ref_count * REFERRAL_CREDITS}</code>"
    )
    await safe_edit(query, text, back_to_main_kb())

# ─────────────────────────── History ───────────────────────────

async def menu_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    history = await get_user_history(user.id, limit=15)
    if not history:
        lines = "<i>No history yet. Run a lookup to get started!</i>"
    else:
        lines = ""
        for h in history:
            t = h.get("created_at", "")[:16].replace("T", " ")
            htype = h.get("type", "")
            icon = "➕" if htype == "credit" else ("➖" if htype == "debit" else "🔍")
            sign = "+" if htype == "credit" else "-"
            lines += f"{icon} <b>{h.get('reason','')[:50]}</b> — <code>{sign}{h.get('amount',0)}</code> — <i>{t}</i>\n"

    text = (
        f"📜 <b>HISTORY</b> (last 15)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{lines}"
    )
    await safe_edit(query, text, back_to_main_kb())

# ─────────────────────────── Redeem Code ───────────────────────────

async def menu_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "redeem_code"
    text = (
        f"🎟️ <b>REDEEM CODE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Enter your redeem code below:\n\n"
        f"<i>Type the code in the chat.</i>"
    )
    await safe_edit(query, text, back_to_main_kb())

async def handle_redeem_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    user = update.effective_user
    credits = await use_redeem_code(code)
    if credits is None:
        await update.message.reply_text(
            f"❌ <b>Invalid or expired code:</b> <code>{code}</code>",
            parse_mode=ParseMode.HTML, reply_markup=back_to_main_kb()
        )
    else:
        await add_credits(user.id, credits, f"Redeem code: {code}")
        u = await get_user(user.id)
        await update.message.reply_text(
            f"✅ <b>Code Redeemed!</b>\n\n"
            f"🎁 +<code>{credits}</code> credits added!\n"
            f"💳 New balance: <code>{u['credits']}</code>",
            parse_mode=ParseMode.HTML, reply_markup=back_to_main_kb()
        )

# ─────────────────────────── Support ───────────────────────────

async def menu_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        f"💬 <b>CONTACT SUPPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Need help? Contact our support team:\n\n"
        f"📩 Message the admin directly.\n"
        f"⏱️ Response time: Usually within 24h.\n\n"
        f"<i>Use the button below to message admin.</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Message Admin", url=f"https://t.me/{(await context.bot.get_me()).username}")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ])
    await safe_edit(query, text, kb)
