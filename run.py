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

# Setup Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.ERROR
)

# --- FOLDER SETUP ---
DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER): 
    os.makedirs(DATA_FOLDER)

# Path File
OTP_SAVE_FILE = os.path.join(DATA_FOLDER, "smc.json")
WAIT_JSON_FILE = os.path.join(DATA_FOLDER, "wait.json")
USER_FILE = os.path.join(DATA_FOLDER, "user.json")
CACHE_FILE = os.path.join(DATA_FOLDER, "cache.json")
INLINE_RANGE_FILE = os.path.join(DATA_FOLDER, "inline.json")
AKSES_GET10_FILE = os.path.join(DATA_FOLDER, "aksesget10.json")
PROFILE_FILE = os.path.join(DATA_FOLDER, "profile.json")
RANGE_CACHE_FILE = os.path.join(DATA_FOLDER, "range_cache_mnit.json")
COUNTRY_JSON_FILE = os.path.join(DATA_FOLDER, "country.json")

# URL & NETWORK
LOGIN_URL = "https://x.mnitnetwork.com/mauth/login"
DASHBOARD_INFO_URL = "https://x.mnitnetwork.com/mdashboard/getnum"
DASHBOARD_CONSOLE_URL = "https://x.mnitnetwork.com/mdashboard/console"

# --- TOKEN & ID CONFIGURATION ---

# 1. Message Bot Config
MSG_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_MSG")
MSG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_MSG")
try: MSG_ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID_MSG") or 0)
except: MSG_ADMIN_ID = None
MSG_BOT_LINK = "https://t.me/myzuraisgoodbot"
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

# --- CONSTANTS ---
OTP_PRICE = 0.003500
MIN_WD_AMOUNT = 1.000000
WAIT_TIMEOUT_SECONDS = int(os.getenv("WAIT_TIMEOUT_SECONDS", 1800))
EXTENDED_WAIT_SECONDS = 300

# ==============================================================================
# 2. SHARED UTILS (FILE I/O & HELPERS)
# ==============================================================================

def load_json_file(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding='utf-8') as f:
            try: return json.load(f)
            except:
                if "profile" in filename: return {}
                return []
    if "profile" in filename: return {}
    return []

def save_json_file(filename, data):
    with open(filename, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=True)

def get_country_emoji(country_name: str) -> str:
    db = load_json_file(COUNTRY_JSON_FILE)
    if isinstance(db, dict):
        return db.get(country_name.strip().upper(), "🌍")
    return "🌍"

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

# ==============================================================================
# 3. MODUL: MESSAGE BOT (CORE LOGIC)
# ==============================================================================

MSG_BOT_STATUS = {"status": "Starting", "uptime": "--", "total_otps_sent": 0, "monitoring_active": False}
MSG_START_TIME = time.time()
MSG_AWAITING_CREDENTIALS = False

class MessageOTPFilter:
    CLEANUP_KEY = '__LAST_CLEANUP_GMT__' 
    def __init__(self, file='otp_cache.json'): 
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
        self.url, self.page, self.is_logged_in = url, None, False
        self._temp_username, self._temp_password = None, None

    async def check_url_login_status(self) -> bool:
        if not self.page: return False
        try:
            self.is_logged_in = "mdashboard" in self.page.url
            return self.is_logged_in
        except: return False

    async def login(self):
        if not self.page: return False
        try:
            await self.page.goto(LOGIN_URL, wait_until='load', timeout=15000) 
            await self.page.type('input[type="email"]', self._temp_username) 
            await self.page.type('input[type="password"]', self._temp_password)
            await self.page.click('button[type="submit"]') 
            await self.page.wait_for_url(re.compile(r".*/mdashboard.*"), timeout=30000) 
            self.is_logged_in = True
            return True
        except: return False

    async def fetch_sms(self) -> List[Dict[str, Any]]:
        if not self.page or not self.is_logged_in: return []
        messages = []
        try:
            # Pastikan di URL dashboard info
            if "getnum" not in self.page.url:
                await self.page.goto(DASHBOARD_INFO_URL, wait_until='domcontentloaded')

            async with self.page.expect_response(lambda r: "/getnum/info" in r.url, timeout=5000) as resp_info:
                try: await self.page.click('th:has-text("Number Info")', timeout=1000)
                except: pass

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
    wait_list = load_json_file(WAIT_JSON_FILE)
    clean_target = re.sub(r'[^\d]', '', phone_number)
    for entry in wait_list:
        clean_entry = re.sub(r'[^\d]', '', str(entry.get("number", "")))
        if clean_target == clean_entry:
            return {"username": entry.get("username", "unknown"), "user_id": entry.get("user_id")}
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
    emoji = get_country_emoji(otp_data.get('range', ''))

    return (
        f"💭 <b>New Message Received</b>\n\n"
        f"<b>👤 User:</b> {user_tag}\n"
        f"<b>📱 Number:</b> <code>{msg_mask_phone_number_zura(phone)}</code>\n"
        f"<b>🌍 Country:</b> <b>{otp_data.get('range')} {emoji}</b>\n"
        f"<b>✅ Service:</b> <b>{otp_data.get('service')}</b>\n\n"
        f"🔐 OTP: <code>{otp}</code>\n\n"
        f"<b>FULL MESSAGE:</b>\n"
        f"<blockquote>{raw_msg}</blockquote>"
    )

def msg_create_inline_keyboard(otp: str):
    keyboard = {
        "inline_keyboard": [
            [{"text": f"{otp}", "callback_data": f"copy:{otp}"}, {"text": "🎭 Owner", "url": MSG_ADMIN_LINK}],
            [{"text": "📞 Get Number", "url": MSG_BOT_LINK}]
        ]
    }
    return json.dumps(keyboard)

def msg_send_tg(text, with_inline_keyboard=False, target_chat_id=None, otp_code=None):
    cid = target_chat_id if target_chat_id is not None else MSG_CHAT_ID
    if not MSG_BOT_TOKEN or not cid: return
    payload = {'chat_id': cid, 'text': text, 'parse_mode': 'HTML'}
    if with_inline_keyboard and otp_code: payload['reply_markup'] = msg_create_inline_keyboard(otp_code)
    try: requests.post(f"https://api.telegram.org/bot{MSG_BOT_TOKEN}/sendMessage", json=payload, timeout=15)
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

async def task_message_bot_loop(browser_context):
    global MSG_BOT_STATUS, MSG_AWAITING_CREDENTIALS
    message_monitor.page = await browser_context.new_page()
    last_update_id = 0
    
    while True:
        try:
            # 1. Telegram Updates
            upd_url = f"https://api.telegram.org/bot{MSG_BOT_TOKEN}/getUpdates?offset={last_update_id+1}"
            upd = requests.get(upd_url, timeout=5).json()
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
                        await message_monitor.login()
                        msg_send_tg("✅ Login Attempted.", target_chat_id=user_id)
                    continue

                if text == "/status":
                    upt = str(timedelta(seconds=int(time.time() - MSG_START_TIME)))
                    status_text = f"🤖 <b>Bot Zura Status</b>\n⚡ Live: {'✅' if MSG_BOT_STATUS['monitoring_active'] else '⏸️'}\nUptime: <code>{upt}</code>\nTotal Sent: <b>{MSG_BOT_STATUS['total_otps_sent']}</b>"
                    msg_send_tg(status_text, target_chat_id=user_id)
                elif text == "/login": 
                    MSG_AWAITING_CREDENTIALS = True
                    msg_send_tg("🔑 Masukkan Email & Password (spasi):", target_chat_id=user_id)
                elif text == "/startnew": 
                    MSG_BOT_STATUS["monitoring_active"] = True
                    msg_send_tg("▶️ Real-time Mode Started.", target_chat_id=user_id)
                elif text == "/stop": 
                    MSG_BOT_STATUS["monitoring_active"] = False
                    msg_send_tg("⏸️ Monitoring Stopped.", target_chat_id=user_id)
        except: pass

        try:
            await message_monitor.check_url_login_status()
            if MSG_BOT_STATUS["monitoring_active"] and message_monitor.is_logged_in:
                msgs = await message_monitor.fetch_sms()
                new_otps = msg_otp_filter.filter(msgs)
                if new_otps:
                    for otp_data in new_otps:
                        # Save to smc.json for Forwarder
                        existing_smc = load_json_file(OTP_SAVE_FILE)
                        existing_smc.append({
                            "service": otp_data['service'], "number": otp_data['phone'],
                            "otp": otp_data['otp'], "full_message": otp_data['raw_message']
                        })
                        save_json_file(OTP_SAVE_FILE, existing_smc)
                        
                        msg_send_tg(msg_format_otp_message(otp_data), with_inline_keyboard=True, otp_code=otp_data['otp'])
                        MSG_BOT_STATUS['total_otps_sent'] += 1
                        await asyncio.sleep(0.5)
                await msg_wait_for_realtime_change(message_monitor.page)
            else:
                await asyncio.sleep(5)
        except: await asyncio.sleep(5)

# ==============================================================================
# 4. MODUL: GET BOT (PLAYWRIGHT INTERACTION & USER MGMT)
# ==============================================================================

playwright_lock = asyncio.Lock()
shared_page = None 
get_verified_users = set()
get_waiting_admin_input = set()
get_manual_range_input = set() 
get_get10_range_input = set()
get_waiting_dana_input = set() 
get_pending_message = {}
get_last_used_range = {}

STATUS_MAP = {
    0: "Menunggu di antrian sistem aktif..", 3: "Mengirim permintaan nomor baru go.",
    4: "Memulai pencarian di tabel data..", 5: "Mencari nomor pada siklus satu run",
    8: "Mencoba ulang pada siklus dua wait", 12: "Nomor ditemukan memproses data fin"
}

def get_progress_message(current_step, prefix_range, num_count):
    progress_ratio = min(current_step / 12, 1.0)
    filled_count = math.ceil(progress_ratio * 12)
    progress_bar = "█" * filled_count + "░" * (12 - filled_count)
    current_status = STATUS_MAP.get(current_step, STATUS_MAP[0])
    return (
        f"<code>{current_status}</code>\n"
        f"<blockquote>Range: <code>{prefix_range}</code> | Jumlah: <code>{num_count}</code></blockquote>\n"
        f"<code>Load:</code> [{progress_bar}]"
    )

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
    return profiles[str_id]

# --- TELEGRAM API HELPERS ---
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

async def process_get_number(context, user_id, prefix, count, username, first_name, msg_id=None):
    global shared_page
    async with playwright_lock:
        try:
            if not msg_id: msg_id = get_tg_send(user_id, get_progress_message(0, prefix, count))
            else: get_tg_edit(user_id, msg_id, get_progress_message(0, prefix, count))

            if not shared_page or shared_page.is_closed():
                shared_page = await context.new_page()
            
            if DASHBOARD_INFO_URL not in shared_page.url:
                await shared_page.goto(DASHBOARD_INFO_URL)

            # Input Range
            input_sel = "input[name='numberrange']"
            await shared_page.fill(input_sel, "")
            await shared_page.fill(input_sel, prefix)
            
            # Click Get
            btn_sel = "button:has-text('Get Number')"
            for _ in range(count):
                await shared_page.click(btn_sel)
                await asyncio.sleep(0.1)

            get_tg_edit(user_id, msg_id, get_progress_message(5, prefix, count))
            
            # Wait & Scrape
            found_numbers = []
            for _ in range(20): # Polling 10s
                rows = await shared_page.locator("tbody tr").all()
                for row in rows:
                    cols = await row.locator("td").all()
                    if len(cols) >= 2:
                        num_raw = await cols[0].locator("span.font-mono").inner_text()
                        status_raw = await cols[0].locator("div:nth-child(2) span").inner_text()
                        country_raw = await cols[1].locator("span.text-slate-200").inner_text()
                        
                        num = normalize_number(num_raw)
                        if "success" not in status_raw.lower() and "failed" not in status_raw.lower():
                            if num not in [n['number'] for n in found_numbers]:
                                found_numbers.append({'number': num, 'country': country_raw.strip().upper()})
                
                if len(found_numbers) >= count: break
                await asyncio.sleep(0.5)

            if not found_numbers:
                get_tg_edit(user_id, msg_id, "❌ Nomor tidak ditemukan. Coba range lain.")
                return

            # Success Response
            emoji = get_country_emoji(found_numbers[0]['country'])
            final_msg = f"✅ The number is ready\n\n"
            for idx, n in enumerate(found_numbers[:count]):
                final_msg += f"📞 Number {idx+1}: <code>{n['number']}</code>\n"
                # Add to wait list
                wait_list = load_json_file(WAIT_JSON_FILE)
                wait_list.append({
                    "number": n['number'], "user_id": user_id, 
                    "username": username or first_name, "timestamp": time.time()
                })
                save_json_file(WAIT_JSON_FILE, wait_list)

            final_msg += f"\n{emoji} COUNTRY: {found_numbers[0]['country']}\n🏷️ Range: <code>{prefix}</code>\n\n<b>Menunggu OTP...</b>"
            kb = {"inline_keyboard": [[{"text": "🔄 Change", "callback_data": f"select_range:{prefix}"}], [{"text": "🌐 Menu", "callback_data": "getnum"}]]}
            get_tg_edit(user_id, msg_id, final_msg, reply_markup=kb)

        except Exception as e:
            get_tg_send(user_id, f"❌ Error: {str(e)}")

async def task_get_bot_loop(context):
    offset = 0
    print("✅ [GET BOT] Polling Started")
    while True:
        try:
            updates = requests.get(f"{GET_API_URL}/getUpdates?offset={offset}&timeout=10").json()
            for u in updates.get("result", []):
                offset = u["update_id"] + 1
                if "message" in u:
                    m = u["message"]
                    uid, text = m["from"]["id"], m.get("text", "")
                    fname = m["from"].get("first_name", "User")
                    uname = m["from"].get("username")

                    if text == "/start":
                        get_user_profile(uid, fname)
                        kb = {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}], [{"text": "💸 Withdraw", "callback_data": "withdraw_menu"}]]}
                        get_tg_send(uid, f"Halo {fname}! Selamat datang di Zura Bot.", kb)
                    
                    elif text == "/setdana":
                        get_waiting_dana_input.add(uid)
                        get_tg_send(uid, "Kirim data DANA:\n\n<code>Nomor\nNama</code>")

                    elif uid in get_waiting_dana_input:
                        lines = text.split('\n')
                        if len(lines) >= 2:
                            prof = load_json_file(PROFILE_FILE)
                            prof[str(uid)]["dana"] = lines[0].strip()
                            prof[str(uid)]["dana_an"] = lines[1].strip()
                            save_json_file(PROFILE_FILE, prof)
                            get_waiting_dana_input.remove(uid)
                            get_tg_send(uid, "✅ Data DANA disimpan.")
                
                if "callback_query" in u:
                    cq = u["callback_query"]
                    uid, data = cq["from"]["id"], cq["data"]
                    mid = cq["message"]["message_id"]
                    
                    if data == "getnum":
                        ranges = load_json_file(INLINE_RANGE_FILE)
                        kb_list = [[{"text": f"{r['emoji']} {r['range']}", "callback_data": f"select_range:{r['range']}"}] for r in ranges]
                        kb_list.append([{"text": "✍️ Input Manual", "callback_data": "manual_input"}])
                        get_tg_edit(uid, mid, "Pilih Range:", {"inline_keyboard": kb_list})
                    
                    elif data.startswith("select_range:"):
                        pre = data.split(":")[1]
                        asyncio.create_task(process_get_number(context, uid, pre, 1, cq["from"].get("username"), cq["from"].get("first_name"), mid))

        except: await asyncio.sleep(2)
        await asyncio.sleep(0.1)

# ==============================================================================
# 5. MODUL: SMS FORWARDER (DISPATCHER)
# ==============================================================================

async def task_sms_forwarder_loop():
    print("✅ [SMS FORWARDER] Active")
    while True:
        try:
            wait_list = load_json_file(WAIT_JSON_FILE)
            smc_data = load_json_file(OTP_SAVE_FILE)
            
            if not wait_list or not smc_data:
                await asyncio.sleep(2); continue

            updated_wait = []
            used_smc_indices = set()

            for wait_item in wait_list:
                num = wait_item['number']
                found = False
                for i, sms in enumerate(smc_data):
                    if i in used_smc_indices: continue
                    if normalize_number(sms['number']) == normalize_number(num):
                        # Match Found!
                        txt = (
                            f"🔔 <b>OTP RECEIVED</b>\n\n"
                            f"☎️ Nomor: <code>{num}</code>\n"
                            f"⚙️ Service: {sms['service']}\n"
                            f"🔐 OTP: <code>{sms['otp']}</code>\n\n"
                            f"🗯️ Full: {html.escape(sms['full_message'])}"
                        )
                        kb = {"inline_keyboard": [[{"text": f"📋 {sms['otp']}", "callback_data": "none"}]]}
                        get_tg_send(wait_item['user_id'], txt, kb)
                        
                        # Update Profile Balance
                        profs = load_json_file(PROFILE_FILE)
                        sid = str(wait_item['user_id'])
                        if sid in profs:
                            profs[sid]["balance"] += OTP_PRICE
                            profs[sid]["otp_semua"] += 1
                            save_json_file(PROFILE_FILE, profs)
                        
                        used_smc_indices.add(i)
                        found = True; break
                
                if not found and (time.time() - wait_item['timestamp'] < WAIT_TIMEOUT_SECONDS):
                    updated_wait.append(wait_item)
            
            # Cleanup processed items
            new_smc = [s for i, s in enumerate(smc_data) if i not in used_smc_indices]
            save_json_file(OTP_SAVE_FILE, new_smc)
            save_json_file(WAIT_JSON_FILE, updated_wait)

        except: pass
        await asyncio.sleep(2)

# ==============================================================================
# 6. MODUL: RANGE MONITOR (CONSOLE LOG)
# ==============================================================================

async def task_range_bot_loop(context):
    if not RANGE_BOT_TOKEN: return
    page = await context.new_page()
    filter_range = []
    
    while True:
        try:
            if DASHBOARD_CONSOLE_URL not in page.url:
                await page.goto(DASHBOARD_CONSOLE_URL)
            
            # Scrape console for new ranges
            logs = await page.locator(".group.flex.flex-col").all()
            for log in logs[:5]:
                try:
                    p_raw = await log.locator(".font-mono").last.inner_text()
                    c_raw = await log.locator(".text-slate-600").inner_text()
                    m_raw = await log.locator("p").inner_text()
                    
                    phone = clean_phone_number(p_raw)
                    if "XXX" in phone and phone not in filter_range:
                        filter_range.append(phone)
                        country = c_raw.split("•")[-1].strip()
                        
                        # Save to inline.json if not exists
                        inline = load_json_file(INLINE_RANGE_FILE)
                        if not any(x['range'] == phone for x in inline):
                            inline.append({"range": phone, "country": country, "emoji": get_country_emoji(country)})
                            save_json_file(INLINE_RANGE_FILE, inline[-15:]) # Keep last 15
                        
                        # Send to Range Channel
                        txt = f"🔥 <b>New Range Detected</b>\n\n📱 Range: <code>{phone}</code>\n🌍 {country} {get_country_emoji(country)}\n\n<blockquote>{m_raw}</blockquote>"
                        requests.post(f"https://api.telegram.org/bot{RANGE_BOT_TOKEN}/sendMessage", json={"chat_id": RANGE_CHAT_ID, "text": txt, "parse_mode": "HTML"})
                except: continue
            
            if len(filter_range) > 50: filter_range = filter_range[-20:]
            await asyncio.sleep(15)
        except: await asyncio.sleep(15)

# ==============================================================================
# 7. FLASK & MAIN ORCHESTRATOR
# ==============================================================================

app = Flask(__name__)
@app.route('/')
def index(): return "Zura Unified System Active"

async def main():
    print(f"🚀 [SYSTEM] Booting on Python {sys.version.split()[0]}...")
    
    # 1. Start Web Server
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, use_reloader=False), daemon=True).start()

    # 2. Start Playwright with Persistent Context (Internal Chromium)
    async with async_playwright() as p:
        print("🌐 [BROWSER] Launching Chromium...")
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir="browser_session",
            headless=False, # Set False agar Anda bisa login manual di awal
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        # 3. Parallel Execution
        await asyncio.gather(
            task_message_bot_loop(browser_context),
            task_get_bot_loop(browser_context),
            task_sms_forwarder_loop(),
            task_range_bot_loop(browser_context)
        )

if __name__ == "__main__":
    try:
        # Python 3.14 Windows fix: Proactor is default, no policy setting needed.
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 System Halted.")
