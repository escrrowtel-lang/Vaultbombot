import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from data_manager import get_user, deduct_credits, load_admin_data, set_admin_setting, is_admin
from bomber_service import run_api_bomb, run_custom_bomb
from config import BOMBER_CREDITS_DEFAULT, BOMBER_QUANTITY_DEFAULT

logger = logging.getLogger(__name__)

async def safe_edit(query, text, reply_markup=None, parse_mode=ParseMode.HTML):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        try:
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"safe_edit: {e}")

# ─────────────────────────── Helpers ───────────────────────────

async def get_bomber_settings() -> dict:
    """Load bomber credits/quantity from admin_settings, fall back to defaults."""
    admin = await load_admin_data()
    return {
        "api_bomb_credits":    admin.get("api_bomb_credits",    BOMBER_CREDITS_DEFAULT["api_bomb"]),
        "custom_bomb_credits": admin.get("custom_bomb_credits", BOMBER_CREDITS_DEFAULT["custom_bomb"]),
        "api_bomb_cycles":     admin.get("api_bomb_cycles",     BOMBER_QUANTITY_DEFAULT["api_bomb"]),
        "custom_bomb_count":   admin.get("custom_bomb_count",   BOMBER_QUANTITY_DEFAULT["custom_bomb"]),
        "fast2sms_key":        admin.get("fast2sms_key",        None),
    }

def back_kb(target="menu_main", label="🏠 Main Menu"):
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=target)]])

# ─────────────────────────── Bomber Menu ───────────────────────────

async def menu_bomber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    u = await get_user(user.id)
    s = await get_bomber_settings()

    text = (
        f"💣 <b>BOMBER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💳 Your Credits: <code>{u['credits']}</code>\n\n"
        f"<b>Choose Bomb Type:</b>\n\n"
        f"⚡ <b>API Bomb</b>\n"
        f"  Hits <b>{len(__import__('bomber_service').ULTIMATEAPIS)}+ OTP endpoints</b> across 25+ Indian apps.\n"
        f"  Cycles: <code>{s['api_bomb_cycles']}</code> | Cost: <code>{s['api_bomb_credits']}</code> credits\n\n"
        f"✉️ <b>Custom Message Bomb</b>\n"
        f"  Sends your custom message <b>{s['custom_bomb_count']}x</b> via SMS gateway.\n"
        f"  Cost: <code>{s['custom_bomb_credits']}</code> credits"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ API Bomb",             callback_data="bomber_api_start")],
        [InlineKeyboardButton("✉️ Custom Message Bomb",  callback_data="bomber_custom_start")],
        [InlineKeyboardButton("🏠 Main Menu",            callback_data="menu_main")],
    ])
    await safe_edit(query, text, kb)

# ─────────────────────────── API Bomb Flow ───────────────────────────

async def bomber_api_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    u = await get_user(user.id)
    s = await get_bomber_settings()
    cost = s["api_bomb_credits"]

    if u["credits"] < cost:
        text = (
            f"❌ <b>Insufficient Credits</b>\n\n"
            f"API Bomb costs <code>{cost}</code> credits.\n"
            f"Your balance: <code>{u['credits']}</code>\n\n"
            f"<i>Buy more credits to continue.</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Buy Credits",  callback_data="menu_buy")],
            [InlineKeyboardButton("🏠 Main Menu",    callback_data="menu_main")],
        ])
        await safe_edit(query, text, kb)
        return

    context.user_data["bomber_mode"] = "api"
    context.user_data["awaiting"]    = "bomber_phone"

    text = (
        f"⚡ <b>API BOMB</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💳 Cost: <code>{cost}</code> credits\n"
        f"🔁 Cycles: <code>{s['api_bomb_cycles']}</code>\n\n"
        f"📱 Enter the target phone number (10 digits):"
    )
    await safe_edit(query, text, back_kb("menu_bomber", "⬅️ Back"))

async def bomber_custom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    u = await get_user(user.id)
    s = await get_bomber_settings()
    cost = s["custom_bomb_credits"]

    if u["credits"] < cost:
        text = (
            f"❌ <b>Insufficient Credits</b>\n\n"
            f"Custom Bomb costs <code>{cost}</code> credits.\n"
            f"Your balance: <code>{u['credits']}</code>\n\n"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Buy Credits", callback_data="menu_buy")],
            [InlineKeyboardButton("🏠 Main Menu",   callback_data="menu_main")],
        ])
        await safe_edit(query, text, kb)
        return

    context.user_data["bomber_mode"] = "custom"
    context.user_data["awaiting"]    = "bomber_phone"

    text = (
        f"✉️ <b>CUSTOM MESSAGE BOMB</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💳 Cost: <code>{cost}</code> credits\n"
        f"📨 Messages: <code>{s['custom_bomb_count']}</code>\n\n"
        f"📱 Enter the target phone number (10 digits):"
    )
    await safe_edit(query, text, back_kb("menu_bomber", "⬅️ Back"))

# ─────────────────────────── Text Input Handler ───────────────────────────

async def handle_bomber_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 1: receive phone number."""
    phone = update.message.text.strip()
    digits = ''.join(filter(str.isdigit, phone))

    if len(digits) < 10:
        await update.message.reply_text(
            "❌ Invalid number. Enter 10-digit mobile number.",
            parse_mode=ParseMode.HTML,
        )
        return

    context.user_data["bomber_phone"] = digits

    if context.user_data.get("bomber_mode") == "custom":
        context.user_data["awaiting"] = "bomber_message"
        await update.message.reply_text(
            f"✅ Target: <code>{digits}</code>\n\n"
            f"✉️ Now enter the <b>custom message</b> to send:",
            parse_mode=ParseMode.HTML,
        )
    else:
        # API mode — go straight to confirm
        context.user_data["awaiting"] = "bomber_confirm"
        s = await get_bomber_settings()
        await update.message.reply_text(
            f"🎯 <b>Confirm API Bomb</b>\n\n"
            f"📱 Target: <code>{digits}</code>\n"
            f"🔁 Cycles: <code>{s['api_bomb_cycles']}</code>\n"
            f"💳 Cost: <code>{s['api_bomb_credits']}</code> credits\n\n",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 LAUNCH",     callback_data="bomber_launch_api")],
                [InlineKeyboardButton("❌ Cancel",     callback_data="menu_bomber")],
            ])
        )

async def handle_bomber_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 2 (custom only): receive message text."""
    msg = update.message.text.strip()
    if not msg:
        await update.message.reply_text("❌ Message cannot be empty.")
        return

    context.user_data["bomber_message"] = msg
    context.user_data["awaiting"] = "bomber_confirm"

    phone = context.user_data.get("bomber_phone", "")
    s = await get_bomber_settings()

    await update.message.reply_text(
        f"🎯 <b>Confirm Custom Bomb</b>\n\n"
        f"📱 Target: <code>{phone}</code>\n"
        f"✉️ Message: <i>{msg[:80]}</i>\n"
        f"📨 Count: <code>{s['custom_bomb_count']}</code>\n"
        f"💳 Cost: <code>{s['custom_bomb_credits']}</code> credits\n\n",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 LAUNCH",  callback_data="bomber_launch_custom")],
            [InlineKeyboardButton("❌ Cancel",  callback_data="menu_bomber")],
        ])
    )

# ─────────────────────────── Launch ───────────────────────────

async def bomber_launch_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Launching...")

    user = query.from_user
    phone = context.user_data.pop("bomber_phone", None)
    context.user_data.pop("awaiting", None)
    context.user_data.pop("bomber_mode", None)

    if not phone:
        await safe_edit(query, "⚠️ Session expired. Start again.", back_kb("menu_bomber", "💣 Bomber"))
        return

    s = await get_bomber_settings()
    cost = s["api_bomb_credits"]
    cycles = s["api_bomb_cycles"]

    success = await deduct_credits(user.id, cost, f"API Bomb → {phone}")
    if not success:
        await safe_edit(query, "❌ Insufficient credits.", back_kb("menu_bomber", "💣 Bomber"))
        return

    await safe_edit(query, f"⚡ <b>Bombing...</b>\n\n📱 Target: <code>{phone}</code>\n🔁 Cycles: <code>{cycles}</code>\n\n<i>Please wait...</i>")

    result = await run_api_bomb(phone, cycles=cycles)
    u = await __import__('data_manager').get_user(user.id)

    await safe_edit(query,
        f"✅ <b>API Bomb Complete!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📱 Target: <code>{result['phone']}</code>\n"
        f"📊 Total Requests: <code>{result['total']}</code>\n"
        f"✅ Successful: <code>{result['success']}</code>\n"
        f"❌ Failed: <code>{result['failed']}</code>\n\n"
        f"💳 Credits remaining: <code>{u['credits']}</code>",
        back_kb("menu_bomber", "💣 Bomb Again")
    )

async def bomber_launch_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Launching...")

    user = query.from_user
    phone   = context.user_data.pop("bomber_phone", None)
    message = context.user_data.pop("bomber_message", None)
    context.user_data.pop("awaiting", None)
    context.user_data.pop("bomber_mode", None)

    if not phone or not message:
        await safe_edit(query, "⚠️ Session expired. Start again.", back_kb("menu_bomber", "💣 Bomber"))
        return

    s = await get_bomber_settings()
    cost  = s["custom_bomb_credits"]
    count = s["custom_bomb_count"]
    key   = s.get("fast2sms_key")

    success = await deduct_credits(user.id, cost, f"Custom Bomb → {phone}")
    if not success:
        await safe_edit(query, "❌ Insufficient credits.", back_kb("menu_bomber", "💣 Bomber"))
        return

    await safe_edit(query, f"✉️ <b>Sending...</b>\n\n📱 Target: <code>{phone}</code>\n📨 Messages: <code>{count}</code>\n\n<i>Please wait...</i>")

    result = await run_custom_bomb(phone, message, count, api_key=key)
    u = await __import__('data_manager').get_user(user.id)

    note = f"\n\n⚠️ <i>{result['note']}</i>" if result.get("note") else ""

    await safe_edit(query,
        f"✅ <b>Custom Bomb Complete!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📱 Target: <code>{result['phone']}</code>\n"
        f"📨 Sent: <code>{result['success']}</code>\n"
        f"❌ Failed: <code>{result['failed']}</code>"
        f"{note}\n\n"
        f"💳 Credits remaining: <code>{u['credits']}</code>",
        back_kb("menu_bomber", "💣 Bomb Again")
    )

# ─────────────────────────── Admin Bomber Settings ───────────────────────────

async def admin_bomber_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()

    s = await get_bomber_settings()
    text = (
        f"💣 <b>BOMBER SETTINGS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ <b>API Bomb</b>\n"
        f"  Credits per run: <code>{s['api_bomb_credits']}</code>\n"
        f"  Cycles per run:  <code>{s['api_bomb_cycles']}</code>\n\n"
        f"✉️ <b>Custom Bomb</b>\n"
        f"  Credits per run: <code>{s['custom_bomb_credits']}</code>\n"
        f"  Messages per run:<code>{s['custom_bomb_count']}</code>\n\n"
        f"🔑 SMS Key (fast2sms): <code>{'Set ✅' if s['fast2sms_key'] else 'Not set ❌'}</code>\n\n"
        f"<i>Select what to change:</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ API Credits",         callback_data="admin_set_api_bomb_credits")],
        [InlineKeyboardButton("🔁 API Cycles",          callback_data="admin_set_api_bomb_cycles")],
        [InlineKeyboardButton("✉️ Custom Credits",      callback_data="admin_set_custom_bomb_credits")],
        [InlineKeyboardButton("📨 Custom Count",        callback_data="admin_set_custom_bomb_count")],
        [InlineKeyboardButton("🔑 Set SMS API Key",     callback_data="admin_set_fast2sms_key")],
        [InlineKeyboardButton("⬅️ Back",                callback_data="admin_panel")],
    ])
    await safe_edit(query, text, kb)

async def admin_bomber_set_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()

    field_map = {
        "admin_set_api_bomb_credits":    ("admin_awaiting", "bomber_api_credits",    "⚡ API Bomb credits per run (number):"),
        "admin_set_api_bomb_cycles":     ("admin_awaiting", "bomber_api_cycles",     "🔁 API Bomb cycles per run (number):"),
        "admin_set_custom_bomb_credits": ("admin_awaiting", "bomber_custom_credits", "✉️ Custom Bomb credits per run (number):"),
        "admin_set_custom_bomb_count":   ("admin_awaiting", "bomber_custom_count",   "📨 Custom Bomb message count per run (number):"),
        "admin_set_fast2sms_key":        ("admin_awaiting", "bomber_sms_key",        "🔑 Enter fast2sms API key:"),
    }
    if query.data not in field_map:
        return

    key, awaiting_val, prompt = field_map[query.data]
    context.user_data[key] = awaiting_val
    await safe_edit(query, f"<b>{prompt}</b>\n\nType the value now:",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_bomber_settings")]]))

async def handle_admin_bomber_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if it handled the input, False otherwise."""
    if not await is_admin(update.effective_user.id):
        return False

    awaiting = context.user_data.get("admin_awaiting", "")
    val = update.message.text.strip()

    field_map = {
        "bomber_api_credits":    ("api_bomb_credits",    True),
        "bomber_api_cycles":     ("api_bomb_cycles",     True),
        "bomber_custom_credits": ("custom_bomb_credits", True),
        "bomber_custom_count":   ("custom_bomb_count",   True),
        "bomber_sms_key":        ("fast2sms_key",        False),
    }

    if awaiting not in field_map:
        return False

    db_key, is_int = field_map[awaiting]
    context.user_data.pop("admin_awaiting", None)

    if is_int:
        try:
            val = int(val)
        except ValueError:
            await update.message.reply_text("❌ Must be a number.")
            return True

    await set_admin_setting(db_key, val)
    await update.message.reply_text(
        f"✅ <code>{db_key}</code> set to <code>{val}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_bomber_settings")]])
    )
    return True
