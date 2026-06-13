import os
import json
import requests
from flask import Flask, request, jsonify
from agent import chat

app = Flask(__name__)

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")

WHATSAPP_API_URL = f"https://graph.facebook.com/v25.0/{{}}/messages"


def send_whatsapp_message(to: str, message: str) -> None:
    url = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] Failed to send message to {to}: {e}")


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("[INFO] Webhook verified successfully")
        return challenge, 200
    else:
        print("[WARN] Webhook verification failed")
        return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    try:
        data = request.get_json()
        print(f"[DEBUG] Incoming payload: {json.dumps(data)}")

        if not data or data.get("object") != "whatsapp_business_account":
            print(f"[DEBUG] Ignored - object type: {data.get('object') if data else 'None'}")
            return jsonify({"status": "ignored"}), 200

        entries = data.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])

                for message in messages:
                    phone_number = message.get("from")
                    message_type = message.get("type")

                    if message_type == "text":
                        user_text = message["text"]["body"]
                        print(f"[MSG] From {phone_number}: {user_text}")

                        agent_reply = chat(phone_number, user_text)
                        send_whatsapp_message(phone_number, agent_reply)
                        print(f"[REPLY] To {phone_number}: {agent_reply[:80]}...")

                    else:
                        # Non-text message fallback
                        fallback = (
                            "Hi! I can only read text messages right now. "
                            "Please type your message and I'll be happy to help! 😊"
                        )
                        send_whatsapp_message(phone_number, fallback)

    except Exception as e:
        print(f"[ERROR] Webhook handler error: {e}")

    # Always return 200 to prevent Meta from retrying
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(port=8000, host="0.0.0.0", debug=True)
