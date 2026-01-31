import asyncio
import os
import json
import re
import time
import math
import html
import requests
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Set

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv
from threading import Thread

# --- Flask untuk Fake Server (agar tidak mati di host tertentu) ---
from flask import Flask
app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "All-in-One Bot Running"

# ==============================================================================
# KONFIGURASI DAN SETUP
# ==============================================================================
load_dotenv()

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)

FILES = {
    "COUNTRY": os.path.join(DATA_DIR, "country.json"),
    "SMC": os.path.join(DATA_DIR, "smc.json"),
    "WAIT": os.path.join(DATA_DIR, "wait.json"),
    "USER": os.path.join(DATA_DIR, "user.json"),
    "CACHE": os.path.join(DATA_DIR, "cache.json"),
    "INLINE": os.path.join(DATA_DIR, "inline.json"),
    "AKSES_GET10": os.path.join(DATA_DIR, "aksesget10.json"),
    "PROFILE": os.path.join(DATA_DIR, "profile.json"),
    "OTP_CACHE": os.path.join(DATA_DIR, "otp_cache_msg.json"), # Cache khusus Message Bot
    "RANGE_CACHE": os.path.join(DATA_DIR, "range_cache_mnit.json") # Cache khusus Range Bot
}

# --- Initialize Files ---
def init_files():
    defaults = {k: "[]" for k in FILES}
    defaults["PROFILE"] = "{}"
    defaults["OTP_CACHE"] = "{}"
    defaults["RANGE_CACHE"] = "{}"
    # Country json harusnya sudah ada, kalau tidak buat kosong dulu
    if not os.path.exists(FILES["COUNTRY"]): defaults["COUNTRY"] = "{}"

    for key, path in FILES.items():
        if key == "COUNTRY": continue # Skip overwrite country
        if not os.path.exists(path):
            with open(path, "w") as f: f.write(defaults[key])

init_files()

# --- Load Country Data ---
def load_country_data():
    try:
        with open(FILES["COUNTRY"], "r", encoding='utf-8') as f:
            return json.load(f)
    except: return {}

GLOBAL_COUNTRY_EMOJI = load_country_data()

def get_country_emoji(country_name: str) -> str:
    return GLOBAL_COUNTRY_EMOJI.get(country_name.strip().upper(), "🌍")

# --- ENV VARIABLES ---
# Message Bot
BOT_MSG = os.getenv("TELEGRAM_BOT_TOKEN_MSG")
CHAT_MSG = os.getenv("TELEGRAM_CHAT_ID_MSG")
ADMIN_MSG = int(os.getenv("TELEGRAM_ADMIN_ID_MSG") or 0)

# Get & SMS Bot
BOT_GET = os.getenv("BOT_TOKEN_GET")
GROUP_ID_1 = int(os.getenv("GROUP_ID_1") or 0)
GROUP_ID_2 = int(os.getenv("GROUP_ID_2") or 0)
ADMIN_GET = int(os.getenv("ADMIN_ID_GET") or 0)
API_GET = f"https://api.telegram.org/bot{BOT_GET}"

# Range Bot
BOT_RANGE = os.getenv("BOT_TOKEN_RANGE")
CHAT_RANGE = os.getenv("TELEGRAM_CHAT_ID_RANGE") # Note: di script asli ada double dash, kita bersihkan
if CHAT_RANGE and CHAT_RANGE.startswith("--"): CHAT_RANGE = CHAT_RANGE[1:]
ADMIN_RANGE = int(os.getenv("ADMIN_ID_RANGE") or 0)

# Config Logic
WAIT_TIMEOUT_SECONDS = int(os.getenv("WAIT_TIMEOUT_SECONDS", 1800))
OTP_PRICE = 0.003500
MIN_WD_AMOUNT = 1.000000

# Login Credentials (Manual Override jika env kosong)
MNIT_EMAIL = os.getenv("MNIT_EMAIL", "")
MNIT_PASSWORD = os.getenv("MNIT_PASSWORD", "")

# URLs
LOGIN_URL = "https://x.mnitnetwork.com/mauth/login"
DASHBOARD_URL = "https://x.mnitnetwork.com/mdashboard/getnum"
CONSOLE_URL = "https://x.mnitnetwork.com/mdashboard/console"
TELEGRAM_BOT_LINK = "https://t.me/myzuraisgoodbot"
TELEGRAM_ADMIN_LINK = "https://t.me/Imr1d"
DONATE_LINK = "https://zurastore.my.id/donate"
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1"
GROUP_LINK_2 = "https://t.me/zura14g"

# --- Shared Utilities ---
def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding='utf-8') as f: return json.load(f)
        except: return [] if "profile" not in path and "cache" not in path else {}
    return [] if "profile" not in path and "cache" not in path else {}

def save_json(path, data):
    with open(path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def normalize_number(number):
    s = str(number).strip().replace(" ", "").replace("-", "")
    if not s.startswith('+') and s.isdigit(): s = '+' + s
    return s

# ==============================================================================
# CLASS: MESSAGE BOT (Monitoring General SMS)
# ==============================================================================
class MessageBot:
    def __init__(self, context):
        self.context = context
        self.page = None
        self.last_cleanup = ""

    async def start(self):
        self.page = await self.context.new_page()
        await self.page.goto(DASHBOARD_URL, wait_until='domcontentloaded')
        print("✅ [MESSAGE BOT] Page Initialized.")

    def filter_otp(self, lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cache = load_json(FILES["OTP_CACHE"])
        
        # Cleanup harian
        now_gmt = datetime.now(timezone.utc).strftime('%Y%m%d')
        last_clean = cache.pop('__LAST_CLEANUP_GMT__', '19700101')
        
        if now_gmt > last_clean:
            cache = {}
            last_clean = now_gmt
        
        out = []
        for d in lst:
            key = f"{d.get('otp')}_{d.get('phone')}"
            if d.get('otp') and key not in cache:
                cache[key] = {'t': datetime.now().isoformat()}
                out.append(d)
        
        cache['__LAST_CLEANUP_GMT__'] = last_clean
        save_json(FILES["OTP_CACHE"], cache)
        return out

    def mask_phone(self, phone):
        if not phone or phone == "N/A": return phone
        digits = re.sub(r'[^\d]', '', phone)
        if len(digits) < 7: return phone
        prefix = phone[0] if phone.startswith('+') else ""
        return f"{prefix}{digits[:5]}***{digits[-4:]}"

    def extract_otp(self, text):
        if not text: return None
        patterns = [r'(\d{3}[\s-]\d{3})', r'(?:code|otp|kode)[:\s]*([\d\s-]+)', r'\b(\d{4,8})\b']
        for p in patterns:
            m = re.search(p, text, re.I)
            if m: return re.sub(r'[^\d]', '', m.group(1) if m.groups() else m.group(0))
        return None

    def get_user_data(self, phone):
        wait_list = load_json(FILES["WAIT"])
        clean_target = re.sub(r'[^\d]', '', phone)
        for entry in wait_list:
            clean_entry = re.sub(r'[^\d]', '', str(entry.get("number", "")))
            if clean_target == clean_entry:
                return {"username": entry.get("username", "unknown"), "user_id": entry.get("user_id")}
        return {"username": "unknown", "user_id": None}

    async def fetch_sms(self):
        if not self.page: return []
        messages = []
        try:
            # Menggunakan teknik parsing DOM Playwright agar tidak blocking
            # Kita refresh jika perlu atau tunggu elemen
            try:
                # Cek apakah ada tabel
                await self.page.wait_for_selector('tbody', timeout=2000)
            except: pass

            # Mengambil data dari endpoint API (mirip script asli yg expect_response)
            # Namun untuk stabilitas 'One File', kita scrape DOM saja atau gunakan existing flow
            # Script asli menggunakan expect_response lambda
            pass # Logic fetch ada di loop utama
        except: pass
        return []

    async def logic_loop(self):
        while True:
            try:
                # Script asli message.py menggunakan expect_response pada /getnum/info
                # Kita simulasi klik "Number Info" untuk memicu request
                try:
                    async with self.page.expect_response(lambda r: "/getnum/info" in r.url, timeout=5000) as resp_info:
                        try:
                            # Klik header untuk trigger refresh/fetch
                            await self.page.click('th:has-text("Number Info")', timeout=1000)
                        except: 
                            await self.page.reload(wait_until='domcontentloaded')

                        response = await resp_info.value
                        json_data = await response.json()
                        
                        numbers = json_data.get('data', {}).get('numbers', [])
                        msgs = []
                        for item in numbers:
                            if item.get('status') == 'success' and item.get('message'):
                                raw_msg = item.get('message')
                                msgs.append({
                                    "otp": self.extract_otp(raw_msg),
                                    "phone": "+" + str(item.get('number')),
                                    "service": item.get('full_number') or "Facebook",
                                    "range": item.get('country', 'N/A'),
                                    "raw_message": raw_msg
                                })
                        
                        new_otps = self.filter_otp(msgs)
                        for otp_data in new_otps:
                            # Save to SMC for SMS/Get Bot
                            self.save_otp_to_smc(otp_data)
                            
                            # Send to Admin Channel (Message Bot function)
                            self.send_telegram(otp_data)
                except: pass
                
                await asyncio.sleep(2)
            except Exception as e:
                # print(f"[MSG BOT ERROR] {e}")
                await asyncio.sleep(5)

    def save_otp_to_smc(self, otp_data):
        data = {
            "service": otp_data.get('service', 'Unknown'),
            "number": otp_data.get('phone', 'N/A'),
            "otp": otp_data.get('otp', 'N/A'),
            "full_message": otp_data.get('raw_message', '')
        }
        existing = load_json(FILES["SMC"])
        existing.append(data)
        save_json(FILES["SMC"], existing)

    def send_telegram(self, otp_data):
        if not BOT_MSG or not CHAT_MSG: return
        otp, phone = otp_data.get('otp', 'N/A'), otp_data.get('phone', 'N/A')
        user_info = self.get_user_data(phone)
        user_tag = f"@{user_info['username'].replace('@', '')}" if user_info['username'] != "unknown" else "unknown"
        raw_msg = html.escape(otp_data.get('raw_message', 'No message content'))
        
        msg = (
            f"💭 <b>New Message Received</b>\n\n"
            f"<b>👤 User:</b> {user_tag}\n"
            f"<b>📱 Number:</b> <code>{self.mask_phone(phone)}</code>\n"
            f"<b>🌍 Country:</b> <b>{otp_data.get('range')} {get_country_emoji(otp_data.get('range', ''))}</b>\n"
            f"<b>✅ Service:</b> <b>{otp_data.get('service')}</b>\n\n"
            f"🔐 OTP: <code>{otp}</code>\n\n"
            f"<b>FULL MESSAGE:</b>\n"
            f"<blockquote>{raw_msg}</blockquote>"
        )
        
        kb = {"inline_keyboard": [[{"text": f"{otp}", "copy_text": {"text": otp}}, {"text": "🎭 Owner", "url": TELEGRAM_ADMIN_LINK}], [{"text": "📞 Get Number", "url": TELEGRAM_BOT_LINK}]]}
        
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_MSG}/sendMessage", json={'chat_id': CHAT_MSG, 'text': msg, 'parse_mode': 'HTML', 'reply_markup': kb}, timeout=10)
        except: pass

# ==============================================================================
# CLASS: RANGE BOT (Monitoring Console)
# ==============================================================================
class RangeBot:
    def __init__(self, context):
        self.context = context
        self.page = None
        self.sent_messages = {}
        self.ALLOWED_SERVICES = ['whatsapp', 'facebook']
        self.BANNED_COUNTRIES = ['angola']

    async def start(self):
        self.page = await self.context.new_page()
        await self.page.goto(CONSOLE_URL, wait_until='networkidle')
        print("✅ [RANGE BOT] Page Initialized.")

    async def logic_loop(self):
        while True:
            try:
                if self.page.url != CONSOLE_URL:
                    await self.page.goto(CONSOLE_URL, wait_until='domcontentloaded')
                
                # Selector logic from range.py
                CONSOLE_SELECTOR = ".group.flex.flex-col.sm\\:flex-row.sm\\:items-start.gap-3.p-3.rounded-lg"
                try: await self.page.wait_for_selector(CONSOLE_SELECTOR, timeout=5000)
                except: pass

                elements = await self.page.locator(CONSOLE_SELECTOR).all()
                msgs = []
                
                for element in elements:
                    try:
                        c_el = element.locator(".flex-shrink-0 .text-\\[10px\\].text-slate-600.mt-1.font-mono")
                        c_raw = await c_el.inner_text() if await c_el.count() > 0 else ""
                        c_name = re.search(r'•\s*(.*)$', c_raw.strip()).group(1).strip() if "•" in c_raw else "Unknown"
                        if c_name.lower() in self.BANNED_COUNTRIES: continue
                        
                        s_el = element.locator(".flex-grow.min-w-0 .text-xs.font-bold.text-blue-400")
                        s_raw = await s_el.inner_text() if await s_el.count() > 0 else ""
                        
                        is_allowed = False
                        for a in self.ALLOWED_SERVICES:
                            if a in s_raw.lower(): is_allowed = True; break
                        if not is_allowed: continue

                        # Clean service name
                        service = s_raw.strip().title()
                        if 'whatsapp' in s_raw.lower(): service = 'WhatsApp'
                        elif 'facebook' in s_raw.lower(): service = 'Facebook'
                        
                        p_el = element.locator(".flex-grow.min-w-0 .text-\\[10px\\].font-mono")
                        p_raw = await p_el.last.inner_text() if await p_el.count() > 0 else "N/A"
                        phone = re.sub(r'[^0-9X]', '', p_raw) or p_raw
                        
                        m_el = element.locator(".flex-grow.min-w-0 p")
                        m_raw = await m_el.inner_text() if await m_el.count() > 0 else ""
                        full_message = m_raw.replace('➜', '').strip()

                        if 'XXX' in phone and full_message:
                            msgs.append({"range_key": phone, "country": c_name, "service": service, "raw_message": full_message})
                    except: continue

                # Filter Unique
                unique = self.filter_messages(msgs)
                if unique:
                    for log in unique:
                        await self.send_to_telegram(log)
                
                # Cleanup Sent Messages
                self.cleanup_sent()
                await asyncio.sleep(5)
            except Exception as e:
                # print(f"[RANGE BOT ERROR] {e}")
                await asyncio.sleep(10)

    def filter_messages(self, lst):
        cache = load_json(FILES["RANGE_CACHE"])
        # Cleanup
        now_gmt = datetime.now(timezone.utc).strftime('%Y%m%d')
        last_clean = cache.pop('__LAST_CLEANUP_GMT__', '19700101')
        if now_gmt > last_clean: cache = {}; last_clean = now_gmt
        
        out = []
        for d in lst:
            key = f"{d['range_key']}_{hash(d['raw_message'])}"
            if key not in cache:
                cache[key] = {'timestamp': datetime.now().isoformat()}
                out.append(d)
        cache['__LAST_CLEANUP_GMT__'] = last_clean
        save_json(FILES["RANGE_CACHE"], cache)
        return out

    async def send_to_telegram(self, log):
        if not BOT_RANGE or not CHAT_RANGE: return
        
        range_val = log['range_key']
        if range_val in self.sent_messages:
            self.sent_messages[range_val]['count'] += 1
        else:
            self.sent_messages[range_val] = {'count': 1, 'timestamp': datetime.now()}
        
        count = self.sent_messages[range_val]['count']
        range_with_count = f"<code>{range_val}</code> ({count}x)" if count > 1 else f"<code>{range_val}</code>"
        
        msg = (
            "🔥Live message new range\n\n" 
            f"📱Range    : {range_with_count}\n"
            f"{get_country_emoji(log['country'])}Country : {log['country']}\n"
            f"⚙️ Service : {log['service']}\n\n" 
            "🗯️Message Available :\n"
            f"<blockquote>{html.escape(log['raw_message'])}</blockquote>"
        )
        
        kb = {"inline_keyboard": [[{"text": "📞GetNumber", "url": "https://t.me/myzuraisgoodbot?start=ZuraBot"}]]}
        
        # Kirim menggunakan requests (blocking inside async, but fast enough)
        try:
            # Delete old message if exists
            if 'message_id' in self.sent_messages[range_val]:
                requests.post(f"https://api.telegram.org/bot{BOT_RANGE}/deleteMessage", json={'chat_id': CHAT_RANGE, 'message_id': self.sent_messages[range_val]['message_id']})
            
            res = requests.post(f"https://api.telegram.org/bot{BOT_RANGE}/sendMessage", json={'chat_id': CHAT_RANGE, 'text': msg, 'parse_mode': 'HTML', 'reply_markup': kb})
            if res.ok:
                self.sent_messages[range_val]['message_id'] = res.json()['result']['message_id']
                self.sent_messages[range_val]['timestamp'] = datetime.now()
                
            # Save inline
            self.save_inline(range_val, log['country'], log['service'])
        except: pass

    def cleanup_sent(self):
        ten_minutes_ago = datetime.now() - timedelta(minutes=10)
        remove = [k for k, v in self.sent_messages.items() if v['timestamp'] < ten_minutes_ago]
        for k in remove: del self.sent_messages[k]

    def save_inline(self, range_val, country, service):
        service_map = {'whatsapp': 'WA', 'facebook': 'FB'}
        short = service_map.get(service.lower(), 'WA') # Default WA logic from script
        data = load_json(FILES["INLINE"])
        if any(item['range'] == range_val for item in data): return
        
        data.append({
            "range": range_val,
            "country": country.upper(),
            "emoji": get_country_emoji(country),
            "service": short
        })
        if len(data) > 10: data = data[-10:]
        save_json(FILES["INLINE"], data)

# ==============================================================================
# CLASS: SMS REWARD BOT (Distribution & Balance)
# ==============================================================================
class SmsRewardBot:
    def update_profile(self, user_id):
        profiles = load_json(FILES["PROFILE"])
        sid = str(user_id)
        if sid not in profiles:
            profiles[sid] = {"name": "User", "dana": "Belum Diset", "dana_an": "Belum Diset", "balance": 0.0, "otp_semua": 0, "otp_hari_ini": 0, "last_active": datetime.now().strftime("%Y-%m-%d")}
        
        p = profiles[sid]
        today = datetime.now().strftime("%Y-%m-%d")
        if p.get("last_active") != today:
            p["otp_hari_ini"] = 0
            p["last_active"] = today
        
        old_bal = p.get("balance", 0.0)
        p["otp_semua"] += 1
        p["otp_hari_ini"] += 1
        p["balance"] = old_bal + OTP_PRICE
        
        save_json(FILES["PROFILE"], profiles)
        return old_bal, p["balance"]

    async def run(self):
        print("✅ [SMS REWARD BOT] Started.")
        while True:
            try:
                wait_list = load_json(FILES["WAIT"])
                sms_data = load_json(FILES["SMC"])
                
                if not wait_list or not sms_data:
                    await asyncio.sleep(2)
                    continue
                
                new_wait = []
                current = time.time()
                changed = False
                
                for w in wait_list:
                    wnum = w.get('number', 'N/A')
                    uid = w.get('user_id')
                    start = w.get('timestamp', 0)
                    otp_recv = w.get('otp_received_time')
                    
                    # Cleanup finished session (5 min after OTP)
                    if otp_recv:
                        if current - otp_recv > 300: 
                            changed = True
                            continue # Remove
                        new_wait.append(w)
                        continue
                    
                    # Timeout (30 min)
                    if current - start > WAIT_TIMEOUT_SECONDS:
                        self.send_msg(uid, f"⚠️ <b>Waktu Habis</b>\nNomor: <code>{wnum}</code> telah dihapus karena tidak ada SMS masuk.")
                        changed = True
                        continue
                        
                    # Match SMS
                    remaining_sms = []
                    found = False
                    for sms in sms_data:
                        snum = str(sms.get("number") or sms.get("Number"))
                        if not found and snum == str(wnum):
                            otp = sms.get("otp") or "N/A"
                            svc = sms.get("service", "Unknown")
                            raw = sms.get("full_message") or "No content"
                            
                            is_wa = "whatsapp" in svc.lower()
                            if is_wa: bal_txt = "<i>WhatsApp OTP no balance</i>"
                            else:
                                o, n = self.update_profile(uid)
                                bal_txt = f"${o:.6f} > ${n:.6f}"
                            
                            msg = (
                                "🔔 <b>New Message Detected</b>\n\n"
                                f"☎️ <b>Nomor:</b> <code>{wnum}</code>\n"
                                f"⚙️ <b>Service:</b> <b>{svc}</b>\n\n"
                                f"💰 <b>added:</b> {bal_txt}\n\n"
                                f"🗯️ <b>Full Message:</b>\n"
                                f"<blockquote>{html.escape(raw)}</blockquote>\n\n"
                                "⚡ <b>Tap the Button To Copy OTP</b> ⚡"
                            )
                            kb = {"inline_keyboard": [[{"text": f" {otp}", "copy_text": {"text": otp}}, {"text": "💸 Donate", "url": DONATE_LINK}]]}
                            self.send_msg(uid, msg, kb)
                            
                            w['otp_received_time'] = time.time()
                            found = True
                            changed = True
                        else:
                            remaining_sms.append(sms)
                    
                    sms_data = remaining_sms
                    new_wait.append(w)
                
                if changed:
                    save_json(FILES["WAIT"], new_wait)
                    save_json(FILES["SMC"], sms_data)
                
                await asyncio.sleep(2)
            except Exception as e:
                # print(f"[SMS REWARD ERROR] {e}")
                await asyncio.sleep(5)

    def send_msg(self, chat_id, text, markup=None):
        if not BOT_GET: return
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_GET}/sendMessage", json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML', 'reply_markup': markup}, timeout=10)
        except: pass

# ==============================================================================
# CLASS: GET BOT (Telegram Interaction & Scraping)
# ==============================================================================
class GetBot:
    def __init__(self, context):
        self.context = context
        self.page = None
        self.pending_msg = {}
        self.waiting_input = {}
        self.lock = asyncio.Lock()
        
        # States
        self.waiting_broadcast = set()
        self.broadcast_data = {}
        self.waiting_admin = set()
        self.manual_range = set()
        self.get10_range = set()
        self.waiting_dana = set()
        self.last_used_range = {}

    async def start(self):
        self.page = await self.context.new_page()
        await self.page.goto(DASHBOARD_URL, wait_until='domcontentloaded')
        print("✅ [GET BOT] Page Initialized.")

    # --- Helpers ---
    def tg_send(self, chat_id, text, markup=None):
        try:
            r = requests.post(f"{API_GET}/sendMessage", json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML', 'reply_markup': markup}, timeout=10).json()
            return r['result']['message_id'] if r.get('ok') else None
        except: return None

    def tg_edit(self, chat_id, msg_id, text, markup=None):
        try: requests.post(f"{API_GET}/editMessageText", json={'chat_id': chat_id, 'message_id': msg_id, 'text': text, 'parse_mode': 'HTML', 'reply_markup': markup}, timeout=10)
        except: pass
    
    def tg_del(self, chat_id, msg_id):
        try: requests.post(f"{API_GET}/deleteMessage", json={'chat_id': chat_id, 'message_id': msg_id}, timeout=10)
        except: pass

    def get_progress_msg(self, step, prefix, count):
        bar_len = 12
        ratio = min(step / 12, 1.0)
        filled = math.ceil(ratio * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        status = {0: "Menunggu di antrian sistem aktif..", 3: "Mengirim permintaan nomor baru go.", 5: "Mencari nomor pada siklus satu run", 12: "Nomor ditemukan memproses data fin"}.get(step, "Memproses...")
        if step < 3: status = "Menunggu di antrian sistem aktif.."
        elif step < 5: status = "Memulai pencarian di tabel data.."
        elif step < 8: status = "Mencari nomor pada siklus satu run"
        elif step < 12: status = "Mencoba ulang pada siklus dua wait"
        return f"<code>{status}</code>\n<blockquote>Range: <code>{prefix}</code> | Jumlah: <code>{count}</code></blockquote>\n<code>Load:</code> [{bar}]"

    # --- Core Logic Scraping ---
    async def process_req(self, user_id, prefix, count, uname, fname, msg_id=None):
        msg_id = msg_id or self.pending_msg.pop(user_id, None)
        
        if self.lock.locked():
            if not msg_id: msg_id = self.tg_send(user_id, self.get_progress_msg(0, prefix, count))
            else: self.tg_edit(user_id, msg_id, self.get_progress_msg(0, prefix, count))
        
        async with self.lock:
            try:
                if not msg_id: msg_id = self.tg_send(user_id, self.get_progress_msg(0, prefix, count))
                
                # Check Page
                if self.page.url != DASHBOARD_URL:
                    await self.page.goto(DASHBOARD_URL, wait_until='domcontentloaded')

                # Fill Input
                INP = "input[name='numberrange']"
                await self.page.wait_for_selector(INP, state='visible', timeout=10000)
                await self.page.fill(INP, "")
                await self.page.fill(INP, prefix)
                
                # Click
                BTN = "button:has-text('Get Number')"
                await self.page.wait_for_selector(BTN, state='visible', timeout=10000)
                
                self.tg_edit(user_id, msg_id, self.get_progress_msg(3, prefix, count))
                for _ in range(count):
                    await self.page.click(BTN, force=True)
                
                self.tg_edit(user_id, msg_id, self.get_progress_msg(5, prefix, count))
                
                # Wait for results
                found = []
                # Logic Scraping Loop (simplified from original)
                start_time = time.time()
                while time.time() - start_time < 12: # 12 seconds max wait
                    rows = await self.page.locator("tbody tr").all()
                    current_batch = []
                    for row in rows[:count+5]: # Check top rows
                        try:
                            txt = await row.locator("td:nth-child(1) span.font-mono").inner_text()
                            num = normalize_number(txt.strip())
                            
                            # Cek status
                            st_el = row.locator("td:nth-child(1) div:nth-child(2) span")
                            st = await st_el.inner_text() if await st_el.count() else ""
                            
                            if "success" in st.lower() or "failed" in st.lower(): continue
                            
                            # Cek cache
                            cache = load_json(FILES["CACHE"])
                            if any(normalize_number(c['number']) == num for c in cache): continue

                            cnt_el = row.locator("td:nth-child(2) span.text-slate-200")
                            cnt = await cnt_el.inner_text() if await cnt_el.count() else "UNKNOWN"
                            
                            if num and len(num) > 5:
                                current_batch.append({'number': num, 'country': cnt.strip().upper()})
                        except: continue
                    
                    found = current_batch
                    if len(found) >= count: break
                    await asyncio.sleep(0.5)
                    self.tg_edit(user_id, msg_id, self.get_progress_msg(8, prefix, count))

                if not found:
                    self.tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN. Coba lagi atau ganti range.")
                    return

                self.tg_edit(user_id, msg_id, self.get_progress_msg(12, prefix, count))
                
                # Save Data
                cache_data = load_json(FILES["CACHE"])
                wait_list = load_json(FILES["WAIT"])
                
                ident = f"@{uname}" if uname else f'<a href="tg://user?id={user_id}">{fname}</a>'
                
                for entry in found[:count]:
                    cache_data.append({"number": entry['number'], "country": entry['country'], "user_id": user_id, "time": time.time()})
                    if len(cache_data) > 1000: cache_data.pop(0)
                    
                    # Remove old wait
                    wait_list = [x for x in wait_list if x['number'] != entry['number']]
                    wait_list.append({"number": entry['number'], "user_id": user_id, "username": ident, "timestamp": time.time()})

                save_json(FILES["CACHE"], cache_data)
                save_json(FILES["WAIT"], wait_list)
                
                # Format Result
                main_cnt = found[0]['country']
                emoji = get_country_emoji(main_cnt)
                
                if count == 10:
                    t = "✅The number is already.\n\n<code>" + "\n".join([x['number'] for x in found[:10]]) + "</code>"
                else:
                    t = "✅ The number is ready\n\n"
                    if count == 1: t += f"📞 Number  : <code>{found[0]['number']}</code>\n"
                    else: 
                        for i, x in enumerate(found[:count]): t += f"📞 Number {i+1} : <code>{x['number']}</code>\n"
                    t += f"{emoji} COUNTRY : {main_cnt}\n🏷️ Range   : <code>{prefix}</code>\n\n<b>🤖 Number available please use, Waiting for OTP</b>\n"

                kb = {"inline_keyboard": [
                    [{"text": "🔄 Change 1 Number", "callback_data": f"ch:1:{prefix}"}], 
                    [{"text": "🔄 Change 3 Number", "callback_data": f"ch:3:{prefix}"}],
                    [{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}, {"text": "🌐 Change Range", "callback_data": "getnum"}]
                ]}
                self.tg_edit(user_id, msg_id, t, kb)

            except Exception as e:
                # print(f"[PROCESS REQ ERROR] {e}")
                self.tg_edit(user_id, msg_id, "❌ Terjadi kesalahan. Coba lagi.")

    # --- Telegram Loop (Converted to async request handling via thread/loop) ---
    async def telegram_loop(self):
        print("✅ [GET BOT] Telegram Polling Started.")
        offset = 0
        while True:
            try:
                # Use synchronous requests in executor to avoid blocking main loop
                loop = asyncio.get_running_loop()
                data = await loop.run_in_executor(None, lambda: requests.get(f"{API_GET}/getUpdates", params={"offset": offset, "timeout": 5}).json())
                
                for upd in data.get("result", []):
                    offset = upd["update_id"] + 1
                    
                    # --- MESSAGE HANDLING ---
                    if "message" in upd:
                        msg = upd["message"]
                        uid = msg["from"]["id"]
                        cid = msg["chat"]["id"]
                        txt = msg.get("text", "")
                        fname = msg["from"].get("first_name", "User")
                        uname = msg["from"].get("username")
                        
                        # --- Admin Commands ---
                        if uid == ADMIN_GET:
                            if txt.startswith("/add"):
                                self.waiting_admin.add(uid)
                                self.tg_send(uid, "Kirim format: <code>range > country > service</code>")
                                continue
                            if txt == "/info":
                                self.waiting_broadcast.add(uid)
                                self.tg_send(uid, "Kirim pesan siaran. ketik .batal untuk batal.")
                                continue
                            if txt.startswith("/get10akses "):
                                tid = txt.split(" ")[1]
                                ak = load_json(FILES["AKSES_GET10"])
                                if int(tid) not in ak: 
                                    ak.append(int(tid))
                                    save_json(FILES["AKSES_GET10"], ak)
                                self.tg_send(uid, f"Akses get10 diberikan ke {tid}")
                                continue
                            if txt == "/list":
                                prof = load_json(FILES["PROFILE"])
                                c = ""
                                for i, (k,v) in enumerate(prof.items()):
                                    c += f"ID: {k} | Bal: {v.get('balance',0)}\n"
                                    if i % 10 == 0 and c: 
                                        self.tg_send(uid, c); c=""
                                if c: self.tg_send(uid, c)
                                continue

                        # --- User Commands ---
                        if txt == "/start":
                            users = set(load_json(FILES["USER"]))
                            users.add(uid)
                            save_json(FILES["USER"], list(users))
                            
                            # Check Groups
                            m1 = requests.get(f"{API_GET}/getChatMember", params={"chat_id": GROUP_ID_1, "user_id": uid}).json()
                            m2 = requests.get(f"{API_GET}/getChatMember", params={"chat_id": GROUP_ID_2, "user_id": uid}).json()
                            is_mem = (m1.get('result',{}).get('status') in ['member','creator','administrator']) and (m2.get('result',{}).get('status') in ['member','creator','administrator'])
                            
                            if is_mem:
                                p = load_json(FILES["PROFILE"]).get(str(uid), {})
                                bal = p.get('balance', 0.0)
                                t = f"✅ <b>Verifikasi Berhasil</b>\n\n👤 <b>Profil:</b>\n🔖 Nama: {fname}\n💰 Balance: ${bal:.6f}\n"
                                kb = {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}, {"text": "👨‍💼 Admin", "url": TELEGRAM_ADMIN_LINK}], [{"text": "💸 Withdraw Money", "callback_data": "wd_menu"}]]}
                                self.tg_send(uid, t, kb)
                            else:
                                kb = {"inline_keyboard": [[{"text": "📌 Grup 1", "url": GROUP_LINK_1}], [{"text": "📌 Grup 2", "url": GROUP_LINK_2}], [{"text": "✅ Verifikasi", "callback_data": "verify"}]]}
                                self.tg_send(uid, "Halo! Harap gabung kedua grup:", kb)
                            continue

                        # --- Input Handlers ---
                        if uid in self.waiting_admin:
                            self.waiting_admin.remove(uid)
                            # Parse range logic here (simplified)
                            lines = txt.split('\n')
                            il = load_json(FILES["INLINE"])
                            for l in lines:
                                if '>' in l:
                                    p = l.split('>')
                                    il.append({"range": p[0].strip(), "country": p[1].strip().upper(), "service": p[2].strip().upper() if len(p)>2 else "WA", "emoji": get_country_emoji(p[1].strip())})
                            save_json(FILES["INLINE"], il)
                            self.tg_send(uid, "Range disimpan.")
                            continue
                        
                        if uid in self.waiting_broadcast:
                            if txt == ".batal": 
                                self.waiting_broadcast.remove(uid)
                                self.tg_send(uid, "Batal.")
                            else:
                                self.waiting_broadcast.remove(uid)
                                us = load_json(FILES["USER"])
                                self.tg_send(uid, f"Mengirim ke {len(us)} user...")
                                for u in us: 
                                    self.tg_send(u, txt)
                                self.tg_send(uid, "Selesai.")
                            continue
                        
                        if uid in self.waiting_dana:
                            lines = txt.split('\n')
                            if len(lines) >= 2:
                                prof = load_json(FILES["PROFILE"])
                                if str(uid) not in prof: prof[str(uid)] = {}
                                prof[str(uid)]["dana"] = lines[0].strip()
                                prof[str(uid)]["dana_an"] = " ".join(lines[1:]).strip()
                                save_json(FILES["PROFILE"], prof)
                                self.tg_send(uid, "Dana disimpan.")
                                self.waiting_dana.remove(uid)
                            else: self.tg_send(uid, "Format salah. Baris 1: No, Baris 2: Nama.")
                            continue

                        # Get 10 Input
                        if uid in self.get10_range:
                            self.get10_range.remove(uid)
                            if re.match(r"^\+?\d+[Xx*#]+$", txt.strip()):
                                asyncio.create_task(self.process_req(uid, txt.strip(), 10, uname, fname))
                            else: self.tg_send(uid, "Format salah.")
                            continue
                        
                        # Manual Range Input
                        if uid in self.manual_range:
                            self.manual_range.remove(uid)
                            if re.match(r"^\+?\d+[Xx*#]+$", txt.strip()):
                                asyncio.create_task(self.process_req(uid, txt.strip(), 1, uname, fname))
                            else: self.tg_send(uid, "Format salah.")
                            continue
                        
                        if txt == "/get10":
                            ak = load_json(FILES["AKSES_GET10"])
                            if uid == ADMIN_GET or uid in ak:
                                self.get10_range.add(uid)
                                self.tg_send(uid, "Kirim range contoh 225071606XXX")
                            else: self.tg_send(uid, "No Access.")
                            continue

                    # --- CALLBACK HANDLING ---
                    if "callback_query" in upd:
                        cq = upd["callback_query"]
                        uid = cq["from"]["id"]
                        data_cb = cq["data"]
                        cid = cq["message"]["chat"]["id"]
                        mid = cq["message"]["message_id"]
                        fname = cq["from"].get("first_name", "User")
                        uname = cq["from"].get("username")
                        
                        if data_cb == "verify":
                            # Re-check logic (same as start)
                            users = set(load_json(FILES["USER"]))
                            if uid not in users: users.add(uid); save_json(FILES["USER"], list(users))
                            m1 = requests.get(f"{API_GET}/getChatMember", params={"chat_id": GROUP_ID_1, "user_id": uid}).json()
                            m2 = requests.get(f"{API_GET}/getChatMember", params={"chat_id": GROUP_ID_2, "user_id": uid}).json()
                            is_mem = (m1.get('result',{}).get('status') in ['member','creator','administrator']) and (m2.get('result',{}).get('status') in ['member','creator','administrator'])
                            
                            if is_mem:
                                p = load_json(FILES["PROFILE"]).get(str(uid), {})
                                bal = p.get('balance', 0.0)
                                t = f"✅ <b>Verifikasi Berhasil</b>\n\n💰 Balance: ${bal:.6f}"
                                kb = {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}, {"text": "👨‍💼 Admin", "url": TELEGRAM_ADMIN_LINK}], [{"text": "💸 Withdraw Money", "callback_data": "wd_menu"}]]}
                                self.tg_edit(cid, mid, t, kb)
                            else:
                                kb = {"inline_keyboard": [[{"text": "📌 Grup 1", "url": GROUP_LINK_1}], [{"text": "📌 Grup 2", "url": GROUP_LINK_2}], [{"text": "✅ Verifikasi", "callback_data": "verify"}]]}
                                self.tg_edit(cid, mid, "❌ Belum gabung kedua grup.", kb)
                        
                        elif data_cb == "getnum":
                            ir = load_json(FILES["INLINE"])
                            kb_list = []
                            for i in ir:
                                t = f"{i['emoji']} {i['country']} {i.get('service','WA')}"
                                kb_list.append([{"text": t, "callback_data": f"sel:{i['range']}"}])
                            kb_list.append([{"text": "Input Manual Range..🖊️", "callback_data": "manual_range"}])
                            self.tg_edit(cid, mid, "<b>Get Number</b>\nPilih range:", {"inline_keyboard": kb_list})
                        
                        elif data_cb == "manual_range":
                            self.manual_range.add(uid)
                            self.tg_edit(cid, mid, "Kirim range manual:")
                            self.pending_msg[uid] = mid
                        
                        elif data_cb.startswith("sel:"):
                            rng = data_cb.split(":")[1]
                            asyncio.create_task(self.process_req(uid, rng, 1, uname, fname, mid))
                        
                        elif data_cb.startswith("ch:"):
                            parts = data_cb.split(":")
                            cnt = int(parts[1])
                            rng = parts[2]
                            self.tg_del(cid, mid)
                            msg_n = self.tg_send(cid, "Memproses ganti nomor...")
                            asyncio.create_task(self.process_req(uid, rng, cnt, uname, fname, msg_n))
                        
                        elif data_cb == "wd_menu":
                            prof = load_json(FILES["PROFILE"]).get(str(uid), {})
                            d = prof.get("dana", "Belum Diset")
                            da = prof.get("dana_an", "-")
                            bal = prof.get("balance", 0.0)
                            t = f"<b>💸 Withdraw</b>\nDana: {d}\nA/N: {da}\nBal: ${bal:.6f}\nMin: ${MIN_WD_AMOUNT}"
                            kb = {"inline_keyboard": [
                                [{"text": "$1", "callback_data": "wd:1.0"}, {"text": "$2", "callback_data": "wd:2.0"}],
                                [{"text": "⚙️ Setting Dana", "callback_data": "set_dana"}],
                                [{"text": "🔙 Kembali", "callback_data": "verify"}]
                            ]}
                            self.tg_edit(cid, mid, t, kb)
                        
                        elif data_cb == "set_dana":
                            self.waiting_dana.add(uid)
                            self.tg_edit(cid, mid, "Kirim:\nNo Dana\nNama")

                        elif data_cb.startswith("wd:"):
                            amt = float(data_cb.split(":")[1])
                            prof = load_json(FILES["PROFILE"])
                            if str(uid) not in prof or prof[str(uid)].get("dana") == "Belum Diset":
                                self.tg_send(cid, "Set dana dulu!")
                            elif prof[str(uid)].get("balance", 0) < amt:
                                self.tg_send(cid, "Saldo kurang!")
                            else:
                                prof[str(uid)]["balance"] -= amt
                                save_json(FILES["PROFILE"], prof)
                                # Admin Notif (Simplified)
                                ad_msg = f"User {uid} WD ${amt}. Dana: {prof[str(uid)]['dana']}"
                                kb_ad = {"inline_keyboard": [[{"text": "Approve", "callback_data": f"ap:{uid}:{amt}"}, {"text": "Cancel", "callback_data": f"cn:{uid}:{amt}"}]]}
                                self.tg_send(ADMIN_GET, ad_msg, kb_ad)
                                self.tg_edit(cid, mid, "Permintaan dikirim.")

                        # Admin WD Action
                        elif uid == ADMIN_GET and (data_cb.startswith("ap:") or data_cb.startswith("cn:")):
                            act, tuid, tamt = data_cb.split(":")
                            if act == "ap":
                                self.tg_edit(cid, mid, "Approved.")
                                self.tg_send(tuid, "WD Sukses.")
                            else:
                                prof = load_json(FILES["PROFILE"])
                                prof[tuid]["balance"] += float(tamt)
                                save_json(FILES["PROFILE"], prof)
                                self.tg_edit(cid, mid, "Cancelled & Refunded.")
                                self.tg_send(tuid, "WD Dibatalkan.")

            except Exception as e:
                # print(f"[TELEGRAM LOOP ERROR] {e}")
                pass
            
            await asyncio.sleep(0.1)

# ==============================================================================
# MAIN SYSTEM LOGIC
# ==============================================================================
async def main():
    print("🚀 [SYSTEM] Starting All-In-One Bot...")
    
    # 1. Start Playwright
    async with async_playwright() as p:
        # Launch Browser (Headless - No CDP needed)
        # Use args to bypass some bot detection if needed
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context()
        
        # 2. Global Login
        print("🔑 [SYSTEM] Attempting Login to MNIT Network...")
        page = await context.new_page()
        try:
            await page.goto(LOGIN_URL, timeout=30000)
            
            # Cek jika sudah login
            if "mdashboard" in page.url:
                print("✅ [SYSTEM] Already Logged In.")
            else:
                # Login Process
                if not MNIT_EMAIL or not MNIT_PASSWORD:
                    print("❌ [SYSTEM] Email/Password not set in .env! Cannot login.")
                else:
                    await page.fill('input[type="email"]', MNIT_EMAIL)
                    await page.fill('input[type="password"]', MNIT_PASSWORD)
                    await page.click('button[type="submit"]')
                    try:
                        await page.wait_for_url(re.compile(r".*/mdashboard.*"), timeout=30000)
                        print("✅ [SYSTEM] Login Success!")
                    except:
                        print("❌ [SYSTEM] Login Failed (Timeout/Wrong Creds). Bots might not work.")
        except Exception as e:
            print(f"⚠️ [SYSTEM] Login Error: {e}")
        finally:
            await page.close()

        # 3. Instantiate Bots
        msg_bot = MessageBot(context)
        range_bot = RangeBot(context)
        sms_reward_bot = SmsRewardBot()
        get_bot = GetBot(context)

        # 4. Start Browser Tasks
        await msg_bot.start()
        await range_bot.start()
        await get_bot.start()

        # 5. Run Loops Concurrently
        await asyncio.gather(
            msg_bot.logic_loop(),
            range_bot.logic_loop(),
            sms_reward_bot.run(),
            get_bot.telegram_loop()
        )

if __name__ == "__main__":
    # Run Fake Server for Hosting
    Thread(target=lambda: app_flask.run(host='0.0.0.0', port=5000), daemon=True).start()
    
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 System Stopped.")

