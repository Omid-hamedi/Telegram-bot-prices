# -*- coding: utf-8 -*-
import io
import json
import math
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

# ===================== تنظیمات =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip() or "PUT_YOUR TOKEN HERE" #توکن رو اینجا بزار . put your token here
if not BOT_TOKEN or BOT_TOKEN.startswith("__"):
    sys.exit("❌ توکن ربات تنظیم نشده است.")

SUPPORT_ID = os.environ.get("SUPPORT_ID", "") #put your telegram id
ADMIN_ID = int(os.environ.get("ADMIN_ID") or 0)  # آیدی عددی خودت را به‌جای 0 بگذار PUT YOUR ID IN 0

TRC20_WALLET = os.environ.get("TRC20_WALLET", "").strip()
TON_WALLET = os.environ.get("TON_WALLET", "").strip()
HAS_WALLET = bool(TRC20_WALLET or TON_WALLET)

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": BROWSER_UA, "Accept": "application/json"}

COINGECKO_KEY = os.environ.get("COINGECKO_KEY", "").strip() or "API KEY HERE"  # put  api key . کلید ای پی ایتو اینجا وارد کن
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_IDS = {
    "btc": "bitcoin", "eth": "ethereum", "ton": "the-open-network", "trx": "tron",
    "sol": "solana", "doge": "dogecoin", "xrp": "ripple", "bnb": "binancecoin",
}
NERKH_URL = "https://nerkh.jahankhahan.shop/data/live.jso"

# نام هر دارایی در algotik-tse (اولین نام جواب بدهد کافی است)
ALG_NAMES = {
    "usd": ["dollar", "دلار"],
    "eur": ["euro", "یورو"],
    "gbp": ["pound", "پوند"],
    "aed": ["dirham", "درهم"],
    "try": ["lira", "لیر"],
    "gold18": ["gold_18", "طلای 18 عیار"],
    "gold24": ["gold_24", "طلای 24 عیار"],
    "sekee": ["sekeh", "سکه"],
    "nim": ["nim_sekeh", "نیم سکه"],
    "rob": ["rob_sekeh", "ربع سکه"],
    "gerami": ["sekeh_gerami", "سکه گرمی"],
    "ounce": ["ons", "انس"],
}

ALG_REFRESH = 60
NERKH_REFRESH = 30
CG_REFRESH = 360

CHECK_INTERVAL = 20
CACHE_SECONDS = 10
STALE_SECONDS = 900
DEFAULT_THRESHOLD = 0.5
THRESHOLDS = [0, 0.25, 0.5, 1, 2, 5]
DAILY_HOURS = [8, 9, 12, 18, 21]
MAX_ALERTS = 10
HISTORY_STEP = 300
HISTORY_KEEP = 7 * 86400
DATA_FILE = "bot_data.json"
HISTORY_FILE = "history.json"
OLD_SUBS_FILE = "subscribers.json"
TEHRAN = timezone(timedelta(hours=3, minutes=30))
# ====================================================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# ---------------- تعریف دارایی‌ها ----------------
CATS = {"fx": "💱 ارزها", "gold": "🏅 طلا و سکه", "crypto": "₿ ارز دیجیتال"}

# key, عنوان، دسته، واحد مقدار (برای ماشین‌حساب)
_ASSET_LIST = [
    ("usd", "💵 دلار", "fx", "دلار"),
    ("eur", "💶 یورو", "fx", "یورو"),
    ("gbp", "💷 پوند", "fx", "پوند"),
    ("aed", "🇦🇪 درهم امارات", "fx", "درهم"),
    ("try", "🇹🇷 لیر ترکیه", "fx", "لیر"),
    ("usdt", "🪙 تتر", "fx", "تتر"),
    ("gold18", "🥇 طلای ۱۸ عیار", "gold", "گرم"),
    ("gold24", "🥇 طلای ۲۴ عیار", "gold", "گرم"),
    ("sekee", "🏅 سکه امامی", "gold", "عدد"),
    ("nim", "🏅 نیم سکه", "gold", "عدد"),
    ("rob", "🏅 ربع سکه", "gold", "عدد"),
    ("gerami", "🏅 سکه گرمی", "gold", "عدد"),
    ("ounce", "🌍 انس طلا", "gold", "اونس"),
    ("btc", "₿ بیت‌کوین", "crypto", "BTC"),
    ("eth", "💠 اتریوم", "crypto", "ETH"),
    ("ton", "💎 تون", "crypto", "TON"),
    ("trx", "🔺 ترون", "crypto", "TRX"),
    ("sol", "☀️ سولانا", "crypto", "SOL"),
    ("doge", "🐶 دوج‌کوین", "crypto", "DOGE"),
    ("xrp", "💧 ریپل", "crypto", "XRP"),
    ("bnb", "🔶 بایننس‌کوین", "crypto", "BNB"),
]
ASSETS = {k: t for k, t, _, _ in _ASSET_LIST}
CAT_OF = {k: c for k, _, c, _ in _ASSET_LIST}
QTY = {k: q for k, _, _, q in _ASSET_LIST}
ASSETS_IN = {c: [k for k, _, cc, _ in _ASSET_LIST if cc == c] for c in CATS}
CRYPTO_SYMS = ASSETS_IN["crypto"]

# دکمه‌های منو
BTN_USD, BTN_USDT = "💵 قیمت دلار", "🪙 قیمت تتر"
BTN_GOLD, BTN_OUNCE = "🥇 قیمت طلای ۱۸ عیار", "🌍 قیمت انس طلا"
BTN_FX, BTN_GOLDS, BTN_CRYPTO = "💱 ارزها", "🏅 سکه و طلا", "₿ ارز دیجیتال"
BTN_ALL, BTN_CALC = "📊 همه قیمت‌ها", "🧮 ماشین‌حساب"
BTN_ALERT, BTN_CHART = "🎯 هشدار قیمتی", "📈 نمودار"
BTN_SETTINGS, BTN_HELP = "⚙️ تنظیمات", "📖 راهنما"
QUICK = {BTN_USD: "usd", BTN_GOLD: "gold18", BTN_USDT: "usdt", BTN_OUNCE: "ounce"}
CAT_BTNS = {BTN_FX: "fx", BTN_GOLDS: "gold", BTN_CRYPTO: "crypto"}

MODES = ("price", "alert", "chart", "calc", "auto")
MODE_PROMPT = {
    "price": "یکی را انتخاب کنید 👇",
    "alert": "🎯 هشدار برای کدام مورد تنظیم شود؟",
    "chart": "📈 نمودار کدام مورد؟",
    "calc": "🧮 ماشین‌حساب برای کدام مورد؟",
    "auto": "⏱ کدام ارزها را خودکار دنبال کنم؟",
}
MODE_PREFIX = {"price": "p", "alert": "an", "chart": "chp", "calc": "cc", "auto": "sub"}


_ALIAS_RAW = {
    "usd": ["دلار", "دلار آمریکا", "dollar", "usd"],
    "eur": ["یورو", "euro", "eur"],
    "gbp": ["پوند", "gbp"],
    "aed": ["درهم", "aed"],
    "try": ["لیر", "try"],
    "usdt": ["تتر", "usdt", "tether"],
    "gold18": ["طلا", "طلای 18", "طلای 18 عیار", "طلای ۱۸", "gold", "gold18"],
    "gold24": ["طلای 24", "طلای 24 عیار", "gold24"],
    "sekee": ["سکه", "سکه امامی", "امامی", "emami"],
    "nim": ["نیم", "نیم سکه"],
    "rob": ["ربع", "ربع سکه"],
    "gerami": ["سکه گرمی", "گرمی"],
    "ounce": ["انس", "اونس", "انس طلا", "ons", "ounce"],
    "btc": ["بیت کوین", "بیتکوین", "btc", "bitcoin"],
    "eth": ["اتریوم", "eth", "ethereum"],
    "ton": ["تون", "ton", "تون کوین"],
    "trx": ["ترون", "trx", "tron"],
    "sol": ["سولانا", "sol", "solana"],
    "doge": ["دوج", "دوج کوین", "doge", "dogecoin"],
    "xrp": ["ریپل", "xrp", "ripple"],
    "bnb": ["بایننس کوین", "bnb"],
}


_TR = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩يك", "01234567890123456789یک")


def norm(x):
    """یکسان‌سازی ارقام، ی و ک عربی، نیم‌فاصله و حروف."""
    return re.sub(r"\s+", " ", str(x).translate(_TR).replace("\u200c", " ").lower()).strip()


ALIASES = {norm(a): k for k, names in _ALIAS_RAW.items() for a in names}


def _to_num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return None


def parse_number(text):
    t = norm(text).replace(",", "").replace("٬", "").replace("٫", ".")
    try:
        v = float(t)
        return v if math.isfinite(v) else None
    except Exception:
        return None


def fmt(n):
    n = float(n)
    if n >= 1000:
        return f"{n:,.0f}"
    if n >= 1:
        return f"{n:,.2f}"
    if n >= 0.01:
        return f"{n:,.4f}"
    return f"{n:.6f}"


def fmt_q(n):
    """مقدار کاربر بدون صفرهای اضافی (500 به‌جای 500.00)."""
    n = float(n)
    s = f"{n:,.0f}" if n >= 1000 else f"{n:,.6f}".rstrip("0").rstrip(".")
    return s or "0"


def hhmm(ts, sec=True):
    return datetime.fromtimestamp(ts, TEHRAN).strftime("%H:%M:%S" if sec else "%H:%M")


def md_escape(text):
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, "\\" + ch)
    return text


def wallet_text():
    parts = ["💎 آدرس‌های کیف پول:\n"]
    if TRC20_WALLET:
        parts.append(f"USDT (TRC20):\n`{TRC20_WALLET}`\n")
    if TON_WALLET:
        parts.append(f"TON:\n`{TON_WALLET}`")
    return "\n".join(parts)



DB = {"subs": {}, "alerts": [], "thr": {}, "daily": {}, "users": set(), "last": {}, "next_id": 1}
_db_lock = threading.RLock()
STATE = {}  # chat_id -> حالت انتظار برای ورودی متنی (هشدار / ماشین‌حساب)


def load_db():
    with _db_lock:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            DB["subs"] = {int(c): {k for k in ks if k in ASSETS} for c, ks in raw.get("subs", {}).items()}
            DB["alerts"] = [a for a in raw.get("alerts", []) if a.get("key") in ASSETS]
            DB["thr"] = {int(c): float(v) for c, v in raw.get("thr", {}).items()}
            DB["daily"] = {int(c): int(v) for c, v in raw.get("daily", {}).items()}
            DB["users"] = {int(c) for c in raw.get("users", [])}
            DB["last"] = {k: float(v) for k, v in raw.get("last", {}).items()}
            DB["next_id"] = int(raw.get("next_id", 1))
        except FileNotFoundError:
            try:  # انتقال از نسخه‌ی قبلی
                with open(OLD_SUBS_FILE, "r", encoding="utf-8") as f:
                    for cid, ks in json.load(f).items():
                        valid = {k for k in ks if k in ASSETS}
                        if valid:
                            DB["subs"][int(cid)] = valid
                            DB["users"].add(int(cid))
            except Exception:
                pass
        except Exception as e:
            print("load_db error:", e)


def save_db():
    with _db_lock:
        try:
            raw = {
                "subs": {str(c): sorted(k) for c, k in DB["subs"].items()},
                "alerts": DB["alerts"],
                "thr": {str(c): v for c, v in DB["thr"].items()},
                "daily": {str(c): v for c, v in DB["daily"].items()},
                "users": sorted(DB["users"]),
                "last": DB["last"],
                "next_id": DB["next_id"],
            }
            tmp = DATA_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False)
            os.replace(tmp, DATA_FILE)
        except Exception as e:
            print("save_db error:", e)


def touch_user(chat):
    if getattr(chat, "type", "private") != "private":
        return
    with _db_lock:
        if chat.id not in DB["users"]:
            DB["users"].add(chat.id)
            save_db()


def drop_chat(chat_id):
    with _db_lock:
        DB["subs"].pop(chat_id, None)
        DB["thr"].pop(chat_id, None)
        DB["daily"].pop(chat_id, None)
        DB["users"].discard(chat_id)
        DB["alerts"] = [a for a in DB["alerts"] if a["chat"] != chat_id]
        for k in [k for k in DB["last"] if k.startswith(f"{chat_id}|")]:
            DB["last"].pop(k, None)
        save_db()
    STATE.pop(chat_id, None)



HISTORY = {}
_hist_lock = threading.Lock()
_hist_dirty = {"v": False}
_plot_lock = threading.Lock()


def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        with _hist_lock:
            for k, pts in raw.items():
                if k in ASSETS:
                    HISTORY[k] = [[float(t), float(p)] for t, p in pts]
    except FileNotFoundError:
        pass
    except Exception as e:
        print("load_history error:", e)


def save_history():
    with _hist_lock:
        if not _hist_dirty["v"]:
            return
        try:
            tmp = HISTORY_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(HISTORY, f)
            os.replace(tmp, HISTORY_FILE)
            _hist_dirty["v"] = False
        except Exception as e:
            print("save_history error:", e)


def record_history(result, since):
    with _hist_lock:
        for key, d in result.items():
            pts = HISTORY.setdefault(key, [])
            if not pts or d["ts"] - pts[-1][0] >= HISTORY_STEP:
                pts.append([d["ts"], d["price"]])
                _hist_dirty["v"] = True
            cutoff = d["ts"] - HISTORY_KEEP
            while pts and pts[0][0] < cutoff:
                pts.pop(0)


def day_range(key, hours=24):
    cutoff = time.time() - hours * 3600
    with _hist_lock:
        vals = [p for t, p in HISTORY.get(key, []) if t >= cutoff]
    return (min(vals), max(vals)) if len(vals) >= 2 else None


def make_chart(key, hours):

    try:
        from matplotlib.figure import Figure
        import matplotlib.dates as mdates
    except Exception:
        return "nolib"
    cutoff = time.time() - hours * 3600
    with _hist_lock:
        pts = [(t, p) for t, p in HISTORY.get(key, []) if t >= cutoff]
    if len(pts) < 2:
        return None
    xs = [datetime.fromtimestamp(t, TEHRAN) for t, _ in pts]
    ys = [p for _, p in pts]
    with _plot_lock:
        fig = Figure(figsize=(8, 4), dpi=110)
        ax = fig.subplots()
        ax.plot(xs, ys, linewidth=1.8)
        ax.fill_between(xs, ys, min(ys), alpha=0.12)
        ax.set_title(f"{key.upper()}  -  last {'24h' if hours == 24 else '7d'}")
        ax.grid(True, alpha=0.3)
        pattern = "%H:%M" if hours <= 24 else "%m/%d %H:%M"
        ax.xaxis.set_major_formatter(mdates.DateFormatter(pattern, tz=TEHRAN))
        fig.autofmt_xdate()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return buf



try:
    import algotik_tse as att
    ATT_ERROR = ""
except Exception as _e:  # نصب نبودن کتابخانه
    att = None
    ATT_ERROR = f"{type(_e).__name__}: {_e}"

_cache = {"time": 0, "data": {}}
_lock = threading.Lock()
_src = {}            # وضعیت هر منبع: آخرین نتیجه، زمان و خطا
_alg_errs = {}       # خطای هر نام در algotik-tse
_alg_fail = {}       # key -> [تعداد خطای پیاپی، زمان تلاش بعدی]
_nerkh_sample = {"s": ""}
TETHER_WORDS = ("tether", "usdt", "تتر")


def _cached(name, ttl, fn):
    """نتیجه‌ی fn را تا ttl ثانیه نگه می‌دارد؛ در خطا آخرین مقدار سالم (تا STALE_SECONDS) برمی‌گردد."""
    s = _src.setdefault(name, {"t": 0, "v": None, "ts": 0, "err": ""})
    now = time.time()
    if now - s["t"] >= ttl:
        s["t"] = now
        try:
            v = fn()
            if v:
                s["v"], s["ts"], s["err"] = v, time.time(), ""
            else:
                s["err"] = "نتیجه‌ی خالی"
        except Exception as e:
            s["err"] = f"{type(e).__name__}: {e}"[:300]
    if s["v"] is not None and time.time() - s["ts"] > STALE_SECONDS:
        s["v"] = None
    return s["v"], s["ts"]


# ----- algotik-tse -----
def _df_last_prev(df):
    """آخرین قیمت و قیمت ردیف قبلی را از DataFrame درمی‌آورد."""
    if df is None or getattr(df, "empty", True):
        return None
    try:
        if type(df.index).__name__ != "RangeIndex":
            df = df.sort_index()
    except Exception:
        pass
    cols = {str(c).strip().lower(): c for c in df.columns}
    col = next((cols[c] for c in ("close", "final", "last", "price", "adj close", "آخرین", "پایانی", "قیمت")
                if c in cols), None)
    if col is not None:
        vals = [_to_num(x) for x in df[col].tolist()]
    else:  # ستون قیمت مشخص نیست: میانگین ستون‌های عددی غیر از تاریخ و حجم
        skip = ("date", "تاریخ", "vol", "حجم", "count", "تعداد", "value", "ارزش")
        use = [c for c in df.columns if not any(w in str(c).lower() for w in skip)]
        vals = []
        for _, row in df[use].iterrows():
            nums = [n for n in (_to_num(x) for x in row.tolist()) if n is not None and math.isfinite(n)]
            vals.append(sum(nums) / len(nums) if nums else None)
    vals = [v for v in vals if v is not None and math.isfinite(v) and v > 0]
    if not vals:
        return None
    return {"raw": vals[-1], "prev": vals[-2] if len(vals) > 1 else None}


def _alg_one(names):
    last = None
    for nm in names:
        try:
            df = att.get_currency(nm, limit=2)
        except Exception as e:
            last = f"{nm}: {type(e).__name__}: {e}"
            continue
        r = _df_last_prev(df)
        if r:
            return r
        last = f"{nm}: داده‌ی خالی"
    raise RuntimeError(last or "نامی تعریف نشده")


def _algotik_fetch():
    if att is None:
        raise RuntimeError("algotik-tse نصب نیست: " + ATT_ERROR)
    now = time.time()
    todo = {k: n for k, n in ALG_NAMES.items() if _alg_fail.get(k, [0, 0])[1] <= now}
    out, failed = {}, {}
    ex = ThreadPoolExecutor(max_workers=3)
    futs = {ex.submit(_alg_one, names): k for k, names in todo.items()}
    try:
        for f in as_completed(futs, timeout=40):
            k = futs[f]
            try:
                out[k] = f.result()
                _alg_errs.pop(k, None)
            except Exception as e:
                failed[k] = str(e)[:200]
    except Exception:
        _alg_errs["_timeout"] = "بعضی درخواست‌ها به موقع تمام نشد"
    ex.shutdown(wait=False)
    for k, msg in failed.items():
        _alg_errs[k] = msg
        if out:
            n = _alg_fail.get(k, [0, 0])[0] + 1
            _alg_fail[k] = [n, now + (1800 if n >= 3 else 0)]
    for k in out:
        _alg_fail.pop(k, None)
    return out


# ----- CoinGecko -----
def _coingecko_fetch():
    r = requests.get(COINGECKO_URL, headers=HEADERS, timeout=10, params={
        "ids": ",".join(COINGECKO_IDS.values()), "vs_currencies": "usd",
        "include_24hr_change": "true", "x_cg_demo_api_key": COINGECKO_KEY})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
    data = r.json()
    out = {}
    for key, cid in COINGECKO_IDS.items():
        d = data.get(cid) or {}
        p = _to_num(d.get("usd"))
        if p:
            out[key] = {"price": p, "change": d.get("usd_24h_change")}
    return out



def _find_number(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"\d[\d,]*\.?\d*", norm(v))
        return _to_num(m.group(0)) if m else None
    if isinstance(v, dict):
        for k in ("price", "p", "value", "last", "latest", "sell", "rate", "current", "buy"):
            if k in v:
                n = _find_number(v[k])
                if n:
                    return n
    return None


def _find_tether(data):

    hits = []

    def walk(obj, path):
        if isinstance(obj, dict):
            label = norm(" ".join(str(obj.get(k, "")) for k in
                                  ("name", "title", "symbol", "key", "slug", "label", "name_en", "fa", "en")))
            for k, v in obj.items():
                if any(t in norm(k) for t in TETHER_WORDS):
                    n = _find_number(v)
                    if n:
                        hits.append((n, path + [k]))
            if any(t in label for t in TETHER_WORDS):
                n = _find_number(obj)
                if n:
                    hits.append((n, path))
            for k, v in obj.items():
                walk(v, path + [k])
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, path + [i])

    walk(data, [])
    for n, path in hits:
        if 5_000 <= n <= 6_000_000:
            return n, "/".join(map(str, path))
    return None


def _nerkh_fetch():
    errs = []
    urls = [NERKH_URL] + ([NERKH_URL + "n"] if NERKH_URL.endswith(".jso") else [])
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code != 200:
                errs.append(f"{url} -> HTTP {r.status_code}")
                continue
            data = r.json()
            _nerkh_sample["s"] = json.dumps(data, ensure_ascii=False)[:1500]
            found = _find_tether(data)
            if found:
                return {"raw": found[0], "path": found[1]}
            errs.append("تتر در JSON پیدا نشد")
        except Exception as e:
            errs.append(f"{url} -> {type(e).__name__}")
    raise RuntimeError("; ".join(errs))



def guess_toman(v):
    """نرخ دلار و تتر را بر اساس بازه‌ی منطقی (۱۰ هزار تا ۶۰۰ هزار تومان) به تومان می‌رساند."""
    while v > 600_000:
        v /= 10
    while v < 10_000:
        v *= 10
    return v


def fit(raw, anchor, default_factor):
    """بین raw و raw×۰.۱ و raw×۱۰ نزدیک‌ترین عدد به قیمت مرجع را برمی‌گرداند."""
    if anchor and anchor > 0:
        return min((raw, raw * 0.1, raw * 10), key=lambda x: abs(math.log(x / anchor)))
    return raw * default_factor if default_factor else None


def fetch_prices(force=False):
    with _lock:
        now = time.time()
        if not force and _cache["data"] and now - _cache["time"] < CACHE_SECONDS:
            return _cache["data"]

        result = {k: v for k, v in _cache["data"].items() if now - v["ts"] < STALE_SECONDS}

        def put(key, price, unit, change=None, extra=None, ts=None):
            result[key] = {"price": price, "unit": unit, "change": change,
                           "ts": ts or time.time(), "extra": extra or []}

        alg, alg_ts = _cached("alg", ALG_REFRESH, _algotik_fetch)
        teth, teth_ts = _cached("nerkh", NERKH_REFRESH, _nerkh_fetch)
        cg, cg_ts = _cached("coingecko", CG_REFRESH, _coingecko_fetch)
        alg = alg or {}

        def chg(k):
            it = alg.get(k)
            if it and it.get("prev"):
                return f"{(it['raw'] - it['prev']) / it['prev'] * 100:.2f}"
            return None

        # دلار و تتر
        usd_t = usdt_t = factor = None
        if "usd" in alg:
            raw = alg["usd"]["raw"]
            usd_t = guess_toman(raw)
            factor = usd_t / raw
            put("usd", usd_t, "تومان", chg("usd"), ts=alg_ts)
        if teth:
            usdt_t = guess_toman(teth["raw"])
            put("usdt", usdt_t, "تومان", ts=teth_ts)
        if usdt_t is None and usd_t:
            put("usdt", usd_t, "تومان (تقریبی، برابر دلار)", ts=alg_ts)
        if usd_t is None and usdt_t:
            usd_t = usdt_t
            put("usd", usdt_t, "تومان (تقریبی، بر پایه تتر)", ts=teth_ts)

        # انس طلا
        oz = None
        if "ounce" in alg and alg["ounce"]["raw"] > 100:
            oz = alg["ounce"]["raw"]
            put("ounce", oz, "دلار", chg("ounce"), ts=alg_ts)
        oz_ref = oz or result.get("ounce", {}).get("price")
        usd_ref = usd_t or result.get("usd", {}).get("price")
        est24 = oz_ref / 31.1035 * usd_ref if (oz_ref and usd_ref) else None
        est18 = est24 * 0.75 if est24 else None

        def conv(k, anchor):
            it = alg.get(k)
            return fit(it["raw"], anchor, factor) if it else None

        g18 = conv("gold18", est18)
        if g18:
            extra = [f"🫧 اختلاف با قیمت جهانی: `{(g18 / est18 - 1) * 100:+.1f}%`"] if est18 else []
            put("gold18", g18, "تومان (هر گرم)", chg("gold18"), extra, ts=alg_ts)
        elif est18 and "gold18" not in result:
            put("gold18", est18, "تومان (هر گرم، محاسبه‌ای بدون حباب)")

        specs = [
            ("gold24", "تومان (هر گرم)", est24),
            ("sekee", "تومان", est24 * 8.136 if est24 else None),
            ("nim", "تومان", est24 * 4.068 if est24 else None),
            ("rob", "تومان", est24 * 2.034 if est24 else None),
            ("gerami", "تومان", est24),
            ("eur", "تومان", usd_ref * 1.15 if usd_ref else None),
            ("gbp", "تومان", usd_ref * 1.30 if usd_ref else None),
            ("aed", "تومان", usd_ref * 0.272 if usd_ref else None),
            ("try", "تومان", usd_ref * 0.022 if usd_ref else None),
        ]
        for k, unit, anchor in specs:
            v = conv(k, anchor)
            if v:
                put(k, v, unit, chg(k), ts=alg_ts)

        if cg:
            usdt_ref = usdt_t or result.get("usdt", {}).get("price")
            for sym in CRYPTO_SYMS:
                it = cg.get(sym)
                if it:
                    extra = [f"≈ `{fmt(it['price'] * usdt_ref)}` تومان"] if usdt_ref else []
                    ch = it.get("change")
                    ch = f"{ch:.2f}" if isinstance(ch, (int, float)) else None
                    put(sym, it["price"], "دلار", ch, extra, ts=cg_ts)

        if result:
            record_history(result, now)
            _cache["data"] = result
            _cache["time"] = time.time()
        return result or None


def price_text(key, data, prev=None):
    if not data or key not in data:
        return f"❌ قیمت {ASSETS[key]} الان در دسترس نیست. کمی بعد دوباره امتحان کنید."
    d = data[key]
    lines = [f"{ASSETS[key]}\n", f"💰 قیمت: `{fmt(d['price'])}` {d['unit']}"]
    ch = d.get("change")
    if ch not in (None, ""):
        lines.append(f"📈 تغییر: `{ch}%`")
    if prev:
        lines.append(f"↔️ نسبت به اعلان قبلی: `{(d['price'] - prev) / prev * 100:+.2f}%`")
    rng = day_range(key)
    if rng:
        lines.append(f"📊 ۲۴ ساعت: `{fmt(rng[0])}` تا `{fmt(rng[1])}`")
    lines += d.get("extra", [])
    lines.append(f"🕒 {hhmm(d['ts'])}")
    return "\n".join(lines)


def all_prices_text(data):
    txt = "📊 *قیمت‌ها*\n"
    for cat, title in CATS.items():
        txt += f"\n*{title}*\n"
        for k in ASSETS_IN[cat]:
            if data and k in data:
                txt += f"{ASSETS[k]}: `{fmt(data[k]['price'])}` {data[k]['unit']}\n"
            else:
                txt += f"{ASSETS[k]}: ❌ نامشخص\n"
    return txt + f"\n🕒 {hhmm(time.time())}"


def toman_price(key, data):
    """قیمت هر واحد دارایی به تومان (برای دارایی‌های دلاری با نرخ دلار ضرب می‌شود)."""
    d = data.get(key) if data else None
    if not d:
        return None
    if d["unit"].startswith("دلار"):
        u = (data.get("usd") or data.get("usdt") or {}).get("price")
        return d["price"] * u if u else None
    return d["price"]


def calc_text(key, amount, direction, data):
    tp = toman_price(key, data)
    if not tp:
        return "❌ قیمت این مورد الان در دسترس نیست."
    q = QTY[key]
    if direction == "to":
        total = amount * tp
        line = f"🧮 `{fmt_q(amount)}` {q} {ASSETS[key]}\n\n≈ `{fmt(total)}` تومان"
        d = data[key]
        if d["unit"].startswith("دلار"):
            line += f"\n≈ `{fmt(amount * d['price'])}` دلار"
        return line
    return f"🧮 `{fmt_q(amount)}` تومان\n\n≈ `{fmt_q(amount / tp)}` {q} {ASSETS[key]}"


def parse_query(text):
    """متن آزاد کاربر را به (key, amount) تبدیل می‌کند؛ مثلا '500 دلار' یا 'btc'."""
    nt = norm(text)
    nt = re.sub(r"^قیمت ", "", nt)
    if nt in ALIASES:
        return ALIASES[nt], None
    m = re.search(r"\d[\d,]*\.?\d*", nt)
    if not m:
        return None
    amount = _to_num(m.group(0))
    rest = (nt[:m.start()] + " " + nt[m.end():])
    rest = " ".join(w for w in rest.split() if w not in ("گرم", "عدد", "تا", "واحد", "قیمت"))
    if amount and rest in ALIASES:
        return ALIASES[rest], amount
    return None


def safe_send(chat_id, text, **kw):
    try:
        bot.send_message(chat_id, text, **kw)
        return True
    except ApiTelegramException as e:
        if e.error_code == 403 or "chat not found" in str(e).lower():
            drop_chat(chat_id)
        else:
            print("send error:", e)
    except Exception as e:
        print("send error:", e)
    return False


def safe_edit(text, chat_id, mid, reply_markup=None):
    try:
        bot.edit_message_text(text, chat_id, mid, reply_markup=reply_markup)
    except ApiTelegramException as e:
        if "message is not modified" not in str(e):
            raise


def send_or_edit(chat_id, mid, text, kb=None):
    if mid:
        safe_edit(text, chat_id, mid, kb)
    else:
        bot.send_message(chat_id, text, reply_markup=kb)


Btn = types.InlineKeyboardButton


def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(BTN_USD, BTN_USDT)
    kb.add(BTN_GOLD, BTN_OUNCE)
    kb.add(BTN_FX, BTN_GOLDS, BTN_CRYPTO)
    kb.add(BTN_ALL, BTN_CALC)
    kb.add(BTN_ALERT, BTN_CHART)
    kb.add(BTN_SETTINGS, BTN_HELP)
    return kb


def cats_kb(mode):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for c, t in CATS.items():
        kb.add(Btn(t, callback_data=f"cat_{mode}_{c}"))
    return kb


def assets_kb(mode, cat, chat_id=None):
    with _db_lock:
        subs = set(DB["subs"].get(chat_id, set()))
    kb = types.InlineKeyboardMarkup(row_width=2)
    btns = []
    for k in ASSETS_IN[cat]:
        mark = "✅ " if mode == "auto" and k in subs else ""
        btns.append(Btn(f"{mark}{ASSETS[k]}", callback_data=f"{MODE_PREFIX[mode]}_{k}"))
    kb.add(*btns)
    if mode == "auto":
        kb.add(Btn("🔙 بازگشت", callback_data="auto_menu"))
    elif mode != "price":
        kb.add(Btn("🔙 بازگشت", callback_data=f"cats_{mode}"))
    return kb


def price_kb(key):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(Btn("🔄 بروزرسانی", callback_data=f"p_{key}"))
    kb.add(Btn("📈 ۲۴ ساعت", callback_data=f"ch_{key}_24"), Btn("📈 ۷ روز", callback_data=f"ch_{key}_168"))
    kb.add(Btn("🎯 هشدار", callback_data=f"an_{key}"), Btn("🧮 محاسبه", callback_data=f"cc_{key}"))
    kb.add(Btn("🔙 هم‌دسته‌ها", callback_data=f"cat_price_{CAT_OF[key]}"))
    return kb


def settings_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        Btn("⏱ حالت خودکار (اعلان با تغییر قیمت)", callback_data="auto_menu"),
        Btn("🎚 حساسیت اعلان خودکار", callback_data="thr"),
        Btn("🗞 گزارش روزانه", callback_data="daily"),
        Btn("🎯 هشدارهای من", callback_data="alerts"),
        Btn("🔔 وضعیت اعلان‌های من", callback_data="my_status"),
    )
    return kb


def help_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(Btn("💬 پشتیبانی", callback_data="support"))
    if HAS_WALLET:
        kb.add(Btn("❤️ حمایت از ما", callback_data="donate"))
    kb.add(Btn("ℹ️ درباره ربات", callback_data="about"))
    return kb


def back_kb(target="back_settings"):
    return types.InlineKeyboardMarkup().add(Btn("🔙 بازگشت", callback_data=target))


HELP_TEXT = (
    "📖 *راهنما*\n\n"
    "• دکمه‌های منو: قیمت دلار، تتر، طلا، سکه، ارز دیجیتال و ...\n"
    "• 📊 *همه قیمت‌ها*: همه چیز یکجا\n"
    "• 🎯 *هشدار قیمتی*: وقتی قیمت به عدد دلخواه رسید خبرتان می‌کنم\n"
    "• ⚙️ *تنظیمات*: اعلان خودکار با تغییر قیمت، حساسیت اعلان و گزارش روزانه\n"
    "• 🧮 *ماشین‌حساب*: یا مستقیم بنویسید، مثلا `500 دلار` یا `10 گرم طلا` یا `2 btc`\n"
    "• 📈 *نمودار* قیمت ۲۴ ساعت و ۷ روز اخیر\n"
    "• نوشتن اسم یک ارز (مثل `دلار` یا `btc`) هم قیمتش را می‌دهد"
)


def process_alerts(data):
    fired = []
    with _db_lock:
        keep = []
        for a in DB["alerts"]:
            d = data.get(a["key"])
            if d:
                p = d["price"]
                if (a["dir"] == "above" and p >= a["target"]) or (a["dir"] == "below" and p <= a["target"]):
                    fired.append(a)
                    continue
            keep.append(a)
        if fired:
            DB["alerts"] = keep
            save_db()
    for a in fired:
        word = "بالاتر از" if a["dir"] == "above" else "پایین‌تر از"
        safe_send(a["chat"], f"🎯 *هشدار قیمتی*\n\n{ASSETS[a['key']]} به {word} `{fmt(a['target'])}` رسید.\n\n"
                  + price_text(a["key"], data))
        time.sleep(0.05)


def process_subs(data):
    with _db_lock:
        snap = {c: set(k) for c, k in DB["subs"].items()}
        thr = dict(DB["thr"])
    dirty = False
    for chat, keys in snap.items():
        th = thr.get(chat, DEFAULT_THRESHOLD)
        for key in keys:
            d = data.get(key)
            if not d:
                continue
            price = d["price"]
            lk = f"{chat}|{key}"
            last = DB["last"].get(lk)
            if last is not None:
                if th <= 0:
                    if price == last:
                        continue
                elif last == 0 or abs(price - last) / last * 100 < th:
                    continue
            if safe_send(chat, "🔔 *تغییر قیمت*\n\n" + price_text(key, data, prev=last)):
                with _db_lock:
                    DB["last"][lk] = price
                dirty = True
                time.sleep(0.05)
            elif chat not in DB["subs"]:
                break
    if dirty:
        save_db()


_daily_sent = {}


def process_daily(data):
    now = datetime.now(TEHRAN)
    today = now.date().isoformat()
    with _db_lock:
        targets = [c for c, h in DB["daily"].items() if h == now.hour]
    for c in targets:
        if _daily_sent.get(c) == today:
            continue
        _daily_sent[c] = today
        safe_send(c, "🗞 *گزارش روزانه*\n\n" + all_prices_text(data))
        time.sleep(0.05)


def auto_worker():
    last_hist_save = time.time()
    while True:
        try:
            data = fetch_prices(force=True)
            if data:
                process_alerts(data)
                process_subs(data)
                process_daily(data)
            if time.time() - last_hist_save > 600:
                save_history()
                last_hist_save = time.time()
        except Exception as e:
            print("auto_worker error:", e)
        time.sleep(CHECK_INTERVAL)


def show_price(chat_id, key, mid=None):
    send_or_edit(chat_id, mid, price_text(key, fetch_prices()), price_kb(key))


def show_cats(chat_id, mode, mid=None):
    send_or_edit(chat_id, mid, MODE_PROMPT[mode], cats_kb(mode))


def show_auto_menu(chat_id, mid=None):
    kb = cats_kb("auto")
    kb.add(Btn("⛔ توقف همه", callback_data="stop_all"))
    kb.add(Btn("🔙 بازگشت", callback_data="back_settings"))
    send_or_edit(chat_id, mid,
                 "⏱ *حالت خودکار*\n\nدسته را انتخاب کنید و ارزهای مورد نظر را فعال کنید؛ "
                 "با تغییر قیمت (طبق حساسیتی که تنظیم کرده‌اید) برایتان پیام می‌فرستم.", kb)


def show_alerts(chat_id, mid=None):
    with _db_lock:
        mine = [a for a in DB["alerts"] if a["chat"] == chat_id]
    kb = types.InlineKeyboardMarkup(row_width=1)
    lines = []
    for a in mine:
        arrow = "⬆️" if a["dir"] == "above" else "⬇️"
        lines.append(f"{arrow} {ASSETS[a['key']]} — {fmt(a['target'])}")
        kb.add(Btn(f"❌ حذف: {ASSETS[a['key']]} {arrow} {fmt(a['target'])}", callback_data=f"adel_{a['id']}"))
    kb.add(Btn("➕ هشدار جدید", callback_data="cats_alert"))
    kb.add(Btn("🔙 بازگشت", callback_data="back_settings"))
    if lines:
        text = f"🎯 *هشدارهای قیمتی من* ({len(lines)}/{MAX_ALERTS})\n\n" + "\n".join(lines)
    else:
        text = "🎯 *هشدارهای قیمتی*\n\nهنوز هشداری نساخته‌اید."
    send_or_edit(chat_id, mid, text, kb)


def show_thr(chat_id, mid=None):
    with _db_lock:
        cur = DB["thr"].get(chat_id, DEFAULT_THRESHOLD)
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(*[Btn(("✅ " if v == cur else "") + ("هر تغییر" if v == 0 else f"{v}٪"), callback_data=f"th_{v}")
             for v in THRESHOLDS])
    kb.add(Btn("🔙 بازگشت", callback_data="back_settings"))
    cur_txt = "هر تغییر" if cur == 0 else f"{cur}٪"
    send_or_edit(chat_id, mid,
                 "🎚 *حساسیت اعلان خودکار*\n\nفقط وقتی قیمت نسبت به آخرین اعلان حداقل این‌قدر تغییر کند پیام می‌فرستم.\n"
                 f"حساسیت فعلی: `{cur_txt}`", kb)


def show_daily(chat_id, mid=None):
    with _db_lock:
        cur = DB["daily"].get(chat_id)
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(*[Btn(("✅ " if h == cur else "") + f"{h:02d}:00", callback_data=f"dl_{h}") for h in DAILY_HOURS])
    kb.add(Btn("⛔ خاموش" + (" ✅" if cur is None else ""), callback_data="dl_off"))
    kb.add(Btn("🔙 بازگشت", callback_data="back_settings"))
    send_or_edit(chat_id, mid,
                 "🗞 *گزارش روزانه*\n\nهر روز در ساعت انتخابی (به وقت ایران) خلاصه‌ی همه‌ی قیمت‌ها را می‌فرستم.", kb)


def send_chart(chat_id, key, hours):
    res = make_chart(key, hours)
    if res == "nolib":
        bot.send_message(chat_id, "📈 برای نمودار باید کتابخانه‌ی matplotlib نصب شود:\n`pip install matplotlib`")
    elif res is None:
        bot.send_message(chat_id, "📈 هنوز داده‌ی کافی ثبت نشده؛ چند دقیقه‌ی دیگر دوباره امتحان کنید.")
    else:
        bot.send_photo(chat_id, res, caption=f"{ASSETS[key]} — {'۲۴ ساعت' if hours == 24 else '۷ روز'} اخیر")


def my_status_text(chat_id):
    with _db_lock:
        s = set(DB["subs"].get(chat_id, set()))
        th = DB["thr"].get(chat_id, DEFAULT_THRESHOLD)
        daily = DB["daily"].get(chat_id)
        n_alerts = sum(1 for a in DB["alerts"] if a["chat"] == chat_id)
    lines = ["🔔 *وضعیت من*\n"]
    if s:
        lines.append("اعلان خودکار:\n" + "\n".join(f"• {ASSETS[k]}" for k in ASSETS if k in s))
    else:
        lines.append("🔕 اعلان خودکاری فعال نیست.")
    lines.append(f"\n🎚 حساسیت: `{'هر تغییر' if th == 0 else str(th) + '٪'}`")
    lines.append(f"🗞 گزارش روزانه: {f'{daily:02d}:00' if daily is not None else 'خاموش'}")
    lines.append(f"🎯 هشدارهای فعال: {n_alerts}")
    return "\n".join(lines)


def _is_admin(m):
    return bool(ADMIN_ID) and m.from_user.id == ADMIN_ID


@bot.message_handler(commands=["start"])
def start(m):
    touch_user(m.chat)
    STATE.pop(m.chat.id, None)
    bot.send_message(
        m.chat.id,
        f"سلام {m.from_user.first_name} 👋\nبه ربات قیمت لحظه‌ای خوش اومدی.\nاز منوی زیر انتخاب کن:",
        reply_markup=main_menu(), parse_mode=None)


@bot.message_handler(commands=["help"])
def help_cmd(m):
    touch_user(m.chat)
    bot.send_message(m.chat.id, HELP_TEXT, reply_markup=help_kb())


@bot.message_handler(commands=["price"])
def price_cmd(m):
    arg = m.text.partition(" ")[2].strip()
    q = parse_query(arg) if arg else None
    if q:
        show_price(m.chat.id, q[0])
    else:
        bot.send_message(m.chat.id, "مثال: `/price btc` یا `/price دلار`")


@bot.message_handler(commands=["admin"])
def admin_cmd(m):
    if not _is_admin(m):
        return
    with _db_lock:
        txt = (f"👑 پنل ادمین\n\n👥 کاربران: {len(DB['users'])}\n🔔 دارای اعلان خودکار: {len(DB['subs'])}\n"
               f"🎯 هشدارهای فعال: {len(DB['alerts'])}\n🗞 گزارش روزانه: {len(DB['daily'])}\n\n"
               "پیام همگانی:\n/broadcast متن پیام\n\nعیب‌یابی: /debug")
    bot.send_message(m.chat.id, txt, parse_mode=None)


@bot.message_handler(commands=["broadcast"])
def broadcast_cmd(m):
    if not _is_admin(m):
        return
    text = m.text.partition(" ")[2].strip()
    if not text:
        bot.send_message(m.chat.id, "استفاده: /broadcast متن پیام", parse_mode=None)
        return
    with _db_lock:
        ids = list(DB["users"])
    ok = 0
    for cid in ids:
        if safe_send(cid, text, parse_mode=None):
            ok += 1
        time.sleep(0.05)
    bot.send_message(m.chat.id, f"✅ برای {ok} از {len(ids)} کاربر ارسال شد.", parse_mode=None)


@bot.message_handler(commands=["debug"])
def debug(m):
    if not _is_admin(m):
        return
    prices = fetch_prices(force=True) or {}
    missing = [k for k in ASSETS if k not in prices]
    lines = [f"✅ موجود: {len(prices)}", f"❌ ناموجود: {', '.join(missing) or '—'}", ""]
    for name, st in _src.items():
        lines.append(f"{name}: {'OK' if st['v'] else 'FAIL'} {st['err']}")
    if att is None:
        lines.append("algotik-tse نصب نیست: " + ATT_ERROR)
    for k, e in _alg_errs.items():
        lines.append(f"algotik[{k}]: {e}")
    nerkh = (_src.get("nerkh") or {}).get("v")
    if nerkh:
        lines.append(f"تتر از مسیر: {nerkh['path']} (خام: {nerkh['raw']})")
    bot.send_message(m.chat.id, "\n".join(lines)[:4000], parse_mode=None)
    if _nerkh_sample["s"] and not nerkh:
        bot.send_message(m.chat.id, "نمونه‌ی JSON تتر:\n" + _nerkh_sample["s"][:3500], parse_mode=None)


def handle_state_input(m, st):
    chat_id = m.chat.id
    num = parse_number(m.text)
    if num is None or num <= 0:
        bot.send_message(chat_id, "❌ یک عدد معتبر بفرستید (مثلا 100000) یا یکی از دکمه‌های منو را بزنید.",
                         parse_mode=None)
        return
    key = st["key"]
    data = fetch_prices()
    if st["mode"] == "calc":
        STATE.pop(chat_id, None)
        bot.send_message(chat_id, calc_text(key, num, st["dir"], data))
        return
    # هشدار قیمتی
    d = (data or {}).get(key)
    if not d:
        STATE.pop(chat_id, None)
        bot.send_message(chat_id, "❌ قیمت این مورد الان در دسترس نیست؛ کمی بعد دوباره امتحان کنید.")
        return
    cur = d["price"]
    if (st["dir"] == "above" and cur >= num) or (st["dir"] == "below" and cur <= num):
        bot.send_message(chat_id, f"⚠️ قیمت فعلی (`{fmt(cur)}`) همین حالا هم در این محدوده است. "
                                  "عدد دیگری بفرستید یا انصراف دهید.")
        return
    with _db_lock:
        if sum(1 for a in DB["alerts"] if a["chat"] == chat_id) >= MAX_ALERTS:
            STATE.pop(chat_id, None)
            bot.send_message(chat_id, f"❌ حداکثر {MAX_ALERTS} هشدار فعال می‌توانید داشته باشید. یکی را حذف کنید.")
            return
        DB["alerts"].append({"id": DB["next_id"], "chat": chat_id, "key": key, "dir": st["dir"],
                             "target": num, "created": time.time()})
        DB["next_id"] += 1
        save_db()
    STATE.pop(chat_id, None)
    word = "بالاتر از" if st["dir"] == "above" else "پایین‌تر از"
    bot.send_message(chat_id, f"✅ هشدار ثبت شد.\n\nوقتی {ASSETS[key]} {word} `{fmt(num)}` {d['unit']} شد خبرتان می‌کنم.")


@bot.message_handler(func=lambda m: True, content_types=["text"])
def text_handler(m):
    touch_user(m.chat)
    chat_id, t = m.chat.id, m.text.strip()

    if t in QUICK:
        STATE.pop(chat_id, None)
        bot.send_chat_action(chat_id, "typing")
        show_price(chat_id, QUICK[t])
    elif t in CAT_BTNS:
        STATE.pop(chat_id, None)
        cat = CAT_BTNS[t]
        bot.send_message(chat_id, f"{CATS[cat]}\n\n{MODE_PROMPT['price']}", reply_markup=assets_kb("price", cat))
    elif t == BTN_ALL:
        STATE.pop(chat_id, None)
        bot.send_chat_action(chat_id, "typing")
        bot.send_message(chat_id, all_prices_text(fetch_prices()))
    elif t == BTN_CALC:
        STATE.pop(chat_id, None)
        show_cats(chat_id, "calc")
    elif t == BTN_ALERT:
        STATE.pop(chat_id, None)
        show_alerts(chat_id)
    elif t == BTN_CHART:
        STATE.pop(chat_id, None)
        show_cats(chat_id, "chart")
    elif t == BTN_SETTINGS:
        STATE.pop(chat_id, None)
        bot.send_message(chat_id, "⚙️ *تنظیمات*", reply_markup=settings_kb())
    elif t == BTN_HELP:
        STATE.pop(chat_id, None)
        help_cmd(m)
    elif chat_id in STATE:
        handle_state_input(m, STATE[chat_id])
    else:
        q = parse_query(t)
        if q and q[1] is None:
            show_price(chat_id, q[0])
        elif q:
            bot.send_message(chat_id, calc_text(q[0], q[1], "to", fetch_prices()))
        else:
            bot.send_message(chat_id, "از دکمه‌های منو استفاده کنید 👇\nیا اسم یک ارز را بنویسید، مثلا `دلار` یا `500 دلار`.",
                             reply_markup=main_menu())


@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):
    chat_id, mid, d = c.message.chat.id, c.message.message_id, c.data
    touch_user(c.message.chat)
    parts = d.split("_")
    cmd = parts[0]
    key = parts[1] if len(parts) > 1 else None
    toast = None

    try:
        if d == "back_help":
            safe_edit(HELP_TEXT, chat_id, mid, help_kb())
        elif d == "back_settings":
            safe_edit("⚙️ *تنظیمات*", chat_id, mid, settings_kb())

        elif cmd == "cat" and len(parts) == 3 and key in MODES and parts[2] in CATS:
            safe_edit(f"{CATS[parts[2]]}\n\n{MODE_PROMPT[key]}", chat_id, mid, assets_kb(key, parts[2], chat_id))
        elif cmd == "cats" and key in MODES:
            if key == "auto":
                show_auto_menu(chat_id, mid)
            else:
                show_cats(chat_id, key, mid)
        elif d == "auto_menu":
            show_auto_menu(chat_id, mid)

        elif cmd == "p" and key in ASSETS:
            show_price(chat_id, key, mid)

        elif cmd == "chp" and key in ASSETS:
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(Btn("۲۴ ساعت", callback_data=f"ch_{key}_24"), Btn("۷ روز", callback_data=f"ch_{key}_168"))
            kb.add(Btn("🔙 بازگشت", callback_data=f"cat_chart_{CAT_OF[key]}"))
            safe_edit(f"📈 {ASSETS[key]}\n\nبازه‌ی نمودار:", chat_id, mid, kb)
        elif cmd == "ch" and key in ASSETS and len(parts) == 3 and parts[2] in ("24", "168"):
            send_chart(chat_id, key, int(parts[2]))

        elif cmd == "an" and key in ASSETS:
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(Btn("⬆️ وقتی بالاتر رفت", callback_data=f"ad_{key}_above"),
                   Btn("⬇️ وقتی پایین‌تر آمد", callback_data=f"ad_{key}_below"),
                   Btn("🔙 بازگشت", callback_data="alerts"))
            safe_edit(f"🎯 هشدار برای {ASSETS[key]}\n\nکی خبرتان کنم؟", chat_id, mid, kb)
        elif cmd == "ad" and key in ASSETS and len(parts) == 3 and parts[2] in ("above", "below"):
            STATE[chat_id] = {"mode": "alert", "key": key, "dir": parts[2]}
            cur = (fetch_prices() or {}).get(key)
            cur_line = f"\nقیمت فعلی: `{fmt(cur['price'])}` {cur['unit']}" if cur else ""
            word = "یا بالاتر" if parts[2] == "above" else "یا پایین‌تر"
            safe_edit(f"🎯 {ASSETS[key]}\n\nعدد هدف را بفرستید (فقط عدد). وقتی قیمت به آن عدد {word} رسید خبر می‌دهم.{cur_line}",
                      chat_id, mid, back_kb("cancel"))
        elif d == "cancel":
            STATE.pop(chat_id, None)
            safe_edit("❌ لغو شد.", chat_id, mid)
        elif d == "alerts":
            show_alerts(chat_id, mid)
        elif cmd == "adel" and key and key.isdigit():
            with _db_lock:
                DB["alerts"] = [a for a in DB["alerts"] if not (a["id"] == int(key) and a["chat"] == chat_id)]
                save_db()
            toast = "هشدار حذف شد"
            show_alerts(chat_id, mid)

        elif cmd == "cc" and key in ASSETS:
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(Btn(f"➡️ {QTY[key]} به تومان", callback_data=f"cd_{key}_to"),
                   Btn(f"⬅️ تومان به {QTY[key]}", callback_data=f"cd_{key}_from"),
                   Btn("🔙 بازگشت", callback_data=f"cat_calc_{CAT_OF[key]}"))
            safe_edit(f"🧮 {ASSETS[key]}\n\nنوع تبدیل؟", chat_id, mid, kb)
        elif cmd == "cd" and key in ASSETS and len(parts) == 3 and parts[2] in ("to", "from"):
            STATE[chat_id] = {"mode": "calc", "key": key, "dir": parts[2]}
            ask = f"چند {QTY[key]}؟" if parts[2] == "to" else "چند تومان؟"
            safe_edit(f"🧮 {ASSETS[key]}\n\n{ask} عدد را بفرستید.", chat_id, mid, back_kb("cancel"))

        elif cmd == "sub" and key in ASSETS:
            with _db_lock:
                s = DB["subs"].setdefault(chat_id, set())
                if key in s:
                    s.discard(key)
                    DB["last"].pop(f"{chat_id}|{key}", None)
                    toast = f"{ASSETS[key]} غیرفعال شد"
                else:
                    s.add(key)
                    DB["last"].pop(f"{chat_id}|{key}", None)
                    toast = f"{ASSETS[key]} فعال شد ✅"
                if not s:
                    DB["subs"].pop(chat_id, None)
                save_db()
            try:
                bot.edit_message_reply_markup(chat_id, mid, reply_markup=assets_kb("auto", CAT_OF[key], chat_id))
            except ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    raise
        elif d == "stop_all":
            with _db_lock:
                DB["subs"].pop(chat_id, None)
                for k in [k for k in DB["last"] if k.startswith(f"{chat_id}|")]:
                    DB["last"].pop(k, None)
                save_db()
            toast = "همه اعلان‌های خودکار متوقف شد ⛔"
            show_auto_menu(chat_id, mid)

        elif d == "thr":
            show_thr(chat_id, mid)
        elif cmd == "th" and key is not None:
            try:
                v = float(key)
            except ValueError:
                v = None
            if v is not None and v in THRESHOLDS:
                with _db_lock:
                    DB["thr"][chat_id] = v
                    save_db()
                toast = "ذخیره شد ✅"
                show_thr(chat_id, mid)
        elif d == "daily":
            show_daily(chat_id, mid)
        elif cmd == "dl" and key is not None:
            with _db_lock:
                if key == "off":
                    DB["daily"].pop(chat_id, None)
                    toast = "گزارش روزانه خاموش شد"
                elif key.isdigit() and int(key) in DAILY_HOURS:
                    DB["daily"][chat_id] = int(key)
                    toast = "ذخیره شد ✅"
                save_db()
            show_daily(chat_id, mid)

        elif d == "my_status":
            safe_edit(my_status_text(chat_id), chat_id, mid, back_kb())

        elif d == "support":
            kb = types.InlineKeyboardMarkup()
            kb.add(Btn("💬 ارتباط با پشتیبانی", url=f"https://t.me/{SUPPORT_ID.lstrip('@')}"))
            kb.add(Btn("🔙 بازگشت", callback_data="back_help"))
            safe_edit(f"💬 *پشتیبانی*\n\nبرای سوال، گزارش مشکل یا پیشنهاد به {md_escape(SUPPORT_ID)} پیام بدهید.",
                      chat_id, mid, kb)
        elif d == "donate":
            safe_edit("❤️ *حمایت از ما*\n\n" + wallet_text(), chat_id, mid, back_kb("back_help"))
        elif d == "about":
            safe_edit("ℹ️ *درباره ربات*\n\nقیمت لحظه‌ای ارز، طلا، سکه و ارز دیجیتال.\n"
                      "منبع داده: TSETMC (algotik-tse)، CoinGecko و nerkh", chat_id, mid, back_kb("back_help"))

    except Exception as e:
        print("callback error:", repr(e))
        toast = "⚠️ خطایی رخ داد، دوباره تلاش کنید."
    finally:
        try:
            bot.answer_callback_query(c.id, toast)
        except Exception:
            pass


if __name__ == "__main__":
    if att is None:
        print("⚠️ algotik-tse نصب نیست؛ دلار، طلا و سکه کار نمی‌کنند. نصب: pip install algotik-tse")
    load_db()
    load_history()
    threading.Thread(target=auto_worker, daemon=True).start()
    print("Bot is running...")
    bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
