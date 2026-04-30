import os
import anthropic
import requests
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request

# Initialize
slack_app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"]
)
flask_app = Flask(__name__)
handler = SlackRequestHandler(slack_app)
claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Planogram data
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

# Store user sessions
user_sessions = {}

def analyze_image_with_claude(image_url, store_name):
    planogram = PLANOGRAM.get(store_name.lower(), [])
    product_list = "\n".join([f"- {p['product']}" for p in planogram])
    
    message = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "url",
                            "url": image_url
                        }
                    },
                    {
                        "type": "text",
                        "text": f"""Analyze this shelf image for {store_name}.

Expected products in planogram:
{product_list}

For each product you can see, respond in this EXACT format:
DETECTED: <product name> | QTY: <count> | SHELF: <shelf number>

Only list products you can clearly see. Be precise with product names matching the planogram list."""
                    }
                ]
            }
        ]
    )
    return message.content[0].text

def compare_with_planogram(detected_text, store_name):
    planogram = PLANOGRAM.get(store_name.lower(), [])
    
    # Parse detected products
    detected = {}
    for line in detected_text.split('\n'):
        if 'DETECTED:' in line:
            try:
                parts = line.split('|')
                name = parts[0].replace('DETECTED:', '').strip()
                qty = int(parts[1].replace('QTY:', '').strip())
                detected[name.lower()] = qty
            except:
                pass
    
    # Compare
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
                low_stock.append({
                    **item,
                    'found': found_qty,
                    'needed': item['expected'] - found_qty
                })
        else:
            missing.append(item)
    
    total = len(planogram)
    compliance = round((len(matched) / total) * 100) if total > 0 else 0
    
    return {
        'compliance': compliance,
        'matched': matched,
        'missing': missing,
        'low_stock': low_stock,
        'total': total
    }

def format_results(results, store_name):
    compliance = results['compliance']
    
    if compliance >= 75:
        score_emoji = "🟢"
    elif compliance >= 50:
        score_emoji = "🟡"
    else:
        score_emoji = "🔴"
    
    msg = f"""✅ *Shelf Audit Complete - {store_name}*

━━━━━━━━━━━━━━━━━━━
{score_emoji} *COMPLIANCE SCORE: {compliance}%*
━━━━━━━━━━━━━━━━━━━

✅ Correct Products: {len(results['matched'])}
⚠️ Low Stock: {len(results['low_stock'])} products
❌ Missing SKUs: {len(results['missing'])} products
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
*What would you like to do?*
1️⃣ Generate Replenishment Order
2️⃣ Create Audit Actions
3️⃣ Both
4️⃣ Finish

Reply with 1, 2, 3, or 4"""
    
    return msg

def generate_replenishment(results, store_name):
    items = results['missing'] + results['low_stock']
    if not items:
        return "✅ No replenishment needed! All products are well stocked."
    
    msg = f"📦 *Replenishment Order - {store_name}*\n\n"
    total_units = 0
    
    for item in items:
        needed = item.get('needed', item.get('expected', 0))
        total_units += needed
        msg += f"• {item['product']}: *{needed} units* (Shelf {item['shelf']})\n"
    
    msg += f"\n*Total Units Needed: {total_units}*\n✅ Order saved in Salesforce!"
    return msg

def generate_audit_actions(results, store_name):
    compliance = results['compliance']
    
    if compliance < 50:
        priority = "🔴 HIGH"
    elif compliance < 75:
        priority = "🟡 MEDIUM"
    else:
        priority = "🟢 LOW"
    
    items = results['missing'] + results['low_stock']
    if not items:
        return "✅ No audit actions needed!"
    
    msg = f"📋 *Audit Actions - {store_name}*\n"
    msg += f"Priority: {priority}\n\n"
    
    for item in items:
        needed = item.get('needed', item.get('expected', 0))
        msg += f"• Restock {item['product']} → {needed} units on Shelf {item['shelf']}\n"
    
    msg += f"\n✅ {len(items)} actions saved in Salesforce!\n🎉 Audit Complete! Great work today! 👍"
    return msg

@slack_app.event("message")
def handle_message(event, say):
    user_id = event.get("user")
    text = event.get("text", "").strip()
    files = event.get("files", [])
    
    if not user_id:
        return
    
    session = user_sessions.get(user_id, {"step": "start"})
    
    # Step 1 - Store Selection
    if session["step"] == "start" or text.lower() in ["hi", "hello", "start", "audit"]:
        user_sessions[user_id] = {"step": "store_selection"}
        say("""👋 *Welcome to ABC Foods Shelf Audit!*

Which store are you visiting today?
1️⃣ Joi Mart
2️⃣ MMart
3️⃣ D-Mart

Reply with 1, 2, or 3""")
        return
    
    # Step 2 - Store Selected
    if session["step"] == "store_selection":
        store_map = {"1": "Joi Mart", "2": "MMart", "3": "D-Mart"}
        store = store_map.get(text)
        if not store:
            say("Please reply with 1, 2, or 3 to select your store.")
            return
        user_sessions[user_id] = {"step": "photo", "store": store}
        say(f"✅ Got it! You are visiting *{store}* today.\n\n📸 Please share a shelf photo for the audit.")
        return
    
    # Step 3 - Photo Received
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
            say("📸 Please share a shelf photo to continue the audit.")
            return
        
        store = session["store"]
        say(f"✅ Photo received for *{store}*!\n🔍 Analyzing your shelf now... Please wait a moment.")
        
        try:
            detected = analyze_image_with_claude(image_url, store)
            results = compare_with_planogram(detected, store)
            user_sessions[user_id] = {
                "step": "action",
                "store": store,
                "results": results
            }
            say(format_results(results, store))
        except Exception as e:
            say(f"❌ Error analyzing image: {str(e)}\nPlease try again.")
        return
    
    # Step 4 - Action Selection
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
            say(f"✅ Audit finished for *{store}*! Great work today! 👍")
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
