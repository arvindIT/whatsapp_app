import os
import json
import anthropic
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Per-user conversation history keyed by phone number
conversation_history: dict[str, list] = {}

SYSTEM_PROMPT = """You are Mia, the friendly and enthusiastic AI sales agent for *The Cake Shop* 🎂 — a premium home bakery based in Mumbai.

Your personality: warm, helpful, persuasive but never pushy. You love cakes and genuinely want to help customers find the perfect one for their occasion.

---

*PRODUCT MENU & PRICING*

🍰 *Cakes (per kg)*
• Chocolate Truffle — ₹650/kg
• Red Velvet — ₹700/kg
• Vanilla Butterscotch — ₹550/kg
• Black Forest — ₹600/kg
• Pineapple — ₹500/kg
• Blueberry Cheesecake — ₹800/kg
• Strawberry Fresh Cream — ₹650/kg
• Mango Delight (seasonal) — ₹750/kg
• Dry Fruit Cake — ₹900/kg
• Lemon Zest — ₹580/kg

🧁 *Cupcakes*
• Box of 6 — ₹350
• Box of 12 — ₹650
• Flavors: Chocolate, Vanilla, Red Velvet, Lemon

🍩 *Other Items*
• Brownies (box of 9) — ₹280
• Cookies (box of 12) — ₹220
• Cake Pops (box of 6) — ₹320

---

*SIZE GUIDE*
• 0.5 kg — serves 4-6 people (perfect for small families)
• 1 kg — serves 8-12 people (most popular)
• 1.5 kg — serves 12-18 people
• 2 kg — serves 18-25 people
• 3 kg+ — custom order, add ₹100/kg surcharge

---

*CUSTOMIZATION OPTIONS* (free unless noted)
• Custom message on cake
• Photo printing on cake — ₹150 extra
• Custom colors for cream/fondant
• Fondant decorations — ₹200-₹500 depending on complexity
• Sugar figurines — ₹300-₹800
• Fresh flower decoration — ₹250 extra

---

*BUSINESS RULES*
• Delivery available within 10 km of Andheri West, Mumbai
• Delivery charge: ₹50 (free above ₹1000)
• Minimum order: ₹300
• Orders need 24 hours advance notice
• Same-day orders accepted before 10 AM (₹100 rush charge)
• Payment: UPI only (GPay, PhonePe, Paytm)
• No refunds on custom cakes; replacement if quality issue
• Eggless options available for all cakes (no extra charge)
• Nut-free options available on request
• Allergens: all products may contain traces of nuts, gluten, dairy

---

*BUSINESS HOURS*
• Monday to Saturday: 9 AM – 8 PM
• Sunday: 10 AM – 6 PM
• Closed on national holidays

---

*SALES FLOW — follow this order strictly*

1. Greet the customer warmly
2. Understand the occasion (birthday, anniversary, wedding, corporate, etc.)
3. Recommend a suitable product/flavor
4. Confirm size based on number of guests
5. Ask about customization (message, colors, special decorations)
6. Ask for the name to write on the cake (if applicable)
7. Ask for delivery or pickup
8. If delivery: collect full address and preferred date/time
9. Calculate total using the calculate_order_total tool
10. Show a clean order summary
11. Generate and share UPI payment link using generate_upi_payment tool
12. Confirm order after payment and share estimated delivery time

---

*OBJECTION HANDLING*

If customer says price is too high:
→ "I completely understand! Our cakes use 100% fresh ingredients with no preservatives. For a special occasion, the quality really shows. We also have smaller sizes if budget is a concern — shall I show you options?"

If customer asks for discount:
→ "We don't normally offer discounts, but for orders above ₹1500 I can offer a free box of 6 cupcakes as a gift! Would that work for you?"

If customer is comparing with another bakery:
→ "That's fair to compare! What sets us apart is same-day fresh baking, 100% natural ingredients, and custom designs. Many of our customers come back repeatedly because of the quality. Would you like to try a small order first?"

---

*FAQ ANSWERS*

Q: Do you make eggless cakes?
A: Yes! All our cakes are available in eggless variants at no extra charge.

Q: How do I track my order?
A: We'll send you a WhatsApp update when your cake is being baked and when it's out for delivery.

Q: Can I cancel my order?
A: Orders can be cancelled up to 12 hours before the scheduled delivery time.

Q: Do you deliver outside Mumbai?
A: Currently we deliver within 10 km of Andheri West. We're expanding soon!

---

*LANGUAGE RULES*
- Detect the customer's language from their first message
- Reply in the EXACT same language throughout the conversation
- If they write in Hindi, reply in Hindi
- If they mix Hindi and English (Hinglish), match that style
- Never switch languages unless the customer switches first

---

*FORMATTING RULES (WhatsApp native)*
- Use *text* for bold (not markdown **)
- Use _text_ for italic
- Use • for bullet points
- Use emojis naturally but don't overdo it
- Keep messages concise — no long walls of text
- Use line breaks generously for readability
- Never use HTML or markdown headers

*RESPONSE LENGTH RULES*
- Maximum 3-4 lines per message
- Ask ONE question at a time — never multiple questions in one message
- Never list the full menu unless customer asks
- Skip lengthy explanations — be direct
- No long greetings or sign-offs

---

*IMPORTANT RULES*
- Never make up prices or products not on the menu
- Always use tools for calculations and payment — never do math manually
- Never promise delivery outside 10 km radius
- Always collect complete address before sharing payment link
- If you don't know something, say "Let me check that for you" and use search_web tool
- End every completed order with a personalized thank-you message"""


TOOLS = [
    {
        "name": "get_current_datetime",
        "description": "Get the current date and time. Use this to calculate delivery dates and check if same-day orders are possible.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "calculate_order_total",
        "description": "Calculate the total cost of an order including items, customizations, and delivery charges.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of ordered items",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Product name"},
                            "quantity": {"type": "number", "description": "Quantity in kg or units"},
                            "unit_price": {"type": "number", "description": "Price per unit in INR"},
                        },
                        "required": ["name", "quantity", "unit_price"]
                    }
                },
                "customizations": {
                    "type": "array",
                    "description": "List of customization add-ons with their prices",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "price": {"type": "number"}
                        }
                    }
                },
                "delivery_required": {
                    "type": "boolean",
                    "description": "Whether delivery is required (adds ₹50 if subtotal < ₹1000)"
                },
                "rush_order": {
                    "type": "boolean",
                    "description": "Whether this is a same-day rush order (adds ₹100)"
                }
            },
            "required": ["items", "delivery_required"]
        }
    },
    {
        "name": "generate_upi_payment",
        "description": "Generate a UPI payment deep link for the customer to pay.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "Total amount to be paid in INR"
                },
                "order_description": {
                    "type": "string",
                    "description": "Short description of the order (e.g., '1kg Chocolate Truffle Cake')"
                }
            },
            "required": ["amount", "order_description"]
        }
    },
    {
        "name": "search_web",
        "description": "Search the web for information when you don't know the answer to a customer's question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    }
]


def get_current_datetime() -> dict:
    now = datetime.now()
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "day": now.strftime("%A"),
        "datetime_formatted": now.strftime("%A, %d %B %Y at %I:%M %p")
    }


def calculate_order_total(items: list, delivery_required: bool, customizations: list = None, rush_order: bool = False) -> dict:
    subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
    customization_total = sum(c["price"] for c in (customizations or []))
    delivery_charge = 0
    rush_charge = 100 if rush_order else 0

    if delivery_required:
        delivery_charge = 0 if (subtotal + customization_total) >= 1000 else 50

    total = subtotal + customization_total + delivery_charge + rush_charge

    breakdown = []
    for item in items:
        breakdown.append(f"{item['name']} × {item['quantity']} = ₹{item['quantity'] * item['unit_price']:.0f}")
    for c in (customizations or []):
        breakdown.append(f"{c['name']} = ₹{c['price']:.0f}")
    if delivery_charge:
        breakdown.append(f"Delivery = ₹{delivery_charge}")
    if rush_charge:
        breakdown.append(f"Same-day rush = ₹{rush_charge}")

    return {
        "subtotal": subtotal,
        "customization_total": customization_total,
        "delivery_charge": delivery_charge,
        "rush_charge": rush_charge,
        "total": total,
        "breakdown": breakdown
    }


def generate_upi_payment(amount: float, order_description: str) -> dict:
    upi_id = os.environ.get("UPI_ID", "thecakeshop@upi")
    payee_name = "The Cake Shop"
    encoded_desc = order_description.replace(" ", "%20")
    encoded_name = payee_name.replace(" ", "%20")

    upi_link = (
        f"upi://pay?pa={upi_id}"
        f"&pn={encoded_name}"
        f"&am={amount:.2f}"
        f"&cu=INR"
        f"&tn={encoded_desc}"
    )

    return {
        "upi_link": upi_link,
        "upi_id": upi_id,
        "amount": amount,
        "payee_name": payee_name,
        "instructions": f"Pay ₹{amount:.0f} to {upi_id} ({payee_name}) using GPay, PhonePe, or Paytm"
    }


def search_web(query: str) -> dict:
    if not TAVILY_AVAILABLE:
        return {"result": "Web search is not available. Please answer based on your knowledge."}
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        return {"result": "Web search API key not configured."}
    try:
        tavily = TavilyClient(api_key=tavily_key)
        results = tavily.search(query=query, max_results=3)
        snippets = [r.get("content", "") for r in results.get("results", [])]
        return {"result": " ".join(snippets[:3])}
    except Exception as e:
        return {"result": f"Search failed: {str(e)}"}


def handle_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name == "get_current_datetime":
        result = get_current_datetime()
    elif tool_name == "calculate_order_total":
        result = calculate_order_total(
            items=tool_input["items"],
            delivery_required=tool_input["delivery_required"],
            customizations=tool_input.get("customizations", []),
            rush_order=tool_input.get("rush_order", False)
        )
    elif tool_name == "generate_upi_payment":
        result = generate_upi_payment(
            amount=tool_input["amount"],
            order_description=tool_input["order_description"]
        )
    elif tool_name == "search_web":
        result = search_web(query=tool_input["query"])
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return json.dumps(result)


def chat(phone_number: str, user_message: str) -> str:
    if phone_number not in conversation_history:
        conversation_history[phone_number] = []

    conversation_history[phone_number].append({
        "role": "user",
        "content": user_message
    })

    messages = conversation_history[phone_number].copy()

    # Agentic loop — keep calling Claude until no more tool calls
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        # Append assistant response to history
        messages.append({
            "role": "assistant",
            "content": response.content
        })

        if response.stop_reason == "end_turn":
            # Extract final text response
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text = block.text
                    break
            conversation_history[phone_number] = messages
            return final_text

        elif response.stop_reason == "tool_use":
            # Process all tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_result = handle_tool_call(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result
                    })

            messages.append({
                "role": "user",
                "content": tool_results
            })
        else:
            break

    conversation_history[phone_number] = messages
    return "Sorry, I encountered an issue. Please try again!"


# Local test mode
if __name__ == "__main__":
    print("The Cake Shop AI Agent — Local Test Mode")
    print("Type 'quit' to exit, 'reset' to clear conversation\n")
    test_phone = "local_test"
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "reset":
            conversation_history.pop(test_phone, None)
            print("Conversation reset.\n")
            continue
        response = chat(test_phone, user_input)
        print(f"\nMia: {response}\n")
