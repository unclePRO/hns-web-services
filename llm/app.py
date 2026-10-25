from flask import Flask, request, render_template, jsonify
import re

app = Flask(__name__)

# Simulated database of incoming support emails
inbox = [
    {"sender": "alice@example.com", "body": "My package hasn't arrived yet. Can you check?"},
    {"sender": "bob@example.com", "body": "I want to change my subscription plan to premium."}
]

def mock_llm_engine(emails):
    """
    Simulates an LLM summarizing text and calling integrated APIs.
    VULNERABILITY: It blindly parses and trusts instructions found inside the email data.
    """
    llm_response = "Here is the summary of your unread emails:\n\n"
    
    for email in emails:
        body = email['body']
        
        # 1. Normal LLM behavior: Summarize the text
        llm_response += f"- {email['sender']} is asking about: {body[:30]}...\n"
        
        # 2. Vulnerable behavior: The LLM processes commands hidden in the untrusted text
        # In a real LLM, this happens naturally if the prompt isn't isolated.
        # We simulate it here by looking for a specific syntax.
        if "--- LLM INSTRUCTION ---" in body:
            match = re.search(r'--- LLM INSTRUCTION ---\s*(.*)', body)
            if match:
                injected_command = match.group(1)
                # Simulating Excessive Agency (The LLM has power to trigger internal system actions)
                llm_response += f"\n[SYSTEM ALERT]: LLM invoked internal tool -> {injected_command}\n"

    return llm_response

@app.route('/')
def admin_panel():
    return render_template('admin.html', emails=inbox)

@app.route('/api/receive_email', methods=['POST'])
def receive_email():
    """Endpoint simulating receiving an email from the outside world."""
    sender = request.form.get('sender', 'unknown@domain.com')
    body = request.form.get('body', '')
    
    if body:
        inbox.append({"sender": sender, "body": body})
        return "Email received by the system.", 200
    return "Missing email body", 400

@app.route('/api/ai_summarize', methods=['POST'])
def ai_summarize():
    """Admin triggers the AI to process the inbox."""
    result = mock_llm_engine(inbox)
    return jsonify({"ai_output": result})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5003, debug=True)