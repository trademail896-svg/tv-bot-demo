from flask import Flask, request, jsonify
import os
import time
import json
import hmac
import hashlib
import requests

app = Flask(__name__)

# --- CONFIG STRATEGIE ---
LONG_COLORS = {"green", "blue"}
SHORT_COLORS = {"red", "pink", "purple"}  # accept pink/purple
ALLOWED_SYMBOLS = {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

# Mode B : une seule position globale
STATE = {
    "in_position": False,
    "side": None,    # "LONG" ou "SHORT"
    "symbol": None
}

# --- BITMART FUTURES V2 CONFIG ---
BITMART_KEY = (os.environ.get("BITMART_API_KEY", "") or "").strip()
BITMART_SECRET = (os.environ.get("BITMART_API_SECRET", "") or "").strip()
BITMART_MEMO = (os.environ.get("BITMART_API_MEMO", "") or "").strip()


BITMART_MODE = os.environ.get("BITMART_MODE", "DEMO").upper()
BASE_URL = "https://demo-api-cloud-v2.bitmart.com" if BITMART_MODE == "DEMO" else "https://api-cloud-v2.bitmart.com"

LEVERAGE = os.environ.get("LEVERAGE", "1")
OPEN_TYPE = os.environ.get("OPEN_TYPE", "isolated")

def normalize_symbol(tv_symbol: str) -> str:
    return (tv_symbol or "").upper()

def get_size_for_symbol(symbol: str) -> int:
    v = os.environ.get(f"SIZE_{symbol}", "1")
    try:
        n = int(v)
        return max(1, n)
    except Exception:
        return 1

def bm_sign(timestamp_ms: int, body: dict) -> str:
    body_str = json.dumps(body, separators=(",", ":"), sort_keys=True)
    msg = f"{timestamp_ms}#{BITMART_MEMO}#{body_str}"
    return hmac.new(BITMART_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()

def bm_post(path: str, body: dict) -> dict:
    ts = int(time.time() * 1000)
    sign = bm_sign(ts, body)
    headers = {
        "Content-Type": "application/json",
        "X-BM-KEY": BITMART_KEY,
        "X-BM-TIMESTAMP": str(ts),
        "X-BM-SIGN": sign,
    }
    url = f"{BASE_URL}{path}"
    r = requests.post(
        url,
        headers=headers,
        data=json.dumps(body, separators=(",", ":"), sort_keys=True),
        timeout=10
    )
    try:
        return {"http": r.status_code, "json": r.json()}
    except Exception:
        return {"http": r.status_code, "text": r.text}

def bm_open_market(symbol: str, side: str) -> dict:
    # one-way: LONG entry buy=1, SHORT entry sell=4
    bm_side = 1 if side == "LONG" else 4
    body = {
        "symbol": symbol,
        "type": "market",
        "side": bm_side,
        "mode": 1,
        "leverage": str(LEVERAGE),
        "open_type": str(OPEN_TYPE),
        "size": get_size_for_symbol(symbol)
    }
    return bm_post("/contract/private/submit-order", body)

def bm_close_market(symbol: str, side: str) -> dict:
    # close LONG => sell reduce-only (3), close SHORT => buy reduce-only (2)
    bm_side = 3 if side == "LONG" else 2
    body = {
        "symbol": symbol,
        "type": "market",
        "side": bm_side,
        "mode": 1,
        "leverage": str(LEVERAGE),
        "open_type": str(OPEN_TYPE),
        "size": get_size_for_symbol(symbol)
    }
    return bm_post("/contract/private/submit-order", body)

def bm_set_stop_loss(symbol: str, position_side: str, sl_price: float) -> dict:
    # SL uses closing side
    bm_side = 3 if position_side == "LONG" else 2
    px = f"{sl_price:.2f}"
    body = {
        "symbol": symbol,
        "type": "stop_loss",
        "side": bm_side,
        "size": get_size_for_symbol(symbol),
        "trigger_price": px,
        "executive_price": px,
        "price_type": 1,      # last price
        "plan_category": 2,   # position TP/SL
        "category": "market"
    }
    return bm_post("/contract/private/submit-tp-sl-order", body)

@app.get("/")
def home():
    return "Bot TradingView DEMO actif"

@app.post("/webhook")
def webhook():
    data = request.get_json(silent=True) or {}

    # Sécurité : vérifier le secret
    if data.get("secret") != "TV_BOT_DEMO_2026":
        return jsonify({"status": "forbidden"}), 403

    print("ALERTE REÇUE:", data)

    symbol = normalize_symbol(data.get("ticker"))
    event = data.get("event")
    color = data.get("color")
    action = data.get("action")

    if symbol not in ALLOWED_SYMBOLS:
        return jsonify({"status": "ignored_symbol"}), 200

    # Mode B: si une position existe, ignorer les alertes des autres symboles
    if STATE["in_position"] and STATE["symbol"] and symbol != STATE["symbol"]:
        print(f"IGNORED (other symbol) open={STATE['symbol']} got={symbol}")
        return jsonify({"status": "ignored_other_symbol"}), 200

    # --- SORTIES ---
    if STATE["in_position"]:
        if action == "EXIT_LONG" and STATE["side"] == "LONG":
            print(f"EXIT LONG (stoch) {STATE['symbol']}")
            res_close = bm_close_market(STATE["symbol"], STATE["side"])
            print("BITMART CLOSE:", res_close)
            STATE.update({"in_position": False, "side": None, "symbol": None})
            return jsonify({"status": "exit_long"}), 200

        if action == "EXIT_SHORT" and STATE["side"] == "SHORT":
            print(f"EXIT SHORT (stoch) {STATE['symbol']}")
            res_close = bm_close_market(STATE["symbol"], STATE["side"])
            print("BITMART CLOSE:", res_close)
            STATE.update({"in_position": False, "side": None, "symbol": None})
            return jsonify({"status": "exit_short"}), 200

        if event == "VECTOR":
            if STATE["side"] == "LONG" and color in SHORT_COLORS:
                print(f"EXIT LONG (vector opp) {STATE['symbol']}")
                res_close = bm_close_market(STATE["symbol"], STATE["side"])
                print("BITMART CLOSE:", res_close)
                STATE.update({"in_position": False, "side": None, "symbol": None})
                return jsonify({"status": "exit_long"}), 200

            if STATE["side"] == "SHORT" and color in LONG_COLORS:
                print(f"EXIT SHORT (vector opp) {STATE['symbol']}")
                res_close = bm_close_market(STATE["symbol"], STATE["side"])
                print("BITMART CLOSE:", res_close)
                STATE.update({"in_position": False, "side": None, "symbol": None})
                return jsonify({"status": "exit_short"}), 200

        return jsonify({"status": "holding"}), 200

    # --- ENTREE (si aucune position globale) ---
    if event == "VECTOR" and not STATE["in_position"]:
        if color in LONG_COLORS:
            print(f"ENTER LONG {symbol}")
            res_entry = bm_open_market(symbol, "LONG")
            print("BITMART ENTRY:", res_entry)

            sl = float(data.get("low", 0) or 0)
            if sl > 0:
                res_sl = bm_set_stop_loss(symbol, "LONG", sl)
                print("BITMART SL:", res_sl)

            STATE.update({"in_position": True, "side": "LONG", "symbol": symbol})
            return jsonify({"status": "enter_long"}), 200

        if color in SHORT_COLORS:
            print(f"ENTER SHORT {symbol}")
            res_entry = bm_open_market(symbol, "SHORT")
            print("BITMART ENTRY:", res_entry)

            sl = float(data.get("high", 0) or 0)
            if sl > 0:
                res_sl = bm_set_stop_loss(symbol, "SHORT", sl)
                print("BITMART SL:", res_sl)

            STATE.update({"in_position": True, "side": "SHORT", "symbol": symbol})
            return jsonify({"status": "enter_short"}), 200

    return jsonify({"status": "ignored"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

