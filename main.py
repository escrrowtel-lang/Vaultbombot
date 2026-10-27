import asyncio
import logging
import os
from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, Defaults
)
from telegram.constants import ParseMode

from config import BOT_TOKEN
from data_manager import get_user, load_admin_data

# Import handlers
from handlers_user import (
    start_command, menu_main, menu_profile, menu_lookups,
    menu_referral, menu_history, menu_redeem, menu_support,
    handle_lookup_select, handle_lookup_query, handle_lookup_confirm,
    handle_redeem_code_input,
)
from handlers_payment import (
    menu_buy, handle_buy_pkg, handle_pay_done,
    handle_utr_input, handle_screenshot_input, handle_pay_cancel,
    admin_approve_payment, admin_reject_payment,
)
from handlers_bomber import (
    menu_bomber, bomber_api_start, bomber_custom_start,
    bomber_launch_api, bomber_launch_custom,
    handle_bomber_phone, handle_bomber_message,
    admin_bomber_settings, admin_bomber_set_field, handle_admin_bomber_text,
)
from handlers_admin import (
    admin_command, admin_panel, admin_payment_setup,
    admin_set_upi, admin_set_qr, admin_set_group,
    admin_users, admin_find_user, admin_add_credits_start,
    admin_set_credits_start, admin_ban_user_start, admin_unban_user_start,
    admin_stats, admin_pending, admin_codes, admin_create_code,
    admin_list_codes, admin_delete_code, admin_admins,
    admin_add_admin_start, admin_remove_admin_start, admin_maintenance,
    handle_admin_text, handle_admin_photo, handle_admin_forwarded_group,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─────────────────────────── Middleware: Ban + Maintenance ───────────────────────────

async def pre_process(update: Update, context):
    """Check ban status and maintenance mode before processing."""
    user = update.effective_user
    if not user:
        return True
    u = await get_user(user.id, user.username or "", user.full_name)
    if u.get("is_banned"):
        if update.message:
            await update.message.reply_text("🚫 You are banned from using this bot.")
        elif update.callback_query:
            await update.callback_query.answer("🚫 You are banned.", show_alert=True)
        return False

    admin_data = await load_admin_data()
    if admin_data.get("maintenance"):
        from data_manager import is_admin
        if not await is_admin(user.id):
            if update.message:
                await update.message.reply_text("🔧 Bot is under maintenance. Please check back later.")
            elif update.callback_query:
                await update.callback_query.answer("🔧 Maintenance mode.", show_alert=True)
            return False
    return True

# ─────────────────────────── Text Input Router ───────────────────────────

async def handle_text_input(update: Update, context):
    """Central router for all text/photo inputs based on context.user_data['awaiting']."""
    if not await pre_process(update, context):
        return

    awaiting = context.user_data.get("awaiting")
    admin_awaiting = context.user_data.get("admin_awaiting")

    # Admin flows take priority
    if admin_awaiting:
        await handle_admin_text(update, context)
        return

    # Bomber text inputs
    if awaiting == "bomber_phone":
        await handle_bomber_phone(update, context)
        return
    elif awaiting == "bomber_message":
        await handle_bomber_message(update, context)
        return

    if await handle_admin_bomber_text(update, context):
        return

    if awaiting == "utr_input":
        await handle_utr_input(update, context)
    elif awaiting == "redeem_code":
        context.user_data.pop("awaiting", None)
        await handle_redeem_code_input(update, context)
    elif "pending_lookup" in context.user_data:
        await handle_lookup_query(update, context)
    # else: ignore unrecognized text

async def handle_photo_input(update: Update, context):
    """Routes photo input."""
    if not await pre_process(update, context):
        return

    admin_awaiting = context.user_data.get("admin_awaiting")
    if admin_awaiting == "set_qr":
        await handle_admin_photo(update, context)
        return

    awaiting = context.user_data.get("awaiting")
    if awaiting == "screenshot_input":
        await handle_screenshot_input(update, context)
    elif update.message.forward_from_chat:
        await handle_admin_forwarded_group(update, context)

async def handle_forwarded_msg(update: Update, context):
    """Handle forwarded messages for group setup."""
    if not await pre_process(update, context):
        return
    if update.message.forward_from_chat and context.user_data.get("admin_awaiting") == "set_group":
        await handle_admin_forwarded_group(update, context)

# ─────────────────────────── Callback router ───────────────────────────

async def callback_router(update: Update, context):
    if not await pre_process(update, context):
        return
    query = update.callback_query
    data = query.data

    routes = {
        # User
        "menu_main":        menu_main,
        "menu_profile":     menu_profile,
        "menu_lookups":     menu_lookups,
        "menu_referral":    menu_referral,
        "menu_history":     menu_history,
        "menu_redeem":      menu_redeem,
        "menu_support":     menu_support,
        "menu_buy":         menu_buy,
        # Bomber
        "menu_bomber":               menu_bomber,
        "bomber_api_start":          bomber_api_start,
        "bomber_custom_start":       bomber_custom_start,
        "bomber_launch_api":         bomber_launch_api,
        "bomber_launch_custom":      bomber_launch_custom,
        "admin_bomber_settings":     admin_bomber_settings,
        "admin_set_api_bomb_credits":    admin_bomber_set_field,
        "admin_set_api_bomb_cycles":     admin_bomber_set_field,
        "admin_set_custom_bomb_credits": admin_bomber_set_field,
        "admin_set_custom_bomb_count":   admin_bomber_set_field,
        "admin_set_fast2sms_key":        admin_bomber_set_field,
        # Admin panel
        "admin_panel":               admin_panel,
        "admin_payment_setup":       admin_payment_setup,
        "admin_set_upi":             admin_set_upi,
        "admin_set_qr":              admin_set_qr,
        "admin_set_group":           admin_set_group,
        "admin_users":               admin_users,
        "admin_find_user":           admin_find_user,
        "admin_add_credits":         admin_add_credits_start,
        "admin_set_credits":         admin_set_credits_start,
        "admin_ban_user":            admin_ban_user_start,
        "admin_unban_user":          admin_unban_user_start,
        "admin_stats":               admin_stats,
        "admin_pending":             admin_pending,
        "admin_codes":               admin_codes,
        "admin_create_code":         admin_create_code,
        "admin_list_codes":          admin_list_codes,
        "admin_delete_code":         admin_delete_code,
        "admin_admins":              admin_admins,
        "admin_add_admin":           admin_add_admin_start,
        "admin_remove_admin":        admin_remove_admin_start,
        "admin_maintenance":         admin_maintenance,
    }

    if data in routes:
        await routes[data](update, context)
    elif data.startswith("lookup_confirm_"):
        await handle_lookup_confirm(update, context)
    elif data.startswith("lookup_"):
        await handle_lookup_select(update, context)
    elif data.startswith("buy_pkg_"):
        await handle_buy_pkg(update, context)
    elif data.startswith("pay_done_"):
        await handle_pay_done(update, context)
    elif data.startswith("pay_cancel_"):
        await handle_pay_cancel(update, context)
    elif data.startswith("admin_approve_"):
        await admin_approve_payment(update, context)
    elif data.startswith("admin_reject_"):
        await admin_reject_payment(update, context)
    else:
        await query.answer("Unknown action.", show_alert=True)

# ─────────────────────────── Health Server ───────────────────────────

async def health_handler(request):
    return web.Response(text="OK", status=200)

async def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    app_web = web.Application()
    app_web.router.add_get("/", health_handler)
    app_web.router.add_get("/health", health_handler)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health server running on port {port}")

# ─────────────────────────── Main ───────────────────────────

async def main():
    os.makedirs("data", exist_ok=True)

    defaults = Defaults(parse_mode=ParseMode.HTML)
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .defaults(defaults)
        .read_timeout(30)
        .connect_timeout(30)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", lambda u, c: _gated(start_command, u, c)))
    app.add_handler(CommandHandler("admin", lambda u, c: _gated(admin_command, u, c)))

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_router))

    # Text messages
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text_input
    ))

    # Photos
    app.add_handler(MessageHandler(
        filters.PHOTO,
        handle_photo_input
    ))

    # Forwarded messages (for group setup)
    app.add_handler(MessageHandler(
        filters.FORWARDED,
        handle_forwarded_msg
    ))

    logger.info("🛡️ Vault Bot starting...")
    await asyncio.gather(
        start_health_server(),
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    )

async def _gated(handler, update: Update, context):
    if not await pre_process(update, context):
        return
    await handler(update, context)

if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    app_instance = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        try:
            loop.close()
        except Exception:
            pass
