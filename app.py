from flask import Flask, request, jsonify
import os

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


def normalize_symbol(tv_symbol: str) -> str:
    return (tv_symbol or "").upper()


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
    # Si une position globale est ouverte, ignorer les alertes d'autres symboles
    if STATE["in_position"] and STATE["symbol"] and symbol != STATE["symbol"]:
        print(f"IGNORED (other symbol) open={STATE['symbol']} got={symbol}")
        return jsonify({"status": "ignored_other_symbol"}), 200

    # --- SORTIES ---
    if STATE["in_position"]:
        # Sortie via Stoch RSI
        if action == "EXIT_LONG" and STATE["side"] == "LONG":
            print(f"EXIT LONG (stoch) {STATE['symbol']}")
            STATE.update({"in_position": False, "side": None, "symbol": None})
            return jsonify({"status": "exit_long"}), 200

        if action == "EXIT_SHORT" and STATE["side"] == "SHORT":
            print(f"EXIT SHORT (stoch) {STATE['symbol']}")
            STATE.update({"in_position": False, "side": None, "symbol": None})
            return jsonify({"status": "exit_short"}), 200

        # Sortie via vecteur opposé
        if event == "VECTOR":
            if STATE["side"] == "LONG" and color in SHORT_COLORS:
                print(f"EXIT LONG (vector opp) {STATE['symbol']}")
                STATE.update({"in_position": False, "side": None, "symbol": None})
                return jsonify({"status": "exit_long"}), 200

            if STATE["side"] == "SHORT" and color in LONG_COLORS:
                print(f"EXIT SHORT (vector opp) {STATE['symbol']}")
                STATE.update({"in_position": False, "side": None, "symbol": None})
                return jsonify({"status": "exit_short"}), 200

        return jsonify({"status": "holding"}), 200

    # --- ENTREE (si aucune position globale) ---
    if event == "VECTOR" and not STATE["in_position"]:
        if color in LONG_COLORS:
            print(f"ENTER LONG {symbol}")
            STATE.update({"in_position": True, "side": "LONG", "symbol": symbol})
            return jsonify({"status": "enter_long"}), 200

        if color in SHORT_COLORS:
            print(f"ENTER SHORT {symbol}")
            STATE.update({"in_position": True, "side": "SHORT", "symbol": symbol})
            return jsonify({"status": "enter_short"}), 200

    return jsonify({"status": "ignored"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
