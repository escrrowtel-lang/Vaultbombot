"""
data_manager.py - JSON file-based storage (no external DB required).

All data stored in /data directory:
  data/users.json        - user records
  data/admin.json        - admin settings
  data/payments.json     - payment records
  data/redeem_codes.json - redeem codes
  data/history.json      - credit history
"""

import json
import logging
import os
import time
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import (
    DEFAULT_CREDITS, LOOKUP_COSTS, OWNER_ID,
    USER_DATA_FILE, ADMIN_DATA_FILE, PAYMENTS_FILE,
)

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

USERS_FILE     = os.path.join(DATA_DIR, "users.json")
ADMIN_FILE     = os.path.join(DATA_DIR, "admin.json")
PAYMENTS_FILE_ = os.path.join(DATA_DIR, "payments.json")
REDEEM_FILE    = os.path.join(DATA_DIR, "redeem_codes.json")
HISTORY_FILE   = os.path.join(DATA_DIR, "history.json")

_lock = asyncio.Lock()


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_json(path: str, default):
    _ensure_data_dir()
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Read error {path}: {e}")
        return default


def _write_json(path: str, data):
    _ensure_data_dir()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp, path)
    except Exception as e:
        logger.error(f"Write error {path}: {e}")


def get_ist_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))


def _now_iso() -> str:
    return get_ist_now().isoformat()


# Users

def _load_users() -> dict:
    return _read_json(USERS_FILE, {})


def _save_users(users: dict):
    _write_json(USERS_FILE, users)


async def get_user(user_id: int, username: str = "", full_name: str = "") -> dict:
    async with _lock:
        users = _load_users()
        uid = str(user_id)
        if uid in users:
            u = users[uid]
            u["last_seen"] = _now_iso()
            if username:
                u["username"] = username
            if full_name:
                u["full_name"] = full_name
            _save_users(users)
            return u
        row = {
            "user_id":        user_id,
            "username":       username,
            "full_name":      full_name,
            "credits":        DEFAULT_CREDITS,
            "total_earned":   DEFAULT_CREDITS,
            "total_spent":    0,
            "lookups_done":   0,
            "referral_code":  f"REF{user_id}",
            "referred_by":    None,
            "referral_count": 0,
            "is_banned":      False,
            "joined_at":      _now_iso(),
            "last_seen":      _now_iso(),
        }
        users[uid] = row
        _save_users(users)
        return row


async def get_all_users() -> list:
    return list(_load_users().values())


async def update_user(user_id: int, updates: dict):
    async with _lock:
        users = _load_users()
        uid = str(user_id)
        if uid in users:
            users[uid].update(updates)
            _save_users(users)


async def add_credits(user_id: int, amount: int, reason: str = ""):
    async with _lock:
        users = _load_users()
        uid = str(user_id)
        if uid not in users:
            return False
        users[uid]["credits"]      += amount
        users[uid]["total_earned"] += amount
        _save_users(users)
    if reason:
        await _add_history(user_id, "credit", amount, reason)
    return True


async def deduct_credits(user_id: int, amount: int, reason: str = "") -> bool:
    async with _lock:
        users = _load_users()
        uid = str(user_id)
        if uid not in users:
            return False
        u = users[uid]
        if u["credits"] < amount:
            return False
        u["credits"]      -= amount
        u["total_spent"]  += amount
        u["lookups_done"] += 1
        _save_users(users)
    if reason:
        await _add_history(user_id, "debit", amount, reason)
    return True


async def set_user_credits(user_id: int, amount: int) -> bool:
    async with _lock:
        users = _load_users()
        uid = str(user_id)
        if uid not in users:
            return False
        users[uid]["credits"] = amount
        _save_users(users)
    return True


async def ban_user(user_id: int):
    await update_user(user_id, {"is_banned": True})


async def unban_user(user_id: int):
    await update_user(user_id, {"is_banned": False})


async def apply_referral(new_user_id: int, referral_code: str) -> bool:
    from config import REFERRAL_CREDITS, REFERRED_CREDITS
    async with _lock:
        users = _load_users()
        referrer_uid = None
        referrer = None
        for uid, u in users.items():
            if u.get("referral_code") == referral_code:
                referrer_uid = uid
                referrer = u
                break
        if not referrer:
            return False
        if referrer["user_id"] == new_user_id:
            return False
        new_uid = str(new_user_id)
        if new_uid not in users:
            return False
        if users[new_uid].get("referred_by"):
            return False
        users[new_uid]["referred_by"]    = referrer["user_id"]
        users[new_uid]["credits"]        += REFERRED_CREDITS
        users[new_uid]["total_earned"]   += REFERRED_CREDITS
        users[referrer_uid]["credits"]      += REFERRAL_CREDITS
        users[referrer_uid]["total_earned"] += REFERRAL_CREDITS
        users[referrer_uid]["referral_count"] = users[referrer_uid].get("referral_count", 0) + 1
        _save_users(users)
    return True


# History

def _load_history() -> list:
    return _read_json(HISTORY_FILE, [])


def _save_history(history: list):
    _write_json(HISTORY_FILE, history)


async def _add_history(user_id: int, entry_type: str, amount: int, reason: str):
    async with _lock:
        history = _load_history()
        history.append({
            "user_id":    user_id,
            "type":       entry_type,
            "amount":     amount,
            "reason":     reason,
            "created_at": _now_iso(),
        })
        if len(history) > 10000:
            history = history[-10000:]
        _save_history(history)


async def get_user_history(user_id: int, limit: int = 15) -> list:
    history = _load_history()
    user_hist = [h for h in history if h.get("user_id") == user_id]
    return list(reversed(user_hist[-limit:]))


async def add_lookup_history(user_id: int, lookup_type: str, query: str, result_summary: str):
    cost = LOOKUP_COSTS.get(f"{lookup_type}_lookup", 0)
    await _add_history(user_id, lookup_type, cost,
                       f"{lookup_type}:{query} -> {result_summary[:80]}")


# Admin Settings

_ADMIN_DEFAULTS = {
    "payment_group_id": None,
    "upi_id":           None,
    "upi_name":         "Vault Bot",
    "qr_file_id":       None,
    "maintenance":      False,
    "credit_packages": [
        {"id": "pkg_1", "credits": 50,   "price": 29,  "label": "Starter"},
        {"id": "pkg_2", "credits": 150,  "price": 79,  "label": "Popular"},
        {"id": "pkg_3", "credits": 400,  "price": 179, "label": "Pro"},
        {"id": "pkg_4", "credits": 1000, "price": 399, "label": "Elite"},
    ],
    "admins": [],
}


def _load_admin() -> dict:
    stored = _read_json(ADMIN_FILE, {})
    data = dict(_ADMIN_DEFAULTS)
    data.update(stored)
    return data


def _save_admin(data: dict):
    _write_json(ADMIN_FILE, data)


async def load_admin_data() -> dict:
    return _load_admin()


async def set_admin_setting(key: str, value):
    async with _lock:
        data = _load_admin()
        data[key] = value
        _save_admin(data)


async def save_admin_data(data: dict):
    async with _lock:
        current = _load_admin()
        current.update(data)
        _save_admin(current)


async def get_admin_setting(key: str):
    d = _load_admin()
    return d.get(key)


async def is_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    d = _load_admin()
    return user_id in d.get("admins", [])


async def add_admin(user_id: int):
    async with _lock:
        data = _load_admin()
        admins = data.get("admins", [])
        if user_id not in admins:
            admins.append(user_id)
        data["admins"] = admins
        _save_admin(data)


async def remove_admin(user_id: int):
    async with _lock:
        data = _load_admin()
        data["admins"] = [a for a in data.get("admins", []) if a != user_id]
        _save_admin(data)


# Redeem Codes

def _load_redeem() -> dict:
    return _read_json(REDEEM_FILE, {})


def _save_redeem(codes: dict):
    _write_json(REDEEM_FILE, codes)


async def create_redeem_code(code: str, credits: int, max_uses: int = 1):
    async with _lock:
        codes = _load_redeem()
        codes[code.upper()] = {
            "code":     code.upper(),
            "credits":  credits,
            "uses":     0,
            "max_uses": max_uses,
        }
        _save_redeem(codes)


async def delete_redeem_code(code: str):
    async with _lock:
        codes = _load_redeem()
        codes.pop(code.upper(), None)
        _save_redeem(codes)


async def use_redeem_code(code: str) -> Optional[int]:
    async with _lock:
        codes = _load_redeem()
        rc = codes.get(code.upper())
        if not rc:
            return None
        if rc["uses"] >= rc["max_uses"]:
            return None
        rc["uses"] += 1
        codes[code.upper()] = rc
        _save_redeem(codes)
    return rc["credits"]


async def list_redeem_codes() -> list:
    return list(_load_redeem().values())


# Payments

def _load_payments() -> dict:
    return _read_json(PAYMENTS_FILE_, {})


def _save_payments(payments: dict):
    _write_json(PAYMENTS_FILE_, payments)


async def create_payment(user_id: int, pkg_id: str, credits: int, price: int, pkg_label: str) -> str:
    pay_id = f"PAY{user_id}{int(time.time())}"
    async with _lock:
        payments = _load_payments()
        payments[pay_id] = {
            "pay_id":     pay_id,
            "user_id":    user_id,
            "pkg_id":     pkg_id,
            "pkg_label":  pkg_label,
            "credits":    credits,
            "price":      price,
            "utr":        None,
            "screenshot": None,
            "status":     "pending",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        _save_payments(payments)
    return pay_id


async def update_payment(pay_id: str, updates: dict):
    async with _lock:
        payments = _load_payments()
        if pay_id in payments:
            updates["updated_at"] = _now_iso()
            payments[pay_id].update(updates)
            _save_payments(payments)


async def get_payment(pay_id: str) -> Optional[dict]:
    return _load_payments().get(pay_id)


async def get_pending_payments() -> list:
    return [p for p in _load_payments().values() if p.get("status") == "pending"]

# ─────────────────────────── Firebase Instances ───────────────────────────

async def list_all_firebase() -> list:
    """Return all firebase instances stored in admin_settings."""
    d = await load_admin_data()
    return d.get("firebase_list", [])

async def add_firebase(name: str, url: str, password: str = "") -> dict:
    """Add a new firebase instance. Returns the new entry."""
    import time
    d = await load_admin_data()
    fb_list = d.get("firebase_list", [])
    entry = {
        "id":       f"fb_{int(time.time())}",
        "name":     name.strip(),
        "url":      url.strip().rstrip("/"),
        "password": password.strip(),
    }
    fb_list.append(entry)
    await set_admin_setting("firebase_list", fb_list)
    return entry

async def remove_firebase(fb_id: str) -> bool:
    """Remove firebase instance by id. Returns True if removed."""
    d = await load_admin_data()
    fb_list = d.get("firebase_list", [])
    new_list = [f for f in fb_list if f["id"] != fb_id]
    if len(new_list) == len(fb_list):
        return False
    await set_admin_setting("firebase_list", new_list)
    return True
