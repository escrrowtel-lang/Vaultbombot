import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from data_manager import (
    get_user, add_credits, create_payment, update_payment,
    get_payment, get_pending_payments, load_admin_data
)
from keyboards import (
    buy_credits_kb, payment_flow_kb, payment_confirm_kb, back_to_main_kb
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

# ─────────────────────────── Show Packages ───────────────────────────

async def menu_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    u = await get_user(user.id)

    admin = await load_admin_data()
    packages = admin.get("credit_packages", [])

    text = (
        f"💳 <b>BUY CREDITS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Your Balance: <code>{u['credits']}</code> credits\n\n"
        f"<b>Available Packages:</b>\n\n"
    )
    for pkg in packages:
        text += f"  {'⭐' if pkg['label']=='Popular' else '💎' if pkg['label']=='Elite' else '📦'} <b>{pkg['label']}</b> — {pkg['credits']} credits @ ₹{pkg['price']}\n"

    text += "\n<i>Select a package to proceed with payment.</i>"
    await safe_edit(query, text, buy_credits_kb(packages))

# ─────────────────────────── Package Selected → Show Payment QR ───────────────────────────

async def handle_buy_pkg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pkg_id = query.data.replace("buy_pkg_", "")
    admin = await load_admin_data()
    packages = admin.get("credit_packages", [])
    pkg = next((p for p in packages if p["id"] == pkg_id), None)

    if not pkg:
        await safe_edit(query, "❌ Package not found.", back_to_main_kb())
        return

    upi_id = admin.get("upi_id")
    upi_name = admin.get("upi_name", "Vault Bot")
    qr_file_id = admin.get("qr_file_id")

    if not upi_id:
        await safe_edit(query, "⚠️ Payment setup not complete. Contact support.", back_to_main_kb())
        return

    user = query.from_user

    # Create pending payment record
    pay_id = await create_payment(user.id, pkg_id, pkg["credits"], pkg["price"], pkg["label"])
    context.user_data["current_pay_id"] = pay_id

    text = (
        f"💳 <b>PAYMENT DETAILS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Package: <b>{pkg['label']}</b>\n"
        f"💰 Amount: <b>₹{pkg['price']}</b>\n"
        f"🎯 Credits: <code>{pkg['credits']}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📲 <b>Pay via UPI:</b>\n"
        f"  UPI ID: <code>{upi_id}</code>\n"
        f"  Name: <b>{upi_name}</b>\n"
        f"  Amount: <b>₹{pkg['price']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚠️ <b>Important:</b>\n"
        f"  1. Pay the exact amount: ₹{pkg['price']}\n"
        f"  2. Save your UTR/Transaction ID\n"
        f"  3. Take a screenshot of payment\n"
        f"  4. Click the button below after paying\n\n"
        f"🆔 Payment ID: <code>{pay_id}</code>"
    )

    kb = payment_flow_kb(pay_id)

    if qr_file_id:
        try:
            await query.message.reply_photo(
                photo=qr_file_id,
                caption=text,
                reply_markup=kb,
                parse_mode=ParseMode.HTML
            )
            try:
                await query.message.delete()
            except Exception:
                pass
            return
        except Exception as e:
            logger.error(f"QR send error: {e}")

    await safe_edit(query, text, kb)

# ─────────────────────────── User Clicks "I've Paid" ───────────────────────────

async def handle_pay_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pay_id = query.data.replace("pay_done_", "")
    payment = await get_payment(pay_id)

    if not payment:
        await safe_edit(query, "❌ Payment not found.", back_to_main_kb())
        return

    if payment["status"] != "pending":
        await safe_edit(query, f"ℹ️ This payment is already <b>{payment['status']}</b>.", back_to_main_kb())
        return

    context.user_data["utr_pay_id"] = pay_id
    context.user_data["awaiting"] = "utr_input"

    text = (
        f"✅ <b>SUBMIT PAYMENT PROOF</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Package: <b>{payment['pkg_label']}</b>\n"
        f"💰 Amount: <b>₹{payment['price']}</b>\n\n"
        f"<b>Step 1:</b> Enter your UTR / Transaction ID below:\n\n"
        f"<i>Type your UTR number in the chat.</i>"
    )
    await safe_edit(query, text, InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data=f"pay_cancel_{pay_id}")]
    ]))

async def handle_utr_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives UTR text input."""
    if context.user_data.get("awaiting") != "utr_input":
        return

    pay_id = context.user_data.get("utr_pay_id")
    if not pay_id:
        return

    utr = update.message.text.strip()
    context.user_data["utr_value"] = utr
    context.user_data["awaiting"] = "screenshot_input"

    await update.message.reply_text(
        f"✅ UTR recorded: <code>{utr}</code>\n\n"
        f"<b>Step 2:</b> Send your payment screenshot now.\n\n"
        f"<i>Upload the screenshot image in the chat.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data=f"pay_cancel_{pay_id}")]
        ])
    )

async def handle_screenshot_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives screenshot photo."""
    if context.user_data.get("awaiting") != "screenshot_input":
        return

    pay_id = context.user_data.pop("utr_pay_id", None)
    utr = context.user_data.pop("utr_value", None)
    context.user_data.pop("awaiting", None)

    if not pay_id or not utr:
        await update.message.reply_text("⚠️ Session expired. Start again from /start.")
        return

    # Get photo file_id (highest resolution)
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Please send a photo/screenshot, not a file.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
        )
        context.user_data["utr_pay_id"] = pay_id
        context.user_data["utr_value"] = utr
        context.user_data["awaiting"] = "screenshot_input"
        return

    screenshot_file_id = update.message.photo[-1].file_id
    user = update.effective_user

    # Update payment record
    await update_payment(pay_id, {
        "utr": utr,
        "screenshot_file_id": screenshot_file_id,
        "status": "pending",
    })

    payment = await get_payment(pay_id)

    # ── Forward to payment group ──
    admin = await load_admin_data()
    payment_group_id = admin.get("payment_group_id")

    forward_text = (
        f"🔔 <b>NEW PAYMENT VERIFICATION REQUEST</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 User: <b>{user.full_name}</b> (@{user.username or 'N/A'})\n"
        f"🆔 User ID: <code>{user.id}</code>\n\n"
        f"📦 Package: <b>{payment['pkg_label']}</b>\n"
        f"💰 Amount: ₹<b>{payment['price']}</b>\n"
        f"🎯 Credits: <code>{payment['credits']}</code>\n\n"
        f"🔢 UTR: <code>{utr}</code>\n"
        f"🆔 Pay ID: <code>{pay_id}</code>\n\n"
        f"<i>Approve or Reject below:</i>"
    )

    if payment_group_id:
        try:
            await context.bot.send_photo(
                chat_id=payment_group_id,
                photo=screenshot_file_id,
                caption=forward_text,
                reply_markup=payment_confirm_kb(pay_id),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Forward to group failed: {e}")
            # Fallback: forward to owner
            from config import OWNER_ID
            try:
                await context.bot.send_photo(
                    chat_id=OWNER_ID,
                    photo=screenshot_file_id,
                    caption=forward_text + "\n\n⚠️ <i>Sent to owner (group not set).</i>",
                    reply_markup=payment_confirm_kb(pay_id),
                    parse_mode=ParseMode.HTML
                )
            except Exception as e2:
                logger.error(f"Fallback to owner also failed: {e2}")
    else:
        from config import OWNER_ID
        try:
            await context.bot.send_photo(
                chat_id=OWNER_ID,
                photo=screenshot_file_id,
                caption=forward_text + "\n\n⚠️ <i>Sent to owner (payment group not configured).</i>",
                reply_markup=payment_confirm_kb(pay_id),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Send to owner failed: {e}")

    await update.message.reply_text(
        f"✅ <b>Payment Submitted!</b>\n\n"
        f"🆔 Payment ID: <code>{pay_id}</code>\n"
        f"🔢 UTR: <code>{utr}</code>\n\n"
        f"⏳ Your payment is under review. Credits will be added after admin approval.\n\n"
        f"<i>You'll be notified once approved.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=back_to_main_kb()
    )

async def handle_pay_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Payment cancelled.")
    pay_id = query.data.replace("pay_cancel_", "")
    await update_payment(pay_id, {"status": "cancelled"})
    context.user_data.pop("utr_pay_id", None)
    context.user_data.pop("utr_value", None)
    context.user_data.pop("awaiting", None)
    await safe_edit(query, "❌ Payment cancelled.\n\nYou can start a new payment anytime.", back_to_main_kb())

# ─────────────────────────── Admin: Approve / Reject ───────────────────────────

async def admin_approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    from data_manager import is_admin
    if not await is_admin(query.from_user.id):
        await query.answer("❌ No permission.", show_alert=True)
        return

    await query.answer("Processing approval...")
    pay_id = query.data.replace("admin_approve_", "")
    payment = await get_payment(pay_id)

    if not payment:
        await query.edit_message_caption("❌ Payment not found.", parse_mode=ParseMode.HTML)
        return

    if payment["status"] != "pending":
        await query.edit_message_caption(
            f"ℹ️ Payment already <b>{payment['status']}</b>.",
            parse_mode=ParseMode.HTML
        )
        return

    # Add credits
    await add_credits(payment["user_id"], payment["credits"], f"Purchase: {payment['pkg_label']}")
    await update_payment(pay_id, {"status": "approved"})

    user_data = await get_user(payment["user_id"])

    # Notify user
    try:
        await context.bot.send_message(
            chat_id=payment["user_id"],
            text=(
                f"🎉 <b>Payment Approved!</b>\n\n"
                f"📦 Package: <b>{payment['pkg_label']}</b>\n"
                f"🎯 <code>{payment['credits']}</code> credits added to your account!\n"
                f"💳 New Balance: <code>{user_data['credits']}</code>\n\n"
                f"Thank you for your purchase! 🙏"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=back_to_main_kb()
        )
    except Exception as e:
        logger.error(f"Could not notify user {payment['user_id']}: {e}")

    # Update group message
    try:
        await query.edit_message_caption(
            query.message.caption + f"\n\n✅ <b>APPROVED</b> by @{query.from_user.username or query.from_user.id}",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

async def admin_reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    from data_manager import is_admin
    if not await is_admin(query.from_user.id):
        await query.answer("❌ No permission.", show_alert=True)
        return

    await query.answer("Rejecting...")
    pay_id = query.data.replace("admin_reject_", "")
    payment = await get_payment(pay_id)

    if not payment:
        await query.edit_message_caption("❌ Payment not found.", parse_mode=ParseMode.HTML)
        return

    await update_payment(pay_id, {"status": "rejected"})

    # Notify user
    try:
        await context.bot.send_message(
            chat_id=payment["user_id"],
            text=(
                f"❌ <b>Payment Rejected</b>\n\n"
                f"📦 Package: <b>{payment['pkg_label']}</b>\n"
                f"🔢 UTR: <code>{payment.get('utr', 'N/A')}</code>\n\n"
                f"<i>If you believe this is an error, contact support with your UTR number.</i>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=back_to_main_kb()
        )
    except Exception as e:
        logger.error(f"Could not notify user {payment['user_id']}: {e}")

    try:
        await query.edit_message_caption(
            query.message.caption + f"\n\n❌ <b>REJECTED</b> by @{query.from_user.username or query.from_user.id}",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass
