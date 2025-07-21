#!/usr/bin/env python3
"""
SIMPLIFIED Trading Platform – fixed release

• Adds the missing /api/earn/<client_id> endpoint  
• Corrects the /api/balance and /api/positions routes so they include <client_id>  
• Boots a default client called "live_client" at startup when Binance keys exist
"""

import hmac
import hashlib
import json
import logging
import os
import time
from datetime import datetime
from urllib.parse import urlencode

import requests
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

# ---------------------------------------------------------------------------#
#  Configuration and logging
# ---------------------------------------------------------------------------#
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.config["JSON_SORT_KEYS"] = False
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

# ---------------------------------------------------------------------------#
#  Global state
# ---------------------------------------------------------------------------#
api_clients: dict[str, "BinanceFuturesAPI"] = {}
open_positions = {}
DEFAULT_CLIENT_ID = "live_client"

# ---------------------------------------------------------------------------#
#  Binance helper
# ---------------------------------------------------------------------------#
class BinanceFuturesAPI:
    """Very small wrapper for the handful of endpoints this app needs."""

    BASE_URL = "https://fapi.binance.com"

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": api_key})

    # ----- private helpers --------------------------------------------------#
    def _sign(self, params: dict) -> str:
        q = urlencode(params)
        return hmac.new(self.api_secret.encode(), q.encode(), hashlib.sha256).hexdigest()

    def _private_get(self, path: str, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        params["signature"] = self._sign(params)
        r = self.session.get(f"{self.BASE_URL}{path}", params=params, timeout=10)
        return r.json() if r.ok else {"error": r.text}

    # ----- public helpers ---------------------------------------------------#
    def test(self) -> bool:
        try:
            r = self.session.get(f"{self.BASE_URL}/fapi/v1/ping", timeout=5)
            return r.ok
        except Exception:
            return False

    def get_account_info(self) -> dict:
        return self._private_get("/fapi/v2/account", {})

    def get_balance(self) -> dict:
        info = self.get_account_info()
        if "error" in info:
            return info
        return {
            "total_wallet_balance": float(info.get("totalWalletBalance", 0)),
            "available_balance": float(info.get("availableBalance", 0)),
            "total_unrealized_pnl": float(info.get("totalUnrealizedProfit", 0)),
        }

    def get_positions(self) -> list[dict]:
        info = self.get_account_info()
        if "error" in info:
            return [info]
        out = []
        for p in info.get("positions", []):
            amt = float(p.get("positionAmt", 0))
            if amt != 0:
                out.append(
                    {
                        "symbol": p["symbol"],
                        "side": "LONG" if amt > 0 else "SHORT",
                        "amount": amt,
                        "entry_price": float(p["entryPrice"]),
                        "unrealized_pnl": float(p["unrealizedProfit"]),
                    }
                )
        return out


# ---------------------------------------------------------------------------#
#  Bootstrap default client so the dashboard works out-of-the-box
# ---------------------------------------------------------------------------#
def bootstrap_default_client() -> None:
    if DEFAULT_CLIENT_ID in api_clients:
        return

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    if not (api_key and api_secret):
        logger.info("Binance keys missing – running in view-only mode.")
        return

    client = BinanceFuturesAPI(api_key, api_secret)
    if client.test():
        api_clients[DEFAULT_CLIENT_ID] = client
        logger.info("✅ Default Binance client 'live_client' initialised.")
    else:
        logger.warning("❌ Binance credentials invalid – default client not created.")


bootstrap_default_client()

# ---------------------------------------------------------------------------#
#  Routes
# ---------------------------------------------------------------------------#
@app.route("/")
def index():
    return render_template("simplified_index.html")


@app.route("/api/connect", methods=["POST"])
def connect():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    if not (api_key and api_secret):
        return jsonify({"success": False, "error": "BINANCE_API_KEY/SECRET not set"}), 400

    client_id = f"client_{len(api_clients) + 1}"
    client = BinanceFuturesAPI(api_key, api_secret)
    if not client.test():
        return jsonify({"success": False, "error": "Bad API credentials"}), 400

    api_clients[client_id] = client
    return jsonify({"success": True, "client_id": client_id})


@app.route("/api/balance/<client_id>")
def balance(client_id):
    if client_id not in api_clients:
        return jsonify({"error": "Client not found"}), 404
    return jsonify(api_clients[client_id].get_balance())


@app.route("/api/positions/<client_id>")
def positions(client_id):
    if client_id not in api_clients:
        return jsonify({"error": "Client not found"}), 404
    return jsonify({"positions": api_clients[client_id].get_positions()})


@app.route("/api/earn/<client_id>")
def earn(client_id):
    """Stub until proper Earn integration is finished."""
    if client_id not in api_clients:
        return jsonify({"error": "Client not found"}), 404
    return jsonify({"earn": {"flexible": [], "locked": []}})


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "clients": list(api_clients.keys()),
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@app.errorhandler(404)
def _nf(_):
    return jsonify({"error": "not found"}), 404


# ---------------------------------------------------------------------------#
#  Main
# ---------------------------------------------------------------------------#
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), threaded=True)
