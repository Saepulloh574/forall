import asyncio
import json
import os
import re
import sys
import time
import math
import html
import socket
import logging
import threading
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# --- Third Party Imports ---
import requests
from dotenv import load_dotenv
from flask import Flask
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder

# ==============================================================================
# 1. KONFIGURASI GLOBAL & ENV
# ==============================================================================
load_dotenv()

# Setup Logging sederhana
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.ERROR)

# --- FOLDER SETUP ---
# Menggunakan folder 'data' agar rapi, atau root jika sesuai request path asli
DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER): os.makedirs(DATA_FOLDER)

# Path File (Disatukan path-nya agar semua modul membaca file yang sama)
OTP_SAVE_FILE = os.path.join(DATA_FOLDER, "smc.json")
WAIT_JSON_FILE = os.path.join(DATA_FOLDER, "wait.json")
USER_FILE = os.path.join(DATA_FOLDER, "user.json")
CACHE_FILE = os.path.join(DATA_FOLDER, "cache.json")
INLINE_RANGE_FILE = os.path.join(DATA_FOLDER, "inline.json")
AKSES_GET10_FILE = os.path.join(DATA_FOLDER, "aksesget10.json")
PROFILE_FILE = os.path.join(DATA_FOLDER, "profile.json")
RANGE_CACHE_FILE = os.path.join(DATA_FOLDER, "range_cache_mnit.json")

# URL & NETWORK
LOGIN_URL = "https://x.mnitnetwork.com/mauth/login"
DASHBOARD_INFO_URL = "https://x.mnitnetwork.com/mdashboard/getnum" # Digunakan message.py & get.py
DASHBOARD_CONSOLE_URL = "https://x.mnitnetwork.com/mdashboard/console" # Digunakan range.py
CHROME_DEBUG_URL = "http://127.0.0.1:9222"

# --- TOKEN & ID CONFIGURATION (MAPPING DARI .ENV) ---

# 1. Message Bot Config
MSG_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_MSG")
MSG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_MSG")
try: MSG_ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID_MSG") or 0)
except: MSG_ADMIN_ID = None
MSG_BOT_LINK = "https://t.me/myzuraisgoodbot" # Sesuai script asli
MSG_ADMIN_LINK = "https://t.me/Imr1d"

# 2. Get Bot Config
GET_BOT_TOKEN = os.getenv("BOT_TOKEN_GET")
try:
    GET_GROUP_ID_1 = int(os.getenv("GROUP_ID_1") or 0)
    GET_GROUP_ID_2 = int(os.getenv("GROUP_ID_2") or 0)
    GET_ADMIN_ID = int(os.getenv("ADMIN_ID_GET") or 0)
except:
    GET_GROUP_ID_1 = GET_GROUP_ID_2 = GET_ADMIN_ID = 0

GET_API_URL = f"https://api.telegram.org/bot{GET_BOT_TOKEN}"
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1"
GROUP_LINK_2 = "https://t.me/zura14g"

# 3. Range Bot Config
RANGE_BOT_TOKEN = os.getenv("BOT_TOKEN_RANGE")
RANGE_CHAT_ID = os.getenv("CHAT_ID_RANGE")
try: RANGE_ADMIN_ID = int(os.getenv("ADMIN_ID_RANGE") or 0)
except: RANGE_ADMIN_ID = None

# --- CONSTANTS LAINNYA ---
OTP_PRICE = 0.003500
MIN_WD_AMOUNT = 1.000000
WAIT_TIMEOUT_SECONDS = int(os.getenv("WAIT_TIMEOUT_SECONDS", 1800))
EXTENDED_WAIT_SECONDS = 300

# ==============================================================================
# 2. SHARED UTILS (EMOJI & HELPERS)
# ==============================================================================

# Master Country Emoji (Gabungan terlengkap)
MASTER_COUNTRY_EMOJI = {
  "AFGHANISTAN": "🇦🇫", "ALBANIA": "🇦🇱", "ALGERIA": "🇩🇿", "ANDORRA": "🇦🇩", "ANGOLA": "🇦🇴",
  "ANTIGUA AND BARBUDA": "🇦🇬", "ARGENTINA": "🇦🇷", "ARMENIA": "🇦🇲", "AUSTRALIA": "🇦🇺", "AUSTRIA": "🇦🇹",
  "AZERBAIJAN": "🇦🇿", "BAHAMAS": "🇧🇸", "BAHRAIN": "🇧🇭", "BANGLADESH": "🇧🇩", "BARBADOS": "🇧🇧",
  "BELARUS": "🇧🇾", "BELGIUM": "🇧🇪", "BELIZE": "🇧🇿", "BENIN": "🇧🇯", "BHUTAN": "🇧🇹",
  "BOLIVIA": "🇧🇴", "BOSNIA AND HERZEGOVINA": "🇧🇦", "BOTSWANA": "🇧🇼", "BRAZIL": "🇧🇷", "BRUNEI": "🇧🇳",
  "BULGARIA": "🇧🇬", "BURKINA FASO": "🇧🇫", "BURUNDI": "🇧🇮", "CAMBODIA": "🇰🇭", "CAMEROON": "🇨🇲",
  "CANADA": "🇨🇦", "CAPE VERDE": "🇨🇻", "CENTRAL AFRICAN REPUBLIC": "🇨🇫", "CHAD": "🇹🇩", "CHILE": "🇨🇱",
  "CHINA": "🇨🇳", "COLOMBIA": "🇨🇴", "COMOROS": "🇰🇲", "CONGO": "🇨🇬", "COSTA RICA": "🇨🇷",
  "CROATIA": "🇭🇷", "CUBA": "🇨🇺", "CYPRUS": "🇨🇾", "CZECH REPUBLIC": "🇨🇿", "IVORY COAST": "🇨🇮",
  "DENMARK": "🇩🇰", "DJIBOUTI": "🇩🇯", "DOMINICA": "🇩🇲", "DOMINICAN REPUBLIC": "🇩🇴", "ECUADOR": "🇪🇨",
  "EGYPT": "🇪🇬", "EL SALVADOR": "🇸🇻", "EQUATORIAL GUINEA": "🇬🇶", "ERITREA": "🇪🇷", "ESTONIA": "🇪🇪",
  "ESWATINI": "🇸🇿", "ETHIOPIA": "🇪🇹", "FIJI": "🇫🇯", "FINLAND": "🇫🇮", "FRANCE": "🇫🇷",
  "GABON": "🇬🇦", "GAMBIA": "🇬🇲", "GEORGIA": "🇬🇪", "GERMANY": "🇩🇪", "GHANA": "🇬🇭",
  "GREECE": "🇬🇷", "GRENADA": "🇬🇹", "GUATEMALA": "🇬🇹", "GUINEA": "🇬🇳", "GUINEA-BISSAU": "🇬🇼",
  "GUYANA": "🇬🇾", "HAITI": "🇭🇹", "HONDURAS": "🇭🇳", "HUNGARY": "🇭🇺", "ICELAND": "🇮🇸",
  "INDIA": "🇮🇳", "INDONESIA": "🇮🇩", "IRAN": "🇮🇷", "IRAQ": "🇮🇶", "IRELAND": "🇮🇪",
  "ISRAEL": "🇮🇱", "ITALY": "🇮🇹", "JAMAICA": "🇯🇲", "JAPAN": "🇯🇵", "JORDAN": "🇯🇴",
  "KAZAKHSTAN": "🇰🇿", "KENYA": "🇰🇪", "KIRIBATI": "🇰🇮", "KUWAIT": "🇰🇼", "KYRGYZSTAN": "🇰🇬",
  "LAOS": "🇱🇦", "LATVIA": "🇱🇻", "LEBANON": "🇱🇧", "LESOTHO": "🇱🇸", "LIBERIA": "🇱🇷",
  "LIBYA": "🇱🇾", "LIECHTENSTEIN": "🇱🇮", "LITHUANIA": "🇱🇹", "LUXEMBOURG": "🇱🇺", "MADAGASCAR": "🇲🇬",
  "MALAWI": "🇲🇼", "MALAYSIA": "🇲🇾", "MALDIVES": "🇲🇻", "MALI": "🇲🇱", "MALTA": "🇲🇹",
  "MARSHALL ISLANDS": "🇲🇭", "MAURITANIA": "🇲🇷", "MAURITIUS": "🇲🇺", "MEXICO": "🇲🇽", "MICRONESIA": "🇫🇲",
  "MOLDOVA": "🇲🇩", "MONACO": "🇲🇨", "MONGOLIA": "🇲🇳", "MONTENEGRO": "🇲🇪", "MOROCCO": "🇲🇦",
  "MOZAMBIQUE": "🇲🇿", "MYANMAR": "🇲🇲", "NAMIBIA": "🇳🇦", "NAURU": "🇳🇷", "NEPAL": "🇳🇵",
  "NETHERLANDS": "🇳🇱", "NEW ZEALAND": "🇳🇿", "NICARAGUA": "🇳🇮", "NIGER": "🇳🇪", "NIGERIA": "🇳🇬",
  "NORTH KOREA": "🇰🇵", "NORTH MACEDONIA": "🇲🇰", "NORWAY": "🇳🇴", "OMAN": "🇴🇲", "PAKISTAN": "🇵🇰",
  "PALAU": "🇵🇼", "PALESTINE": "🇵🇸", "PANAMA": "🇵🇦", "PAPUA NEW GUINEA": "🇵🇬", "PARAGUAY": "🇵🇾",
  "PERU": "🇵🇪", "PHILIPPINES": "🇵🇭", "POLAND": "🇵🇱", "PORTUGAL": "🇵🇹", "QATAR": "🇶🇦",
  "ROMANIA": "🇷🇴", "RUSSIA": "🇷🇺", "RWANDA": "🇷🇼", "SAINT KITTS AND NEVIS": "🇰🇳", "SAINT LUCIA": "🇱🇨",
  "SAINT VINCENT AND THE GRENADINES": "🇻🇨", "SAMOA": "🇼🇸", "SAN MARINO": "🇸🇲", "SAO TOME AND PRINCIPE": "🇸🇹",
  "SAUDI ARABIA": "🇸🇦", "SENEGAL": "🇸🇳", "SERBIA": "🇷🇸", "SEYCHELLES": "🇸🇨", "SIERRA LEONE": "🇸🇱",
  "SINGAPORE": "🇸🇬", "SLOVAKIA": "🇸🇰", "SLOVENIA": "🇸🇮", "SOLOMON ISLANDS": "🇸🇧", "SOMALIA": "🇸🇴",
  "SOUTH AFRICA": "🇿🇦", "SOUTH KOREA": "🇰🇷", "SOUTH SUDAN": "🇸🇸", "SPAIN": "🇪🇸", "SRI LANKA": "🇱🇰", 
  "SUDAN": "🇸🇩", "SURINAME": "🇸🇷", "SWEDEN": "🇸🇪", "SWITZERLAND": "🇨🇭", "SYRIA": "🇸🇾",
  "TAJIKISTAN": "🇹🇯", "TANZANIA": "🇹🇿", "THAILAND": "🇹🇭", "TIMOR-LESTE": "🇹🇱", "TOGO": "🇹🇬",
  "TONGA": "🇹🇴", "TRINIDAD AND TOBAGO": "🇹🇹", "TUNISIA": "🇹🇳", "TURKEY": "🇹🇷", "TURKMENISTAN": "🇹🇲",
  "TUVALU": "🇹🇻", "UGANDA": "🇺🇬", "UKRAINE": "🇺🇦", "UNITED ARAB EMIRATES": "🇦🇪", "UNITED KINGDOM": "🇬🇧",
  "UNITED STATES": "🇺🇸", "URUGUAY": "🇺🇾", "UZBEKISTAN": "🇺🇿", "VANUATU": "🇻🇺", "VATICAN CITY": "🇻🇦",
  "VENEZUELA": "🇻🇪", "VIETNAM": "🇻🇳", "YEMEN": "🇾🇪", "ZAMBIA": "🇿🇲", "ZIMBABWE": "🇿🇼", "KOSOVO": "🇽🇰", "UNKNOWN": "🗺️"
}

def get_country_emoji(country_name: str) -> str:
    return MASTER_COUNTRY_EMOJI.get(country_name.strip().upper(), "🌍")

def clean_phone_number(phone):
    if not phone: return "N/A"
    cleaned = re.sub(r'[^0-9X]', '', phone) 
    return cleaned or phone

def normalize_number(number):
    normalized_number = str(number).strip().replace(" ", "").replace("-", "")
    if not normalized_number.startswith('+') and normalized_number.isdigit():
        normalized_number = '+' + normalized_number
    return normalized_number

def clean_service_name(service):
    if not service: return "Unknown"
    maps = {
        'facebook': 'Facebook', 'whatsapp': 'WhatsApp', 'instagram': 'Instagram', 
        'telegram': 'Telegram', 'google': 'Google', 'twitter': 'Twitter', 
        'tiktok': 'TikTok', 'laz+nxcar': 'Facebook', 'mnitnetwork': 'M-NIT Network',
    }
    s_lower = service.strip().lower()
    for k, v in maps.items():
        if k in s_lower: return v
    if s_lower in ['ваш', 'your', 'service', 'code', 'pin']: return "Unknown Service"
    return service.strip().title()

# --- FILE I/O HELPERS ---
def load_json_file(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding='utf-8') as f:
            try: return json.load(f)
            except:
                if filename == PROFILE_FILE: return {}
                return []
    if filename == PROFILE_FILE: return {}
    return []

def save_json_file(filename, data):
    with open(filename, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=True)

# ==============================================================================
# 3. MODUL: MESSAGE BOT (Ported from message.py)
# ==============================================================================

# Global State untuk Message Bot
MSG_BOT_STATUS = {"status": "Starting", "uptime": "--", "total_otps_sent": 0, "monitoring_active": False}
MSG_START_TIME = time.time()
MSG_AWAITING_CREDENTIALS = False

class MessageOTPFilter:
    CLEANUP_KEY = '__LAST_CLEANUP_GMT__' 
    def __init__(self, file='otp_cache.json'): 
        # Simpan di DATA_FOLDER
        self.file = os.path.join(DATA_FOLDER, file)
        self.cache = self._load()
        self.last_cleanup_date_gmt = self.cache.pop(self.CLEANUP_KEY, '19700101') 
        self._cleanup() 
        
    def _load(self):
        if os.path.exists(self.file):
            try: return json.load(open(self.file, 'r'))
            except: return {}
        return {}
        
    def _save(self): 
        temp = self.cache.copy()
        temp[self.CLEANUP_KEY] = self.last_cleanup_date_gmt
        json.dump(temp, open(self.file,'w'), indent=2)
    
    def _cleanup(self):
        now_gmt = datetime.now(timezone.utc).strftime('%Y%m%d')
        if now_gmt > self.last_cleanup_date_gmt:
            self.cache = {}; self.last_cleanup_date_gmt = now_gmt
            self._save()
        
    def filter(self, lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for d in lst:
            key = f"{d.get('otp')}_{d.get('phone')}"
            if d.get('otp') and key not in self.cache:
                self.cache[key] = {'t': datetime.now().isoformat()}
                out.append(d)
        self._save()
        return out

msg_otp_filter = MessageOTPFilter()

class MessageMonitor:
    def __init__(self, url=DASHBOARD_INFO_URL): 
        self.url, self.browser, self.page, self.is_logged_in = url, None, None, False
        self._temp_username, self._temp_password = None, None

    async def initialize(self, p_instance):
        # Kita menggunakan browser yang sama dari Main Loop
        try:
            self.browser = await p_instance.chromium.connect_over_cdp(CHROME_DEBUG_URL)
            self.page = await self.browser.contexts[0].new_page() 
            print("✅ [MESSAGE BOT] Playwright Connected.")
        except Exception as e:
            print(f"⚠️ [MESSAGE BOT] Connection error (bisa jadi share browser): {e}")

    async def check_url_login_status(self) -> bool:
        if not self.page: return False
        try:
            self.is_logged_in = "mdashboard" in self.page.url
            return self.is_logged_in
        except: return False

    async def login(self):
        if not self.page: raise Exception("Page not initialized.")
        await self.page.goto(LOGIN_URL, wait_until='load', timeout=15000) 
        await self.page.type('input[type="email"]', self._temp_username) 
        await self.page.type('input[type="password"]', self._temp_password)
        await self.page.click('button[type="submit"]') 
        try:
            await self.page.wait_for_url(re.compile(r".*/mdashboard.*"), timeout=30000) 
            self.is_logged_in = True
            return True
        except: return False

    async def fetch_sms(self) -> List[Dict[str, Any]]:
        if not self.page or not self.is_logged_in: return []
        messages = []
        try:
            # Gunakan try-except untuk handling jika URL berubah
            if "getnum" not in self.page.url:
                 return []
                 
            async with self.page.expect_response(lambda r: "/getnum/info" in r.url, timeout=5000) as resp_info:
                try: await self.page.click('th:has-text("Number Info")', timeout=1000)
                except: pass # Jika gagal klik, mungkin sudah load atau auto refresh

                response = await resp_info.value
                json_data = await response.json()
                
                numbers = json_data.get('data', {}).get('numbers', [])
                for item in numbers:
                    if item.get('status') == 'success' and item.get('message'):
                        raw_msg = item.get('message')
                        messages.append({
                            "otp": self.extract_otp_from_text(raw_msg),
                            "phone": "+" + str(item.get('number')),
                            "service": item.get('full_number') or "Facebook",
                            "range": item.get('country', 'N/A'),
                            "raw_message": raw_msg
                        })
        except: pass
        return messages

    def extract_otp_from_text(self, text):
        if not text: return None
        patterns = [
            r'(\d{3}[\s-]\d{3})', 
            r'(?:code|otp|kode)[:\s]*([\d\s-]+)', 
            r'\b(\d{4,8})\b'
        ]
        for p in patterns:
            m = re.search(p, text, re.I)
            if m:
                otp = re.sub(r'[^\d]', '', m.group(1) if m.groups() else m.group(0))
                if otp: return otp
        return None

message_monitor = MessageMonitor()

def msg_get_user_data(phone_number: str) -> Dict[str, Any]:
    if not os.path.exists(WAIT_JSON_FILE): return {"username": "unknown", "user_id": None}
    try:
        with open(WAIT_JSON_FILE, 'r') as f:
            wait_list = json.load(f)
            clean_target = re.sub(r'[^\d]', '', phone_number)
            for entry in wait_list:
                clean_entry = re.sub(r'[^\d]', '', str(entry.get("number", "")))
                if clean_target == clean_entry:
                    return {"username": entry.get("username", "unknown"), "user_id": entry.get("user_id")}
    except: pass
    return {"username": "unknown", "user_id": None}

def msg_mask_phone_number_zura(phone):
    if not phone or phone == "N/A": return phone
    digits = re.sub(r'[^\d]', '', phone)
    if len(digits) < 7: return phone
    prefix = phone[0] if phone.startswith('+') else ""
    return f"{prefix}{digits[:5]}***{digits[-4:]}"

def msg_format_otp_message(otp_data: Dict[str, Any]) -> str:
    otp, phone = otp_data.get('otp', 'N/A'), otp_data.get('phone', 'N/A')
    user_info = msg_get_user_data(phone)
    user_tag = f"@{user_info['username'].replace('@', '')}" if user_info['username'] != "unknown" else "unknown"
    raw_msg = html.escape(otp_data.get('raw_message', 'No message content'))

    return (
        f"💭 <b>New Message Received</b>\n\n"
        f"<b>👤 User:</b> {user_tag}\n"
        f"<b>📱 Number:</b> <code>{msg_mask_phone_number_zura(phone)}</code>\n"
        f"<b>🌍 Country:</b> <b>{otp_data.get('range')} {get_country_emoji(otp_data.get('range', ''))}</b>\n"
        f"<b>✅ Service:</b> <b>{otp_data.get('service')}</b>\n\n"
        f"🔐 OTP: <code>{otp}</code>\n\n"
        f"<b>FULL MESSAGE:</b>\n"
        f"<blockquote>{raw_msg}</blockquote>"
    )

def msg_create_inline_keyboard(otp: str):
    keyboard = {
        "inline_keyboard": [
            [{"text": f"{otp}", "copy_text": {"text": otp}}, {"text": "🎭 Owner", "url": MSG_ADMIN_LINK}],
            [{"text": "📞 Get Number", "url": MSG_BOT_LINK}]
        ]
    }
    return json.dumps(keyboard)

def msg_send_tg(text, with_inline_keyboard=False, target_chat_id=None, otp_code=None):
    cid = target_chat_id if target_chat_id is not None else MSG_CHAT_ID
    if not MSG_BOT_TOKEN or not cid: return
    payload = {'chat_id': cid, 'text': text, 'parse_mode': 'HTML'}
    if with_inline_keyboard and otp_code: payload['reply_markup'] = msg_create_inline_keyboard(otp_code)
    try:
        requests.post(f"https://api.telegram.org/bot{MSG_BOT_TOKEN}/sendMessage", json=payload, timeout=15)
    except: pass

def msg_save_otp_to_json(otp_data: Dict[str, Any]):
    # Menyimpan data untuk SMS Forwarder (sms.py logic)
    data = {
        "service": otp_data.get('service', 'Unknown'),
        "number": otp_data.get('phone', 'N/A'),
        "otp": otp_data.get('otp', 'N/A'),
        "full_message": otp_data.get('raw_message', '')
    }
    try:
        existing = load_json_file(OTP_SAVE_FILE)
        existing.append(data)
        save_json_file(OTP_SAVE_FILE, existing)
    except: pass

async def msg_wait_for_realtime_change(page):
    try:
        await page.wait_for_selector('tbody', timeout=30000)
        return await page.evaluate('''
            () => {
                return new Promise((resolve) => {
                    const target = document.querySelector('tbody');
                    if (!target) { resolve(false); return; }
                    const observer = new MutationObserver(() => {
                        observer.disconnect();
                        resolve(true);
                    });
                    observer.observe(target, { childList: true, subtree: true });
                    setTimeout(() => { observer.disconnect(); resolve(false); }, 15000); 
                });
            }
        ''')
    except: return False

async def task_message_bot_loop(shared_browser_context):
    global MSG_BOT_STATUS, MSG_AWAITING_CREDENTIALS
    
    # Init Page di context yang sama
    try:
        if shared_browser_context:
            message_monitor.page = await shared_browser_context.new_page()
            # Cek login via cookies context
            await message_monitor.check_url_login_status()
            print("✅ [MESSAGE BOT] Initialized on Shared Context")
    except Exception as e:
        print(f"⚠️ [MESSAGE BOT] Init Error: {e}")
        return

    # Polling Telegram Command (Sederhana via Requests)
    last_update_id = 0
    
    while True:
        # 1. Telegram Command Check
        try:
            upd = requests.get(f"https://api.telegram.org/bot{MSG_BOT_TOKEN}/getUpdates?offset={last_update_id+1}", timeout=2).json()
            for u in upd.get("result", []):
                last_update_id = u["update_id"]
                m = u.get("message", {})
                text, user_id = m.get("text", ""), m.get("from", {}).get("id")
                if user_id != MSG_ADMIN_ID: continue

                if MSG_AWAITING_CREDENTIALS:
                    parts = text.split()
                    if len(parts) == 2:
                        message_monitor._temp_username, message_monitor._temp_password = parts[0], parts[1]
                        MSG_AWAITING_CREDENTIALS = False
                        # Trigger Login Task (Fire and forget or await)
                        await message_monitor.login()
                        msg_send_tg("✅ Login Attempted.", target_chat_id=user_id)
                    continue

                if text == "/status":
                    upt = str(timedelta(seconds=int(time.time() - MSG_START_TIME)))
                    msg = f"🤖 <b>Bot Zura Status</b>\n⚡ Live: {'✅' if MSG_BOT_STATUS['monitoring_active'] else '⏸️'}\nUptime: <code>{upt}</code>\nTotal Sent: <b>{MSG_BOT_STATUS['total_otps_sent']}</b>"
                    msg_send_tg(msg, target_chat_id=user_id)
                elif text == "/login": 
                    MSG_AWAITING_CREDENTIALS = True; msg_send_tg("🔑 Email Password (spasi):", target_chat_id=user_id)
                elif text == "/startnew": 
                    MSG_BOT_STATUS["monitoring_active"] = True; msg_send_tg("▶️ Real-time Mode Started.", target_chat_id=user_id)
                elif text == "/stop": 
                    MSG_BOT_STATUS["monitoring_active"] = False; msg_send_tg("⏸️ Monitoring Stopped.", target_chat_id=user_id)
        except: pass

        # 2. Monitoring Logic
        try:
            await message_monitor.check_url_login_status()
            if MSG_BOT_STATUS["monitoring_active"] and message_monitor.is_logged_in:
                # Pastikan di halaman info
                if "getnum" not in message_monitor.page.url:
                    await message_monitor.page.goto(DASHBOARD_INFO_URL)

                msgs = await message_monitor.fetch_sms()
                new_otps = msg_otp_filter.filter(msgs)
                
                if new_otps:
                    print(f"📩 [MESSAGE BOT] {len(new_otps)} OTPs found.")
                    for otp_data in new_otps:
                        msg_save_otp_to_json(otp_data)
                        msg_send_tg(msg_format_otp_message(otp_data), with_inline_keyboard=True, otp_code=otp_data['otp'])
                        MSG_BOT_STATUS['total_otps_sent'] += 1
                        await asyncio.sleep(1)
                
                await msg_wait_for_realtime_change(message_monitor.page)
            else:
                await asyncio.sleep(2)
        except Exception as e:
            # print(f"⚠️ [MESSAGE LOOP ERROR] {e}")
            await asyncio.sleep(2)

# ==============================================================================
# 4. MODUL: GET BOT (Ported from get.py)
# ==============================================================================

# Global Var Get Bot
playwright_lock = asyncio.Lock()
shared_page = None 
get_waiting_broadcast_input = set() 
get_broadcast_message = {} 
get_verified_users = set()
get_waiting_admin_input = set()
get_manual_range_input = set() 
get_get10_range_input = set()
get_waiting_dana_input = set() 
get_pending_message = {}
get_last_used_range = {}

# Progress Bar Logic
STATUS_MAP = {
    0:  "Menunggu di antrian sistem aktif..",
    3:  "Mengirim permintaan nomor baru go.",
    4:  "Memulai pencarian di tabel data..",
    5:  "Mencari nomor pada siklus satu run",
    8:  "Mencoba ulang pada siklus dua wait",
    12: "Nomor ditemukan memproses data fin"
}
MAX_BAR_LENGTH = 12 
FILLED_CHAR = "█"
EMPTY_CHAR = "░"

def get_progress_message(current_step, total_steps, prefix_range, num_count):
    progress_ratio = min(current_step / 12, 1.0)
    filled_count = math.ceil(progress_ratio * MAX_BAR_LENGTH)
    empty_count = MAX_BAR_LENGTH - filled_count
    progress_bar = FILLED_CHAR * filled_count + EMPTY_CHAR * empty_count
    current_status = STATUS_MAP.get(current_step)
    if not current_status:
        if current_step < 3: current_status = STATUS_MAP[0]
        elif current_step < 5: current_status = STATUS_MAP[4]
        elif current_step < 8: current_status = STATUS_MAP[5]
        elif current_step < 12: current_status = STATUS_MAP[8]
        else: current_status = STATUS_MAP[12]
    return (
        f"<code>{current_status}</code>\n"
        f"<blockquote>Range: <code>{prefix_range}</code> | Jumlah: <code>{num_count}</code></blockquote>\n"
        f"<code>Load:</code> [{progress_bar}]"
    )

# --- USER & PROFILE MANAGERS ---
def load_users():
    return set(load_json_file(USER_FILE))

def save_users(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        with open(USER_FILE, "w", encoding='utf-8') as f: json.dump(list(users), f, indent=2)

def load_cache(): return load_json_file(CACHE_FILE)
def save_cache(number_entry):
    cache = load_cache()
    if len(cache) >= 1000: cache.pop(0) 
    cache.append(number_entry)
    save_json_file(CACHE_FILE, cache)

def is_in_cache(number):
    cache = load_cache()
    normalized = normalize_number(number) 
    return any(normalize_number(entry["number"]) == normalized for entry in cache)

def load_inline_ranges(): return load_json_file(INLINE_RANGE_FILE)
def save_inline_ranges(ranges): save_json_file(INLINE_RANGE_FILE, ranges)

def load_akses_get10(): return set(load_json_file(AKSES_GET10_FILE))
def save_akses_get10(user_id):
    akses = load_akses_get10()
    akses.add(int(user_id))
    save_json_file(AKSES_GET10_FILE, list(akses))
def has_get10_access(user_id): return user_id == GET_ADMIN_ID or user_id in load_akses_get10()

def get_user_profile(user_id, first_name="User"):
    profiles = load_json_file(PROFILE_FILE)
    str_id = str(user_id)
    if str_id not in profiles:
        profiles[str_id] = {
            "name": first_name, "dana": "Belum Diset", "dana_an": "Belum Diset",
            "balance": 0.000000, "otp_semua": 0, "otp_hari_ini": 0,
            "last_active": datetime.now().strftime("%Y-%m-%d")
        }
        save_json_file(PROFILE_FILE, profiles)
    else:
        if profiles[str_id].get("name") != first_name:
            profiles[str_id]["name"] = first_name
            save_json_file(PROFILE_FILE, profiles)
        today = datetime.now().strftime("%Y-%m-%d")
        if profiles[str_id].get("last_active") != today:
            profiles[str_id]["otp_hari_ini"] = 0
            profiles[str_id]["last_active"] = today
            save_json_file(PROFILE_FILE, profiles)
    return profiles[str_id]

def update_user_dana(user_id, dana_number, dana_name):
    profiles = load_json_file(PROFILE_FILE)
    str_id = str(user_id)
    if str_id in profiles:
        profiles[str_id]["dana"] = dana_number
        profiles[str_id]["dana_an"] = dana_name
        save_json_file(PROFILE_FILE, profiles)
        return True
    return False

def generate_inline_keyboard(ranges):
    keyboard = []
    for item in ranges:
        service = item.get("service", "WA") 
        text = f"{item['emoji']} {item['country']} {service}"
        callback_data = f"select_range:{item['range']}"
        keyboard.append([{"text": text, "callback_data": callback_data}])
    keyboard.append([{"text": "Input Manual Range..🖊️", "callback_data": "manual_range"}])
    return {"inline_keyboard": keyboard}

def add_to_wait_list(number, user_id, username, first_name):
    wait_list = load_json_file(WAIT_JSON_FILE)
    normalized_number = normalize_number(number)
    final_identity = f"@{username.replace('@', '')}" if username and username != "None" else f'<a href="tg://user?id={user_id}">{first_name}</a>'
    wait_list = [item for item in wait_list if item['number'] != normalized_number]
    wait_list.append({
        "number": normalized_number, "user_id": user_id, 
        "username": final_identity, "timestamp": time.time()
    })
    save_json_file(WAIT_JSON_FILE, wait_list)

# --- GET BOT TELEGRAM HELPERS ---
def get_tg_send(chat_id, text, reply_markup=None):
    if not GET_BOT_TOKEN: return
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: data["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{GET_API_URL}/sendMessage", json=data).json()
        if r.get("ok"): return r["result"]["message_id"]
    except: pass
    return None

def get_tg_edit(chat_id, message_id, text, reply_markup=None):
    if not GET_BOT_TOKEN: return
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: data["reply_markup"] = reply_markup
    try: requests.post(f"{GET_API_URL}/editMessageText", json=data)
    except: pass

def get_tg_delete(chat_id, message_id):
    if not GET_BOT_TOKEN: return
    try: requests.post(f"{GET_API_URL}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id})
    except: pass

def get_tg_send_action(chat_id, action="typing"):
    if not GET_BOT_TOKEN: return
    try: requests.post(f"{GET_API_URL}/sendChatAction", data={"chat_id": chat_id, "action": action})
    except: pass

def is_user_in_group(user_id, group_id):
    try:
        r = requests.get(f"{GET_API_URL}/getChatMember", params={"chat_id": group_id, "user_id": user_id}).json()
        return r.get("ok") and r["result"]["status"] in ["member", "administrator", "creator"]
    except: return False

def is_user_in_both_groups(user_id):
    return is_user_in_group(user_id, GET_GROUP_ID_1) and is_user_in_group(user_id, GET_GROUP_ID_2)

async def delayed_delete(chat_id, message_id, delay):
    await asyncio.sleep(delay)
    get_tg_delete(chat_id, message_id)

async def action_task(chat_id, action_interval=4.5):
    while True:
        get_tg_send_action(chat_id, action="typing") 
        await asyncio.sleep(action_interval)

# --- PLAYWRIGHT GET LOGIC ---
async def get_number_and_country_from_row(row_selector, page):
    try:
        row = page.locator(row_selector) 
        if not await row.is_visible(): return None, None, None 
        phone_el = row.locator("td:nth-child(1) span.font-mono")
        number_raw_list = await phone_el.all_inner_texts()
        number_raw = number_raw_list[0].strip() if number_raw_list else None
        number = normalize_number(number_raw) if number_raw else None
        if not number or is_in_cache(number): return None, None, None 
        status_el = row.locator("td:nth-child(1) div:nth-child(2) span")
        status_text_list = await status_el.all_inner_texts()
        status_text = status_text_list[0].strip().lower() if status_text_list else "unknown"
        if "success" in status_text or "failed" in status_text: return None, None, None
        country_el = row.locator("td:nth-child(2) span.text-slate-200")
        country_list = await country_el.all_inner_texts()
        country = country_list[0].strip().upper() if country_list else "UNKNOWN"
        if number and len(number) > 5: return number, country, status_text
        return None, None, None
    except: return None, None, None

async def get_all_numbers_parallel(page, num_to_fetch):
    tasks = []
    for i in range(1, num_to_fetch + 5): 
        row_selector = f"tbody tr:nth-child({i})"
        tasks.append(get_number_and_country_from_row(row_selector, page))
    results = await asyncio.gather(*tasks)
    current_numbers = []
    for number, country, status in results:
        if number and number not in [n['number'] for n in current_numbers]:
            current_numbers.append({'number': number, 'country': country})
    return current_numbers

async def process_user_input(browser_context, user_id, prefix, click_count, username_tg, first_name_tg, message_id_to_edit=None):
    global get_last_used_range, shared_page
    msg_id = message_id_to_edit if message_id_to_edit else get_pending_message.pop(user_id, None)
    action_loop_task = None 
    num_to_fetch = click_count 

    if playwright_lock.locked():
        if not msg_id: msg_id = get_tg_send(user_id, get_progress_message(0, 0, prefix, num_to_fetch))
        else: get_tg_edit(user_id, msg_id, get_progress_message(0, 0, prefix, num_to_fetch))

    async with playwright_lock:
        try:
            action_loop_task = asyncio.create_task(action_task(user_id))
            current_step = 0 
            start_operation_time = time.time()
            if not msg_id:
                msg_id = get_tg_send(user_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
                if not msg_id: return
            
            # Use Shared Page or Create
            if not shared_page or shared_page.is_closed():
                shared_page = await browser_context.new_page()
                await shared_page.goto(DASHBOARD_INFO_URL, wait_until='domcontentloaded')

            INPUT_SELECTOR = "input[name='numberrange']"
            await shared_page.wait_for_selector(INPUT_SELECTOR, state='visible', timeout=10000)
            await shared_page.fill(INPUT_SELECTOR, "")
            await shared_page.fill(INPUT_SELECTOR, prefix)

            current_step = 2 
            BUTTON_SELECTOR = "button:has-text('Get Number')" 
            await shared_page.wait_for_selector(BUTTON_SELECTOR, state='visible', timeout=10000) 
            
            for i in range(click_count):
                await shared_page.click(BUTTON_SELECTOR, force=True)
            
            current_step = 3 
            get_tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
            await asyncio.sleep(0.5) 
            current_step = 4 
            get_tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
            await asyncio.sleep(1) 
            
            delay_duration_round_1 = 5.0 
            delay_duration_round_2 = 5.0
            check_number_interval = 0.25 
            found_numbers = [] 
            
            for round_num, duration in enumerate([delay_duration_round_1, delay_duration_round_2]):
                if round_num == 0: current_step = 5 
                elif round_num == 1:
                    if len(found_numbers) < num_to_fetch: 
                        await shared_page.click(BUTTON_SELECTOR, force=True) 
                        await asyncio.sleep(1.5) 
                        current_step = 8 
                
                start_time = time.time()
                last_number_check_time = 0.0 
                while (time.time() - start_time) < duration:
                    current_time = time.time()
                    if current_time - last_number_check_time >= check_number_interval:
                        current_numbers = await get_all_numbers_parallel(shared_page, num_to_fetch)
                        found_numbers = current_numbers
                        last_number_check_time = current_time 
                        if len(found_numbers) >= num_to_fetch:
                            current_step = 12; break
                    
                    target_step = int(12 * (time.time() - start_operation_time) / (delay_duration_round_1 + delay_duration_round_2 + 4))
                    if target_step > current_step and target_step <= 12:
                         current_step = target_step
                         get_tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
                    await asyncio.sleep(0.05) 
                if len(found_numbers) >= num_to_fetch: break
            
            if not found_numbers:
                get_tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN. Coba lagi atau ganti range.")
                return 

            main_country = found_numbers[0]['country'] if found_numbers else "UNKNOWN"
            if found_numbers:
                current_step = 12
                get_tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))

            for entry in found_numbers:
                save_cache({"number": entry['number'], "country": entry['country'], "user_id": user_id, "time": time.time()})
                add_to_wait_list(entry['number'], user_id, username_tg, first_name_tg)
            
            get_last_used_range[user_id] = prefix 
            emoji = get_country_emoji(main_country) 
            
            if num_to_fetch == 10:
                msg = "✅The number is already.\n\n<code>"
                for entry in found_numbers[:10]: msg += f"{entry['number']}\n"
                msg += "</code>"
            else:
                msg = "✅ The number is ready\n\n"
                if num_to_fetch == 1:
                    msg += f"📞 Number  : <code>{found_numbers[0]['number']}</code>\n"
                else:
                    for idx, num_data in enumerate(found_numbers[:num_to_fetch]):
                        msg += f"📞 Number {idx+1} : <code>{num_data['number']}</code>\n"
                msg += (
                    f"{emoji} COUNTRY : {main_country}\n"
                    f"🏷️ Range   : <code>{prefix}</code>\n\n"
                    "<b>🤖 Number available please use, Waiting for OTP</b>\n"
                )

            inline_kb = {
                "inline_keyboard": [
                    [{"text": "🔄 Change 1 Number", "callback_data": f"change_num:1:{prefix}"}],
                    [{"text": "🔄 Change 3 Number", "callback_data": f"change_num:3:{prefix}"}],
                    [{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}, {"text": "🌐 Change Range", "callback_data": "getnum"}]
                ]
            }
            get_tg_edit(user_id, msg_id, msg, reply_markup=inline_kb)

        except PlaywrightTimeoutError:
            if msg_id: get_tg_edit(user_id, msg_id, "❌ Timeout web. Web lambat atau tombol tidak ditemukan. Mohon coba lagi.")
        except Exception as e:
            if msg_id: get_tg_edit(user_id, msg_id, f"❌ Terjadi kesalahan fatal ({type(e).__name__}). Mohon coba lagi.")
        finally:
            if action_loop_task: action_loop_task.cancel()

async def task_get_bot_loop(shared_browser_context):
    global get_verified_users, get_waiting_broadcast_input, get_broadcast_message
    if not GET_BOT_TOKEN:
        print("⚠️ [GET BOT] Token not set, skipping...")
        return
        
    get_verified_users = load_users()
    offset = 0
    print("✅ [GET BOT] Active.")
    
    while True:
        try:
            r = requests.get(f"{GET_API_URL}/getUpdates", params={"offset": offset, "timeout": 2})
            data = r.json()
        except: 
            await asyncio.sleep(1)
            continue
            
        for upd in data.get("result", []):
            offset = upd["update_id"] + 1
            if "message" in upd:
                msg = upd["message"]
                chat_id = msg["chat"]["id"]
                user_id = msg["from"]["id"]
                first_name = msg["from"].get("first_name", "User")
                username_tg = msg["from"].get("username")
                mention = f"@{username_tg}" if username_tg else f"<a href='tg://user?id={user_id}'>{first_name}</a>"
                text = msg.get("text", "")

                # ADMIN COMMANDS
                if user_id == GET_ADMIN_ID:
                    if text.startswith("/add"):
                        get_waiting_admin_input.add(user_id)
                        get_tg_send(user_id, "Silahkan kirim daftar range dalam format:\n<code>range > country > service</code>")
                        continue
                    elif text.startswith("/get10akses "):
                        try:
                            target_id = text.split(" ")[1]
                            save_akses_get10(target_id)
                            get_tg_send(user_id, f"✅ User <code>{target_id}</code> berhasil diberi akses /get10.")
                        except: pass
                        continue

                # GET10
                if text == "/get10":
                    if has_get10_access(user_id):
                        get_get10_range_input.add(user_id)
                        get_pending_message[user_id] = get_tg_send(user_id, "kirim range contoh 225071606XXX")
                    else: get_tg_send(user_id, "❌ Anda tidak memiliki akses.")
                    continue

                if user_id in get_waiting_admin_input:
                    get_waiting_admin_input.remove(user_id)
                    new_ranges = []
                    for line in text.strip().split('\n'):
                        if ' > ' in line:
                            parts = line.split(' > ')
                            range_prefix = parts[0].strip()
                            country_name = parts[1].strip().upper() 
                            service_name = parts[2].strip().upper() if len(parts) > 2 else "WA"
                            new_ranges.append({"range": range_prefix, "country": country_name, "emoji": get_country_emoji(country_name), "service": service_name})
                    if new_ranges:
                        cur = load_inline_ranges()
                        cur.extend(new_ranges)
                        save_inline_ranges(cur)
                        get_tg_send(user_id, f"✅ Berhasil menyimpan {len(new_ranges)} range baru.")
                    continue
                
                # DANA INPUT
                if user_id in get_waiting_dana_input:
                    lines = text.strip().split('\n')
                    if len(lines) >= 2:
                        get_waiting_dana_input.remove(user_id)
                        update_user_dana(user_id, lines[0].strip(), " ".join(lines[1:]).strip())
                        get_tg_send(user_id, f"✅ <b>Dana Berhasil Disimpan!</b>")
                    else: get_tg_send(user_id, "❌ Format salah. Kirim:\n<code>08123456789\nNama Pemilik</code>")
                    continue

                # GET10 INPUT
                if user_id in get_get10_range_input:
                    get_get10_range_input.remove(user_id)
                    prefix = text.strip()
                    if re.match(r"^\+?\d{3,15}[Xx*#]+$", prefix, re.IGNORECASE):
                        msg_id = get_pending_message.pop(user_id, None)
                        await process_user_input(shared_browser_context, user_id, prefix, 10, username_tg, first_name, msg_id)
                    else: get_tg_send(chat_id, "❌ Format Range tidak valid.")
                    continue
                
                # MANUAL RANGE
                is_manual_format = re.match(r"^\+?\d{3,15}[Xx*#]+$", text.strip(), re.IGNORECASE)
                if user_id in get_manual_range_input or (user_id in get_verified_users and is_manual_format):
                    if user_id in get_manual_range_input: get_manual_range_input.remove(user_id) 
                    prefix = text.strip()
                    msg_id = get_pending_message.pop(user_id, None)
                    if is_manual_format:
                        await process_user_input(shared_browser_context, user_id, prefix, 1, username_tg, first_name, msg_id)
                    continue
                
                if text.startswith("/setdana"):
                    get_waiting_dana_input.add(user_id)
                    get_tg_send(user_id, "Silahkan kirim dana dalam format:\n\n<code>08123456789\nNama Pemilik</code>")
                    continue

                if text == "/start":
                    if is_user_in_both_groups(user_id):
                        get_verified_users.add(user_id); save_users(user_id) 
                        prof_data = get_user_profile(user_id, first_name)
                        full_name = f"{first_name} (@{username_tg})" if username_tg else first_name
                        msg_profile = (
                            f"✅ <b>Verifikasi Berhasil, {mention}</b>\n\n"
                            f"👤 <b>Profil Anda :</b>\n"
                            f"🔖 <b>Nama</b> : {full_name}\n"
                            f"🧾 <b>Dana</b> : {prof_data['dana']}\n"
                            f"👤 <b>A/N</b> : {prof_data['dana_an']}\n"
                            f"📊 <b>Total of all OTPs</b> : {prof_data['otp_semua']}\n"
                            f"📊 <b>daily OTP count</b> : {prof_data['otp_hari_ini']}\n"
                            f"💰 <b>Balance</b> : ${prof_data['balance']:.6f}\n"
                        )
                        kb = {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}, {"text": "👨‍💼 Admin", "url": "https://t.me/"}], [{"text": "💸 Withdraw Money", "callback_data": "withdraw_menu"}]]}
                        get_tg_send(user_id, msg_profile, kb)
                    else:
                        kb = {"inline_keyboard": [[{"text": "📌 Gabung Grup 1", "url": GROUP_LINK_1}], [{"text": "📌 Gabung Grup 2", "url": GROUP_LINK_2}], [{"text": "✅ Verifikasi Ulang", "callback_data": "verify"}],]}
                        get_tg_send(user_id, f"Halo {mention} 👋\nHarap gabung kedua grup di bawah untuk verifikasi:", kb)
                    continue

            if "callback_query" in upd:
                cq = upd["callback_query"]
                user_id = cq["from"]["id"]
                data_cb = cq["data"]
                chat_id = cq["message"]["chat"]["id"]
                menu_msg_id = cq["message"]["message_id"]
                first_name_tg = cq["from"].get("first_name", "User")
                username_tg = cq["from"].get("username")
                mention = f"@{username_tg}" if username_tg else f"<a href='tg://user?id={user_id}'>{first_name_tg}</a>"

                if data_cb == "verify":
                    if not is_user_in_both_groups(user_id):
                        get_tg_edit(chat_id, menu_msg_id, "❌ Belum gabung kedua grup.", {"inline_keyboard": [[{"text": "📌 Gabung Grup 1", "url": GROUP_LINK_1}], [{"text": "📌 Gabung Grup 2", "url": GROUP_LINK_2}], [{"text": "✅ Verifikasi Ulang", "callback_data": "verify"}],]})
                    else:
                        get_verified_users.add(user_id); save_users(user_id) 
                        prof_data = get_user_profile(user_id, first_name_tg)
                        get_tg_edit(chat_id, menu_msg_id, "✅ Verifikasi Berhasil!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}, {"text": "👨‍💼 Admin", "url": "https://t.me/"}], [{"text": "💸 Withdraw Money", "callback_data": "withdraw_menu"}]]})
                    continue
                
                if data_cb == "getnum":
                    if user_id not in get_verified_users: continue
                    inline_ranges = load_inline_ranges()
                    kb = generate_inline_keyboard(inline_ranges) if inline_ranges else {"inline_keyboard": [[{"text": "✍️ Input Manual Range", "callback_data": "manual_range"}]]}
                    get_tg_edit(chat_id, menu_msg_id, "<b>Get Number</b>\n\nSilahkan pilih range atau input manual.", kb)
                    continue

                if data_cb == "manual_range":
                    get_manual_range_input.add(user_id)
                    get_tg_edit(chat_id, menu_msg_id, "<b>Input Manual Range</b>\n\nKirim Range anda, contoh: <code>2327600XXX</code>") 
                    get_pending_message[user_id] = menu_msg_id 
                    continue
                
                if data_cb.startswith("select_range:"):
                    prefix = data_cb.split(":")[1]
                    get_tg_edit(chat_id, menu_msg_id, get_progress_message(0, 0, prefix, 1)) 
                    await process_user_input(shared_browser_context, user_id, prefix, 1, username_tg, first_name_tg, menu_msg_id) 
                    continue

                if data_cb.startswith("change_num:"):
                    parts = data_cb.split(":")
                    get_tg_delete(chat_id, menu_msg_id)
                    await process_user_input(shared_browser_context, user_id, parts[2], int(parts[1]), username_tg, first_name_tg) 
                    continue
                
                if data_cb == "withdraw_menu":
                    prof = get_user_profile(user_id, first_name_tg)
                    kb_wd = {"inline_keyboard": [[{"text": "$1.000000", "callback_data": "wd_req:1.0"}, {"text": "$2.000000", "callback_data": "wd_req:2.0"}], [{"text": "$3.000000", "callback_data": "wd_req:3.0"}, {"text": "$5.000000", "callback_data": "wd_req:5.0"}], [{"text": "⚙️ Setting Dana", "callback_data": "set_dana_cb"}], [{"text": "🔙 Kembali", "callback_data": "verify"}]]}
                    get_tg_edit(chat_id, menu_msg_id, f"<b>💸 Withdraw Money</b>\n💰 Balance: ${prof['balance']:.6f}\nMinimal: ${MIN_WD_AMOUNT:.6f}", kb_wd)
                    continue

                if data_cb == "set_dana_cb":
                    get_waiting_dana_input.add(user_id)
                    get_tg_edit(chat_id, menu_msg_id, "Silahkan kirim dana:\n\n<code>08123456789\nNama Pemilik</code>")
                    continue

                if data_cb.startswith("wd_req:"):
                    amount = float(data_cb.split(":")[1])
                    profiles = load_json_file(PROFILE_FILE)
                    prof = profiles.get(str(user_id))
                    if not prof or prof['dana'] == "Belum Diset": 
                        get_tg_send(chat_id, "❌ Harap Setting Dana terlebih dahulu!")
                        continue
                    if prof['balance'] < amount:
                        get_tg_send(chat_id, f"❌ Saldo tidak cukup! Balance anda: ${prof['balance']:.6f}")
                        continue
                    prof['balance'] -= amount
                    save_json_file(PROFILE_FILE, profiles)
                    kb_admin = {"inline_keyboard": [[{"text": "✅ Approve", "callback_data": f"wd_act:apr:{user_id}:{amount}"}, {"text": "❌ Cancel", "callback_data": f"wd_act:cncl:{user_id}:{amount}"}]]}
                    get_tg_send(GET_ADMIN_ID, f"<b>🔔 Withdraw Req</b>\n👤 {mention}\n💵 ${amount:.6f}\n🧾 {prof['dana']} ({prof['dana_an']})", kb_admin)
                    get_tg_edit(chat_id, menu_msg_id, "✅ <b>Permintaan Terkirim!</b>")
                    continue
                
                if data_cb.startswith("wd_act:"):
                    if user_id != GET_ADMIN_ID: continue
                    parts = data_cb.split(":")
                    target_id, amount = parts[2], float(parts[3])
                    if parts[1] == "apr":
                        get_tg_edit(chat_id, menu_msg_id, f"✅ Withdraw {target_id} ${amount} DISETUJUI.")
                        get_tg_send(target_id, f"✅ Withdraw Anda Sukses! ${amount:.6f}")
                    elif parts[1] == "cncl":
                        profiles = load_json_file(PROFILE_FILE)
                        if str(target_id) in profiles: profiles[str(target_id)]["balance"] += amount; save_json_file(PROFILE_FILE, profiles)
                        get_tg_edit(chat_id, menu_msg_id, f"❌ Withdraw {target_id} DIBATALKAN.")
                        get_tg_send(target_id, "❌ Withdraw Dibatalkan oleh Admin.")
                    continue

        await asyncio.sleep(0.05)

async def task_expiry_monitor():
    while True:
        try:
            wait_list = load_json_file(WAIT_JSON_FILE)
            current_time = time.time()
            updated_list = []
            for item in wait_list:
                if current_time - item['timestamp'] > 1200: 
                    msg_id = get_tg_send(item['user_id'], f"⚠️ Nomor <code>{item['number']}</code> telah kadaluarsa.")
                    if msg_id: asyncio.create_task(delayed_delete(item['user_id'], msg_id, 30))
                else: updated_list.append(item)
            save_json_file(WAIT_JSON_FILE, updated_list)
        except: pass
        await asyncio.sleep(10)

# ==============================================================================
# 5. MODUL: SMS FORWARDER (Ported from sms.py)
# ==============================================================================

DONATE_LINK = "https://zurastore.my.id/donate"

def sms_create_otp_keyboard(otp):
    return json.dumps({"inline_keyboard": [[{"text": f" {otp}", "copy_text": {"text": otp}}, {"text": "💸 Donate", "url": DONATE_LINK}]]})

def sms_update_profile_otp(user_id):
    profiles = load_json_file(PROFILE_FILE)
    str_id = str(user_id)
    if str_id not in profiles:
        profiles[str_id] = {
            "name": "User", "dana": "Belum Diset", "dana_an": "Belum Diset",
            "balance": 0.000000, "otp_semua": 0, "otp_hari_ini": 0,
            "last_active": datetime.now().strftime("%Y-%m-%d")
        }
    p = profiles[str_id]
    today = datetime.now().strftime("%Y-%m-%d")
    if p.get("last_active") != today: p["otp_hari_ini"] = 0; p["last_active"] = today
    old_balance = p.get("balance", 0.0)
    p["otp_semua"] = p.get("otp_semua", 0) + 1
    p["otp_hari_ini"] = p.get("otp_hari_ini", 0) + 1
    p["balance"] = old_balance + OTP_PRICE
    save_json_file(PROFILE_FILE, profiles)
    return old_balance, p["balance"]

async def task_sms_forwarder_loop():
    print("✅ [SMS FORWARDER] Active.")
    while True:
        try:
            wait_list = load_json_file(WAIT_JSON_FILE)
            sms_data = load_json_file(OTP_SAVE_FILE) # Membaca file smc.json
            
            if not wait_list: 
                await asyncio.sleep(2); continue

            new_wait_list = []
            current_time = time.time()
            sms_was_changed = False
            
            for wait_item in wait_list:
                wait_number = wait_item.get('number', 'N/A')
                wait_user_id = wait_item.get('user_id')
                start_timestamp = wait_item.get('timestamp', 0)
                otp_received_time = wait_item.get('otp_received_time')

                if otp_received_time:
                    if current_time - otp_received_time > EXTENDED_WAIT_SECONDS: continue 
                    else: new_wait_list.append(wait_item); continue
                
                elif current_time - start_timestamp > WAIT_TIMEOUT_SECONDS:
                    get_tg_send(wait_user_id, f"⚠️ <b>Waktu Habis</b>\nNomor: <code>{wait_number}</code> dihapus.")
                    continue

                remaining_sms = []
                found_for_this_user = False
                
                for sms_entry in sms_data:
                    entry_num = str(sms_entry.get("number") or sms_entry.get("Number"))
                    
                    if not found_for_this_user and normalize_number(entry_num) == normalize_number(wait_number):
                        otp = sms_entry.get("otp") or sms_entry.get("OTP", "N/A")
                        service = sms_entry.get("service", "Unknown")
                        raw_msg = sms_entry.get("full_message") or sms_entry.get("FullMessage", "No content")
                        
                        balance_text = "<i>WhatsApp OTP no balance</i>" if "whatsapp" in service.lower() else f"${sms_update_profile_otp(wait_user_id)[0]:.6f} > ${sms_update_profile_otp(wait_user_id)[1]:.6f}"
                        
                        response_text = (
                            "🔔 <b>New Message Detected</b>\n\n"
                            f"☎️ <b>Nomor:</b> <code>{wait_number}</code>\n"
                            f"⚙️ <b>Service:</b> <b>{service}</b>\n\n"
                            f"💰 <b>added:</b> {balance_text}\n\n"
                            f"🗯️ <b>Full Message:</b>\n<blockquote>{html.escape(raw_msg)}</blockquote>\n\n"
                            "⚡ <b>Tap the Button To Copy OTP</b> ⚡"
                        )
                        get_tg_send(wait_user_id, response_text, reply_markup=sms_create_otp_keyboard(otp))
                        
                        wait_item['otp_received_time'] = time.time()
                        sms_was_changed = True; found_for_this_user = True
                    else: remaining_sms.append(sms_entry)
                
                sms_data = remaining_sms
                new_wait_list.append(wait_item)

            if sms_was_changed: save_json_file(OTP_SAVE_FILE, sms_data)
            save_json_file(WAIT_JSON_FILE, new_wait_list)
            
        except Exception as e: 
            # print(f"[SMS ERROR] {e}") 
            pass
        await asyncio.sleep(2)

# ==============================================================================
# 6. MODUL: RANGE BOT (Ported from range.py)
# ==============================================================================

RANGE_SENT_MESSAGES = {}

class RangeMessageFilter:
    CLEANUP_KEY = '__LAST_CLEANUP_GMT__' 
    def __init__(self, file=RANGE_CACHE_FILE): 
        self.file = file
        if os.path.exists(self.file):
            try: os.remove(self.file) 
            except: pass
        self.cache = self._load()
        self.last_cleanup_date_gmt = self.cache.pop(self.CLEANUP_KEY, '19700101') 
        self._cleanup() 
    
    def _load(self):
        if os.path.exists(self.file) and os.stat(self.file).st_size > 0:
            try: return json.load(open(self.file, 'r'))
            except: return {}
        return {}
    def _save(self): 
        temp = self.cache.copy(); temp[self.CLEANUP_KEY] = self.last_cleanup_date_gmt
        try: json.dump(temp, open(self.file,'w'), indent=2)
        except: pass
    def _cleanup(self):
        now_gmt = datetime.now(timezone.utc).strftime('%Y%m%d')
        if now_gmt > self.last_cleanup_date_gmt:
            self.cache = {}; self.last_cleanup_date_gmt = now_gmt; self._save()
    def is_dup(self, d):
        self._cleanup(); key = f"{d.get('range_key')}_{hash(d.get('raw_message'))}"
        return key in self.cache
    def add(self, d):
        key = f"{d.get('range_key')}_{hash(d.get('raw_message'))}"
        self.cache[key] = {'timestamp':datetime.now().isoformat()}; self._save()
    def filter(self, lst):
        out = []
        for d in lst:
            if d.get('range_key') != 'N/A' and d.get('raw_message'):
                if not self.is_dup(d): out.append(d); self.add(d)
        return out

range_filter = RangeMessageFilter()

class RangeMonitor:
    def __init__(self, url=DASHBOARD_CONSOLE_URL): 
        self.url = url
        self.page = None
        self.is_logged_in = False 
        self.CONSOLE_SELECTOR = ".group.flex.flex-col.sm\\:flex-row.sm\\:items-start.gap-3.p-3.rounded-lg"

    async def initialize(self, shared_context):
        try:
            self.page = await shared_context.new_page()
            await self.page.goto(self.url, wait_until='networkidle', timeout=30000)
            print("✅ [RANGE BOT] Page Initialized.")
        except: print("⚠️ [RANGE BOT] Init Failed.")

    async def fetch_sms(self):
        if not self.page: return []
        if self.page.url != self.url:
            try: await self.page.goto(self.url, wait_until='domcontentloaded', timeout=15000)
            except: return []
        try: await self.page.wait_for_selector(self.CONSOLE_SELECTOR, timeout=5000)
        except: return []

        messages = []
        elements = await self.page.locator(self.CONSOLE_SELECTOR).all()
        for element in elements:
            try:
                c_el = element.locator(".flex-shrink-0 .text-\\[10px\\].text-slate-600.mt-1.font-mono")
                c_raw = await c_el.inner_text() if await c_el.count() > 0 else ""
                c_name = re.search(r'•\s*(.*)$', c_raw.strip()).group(1).strip() if "•" in c_raw else "Unknown"
                if c_name.lower() in ['angola']: continue 
                
                s_el = element.locator(".flex-grow.min-w-0 .text-xs.font-bold.text-blue-400")
                s_raw = await s_el.inner_text() if await s_el.count() > 0 else ""
                if not any(a in s_raw.lower() for a in ['whatsapp', 'facebook']): continue
                service = clean_service_name(s_raw)
                
                p_el = element.locator(".flex-grow.min-w-0 .text-\\[10px\\].font-mono")
                p_raw = await p_el.last.inner_text() if await p_el.count() > 0 else "N/A"
                phone = clean_phone_number(p_raw) 
                
                m_el = element.locator(".flex-grow.min-w-0 p")
                m_raw = await m_el.inner_text() if await m_el.count() > 0 else ""
                full_message = m_raw.replace('➜', '').strip()

                if 'XXX' in phone and full_message: 
                    messages.append({"range_key": phone, "country": c_name, "service": service, "raw_message": full_message})
            except: continue
        return messages

range_monitor = RangeMonitor()

def range_save_to_inline_json(range_val, country_name, service):
    service_map = {'whatsapp': 'WA', 'facebook': 'FB'}
    service_key = service.lower()
    if service_key not in service_map: return 
    short_service = service_map[service_key]
    
    data_list = load_json_file(INLINE_RANGE_FILE)
    if any(item['range'] == range_val for item in data_list): return

    new_entry = {
        "range": range_val, "country": country_name.upper(), 
        "emoji": get_country_emoji(country_name), "service": short_service
    }
    data_list.append(new_entry)
    if len(data_list) > 10: data_list = data_list[-10:]
    save_json_file(INLINE_RANGE_FILE, data_list)

async def task_range_bot_loop(shared_context):
    if not RANGE_BOT_TOKEN: 
        print("⚠️ [RANGE BOT] Token missing, skipping.")
        return

    # Inisialisasi Bot App (PTB)
    range_app = ApplicationBuilder().token(RANGE_BOT_TOKEN).build()
    
    # Inisialisasi Browser Page
    await range_monitor.initialize(shared_context)

    while True:
        try:
            # Login Check logic
            if "mdashboard" in range_monitor.page.url:
                msgs = await range_monitor.fetch_sms()
                new_unique = range_filter.filter(msgs)

                if new_unique:
                    for log in new_unique:
                        range_val = log['range_key']
                        if range_val in RANGE_SENT_MESSAGES: RANGE_SENT_MESSAGES[range_val]['count'] += 1
                        else: RANGE_SENT_MESSAGES[range_val] = {'count': 1, 'timestamp': datetime.now()}
                        
                        count = RANGE_SENT_MESSAGES[range_val]['count']
                        country = log['country']
                        service = log['service']
                        full_msg = log['raw_message']
                        
                        # Save to JSON
                        range_save_to_inline_json(range_val, country, service)

                        # Format Message
                        txt = (
                            "🔥Live message new range\n\n" 
                            f"📱Range    : <code>{range_val}</code> {'('+str(count)+'x)' if count > 1 else ''}\n"
                            f"{get_country_emoji(country)}Country : {country}\n"
                            f"⚙️ Service : {service}\n\n" 
                            "🗯️Message Available :\n"
                            f"<blockquote>{html.escape(full_msg)}</blockquote>"
                        )
                        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📞GetNumber", url=MSG_BOT_LINK)]])

                        # Logic Delete Old & Send New
                        try:
                            if range_val in RANGE_SENT_MESSAGES and 'message_id' in RANGE_SENT_MESSAGES[range_val]:
                                try: await range_app.bot.delete_message(chat_id=RANGE_CHAT_ID, message_id=RANGE_SENT_MESSAGES[range_val]['message_id'])
                                except: pass
                            
                            sent = await range_app.bot.send_message(chat_id=RANGE_CHAT_ID, text=txt, reply_markup=kb, parse_mode='HTML')
                            RANGE_SENT_MESSAGES[range_val]['message_id'] = sent.message_id
                            RANGE_SENT_MESSAGES[range_val]['timestamp'] = datetime.now()
                        except: pass
                        await asyncio.sleep(0.5)
                
                # Cleanup Old Messages from Memory
                ten_min_ago = datetime.now() - timedelta(minutes=10)
                to_rem = [r for r, d in RANGE_SENT_MESSAGES.items() if d['timestamp'] < ten_min_ago]
                for r in to_rem: del RANGE_SENT_MESSAGES[r]

            else:
                await range_monitor.page.goto(DASHBOARD_CONSOLE_URL)
        except Exception as e:
            # print(f"⚠️ [RANGE LOOP] {e}")
            pass
        await asyncio.sleep(10)

# ==============================================================================
# 7. MAIN ORCHESTRATOR
# ==============================================================================

# Flask Server (Run in Thread)
app = Flask(__name__)
@app.route('/')
def home(): return "One-For-All Bot Running"

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

async def main():
    print("🚀 [SYSTEM] Starting Unified Bot System...")
    
    # 1. Start Flask
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 2. Init Files
    for f in [CACHE_FILE, INLINE_RANGE_FILE, OTP_SAVE_FILE, USER_FILE, WAIT_JSON_FILE, AKSES_GET10_FILE]:
        if not os.path.exists(f): save_json_file(f, [])
    if not os.path.exists(PROFILE_FILE): save_json_file(PROFILE_FILE, {})

    # 3. Start Playwright
    async with async_playwright() as p:
        browser = None
        try:
            # Connect to Existing Chrome (Port 9222)
            browser = await p.chromium.connect_over_cdp(CHROME_DEBUG_URL)
            context = browser.contexts[0]
            print("✅ [SYSTEM] Connected to Chrome Debugger (9222)")
            
            # 4. Gather All Tasks
            await asyncio.gather(
                task_message_bot_loop(context),   # Logic dari message.py
                task_get_bot_loop(context),       # Logic dari get.py (User Bot)
                task_expiry_monitor(),            # Logic dari get.py (Expiry)
                task_sms_forwarder_loop(),        # Logic dari sms.py (Forwarder)
                task_range_bot_loop(context)      # Logic dari range.py (Monitor Range)
            )
            
        except Exception as e:
            print(f"🚨 [FATAL ERROR] {e}")
            print("Pastikan Chrome sudah berjalan dengan: --remote-debugging-port=9222")
            if browser: await browser.close()

if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot Stopped.")
