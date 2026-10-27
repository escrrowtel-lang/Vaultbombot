# 🛡️ Vaultbombot

> Telegram bot with OSINT lookups, SMS bomber, credit system, UPI payments & admin panel.

---

## ✨ Features

- 🔍 **OSINT Lookups** — Phone, IP, Email, Username, Address, Plate, Social, Name
- 💣 **SMS Bomber** — API bomb & custom message bomb modes
- 💰 **Credit System** — Buy credits via UPI, redeem codes, referrals
- 👑 **Admin Panel** — Full control over users, packages, payments, settings
- 📲 **UPI Payments** — QR + UTR verification flow with approve/reject
- 🗄️ **Supabase + JSON** — Dual persistence layer

---

## 📁 Project Structure

```
Vaultbombot/
├── main.py               ← Entry point
├── config.py             ← All config constants
├── data_manager.py       ← JSON persistence layer
├── keyboards.py          ← Inline button layouts
├── handlers_user.py      ← User-facing handlers
├── handlers_payment.py   ← Buy credits / payment flow
├── handlers_admin.py     ← Admin panel handlers
├── handlers_bomber.py    ← Bomber handlers
├── bomber_service.py     ← Bomber core logic
├── requirements.txt
├── render.yaml           ← Render deploy config
├── supabase_schema.sql   ← DB schema
└── BOT_SETUP.md          ← Full setup guide
```

---

## ⚙️ Local Setup

```bash
git clone https://github.com/escrrowtel-lang/Vaultbombot.git
cd Vaultbombot
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add BOT_TOKEN, OWNER_ID, SUPABASE_URL, SUPABASE_KEY
python main.py
```

---

## 🚀 Deploy on Render

1. Push code to GitHub
2. Go to [render.com](https://render.com) → **New → Background Worker**
3. Connect this repo
4. **Build Command:** `pip install -r requirements.txt`
5. **Start Command:** `python main.py`
6. Add environment variables:

| Variable | Value |
|----------|-------|
| `BOT_TOKEN` | From @BotFather |
| `OWNER_ID` | Your Telegram user ID |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | `service_role` key (not anon) |

7. Add a **Disk** → Mount path: `/opt/render/project/src/data` (1 GB)

> ⚠️ Without the disk, data resets on every deploy.

---

## 🤖 Bot Commands

| Command | Access | Description |
|---------|--------|-------------|
| `/start` | Everyone | Register + main menu |
| `/admin` | Admins | Open admin panel |

---

## 💳 Default Credit Packages

| Package | Credits | Price |
|---------|---------|-------|
| Starter | 50 | ₹29 |
| Popular | 150 | ₹79 |
| Pro | 400 | ₹179 |
| Elite | 1000 | ₹399 |

> Editable via Admin Panel → Credit Packages

---

## 🔍 Lookup Costs (Credits)

| Lookup | Credits |
|--------|---------|
| Phone | 5 |
| IP | 3 |
| Email | 5 |
| Username | 4 |
| Address | 8 |
| Plate | 6 |
| Social | 5 |
| Name | 4 |

---

## 💣 Bomber Defaults

| Mode | Credits/Run | Default Qty |
|------|-------------|-------------|
| API Bomb | 10 | 1 cycle |
| Custom Bomb | 5 | 50 msgs |

> Configurable via Admin Panel

---

## 📲 User Flow

```
/start
  └── Main Menu
       ├── 🔍 LOOKUPS    → Pick type → Enter query → Confirm → Result
       ├── 💣 BOMBER     → Pick mode → Enter target → Confirm → Execute
       ├── 👤 My Profile → Credits, stats, referral code
       ├── 💰 Buy Credits → Pick package → UPI QR → Pay → Submit UTR+SS → Approve
       ├── 🎟️ Redeem Code → Enter code → Credits added
       ├── 👥 Referral   → Share link → Earn 25 credits per signup
       └── 📜 History    → Last 15 lookups/transactions
```

---

## 💸 Payment Flow

```
User picks package
  → Bot shows QR + UPI ID + amount
  → User pays via UPI app
  → User clicks "I've Paid"
  → Bot asks for UTR number
  → Bot asks for screenshot
  → Forwarded to payment group with [Approve] [Reject]
  → Admin approves → credits added + user notified
  → Admin rejects  → user notified with UTR for dispute
```

---

## 🛠️ Admin Panel

- User management (credits, ban, add admin)
- Credit packages editor
- Payment setup (UPI ID, QR image, payment group)
- Bomber settings (credits & quantity per mode)
- Broadcast to all users
- Stats & logs

---

## 📦 Dependencies

```
python-telegram-bot==21.5
python-dotenv==1.0.1
supabase==2.7.4
aiohttp==3.9.5
```

---

## 📄 License

Private. All rights reserved.
