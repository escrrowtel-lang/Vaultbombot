import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from data_manager import (
    get_user, deduct_credits, load_admin_data, set_admin_setting, is_admin,
    list_all_firebase, add_firebase, remove_firebase,
)
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
        "api_bomb_credits":             admin.get("api_bomb_credits",             BOMBER_CREDITS_DEFAULT["api_bomb"]),
        "custom_bomb_credits":          admin.get("custom_bomb_credits",          BOMBER_CREDITS_DEFAULT["custom_bomb"]),
        "custom_bomb_credits_per_1000": admin.get("custom_bomb_credits_per_1000", 5),
        "api_bomb_cycles":              admin.get("api_bomb_cycles",              BOMBER_QUANTITY_DEFAULT["api_bomb"]),
        "custom_bomb_count":            admin.get("custom_bomb_count",            BOMBER_QUANTITY_DEFAULT["custom_bomb"]),
        "firebase_list":                admin.get("firebase_list",                []),
    }

def calc_custom_cost(count: int, credits_per_1000: int) -> int:
    import math
    return max(1, math.ceil(count / 1000) * credits_per_1000)

def back_kb(target="menu_main", label="🏠 Main Menu"):
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=target)]])

# ─────────────────────────── Bomber Menu ───────────────────────────

async def menu_bomber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    u = await get_user(user.id)
    s = await get_bomber_settings()

    admin = await load_admin_data()
    ranges = admin.get("api_bomb_quantity_ranges", [
        {"id": "range_1", "label": "0–50",    "cycles": 50,   "credits": 3},
        {"id": "range_2", "label": "100–200",  "cycles": 200,  "credits": 8},
        {"id": "range_3", "label": "200–500",  "cycles": 500,  "credits": 15},
        {"id": "range_4", "label": "500–1000", "cycles": 1000, "credits": 25},
    ])

    import bomber_service
    api_count = len(bomber_service.ULTIMATEAPIS)

    range_lines = "\n".join(
        f"    {'✅' if u['credits'] >= r['credits'] else '❌'} {r['label']} cycles → <code>{r['credits']}</code> credits"
        for r in ranges
    )

    text = (
        f"💣 <b>BOMBER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💳 Your Credits: <code>{u['credits']}</code>\n\n"
        f"<b>Choose Bomb Type:</b>\n\n"
        f"⚡ <b>API Bomb</b>\n"
        f"  Hits <b>{api_count}+ OTP endpoints</b> across 25+ Indian apps.\n"
        f"  Ranges:\n{range_lines}\n\n"
        f"✉️ <b>Custom Message Bomb</b>\n"
        f"  Sends your custom message via SMS gateway.\n"
        f"  Cost: <code>{s['custom_bomb_credits_per_1000']}</code> credits per 1000 SMS"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ API Bomb",             callback_data="bomber_api_start")],
        [InlineKeyboardButton("✉️ Custom Message Bomb",  callback_data="bomber_custom_start")],
        [InlineKeyboardButton("🏠 Main Menu",            callback_data="menu_main")],
    ])
    await safe_edit(query, text, kb)

# ─────────────────────────── API Bomb Flow ───────────────────────────

async def bomber_api_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show quantity range picker for API Bomb."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    u = await get_user(user.id)

    admin = await load_admin_data()
    ranges = admin.get("api_bomb_quantity_ranges", [
        {"id": "range_1", "label": "0–50",    "cycles": 50,   "credits": 3},
        {"id": "range_2", "label": "100–200",  "cycles": 200,  "credits": 8},
        {"id": "range_3", "label": "200–500",  "cycles": 500,  "credits": 15},
        {"id": "range_4", "label": "500–1000", "cycles": 1000, "credits": 25},
    ])

    text = (
        f"⚡ <b>API BOMB</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💳 Your Credits: <code>{u['credits']}</code>\n\n"
        f"🔢 <b>Select quantity range:</b>\n"
        f"<i>Each cycle hits {len(__import__('bomber_service').ULTIMATEAPIS)}+ Indian OTP endpoints</i>\n\n"
    )
    for r in ranges:
        text += f"  • <b>{r['label']} cycles</b> → <code>{r['credits']}</code> credits\n"

    kb_rows = []
    for r in ranges:
        can_afford = "✅" if u["credits"] >= r["credits"] else "❌"
        kb_rows.append([InlineKeyboardButton(
            f"{can_afford} {r['label']} cycles — {r['credits']} credits",
            callback_data=f"bomber_api_range_{r['id']}"
        )])
    kb_rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_bomber")])

    await safe_edit(query, text, InlineKeyboardMarkup(kb_rows))


async def bomber_api_range_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User picked a quantity range — check credits, ask for phone."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    u = await get_user(user.id)

    range_id = query.data.replace("bomber_api_range_", "")
    admin = await load_admin_data()
    ranges = admin.get("api_bomb_quantity_ranges", [
        {"id": "range_1", "label": "0–50",    "cycles": 50,   "credits": 3},
        {"id": "range_2", "label": "100–200",  "cycles": 200,  "credits": 8},
        {"id": "range_3", "label": "200–500",  "cycles": 500,  "credits": 15},
        {"id": "range_4", "label": "500–1000", "cycles": 1000, "credits": 25},
    ])

    chosen = next((r for r in ranges if r["id"] == range_id), None)
    if not chosen:
        await safe_edit(query, "⚠️ Invalid range. Try again.", back_kb("menu_bomber", "⬅️ Back"))
        return

    cost   = chosen["credits"]
    cycles = chosen["cycles"]

    if u["credits"] < cost:
        await safe_edit(query,
            f"❌ <b>Insufficient Credits</b>\n\n"
            f"<b>{chosen['label']} cycles</b> costs <code>{cost}</code> credits.\n"
            f"Your balance: <code>{u['credits']}</code>\n\n"
            f"<i>Buy more credits to continue.</i>",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Buy Credits", callback_data="menu_buy")],
                [InlineKeyboardButton("⬅️ Back",        callback_data="bomber_api_start")],
            ])
        )
        return

    context.user_data["bomber_mode"]        = "api"
    context.user_data["bomber_api_cycles"]  = cycles
    context.user_data["bomber_api_cost"]    = cost
    context.user_data["bomber_api_label"]   = chosen["label"]
    context.user_data["awaiting"]           = "bomber_phone"

    await safe_edit(query,
        f"⚡ <b>API BOMB</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔢 Range:  <b>{chosen['label']} cycles</b>\n"
        f"💳 Cost:   <code>{cost}</code> credits\n\n"
        f"📱 Enter the target phone number (10 digits):",
        back_kb("bomber_api_start", "⬅️ Back")
    )

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
        # API mode — show confirm with selected range info
        context.user_data["awaiting"] = "bomber_confirm"
        cycles = context.user_data.get("bomber_api_cycles", 50)
        cost   = context.user_data.get("bomber_api_cost",   3)
        label  = context.user_data.get("bomber_api_label",  "0–50")
        await update.message.reply_text(
            f"🎯 <b>Confirm API Bomb</b>\n\n"
            f"📱 Target: <code>{digits}</code>\n"
            f"🔢 Range:  <b>{label} cycles</b>\n"
            f"💳 Cost:   <code>{cost}</code> credits\n\n",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 LAUNCH",     callback_data="bomber_launch_api")],
                [InlineKeyboardButton("❌ Cancel",     callback_data="menu_bomber")],
            ])
        )

async def handle_bomber_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 2 (custom only): receive message text → show count picker."""
    msg = update.message.text.strip()
    if not msg:
        await update.message.reply_text("❌ Message cannot be empty.")
        return

    context.user_data["bomber_message"] = msg
    context.user_data["awaiting"] = "bomber_count_input"

    s = await get_bomber_settings()
    rate = s["custom_bomb_credits_per_1000"]

    await update.message.reply_text(
        f"✅ <b>Message saved.</b>\n\n"
        f"📨 <b>How many SMS to send?</b>\n"
        f"💳 Rate: <code>{rate}</code> credits per 1000 SMS\n\n"
        f"Pick a preset or tap <b>Custom</b> to enter a number:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("100",   callback_data="bomber_count_100"),
                InlineKeyboardButton("500",   callback_data="bomber_count_500"),
                InlineKeyboardButton("1000",  callback_data="bomber_count_1000"),
            ],
            [
                InlineKeyboardButton("5000",  callback_data="bomber_count_5000"),
                InlineKeyboardButton("🔥 Max (All Devices)", callback_data="bomber_count_max"),
            ],
            [InlineKeyboardButton("✏️ Custom Number", callback_data="bomber_count_custom")],
            [InlineKeyboardButton("❌ Cancel", callback_data="menu_bomber")],
        ])
    )


async def bomber_count_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles preset count button presses — show confirm screen."""
    query = update.callback_query
    await query.answer()

    data = query.data  # bomber_count_100, bomber_count_max, etc.
    s = await get_bomber_settings()
    rate = s["custom_bomb_credits_per_1000"]

    if data == "bomber_count_custom":
        context.user_data["awaiting"] = "bomber_custom_count_text"
        await safe_edit(query,
            f"✏️ <b>Enter custom SMS count:</b>\n\n"
            f"💳 Rate: <code>{rate}</code> credits per 1000\n\n"
            f"Type a number (e.g. <code>2500</code>):",
            InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="menu_bomber")]])
        )
        return

    if data == "bomber_count_max":
        count = None
        count_label = "MAX (all active devices)"
        cost = rate  # treat Max as at least 1 unit
    else:
        count = int(data.split("_")[-1])
        count_label = str(count)
        cost = calc_custom_cost(count, rate)

    context.user_data["bomber_count"] = count
    phone = context.user_data.get("bomber_phone", "")
    msg   = context.user_data.get("bomber_message", "")

    await safe_edit(query,
        f"🎯 <b>Confirm Custom Bomb</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📱 Target:  <code>{phone}</code>\n"
        f"✉️ Message: <i>{msg[:80]}</i>\n"
        f"📨 Count:   <code>{count_label}</code>\n"
        f"💳 Cost:    <code>{cost}</code> credits\n\n",
        InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 LAUNCH",  callback_data="bomber_launch_custom")],
            [InlineKeyboardButton("❌ Cancel",  callback_data="menu_bomber")],
        ])
    )


async def handle_bomber_custom_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 2b: user types a custom count number."""
    val = update.message.text.strip()
    try:
        count = int(val)
        if count < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Enter a valid positive number.")
        return

    s = await get_bomber_settings()
    rate = s["custom_bomb_credits_per_1000"]
    cost = calc_custom_cost(count, rate)
    context.user_data["bomber_count"] = count
    context.user_data.pop("awaiting", None)

    phone = context.user_data.get("bomber_phone", "")
    msg   = context.user_data.get("bomber_message", "")

    await update.message.reply_text(
        f"🎯 <b>Confirm Custom Bomb</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📱 Target:  <code>{phone}</code>\n"
        f"✉️ Message: <i>{msg[:80]}</i>\n"
        f"📨 Count:   <code>{count}</code>\n"
        f"💳 Cost:    <code>{cost}</code> credits\n\n",
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
    phone  = context.user_data.pop("bomber_phone",     None)
    cycles = context.user_data.pop("bomber_api_cycles", 50)
    cost   = context.user_data.pop("bomber_api_cost",   3)
    label  = context.user_data.pop("bomber_api_label",  "0–50")
    context.user_data.pop("awaiting",    None)
    context.user_data.pop("bomber_mode", None)

    if not phone:
        await safe_edit(query, "⚠️ Session expired. Start again.", back_kb("menu_bomber", "💣 Bomber"))
        return

    success = await deduct_credits(user.id, cost, f"API Bomb → {phone} [{label}]")
    if not success:
        await safe_edit(query, "❌ Insufficient credits.", back_kb("menu_bomber", "💣 Bomber"))
        return

    await safe_edit(query,
        f"⚡ <b>Bombing...</b>\n\n"
        f"📱 Target: <code>{phone}</code>\n"
        f"🔢 Range: <b>{label} cycles</b>\n\n"
        f"<i>Please wait...</i>"
    )

    result = await run_api_bomb(phone, cycles=cycles)
    u = await __import__('data_manager').get_user(user.id)

    await safe_edit(query,
        f"✅ <b>API Bomb Complete!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📱 Target: <code>{result['phone']}</code>\n"
        f"🔢 Range: <b>{label} cycles</b>\n"
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
    # count = None means Max (all devices), otherwise integer
    count   = context.user_data.pop("bomber_count", None)
    context.user_data.pop("awaiting", None)
    context.user_data.pop("bomber_mode", None)

    if not phone or not message:
        await safe_edit(query, "⚠️ Session expired. Start again.", back_kb("menu_bomber", "💣 Bomber"))
        return

    s = await get_bomber_settings()
    rate    = s["custom_bomb_credits_per_1000"]
    fb_list = s.get("firebase_list", [])

    # Calculate cost dynamically
    if count is None:
        cost = rate  # Max mode: charge for 1 unit as minimum
        count_label = "MAX"
    else:
        cost = calc_custom_cost(count, rate)
        count_label = str(count)

    success_deduct = await deduct_credits(user.id, cost, f"Custom Bomb → {phone} × {count_label}")
    if not success_deduct:
        await safe_edit(query,
            f"❌ <b>Insufficient Credits</b>\n\n"
            f"This bomb costs <code>{cost}</code> credits.\n"
            f"Buy more credits to continue.",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Buy Credits", callback_data="menu_buy")],
                [InlineKeyboardButton("⬅️ Back",        callback_data="menu_bomber")],
            ])
        )
        return

    await safe_edit(query,
        f"✉️ <b>Sending...</b>\n\n"
        f"📱 Target: <code>{phone}</code>\n"
        f"📨 Count: <code>{count_label}</code>\n\n"
        f"<i>Contacting all Firebase instances... please wait.</i>"
    )

    result = await run_custom_bomb(phone, message, count, firebase_list=fb_list)
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
    admin = await load_admin_data()
    ranges = admin.get("api_bomb_quantity_ranges", [
        {"id": "range_1", "label": "0–50",    "cycles": 50,   "credits": 3},
        {"id": "range_2", "label": "100–200",  "cycles": 200,  "credits": 8},
        {"id": "range_3", "label": "200–500",  "cycles": 500,  "credits": 15},
        {"id": "range_4", "label": "500–1000", "cycles": 1000, "credits": 25},
    ])
    fb_count = len(s.get("firebase_list", []))

    range_lines = "\n".join(
        f"  • {r['label']} cycles → <code>{r['credits']}</code> credits"
        for r in ranges
    )

    text = (
        f"💣 <b>BOMBER SETTINGS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ <b>API Bomb Ranges</b>\n"
        f"{range_lines}\n\n"
        f"✉️ <b>Custom Bomb (Firebase)</b>\n"
        f"  💰 Credits per 1000 SMS: <code>{s['custom_bomb_credits_per_1000']}</code>\n"
        f"  Firebase instances:      <code>{fb_count}</code> configured\n\n"
        f"<i>Select what to change:</i>"
    )

    kb_rows = []
    for r in ranges:
        kb_rows.append([InlineKeyboardButton(
            f"✏️ {r['label']} → {r['credits']} credits",
            callback_data=f"admin_set_range_credits_{r['id']}"
        )])
    kb_rows += [
        [InlineKeyboardButton("💰 Credits per 1000 SMS",   callback_data="admin_set_credits_per_1000")],
        [InlineKeyboardButton("🔥 Add Firebase",           callback_data="admin_firebase_add")],
        [InlineKeyboardButton("📦 Bulk Add Firebase",      callback_data="admin_firebase_bulk_add")],
        [InlineKeyboardButton("📋 List Firebase",          callback_data="admin_firebase_list")],
        [InlineKeyboardButton("🗑️ Remove Firebase",        callback_data="admin_firebase_remove")],
        [InlineKeyboardButton("⬅️ Back",                   callback_data="admin_panel")],
    ]
    await safe_edit(query, text, InlineKeyboardMarkup(kb_rows))

async def admin_bomber_set_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()

    field_map = {
        "admin_set_api_bomb_credits":    ("admin_awaiting", "bomber_api_credits",       "⚡ API Bomb credits per run (number):"),
        "admin_set_api_bomb_cycles":     ("admin_awaiting", "bomber_api_cycles",        "🔁 API Bomb cycles per run (number):"),
        "admin_set_custom_bomb_credits": ("admin_awaiting", "bomber_custom_credits",    "✉️ Custom Bomb credits per run (number):"),
        "admin_set_custom_bomb_count":   ("admin_awaiting", "bomber_custom_count",      "📨 Custom Bomb message count per run (number):"),
        "admin_set_credits_per_1000":    ("admin_awaiting", "bomber_credits_per_1000",  "💰 Credits charged per 1000 SMS (number):"),
    }
    if query.data not in field_map:
        return

    key, awaiting_val, prompt = field_map[query.data]
    context.user_data[key] = awaiting_val
    await safe_edit(query, f"<b>{prompt}</b>\n\nType the value now:",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_bomber_settings")]]))


async def admin_set_range_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin tapped edit button for a specific range's credit price."""
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()

    # callback_data = "admin_set_range_credits_range_X"
    range_id = query.data.replace("admin_set_range_credits_", "")
    admin = await load_admin_data()
    ranges = admin.get("api_bomb_quantity_ranges", [])
    chosen = next((r for r in ranges if r["id"] == range_id), None)
    if not chosen:
        await safe_edit(query, "⚠️ Range not found.", back_kb("admin_bomber_settings", "⬅️ Back"))
        return

    context.user_data["admin_awaiting"]       = "bomber_range_credits"
    context.user_data["bomber_range_edit_id"] = range_id

    await safe_edit(query,
        f"✏️ <b>Edit Range: {chosen['label']} cycles</b>\n\n"
        f"Current price: <code>{chosen['credits']}</code> credits\n\n"
        f"Enter the <b>new credit price</b> for this range:",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_bomber_settings")]])
    )


async def admin_firebase_bulk_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start bulk-add-firebase flow: paste multiple URLs."""
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "firebase_bulk_add_urls"
    await safe_edit(query,
        "📦 <b>Bulk Add Firebase</b>\n\n"
        "Paste <b>multiple Firebase URLs</b>, one per line:\n\n"
        "<i>Example:</i>\n"
        "<code>https://project1-default-rtdb.firebaseio.com\n"
        "https://project2-default-rtdb.firebaseio.com\n"
        "https://project3-default-rtdb.firebaseio.com</code>\n\n"
        "<i>All valid URLs will be added automatically with names Server1, Server2…</i>",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_bomber_settings")]])
    )

# ─────────────────────────── Firebase Admin Handlers ───────────────────────────

async def admin_firebase_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start add-firebase flow: just paste URL."""
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "firebase_add_url"
    await safe_edit(query,
        "🔥 <b>Add Firebase Instance</b>\n\n"
        "Paste the <b>Firebase URL</b> directly:\n"
        "(e.g. <code>https://my-project-default-rtdb.firebaseio.com</code>)\n\n"
        "<i>Name will be set automatically. No password required.</i>",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_bomber_settings")]]))

async def admin_firebase_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all configured Firebase instances."""
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()

    fb_list = await list_all_firebase()
    if not fb_list:
        await safe_edit(query, "📋 <b>No Firebase instances configured.</b>",
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_bomber_settings")]]))
        return

    lines = []
    for i, fb in enumerate(fb_list, 1):
        lines.append(f"{i}. <b>{fb['name']}</b>\n   ID: <code>{fb['id']}</code>\n   URL: <code>{fb['url'][:50]}...</code>" if len(fb['url']) > 50 else f"{i}. <b>{fb['name']}</b>\n   ID: <code>{fb['id']}</code>\n   URL: <code>{fb['url']}</code>")

    text = "📋 <b>Firebase Instances</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n" + "\n\n".join(lines)
    await safe_edit(query, text,
        InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_bomber_settings")]]))

async def admin_firebase_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start remove-firebase flow: show list with IDs."""
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()

    fb_list = await list_all_firebase()
    if not fb_list:
        await safe_edit(query, "📋 <b>No Firebase instances to remove.</b>",
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_bomber_settings")]]))
        return

    context.user_data["admin_awaiting"] = "firebase_remove_id"
    lines = [f"• <code>{fb['id']}</code> — {fb['name']}" for fb in fb_list]
    text = "🗑️ <b>Remove Firebase</b>\n\nCopy and send the <b>ID</b> to remove:\n\n" + "\n".join(lines)
    await safe_edit(query, text,
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_bomber_settings")]]))

async def handle_admin_bomber_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if it handled the input, False otherwise."""
    if not await is_admin(update.effective_user.id):
        return False

    awaiting = context.user_data.get("admin_awaiting", "")
    val = update.message.text.strip()

    # ── API Bomb range credit edit ──
    if awaiting == "bomber_range_credits":
        range_id = context.user_data.pop("bomber_range_edit_id", None)
        context.user_data.pop("admin_awaiting", None)
        try:
            new_credits = int(val)
            if new_credits < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Must be a positive number.")
            return True

        if range_id:
            admin = await load_admin_data()
            ranges = admin.get("api_bomb_quantity_ranges", [])
            updated = False
            for r in ranges:
                if r["id"] == range_id:
                    r["credits"] = new_credits
                    updated = True
                    break
            if updated:
                await set_admin_setting("api_bomb_quantity_ranges", ranges)
                chosen = next((r for r in ranges if r["id"] == range_id), {})
                await update.message.reply_text(
                    f"✅ Range <b>{chosen.get('label', range_id)}</b> updated to <code>{new_credits}</code> credits.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_bomber_settings")]])
                )
            else:
                await update.message.reply_text("❌ Range not found.", parse_mode=ParseMode.HTML)
        return True

    # ── Numeric bomber fields ──
    num_field_map = {
        "bomber_api_credits":      "api_bomb_credits",
        "bomber_api_cycles":       "api_bomb_cycles",
        "bomber_custom_credits":   "custom_bomb_credits",
        "bomber_custom_count":     "custom_bomb_count",
        "bomber_credits_per_1000": "custom_bomb_credits_per_1000",
    }
    if awaiting in num_field_map:
        db_key = num_field_map[awaiting]
        context.user_data.pop("admin_awaiting", None)
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

    # ── Firebase add flow ──
    if awaiting == "firebase_add_name":
        # Legacy state — treat input as URL directly
        context.user_data["admin_awaiting"] = "firebase_add_url"
        # fall through to firebase_add_url handler below

    if awaiting in ("firebase_add_url", "firebase_add_name"):
        url = val.strip().rstrip("/")
        if not url.startswith("http"):
            await update.message.reply_text(
                "❌ Invalid URL. Must start with <code>https://</code>\n\nPaste the full Firebase URL:",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_bomber_settings")]])
            )
            context.user_data["admin_awaiting"] = "firebase_add_url"
            return True

        # Auto-generate name: Server1, Server2, etc.
        existing = await list_all_firebase()
        auto_name = f"Server{len(existing) + 1}"

        context.user_data.pop("admin_awaiting", None)
        entry = await add_firebase(auto_name, url, "")
        await update.message.reply_text(
            f"✅ <b>Firebase added!</b>\n\n"
            f"Name: <code>{entry['name']}</code>\n"
            f"ID:   <code>{entry['id']}</code>\n"
            f"URL:  <code>{entry['url']}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_bomber_settings")]])
        )
        return True

    if awaiting == "firebase_add_password":
        # Legacy fallback — shouldn't hit normally
        name = context.user_data.pop("firebase_pending_name", "Server")
        url  = context.user_data.pop("firebase_pending_url",  "")
        password = "" if val.lower() == "none" else val
        context.user_data.pop("admin_awaiting", None)
        entry = await add_firebase(name, url, password)
        await update.message.reply_text(
            f"✅ <b>Firebase added!</b>\n\n"
            f"Name: <code>{entry['name']}</code>\n"
            f"ID:   <code>{entry['id']}</code>\n"
            f"URL:  <code>{entry['url']}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_bomber_settings")]])
        )
        return True

    # ── Firebase remove flow ──
    if awaiting == "firebase_remove_id":
        context.user_data.pop("admin_awaiting", None)
        removed = await remove_firebase(val)
        if removed:
            await update.message.reply_text(
                f"✅ Firebase <code>{val}</code> removed.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_bomber_settings")]])
            )
        else:
            await update.message.reply_text(
                f"❌ ID <code>{val}</code> not found.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_bomber_settings")]])
            )
        return True

    # ── Firebase bulk add flow ──
    if awaiting == "firebase_bulk_add_urls":
        context.user_data.pop("admin_awaiting", None)
        lines = [line.strip().rstrip("/") for line in val.splitlines() if line.strip()]
        valid_urls = [u for u in lines if u.startswith("http")]
        invalid_count = len(lines) - len(valid_urls)

        if not valid_urls:
            await update.message.reply_text(
                "❌ No valid URLs found. Each URL must start with <code>https://</code>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_bomber_settings")]])
            )
            return True

        existing = await list_all_firebase()
        start_idx = len(existing) + 1
        added = []
        for i, url in enumerate(valid_urls):
            name = f"Server{start_idx + i}"
            entry = await add_firebase(name, url, "")
            added.append(f"• <b>{entry['name']}</b> — <code>{entry['id']}</code>")

        summary = "\n".join(added)
        extra = f"\n⚠️ {invalid_count} invalid URL(s) skipped." if invalid_count else ""
        await update.message.reply_text(
            f"✅ <b>Bulk Add Complete!</b>\n\n"
            f"Added <b>{len(added)}</b> Firebase instance(s):\n\n"
            f"{summary}{extra}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_bomber_settings")]])
        )
        return True

    return False
