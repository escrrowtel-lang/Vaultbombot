import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from data_manager import (
    is_admin, load_admin_data, save_admin_data, set_admin_setting,
    get_user, get_all_users, add_credits, set_user_credits,
    ban_user, unban_user, add_admin, remove_admin,
    create_redeem_code, delete_redeem_code, get_pending_payments
)
from keyboards import (
    admin_panel_kb, admin_payment_setup_kb, admin_users_kb,
    admin_codes_kb, cancel_kb, back_to_main_kb,
    payment_confirm_kb
)

logger = logging.getLogger(__name__)

async def safe_edit(query, text, reply_markup=None, parse_mode=ParseMode.HTML):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        try:
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"safe_edit error: {e}")

# ─────────────────────────── /admin ───────────────────────────

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_admin(user.id):
        await update.message.reply_text("❌ Access denied.")
        return

    users = await get_all_users()
    pending = await get_pending_payments()
    admin_data = await load_admin_data()

    upi_set = "✅" if admin_data.get("upi_id") else "❌"
    qr_set  = "✅" if admin_data.get("qr_file_id") else "❌"
    grp_set = "✅" if admin_data.get("payment_group_id") else "❌"
    maint   = "🔴 ON" if admin_data.get("maintenance") else "🟢 OFF"

    text = (
        f"👑 <b>ADMIN PANEL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Overview</b>\n"
        f"  👥 Total Users: <code>{len(users)}</code>\n"
        f"  ⏳ Pending Payments: <code>{len(pending)}</code>\n\n"
        f"⚙️ <b>Setup Status</b>\n"
        f"  {upi_set} UPI ID\n"
        f"  {qr_set} QR Image\n"
        f"  {grp_set} Payment Group\n"
        f"  🔧 Maintenance: {maint}\n\n"
        f"<i>Select an action below:</i>"
    )
    await update.message.reply_text(text, reply_markup=admin_panel_kb(), parse_mode=ParseMode.HTML)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id):
        await query.answer("❌ Access denied.", show_alert=True)
        return
    await query.answer()

    users = await get_all_users()
    pending = await get_pending_payments()
    admin_data = await load_admin_data()

    upi_set = "✅" if admin_data.get("upi_id") else "❌"
    qr_set  = "✅" if admin_data.get("qr_file_id") else "❌"
    grp_set = "✅" if admin_data.get("payment_group_id") else "❌"

    text = (
        f"👑 <b>ADMIN PANEL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"  👥 Users: <code>{len(users)}</code>\n"
        f"  ⏳ Pending: <code>{len(pending)}</code>\n"
        f"  {upi_set} UPI  {qr_set} QR  {grp_set} Group\n\n"
        f"<i>Select an action:</i>"
    )
    await safe_edit(query, text, admin_panel_kb())

# ─────────────────────────── Payment Setup ───────────────────────────

async def admin_payment_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()

    admin_data = await load_admin_data()
    upi = admin_data.get("upi_id", "Not set")
    name = admin_data.get("upi_name", "Not set")
    grp = admin_data.get("payment_group_id", "Not set")
    qr = "✅ Set" if admin_data.get("qr_file_id") else "❌ Not set"

    text = (
        f"💳 <b>PAYMENT SETUP</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📲 UPI ID: <code>{upi}</code>\n"
        f"👤 UPI Name: <code>{name}</code>\n"
        f"🖼️ QR Image: {qr}\n"
        f"💬 Payment Group: <code>{grp}</code>\n\n"
        f"<i>Select what to configure:</i>"
    )
    await safe_edit(query, text, admin_payment_setup_kb())

async def admin_set_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "set_upi"
    await safe_edit(query,
        "📲 <b>Set UPI ID</b>\n\nFormat: <code>upiid@bank name</code>\n\nType the UPI ID now:",
        cancel_kb()
    )

async def admin_set_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "set_qr"
    await safe_edit(query,
        "🖼️ <b>Set QR Image</b>\n\nSend the UPI QR code image now:",
        cancel_kb()
    )

async def admin_set_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "set_group"
    await safe_edit(query,
        "💬 <b>Set Payment Group</b>\n\n"
        "Add me to your group, make me admin, then forward a message from that group here.\n\n"
        "<b>OR</b> type the group chat ID directly (e.g. <code>-1001234567890</code>):",
        cancel_kb()
    )

# ─────────────────────────── Users ───────────────────────────

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    await safe_edit(query,
        "👥 <b>USER MANAGEMENT</b>\n\nSelect an action:",
        admin_users_kb()
    )

async def admin_find_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "find_user"
    await safe_edit(query, "🔍 <b>Find User</b>\n\nEnter user ID or @username:", cancel_kb())

async def admin_add_credits_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "add_credits_uid"
    await safe_edit(query, "➕ <b>Add Credits</b>\n\nEnter the user ID:", cancel_kb())

async def admin_set_credits_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "set_credits_uid"
    await safe_edit(query, "✏️ <b>Set Credits</b>\n\nEnter the user ID:", cancel_kb())

async def admin_ban_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "ban_uid"
    await safe_edit(query, "🚫 <b>Ban User</b>\n\nEnter the user ID to ban:", cancel_kb())

async def admin_unban_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "unban_uid"
    await safe_edit(query, "✅ <b>Unban User</b>\n\nEnter the user ID to unban:", cancel_kb())

# ─────────────────────────── Stats ───────────────────────────

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer("Loading stats...")

    users = await get_all_users()
    pending = await get_pending_payments()

    total_credits = sum(u.get("credits", 0) for u in users.values())
    total_lookups = sum(u.get("lookups_done", 0) for u in users.values())
    banned = sum(1 for u in users.values() if u.get("is_banned"))

    text = (
        f"📊 <b>STATISTICS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Total Users: <code>{len(users)}</code>\n"
        f"🚫 Banned Users: <code>{banned}</code>\n"
        f"💳 Total Credits in Circulation: <code>{total_credits}</code>\n"
        f"🔍 Total Lookups Done: <code>{total_lookups}</code>\n"
        f"⏳ Pending Payments: <code>{len(pending)}</code>\n"
    )
    await safe_edit(query, text, InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]
    ]))

# ─────────────────────────── Pending Payments ───────────────────────────

async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()

    pending = await get_pending_payments()
    if not pending:
        await safe_edit(query, "✅ No pending payments.", InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]
        ]))
        return

    text = f"⏳ <b>PENDING PAYMENTS ({len(pending)})</b>\n\n"
    for pay_id, p in list(pending.items())[:10]:
        text += (
            f"🆔 <code>{pay_id}</code>\n"
            f"  👤 UID: <code>{p['user_id']}</code>\n"
            f"  📦 {p['pkg_label']} — ₹{p['price']} — {p['credits']} credits\n"
            f"  🔢 UTR: <code>{p.get('utr', 'N/A')}</code>\n\n"
        )

    await safe_edit(query, text, InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]
    ]))

# ─────────────────────────── Redeem Codes ───────────────────────────

async def admin_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    await safe_edit(query, "🎟️ <b>REDEEM CODES</b>\n\nSelect an action:", admin_codes_kb())

async def admin_create_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "create_code"
    await safe_edit(query,
        "➕ <b>Create Redeem Code</b>\n\n"
        "Format: <code>CODE CREDITS MAX_USES</code>\n"
        "Example: <code>VAULT50 50 10</code>\n\n"
        "Type now:",
        cancel_kb()
    )

async def admin_list_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()

    admin_data = await load_admin_data()
    codes = admin_data.get("redeem_codes", {})

    if not codes:
        await safe_edit(query, "📋 No redeem codes created yet.", admin_codes_kb())
        return

    text = "🎟️ <b>ACTIVE CODES</b>\n\n"
    for code, info in codes.items():
        text += f"<code>{code}</code> — {info['credits']} credits — {info['uses']}/{info['max_uses']} used\n"

    await safe_edit(query, text, admin_codes_kb())

async def admin_delete_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "delete_code"
    await safe_edit(query, "🗑️ <b>Delete Code</b>\n\nEnter the code to delete:", cancel_kb())

# ─────────────────────────── Manage Admins ───────────────────────────

async def admin_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()

    admin_data = await load_admin_data()
    admins = admin_data.get("admins", [])

    text = (
        f"👑 <b>MANAGE ADMINS</b>\n\n"
        f"Current admins: {', '.join(f'<code>{a}</code>' for a in admins) or 'None'}\n\n"
        f"<i>Select action:</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Admin",    callback_data="admin_add_admin")],
        [InlineKeyboardButton("➖ Remove Admin", callback_data="admin_remove_admin")],
        [InlineKeyboardButton("⬅️ Back",         callback_data="admin_panel")],
    ])
    await safe_edit(query, text, kb)

async def admin_add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "add_admin_uid"
    await safe_edit(query, "➕ <b>Add Admin</b>\n\nEnter the user ID to promote:", cancel_kb())

async def admin_remove_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()
    context.user_data["admin_awaiting"] = "remove_admin_uid"
    await safe_edit(query, "➖ <b>Remove Admin</b>\n\nEnter the user ID to demote:", cancel_kb())

# ─────────────────────────── Maintenance ───────────────────────────

async def admin_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await is_admin(query.from_user.id): return
    await query.answer()

    admin_data = await load_admin_data()
    current = admin_data.get("maintenance", False)
    admin_data["maintenance"] = not current
    await save_admin_data(admin_data)

    state = "🔴 ON" if not current else "🟢 OFF"
    await safe_edit(query,
        f"🔧 <b>Maintenance Mode</b>\n\nNow: <b>{state}</b>",
        InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]])
    )

# ─────────────────────────── Text Input Router ───────────────────────────

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes text input for all multi-step admin flows."""
    if not await is_admin(update.effective_user.id):
        return

    awaiting = context.user_data.get("admin_awaiting")
    if not awaiting:
        return

    text = update.message.text.strip()

    # ── UPI setup ──
    if awaiting == "set_upi":
        context.user_data.pop("admin_awaiting")
        parts = text.split(None, 1)
        upi_id = parts[0]
        upi_name = parts[1] if len(parts) > 1 else "Vault Bot"
        admin_data = await load_admin_data()
        admin_data["upi_id"] = upi_id
        admin_data["upi_name"] = upi_name
        await save_admin_data(admin_data)
        await update.message.reply_text(
            f"✅ UPI ID set to <code>{upi_id}</code>\nName: <b>{upi_name}</b>",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="admin_payment_setup")]
            ])
        )

    # ── Payment group by ID text ──
    elif awaiting == "set_group":
        context.user_data.pop("admin_awaiting")
        try:
            group_id = int(text)
            await set_admin_setting("payment_group_id", group_id)
            await update.message.reply_text(
                f"✅ Payment group set to <code>{group_id}</code>",
                parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="admin_payment_setup")]
                ])
            )
        except ValueError:
            await update.message.reply_text("❌ Invalid chat ID. Enter a number like -1001234567890.")

    # ── Find user ──
    elif awaiting == "find_user":
        context.user_data.pop("admin_awaiting")
        uid = text.lstrip("@")
        # Try by ID
        try:
            u = await get_user(int(uid))
            if u:
                await update.message.reply_text(
                    f"👤 <b>User Found</b>\n\n"
                    f"🆔 ID: <code>{u['user_id']}</code>\n"
                    f"📛 Name: {u['full_name']}\n"
                    f"🔗 @{u.get('username','N/A')}\n"
                    f"💳 Credits: <code>{u['credits']}</code>\n"
                    f"🔍 Lookups: <code>{u.get('lookups_done',0)}</code>\n"
                    f"🚫 Banned: {'Yes' if u.get('is_banned') else 'No'}",
                    parse_mode=ParseMode.HTML, reply_markup=admin_users_kb()
                )
                return
        except ValueError:
            pass
        # Try by username
        all_users = await get_all_users()
        found = next((u for u in all_users.values() if u.get("username", "").lower() == uid.lower()), None)
        if found:
            await update.message.reply_text(
                f"👤 <b>User Found</b>\n\n"
                f"🆔 ID: <code>{found['user_id']}</code>\n"
                f"📛 {found['full_name']} (@{found.get('username','N/A')})\n"
                f"💳 Credits: <code>{found['credits']}</code>",
                parse_mode=ParseMode.HTML, reply_markup=admin_users_kb()
            )
        else:
            await update.message.reply_text("❌ User not found.", reply_markup=admin_users_kb())

    # ── Add credits: step 1 get UID ──
    elif awaiting == "add_credits_uid":
        try:
            uid = int(text)
            context.user_data["admin_target_uid"] = uid
            context.user_data["admin_awaiting"] = "add_credits_amount"
            await update.message.reply_text(f"✅ User <code>{uid}</code> selected.\nEnter credits amount to add:", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Enter a valid user ID.")

    # ── Add credits: step 2 get amount ──
    elif awaiting == "add_credits_amount":
        context.user_data.pop("admin_awaiting")
        uid = context.user_data.pop("admin_target_uid", None)
        try:
            amount = int(text)
            await add_credits(uid, amount, "Admin grant")
            u = await get_user(uid)
            await update.message.reply_text(
                f"✅ Added <code>{amount}</code> credits to user <code>{uid}</code>\nNew balance: <code>{u['credits']}</code>",
                parse_mode=ParseMode.HTML, reply_markup=admin_users_kb()
            )
            # Notify user
            try:
                await context.bot.send_message(uid,
                    f"🎁 <b>Credits Added!</b>\n+<code>{amount}</code> credits added by admin.\nNew balance: <code>{u['credits']}</code>",
                    parse_mode=ParseMode.HTML)
            except Exception: pass
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    # ── Set credits: step 1 ──
    elif awaiting == "set_credits_uid":
        try:
            uid = int(text)
            context.user_data["admin_target_uid"] = uid
            context.user_data["admin_awaiting"] = "set_credits_amount"
            await update.message.reply_text(f"✅ User <code>{uid}</code>.\nEnter new credits amount:", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")

    # ── Set credits: step 2 ──
    elif awaiting == "set_credits_amount":
        context.user_data.pop("admin_awaiting")
        uid = context.user_data.pop("admin_target_uid", None)
        try:
            amount = int(text)
            await set_user_credits(uid, amount)
            await update.message.reply_text(
                f"✅ User <code>{uid}</code> credits set to <code>{amount}</code>",
                parse_mode=ParseMode.HTML, reply_markup=admin_users_kb()
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    # ── Ban ──
    elif awaiting == "ban_uid":
        context.user_data.pop("admin_awaiting")
        try:
            uid = int(text)
            await ban_user(uid)
            await update.message.reply_text(f"🚫 User <code>{uid}</code> banned.", parse_mode=ParseMode.HTML, reply_markup=admin_users_kb())
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")

    # ── Unban ──
    elif awaiting == "unban_uid":
        context.user_data.pop("admin_awaiting")
        try:
            uid = int(text)
            await unban_user(uid)
            await update.message.reply_text(f"✅ User <code>{uid}</code> unbanned.", parse_mode=ParseMode.HTML, reply_markup=admin_users_kb())
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")

    # ── Create code ──
    elif awaiting == "create_code":
        context.user_data.pop("admin_awaiting")
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("❌ Format: CODE CREDITS [MAX_USES]")
            return
        code = parts[0].upper()
        try:
            credits = int(parts[1])
            max_uses = int(parts[2]) if len(parts) > 2 else 1
            await create_redeem_code(code, credits, max_uses)
            await update.message.reply_text(
                f"✅ Code <code>{code}</code> created!\nCredits: {credits} | Max uses: {max_uses}",
                parse_mode=ParseMode.HTML, reply_markup=admin_codes_kb()
            )
        except ValueError:
            await update.message.reply_text("❌ Invalid format. Credits must be a number.")

    # ── Delete code ──
    elif awaiting == "delete_code":
        context.user_data.pop("admin_awaiting")
        code = text.upper()
        await delete_redeem_code(code)
        await update.message.reply_text(f"✅ Code <code>{code}</code> deleted.", parse_mode=ParseMode.HTML, reply_markup=admin_codes_kb())

    # ── Add admin ──
    elif awaiting == "add_admin_uid":
        context.user_data.pop("admin_awaiting")
        try:
            uid = int(text)
            await add_admin(uid)
            await update.message.reply_text(f"✅ User <code>{uid}</code> is now an admin.", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")

    # ── Remove admin ──
    elif awaiting == "remove_admin_uid":
        context.user_data.pop("admin_awaiting")
        try:
            uid = int(text)
            await remove_admin(uid)
            await update.message.reply_text(f"✅ User <code>{uid}</code> removed from admins.", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")

# ─────────────────────────── Photo/forward for group/QR setup ───────────────────────────

async def handle_admin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    if context.user_data.get("admin_awaiting") != "set_qr":
        return
    context.user_data.pop("admin_awaiting")

    if not update.message.photo:
        await update.message.reply_text("❌ Send a photo.")
        return

    file_id = update.message.photo[-1].file_id
    await set_admin_setting("qr_file_id", file_id)
    await update.message.reply_text(
        "✅ QR image saved!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_payment_setup")]])
    )

async def handle_admin_forwarded_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detect forwarded group message to auto-set payment group ID."""
    if not await is_admin(update.effective_user.id):
        return
    if context.user_data.get("admin_awaiting") != "set_group":
        return
    if update.message.forward_from_chat:
        group_id = update.message.forward_from_chat.id
        context.user_data.pop("admin_awaiting")
        await set_admin_setting("payment_group_id", group_id)
        await update.message.reply_text(
            f"✅ Payment group set to <code>{group_id}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_payment_setup")]])
        )
