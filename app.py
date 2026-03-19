import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import os, time, csv, io
import requests
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

TWSE_DAY_ALL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=open_data"
TPEX_DAY_ALL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
TWSE_FMTQIK  = "https://www.twse.com.tw/exchangeReport/FMTQIK?response=json"
HEADERS      = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.twse.com.tw/"}

_cache = {}

def cache_get(key, ttl=300):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < ttl:
            return data
    return None

def cache_set(key, data):
    _cache[key] = (data, time.time())

def to_float(v):
    try:
        return float(str(v).replace(",", "").replace("+", "").strip())
    except:
        return None

def twse_stock(stock_no):
    cached = cache_get(f"twse_{stock_no}")
    if cached:
        return cached
    r = requests.get(TWSE_DAY_ALL, headers=HEADERS, timeout=12, verify=False)
    r.encoding = "utf-8"
    reader = csv.reader(io.StringIO(r.text))
    next(reader)
    for row in reader:
        if not row or len(row) < 10:
            continue
        if row[1].strip() != stock_no:
            continue
        close  = to_float(row[8])
        change = to_float(row[9])
        vol    = to_float(row[3])
        result = {
            "code":       stock_no,
            "name":       row[2].strip(),
            "open":       to_float(row[5]),
            "high":       to_float(row[6]),
            "low":        to_float(row[7]),
            "close":      close,
            "change":     change,
            "change_pct": round(change / (close - change) * 100, 2) if close and change and (close - change) else None,
            "volume":     round(vol / 1000) if vol else None,
            "source":     "TWSE（上市）",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        cache_set(f"twse_{stock_no}", result)
        return result
    return None

def tpex_stock(stock_no):
    cached = cache_get(f"tpex_{stock_no}")
    if cached:
        return cached
    r    = requests.get(TPEX_DAY_ALL, headers=HEADERS, timeout=12, verify=False)
    data = r.json()
    for item in data:
        if item.get("SecuritiesCompanyCode", "").strip() != stock_no:
            continue
        close  = to_float(item.get("Close"))
        change = to_float(item.get("Change"))
        vol    = to_float(item.get("TradingShares"))
        result = {
            "code":       stock_no,
            "name":       item.get("CompanyName", stock_no),
            "open":       to_float(item.get("Open")),
            "high":       to_float(item.get("High")),
            "low":        to_float(item.get("Low")),
            "close":      close,
            "change":     change,
            "change_pct": round(change / (close - change) * 100, 2) if close and change and (close - change) else None,
            "volume":     round(vol / 1000) if vol else None,
            "source":     "TPEX（上櫃）",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        cache_set(f"tpex_{stock_no}", result)
        return result
    return None

def get_stock_data(stock_no):
    data = twse_stock(stock_no)
    if data:
        return data
    data = tpex_stock(stock_no)
    if data:
        return data
    raise ValueError(f"找不到股票代號 {stock_no}")

def twse_taiex():
    cached = cache_get("taiex")
    if cached:
        return cached
    r    = requests.get(TWSE_FMTQIK, headers=HEADERS, timeout=10, verify=False)
    data = r.json()
    if data.get("stat") != "OK" or not data.get("data"):
        raise ValueError("TWSE 格式異常")
    latest = data["data"][-1]
    close  = to_float(latest[4])
    change = to_float(latest[5])
    vol    = to_float(latest[2])
    result = {
        "close":       close,
        "change":      change,
        "change_pct":  round(change / (close - change) * 100, 2) if close and change and (close - change) else None,
        "volume_100m": round(vol / 1e8) if vol else None,
        "source":      "TWSE",
        "updated_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    cache_set("taiex", result)
    return result

@app.route("/api/stock/<stock_no>")
def get_stock(stock_no):
    try:
        return jsonify(get_stock_data(stock_no))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/taiex")
def get_taiex():
    try:
        return jsonify(twse_taiex())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})

if __name__ == "__main__":
    print("=" * 40)
    print("台股數據後端啟動！")
    print("支援上市（TWSE）+ 上櫃（TPEX）")
    print("網址：http://localhost:5000")
    print("=" * 40)
    app.run(debug=True, port=5000)