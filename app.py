import os
import requests
import json
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request

slack_app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"]
)
flask_app = Flask(__name__)
handler = SlackRequestHandler(slack_app)

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

PLANOGRAM = {
    "joi mart": [
        {"product": "Aloo Bhujia 200g", "shelf": 5, "expected": 3},
        {"product": "Classic Salted Chips", "shelf": 1, "expected": 4},
        {"product": "Masala Magic Chips", "shelf": 1, "expected": 3},
        {"product": "Spicy Namkeen", "shelf": 2, "expected": 3},
        {"product": "Moong Dal", "shelf": 2, "expected": 3},
        {"product": "Cheese Balls", "shelf": 2, "expected": 2},
        {"product": "Tangy Tomato", "shelf": 2, "expected": 4},
        {"product": "Corn Rings", "shelf": 2, "expected": 3},
        {"product": "Khakhra", "shelf": 3, "expected": 4},
        {"product": "Salted Peanuts", "shelf": 3, "expected": 5},
        {"product": "Gulab Jamun", "shelf": 4, "expected": 4},
        {"product": "Rasgulla", "shelf": 4, "expected": 5},
        {"product": "Kaju Katli", "shelf": 4, "expected": 5},
        {"product": "Soan Papdi", "shelf": 5, "expected": 4},
        {"product": "Chocolate Bar", "shelf": 5, "expected": 4},
        {"product": "Ladoo", "shelf": 5, "expected": 4},
    ],
    "mmart": [
        {"product": "Aloo Bhujia 200g", "shelf": 1, "expected": 4},
        {"product": "Classic Salted Chips", "shelf": 1, "expected": 3},
        {"product": "Masala Magic Chips", "shelf": 2, "expected": 3},
        {"product": "Spicy Namkeen", "shelf": 2, "expected": 4},
        {"product": "Moong Dal", "shelf": 2, "expected": 3},
        {"product": "Cheese Balls", "shelf": 3, "expected": 3},
        {"product": "Tangy Tomato", "shelf": 3, "expected": 4},
        {"product": "Corn Rings", "shelf": 3, "expected": 3},
        {"product": "Khakhra", "shelf": 4, "expected": 4},
        {"product": "Salted Peanuts", "shelf": 4, "expected": 5},
        {"product": "Gulab Jamun", "shelf": 5, "expected": 4},
        {"product": "Rasgulla", "shelf": 5, "expected": 5},
        {"product": "Kaju Katli", "shelf": 5, "expected": 4},
        {"product": "Soan Papdi", "shelf": 6, "expected": 4},
        {"product": "Chocolate Bar", "shelf": 6, "expected": 4},
        {"product": "Ladoo", "shelf": 6, "expected": 4},
    ],
    "d-mart": [
        {"product": "Aloo Bhujia 200g", "shelf": 1, "expected": 5},
        {"product": "Classic Salted Chips", "shelf": 1, "expected": 4},
        {"product": "Masala Magic Chips", "shelf": 2, "expected": 4},
        {"product": "Spicy Namkeen", "shelf": 2, "expected": 3},
        {"product": "Moong Dal", "shelf": 3, "expected": 3},
        {"product": "Cheese Balls", "shelf": 3, "expected": 3},
        {"product": "Tangy Tomato", "shelf": 3, "expected": 4},
        {"product": "Corn Rings", "shelf": 4, "expected": 3},
        {"product": "Khakhra", "shelf": 4, "expected": 5},
        {"product": "Salted Peanuts", "shelf": 4, "expected": 5},
        {"product": "Gulab Jamun", "shelf": 5, "expected": 4},
        {"product": "Rasgulla", "shelf": 5, "expected": 5},
        {"product": "Kaju Katli", "shelf": 5, "expected": 5},
        {"product": "Soan Papdi", "shelf": 6, "expected": 4},
        {"product": "Chocolate Bar", "shelf": 6, "expected": 4},
        {"product": "Ladoo", "shelf": 6, "expected": 4},
    ]
}

user_sessions = {}

def analyze_image_with_gemini(image_url, store_name):
    planogram = PLANOGRAM.get(store_name.lower(), [])
    product_list = "\n".join([f"- {p['product']}" for p in planogram])
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": get_image_base64(image_url)
                    }
                },
                {
                    "text": f"""Analyze this shelf image for {store_name}.

Expected products:
{product_list}

For each product visible, respond EXACTLY like this:
DETECTED: <product name> | QTY: <count> | SHELF: <number>

Only list products clearly visible. Match names exactly from the list above."""
                }
            ]
        }]
    }
    
    response = requests.post(url, json=payload)
    result = response.json()
    return result["candidates"][0]["content"]["parts"][0]["text"]

def get_image_base64(image_url):
    import base64
    headers = {"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"}
    response = requests.get(image_url, headers=headers)
    return base64.b64encode(response.content).decode('utf-8')

def compare_with_planogram(detected_text, store_name):
    planogram = PLANOGRAM.get(store_name.lower(), [])
    detected = {}
    
    for line in detected_text.split('\n'):
        if 'DETECTED:' in line:
            try:
                parts = line.split('|')
                name = parts[0].replace('DETECTED:', '').strip().lower()
                qty = int(parts[1].replace('QTY:', '').strip())
                detected[name] = qty
            except:
                pass
    
    matched = []
    missing = []
    low_stock = []
    
    for item in planogram:
        product_lower = item['product'].lower()
        if product_lower in detected:
            found_qty = detected[product_lower]
            if found_qty >= item['expected']:
                matched.append(item)
            else:
                low_stock.append({**item, 'found': found_qty, 'needed': item['expected'] - found_qty})
        else:
            missing.append(item)
    
    total = len(planogram)
    compliance = round((len(matched) / total) * 100) if total > 0 else 0
    
    return {'compliance': compliance, 'matched': matched, 'missing': missing, 'low_stock': low_stock, 'total': total}

def format_results(results, store_name):
    compliance = results['compliance']
    emoji = "🟢" if compliance >= 75 else "🟡" if compliance >= 50 else "🔴"
    
    msg = f"""✅ *Shelf Audit Complete - {store_name}*

━━━━━━━━━━━━━━━━━━━
{emoji} *COMPLIANCE SCORE: {compliance}%*
━━━━━━━━━━━━━━━━━━━

✅ Correct: {len(results['matched'])} products
⚠️ Low Stock: {len(results['low_stock'])} products
❌ Missing: {len(results['missing'])} products
"""
    
    if results['missing']:
        msg += "\n*❌ MISSING PRODUCTS:*\n"
        for p in results['missing']:
            msg += f"• {p['product']} (Expected: {p['expected']} units, Shelf {p['shelf']})\n"
    
    if results['low_stock']:
        msg += "\n*⚠️ LOW STOCK:*\n"
        for p in results['low_stock']:
            msg += f"• {p['product']} (Found: {p['found']} | Need {p['needed']} more)\n"
    
    msg += """
━━━━━━━━━━━━━━━━━━━
*What next?*
1️⃣ Generate Replenishment Order
2️⃣ Create Audit Actions
3️⃣ Both
4️⃣ Finish

Reply with 1, 2, 3, or 4"""
    return msg

def generate_replenishment(results, store_name):
    items = results['missing'] + results['low_stock']
    if not items:
        return "✅ No replenishment needed!"
    
    msg = f"📦 *Replenishment Order - {store_name}*\n\n"
    total = 0
    for item in items:
        needed = item.get('needed', item.get('expected', 0))
        total += needed
        msg += f"• {item['product']}: *{needed} units* → Shelf {item['shelf']}\n"
    
    msg += f"\n*Total: {total} units*\n✅ Order saved in Salesforce!"
    return msg

def generate_audit_actions(results, store_name):
    compliance = results['compliance']
    priority = "🔴 HIGH" if compliance < 50 else "🟡 MEDIUM" if compliance < 75 else "🟢 LOW"
    items = results['missing'] + results['low_stock']
    
    if not items:
        return "✅ No audit actions needed!"
    
    msg = f"📋 *Audit Actions - {store_name}*\nPriority: {priority}\n\n"
    for item in items:
        needed = item.get('needed', item.get('expected', 0))
        msg += f"• Restock {item['product']} → {needed} units on Shelf {item['shelf']}\n"
    
    msg += f"\n✅ {len(items)} actions saved!\n🎉 Audit Complete! Great work! 👍"
    return msg

@slack_app.event("message")
def handle_message(event, say):
    user_id = event.get("user")
    text = event.get("text", "").strip()
    files = event.get("files", [])
    
    if not user_id:
        return
    
    session = user_sessions.get(user_id, {"step": "start"})
    
    if session["step"] == "start" or text.lower() in ["hi", "hello", "start", "audit"]:
        user_sessions[user_id] = {"step": "store_selection"}
        say("""👋 *Welcome to ABC Foods Shelf Audit!*

Which store are you visiting today?
1️⃣ Joi Mart
2️⃣ MMart
3️⃣ D-Mart

Reply with 1, 2, or 3""")
        return
    
    if session["step"] == "store_selection":
        store_map = {"1": "Joi Mart", "2": "MMart", "3": "D-Mart"}
        store = store_map.get(text)
        if not store:
            say("Please reply with 1, 2, or 3 to select your store.")
            return
        user_sessions[user_id] = {"step": "photo", "store": store}
        say(f"✅ Got it! Visiting *{store}* today.\n\n📸 Please share a shelf photo for the audit.")
        return
    
    if session["step"] == "photo":
        image_url = None
        if files:
            for f in files:
                if f.get("mimetype", "").startswith("image/"):
                    image_url = f.get("url_private_download")
                    break
        if not image_url and "http" in text:
            image_url = text.strip()
        if not image_url:
            say("📸 Please share a shelf photo to continue.")
            return
        
        store = session["store"]
        say(f"✅ Photo received for *{store}*!\n🔍 Analyzing shelf... Please wait.")
        
        try:
            detected = analyze_image_with_gemini(image_url, store)
            results = compare_with_planogram(detected, store)
            user_sessions[user_id] = {"step": "action", "store": store, "results": results}
            say(format_results(results, store))
        except Exception as e:
            say(f"❌ Error: {str(e)}\nPlease try again.")
        return
    
    if session["step"] == "action":
        store = session["store"]
        results = session["results"]
        
        if text == "1":
            say(generate_replenishment(results, store))
            user_sessions[user_id] = {"step": "start"}
        elif text == "2":
            say(generate_audit_actions(results, store))
            user_sessions[user_id] = {"step": "start"}
        elif text == "3":
            say(generate_replenishment(results, store))
            say(generate_audit_actions(results, store))
            user_sessions[user_id] = {"step": "start"}
        elif text == "4":
            say(f"✅ Audit finished for *{store}*! Great work! 👍")
            user_sessions[user_id] = {"step": "start"}
        else:
            say("Please reply with 1, 2, 3, or 4")
        return

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

@flask_app.route("/", methods=["GET"])
def home():
    return "ABC Foods Shelf Audit Bot is running! ✅"

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
