from flask import Flask, request, jsonify
import os

app = Flask(__name__)

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
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

