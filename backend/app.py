from flask import Flask, render_template, request, jsonify
import google.genai as genai
from google.genai import types
import os
from dotenv import load_dotenv

# ----------------------------
# Load environment variables from .env
# ----------------------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in environment or .env file!")

# ----------------------------
# Initialize Gemini client
# ----------------------------
client = genai.Client(api_key=GOOGLE_API_KEY)

# ----------------------------
# Setup paths for templates & static
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# ----------------------------
# Initialize Flask
# ----------------------------
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)

# ----------------------------
# AI Functions
# ----------------------------
def call_gemini(prompt, model="gemini-2.5-flash", temperature=0.7):
    """
    Calls Gemini API using generate_content() and returns the text response.
    """
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature
            )
        )
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return f"Error: {str(e)}"

def detect_intent(email_text):
    """
    Detects the intent of an email: Inquiry, Complaint, Offer, or Information.
    """
    prompt = (
        f"Classify the following email into EXACTLY ONE of these intents: "
        f"Inquiry, Complaint, Offer, Information.\n\n"
        f"Email: {email_text}\n\n"
        f"Respond with ONLY the intent word, nothing else."
    )
    result = call_gemini(prompt, temperature=0.1)
    # Extract first word to handle any extra formatting
    intent = result.split()[0].strip()
    # Validate intent
    valid_intents = ["Inquiry", "Complaint", "Offer", "Information"]
    return intent if intent in valid_intents else "Inquiry"

def generate_reply(email_text, intent, tone="formal"):
    """
    Generates a professional email reply based on intent and tone.
    """
    tone_instructions = {
        "formal": "Use professional, respectful language. Avoid contractions. Be precise and courteous.",
        "friendly": "Use warm, approachable language. Be conversational but still professional. Use contractions naturally.",
        "persuasive": "Focus on benefits and value. Create enthusiasm. Motivate action while remaining professional."
    }
    
    instruction = tone_instructions.get(tone, tone_instructions["formal"])
    
    prompt = (
        f"You are a professional email assistant. Write a {tone} reply to the following email.\n\n"
        f"Email: {email_text}\n\n"
        f"Intent: {intent}\n\n"
        f"Tone guidelines: {instruction}\n\n"
        f"Write a complete, professional email reply:"
    )
    return call_gemini(prompt, temperature=0.7).strip()

def suggest_tones(reply_text):
    """
    Provides guidance on when to use different tones.
    """
    prompt = (
        f"Based on the following email reply, provide brief guidance on when to use "
        f"each of these three tones: Formal, Friendly, and Persuasive.\n\n"
        f"Original reply: {reply_text}\n\n"
        f"For each tone, explain in 2-3 sentences when it would be most appropriate to use."
    )
    return call_gemini(prompt, temperature=0.5).strip()

# ----------------------------
# Routes
# ----------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    """
    Main route for email input and analysis.
    """
    email_text = ""
    error = None
    
    if request.method == "POST":
        # Check if file was uploaded
        if "email_file" in request.files and request.files["email_file"].filename != "":
            file = request.files["email_file"]
            try:
                email_text = file.read().decode("utf-8")
            except Exception as e:
                error = f"Error reading file: {str(e)}"
                return render_template("index.html", error=error, email_text="")
        else:
            email_text = request.form.get("email_text", "").strip()

        tone = request.form.get("tone", "formal")

        # Validate input
        if not email_text:
            error = "Please provide email text or upload a file."
            return render_template("index.html", error=error, email_text=email_text)

        try:
            # AI processing
            print(f"Processing email with tone: {tone}")
            intent = detect_intent(email_text)
            print(f"Detected intent: {intent}")
            
            reply = generate_reply(email_text, intent, tone)
            print(f"Generated reply length: {len(reply)}")
            
            tone_suggestions = suggest_tones(reply)
            print(f"Generated tone suggestions")

            return render_template(
                "result.html",
                email_text=email_text,
                intent=intent,
                reply=reply,
                tone_suggestions=tone_suggestions,
                selected_tone=tone
            )
        except Exception as e:
            error = f"Error processing email: {str(e)}"
            print(f"Error: {error}")
            return render_template("index.html", error=error, email_text=email_text)

    return render_template("index.html", error=error, email_text=email_text)

@app.route("/regenerate", methods=["POST"])
def regenerate():
    """
    API endpoint to regenerate reply with a different tone.
    """
    try:
        data = request.get_json()
        email_text = data.get("email_text", "")
        intent = data.get("intent", "")
        tone = data.get("tone", "formal")
        
        if not email_text or not intent:
            return jsonify({"error": "Missing required fields"}), 400
        
        # Generate new reply with selected tone
        reply = generate_reply(email_text, intent, tone)
        
        return jsonify({"reply": reply, "tone": tone})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------
# Run app
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)