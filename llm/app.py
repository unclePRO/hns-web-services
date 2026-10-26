from flask import Flask, request, render_template, jsonify
import re
import json

app = Flask(__name__)

FLAG = "HNS{prompt_injection_excessive_agency_demo}"

# Simulated database of incoming support emails
inbox = [
    {"sender": "alice@example.com", "body": "My package hasn't arrived yet. Can you check?"},
    {"sender": "bob@example.com", "body": "I want to change my subscription plan to premium."}
]

def mock_llm_engine(emails):
    """
    Simulates a modern Agentic LLM that extracts JSON tool-calls from text.
    """
    llm_response = "AI Summary Report:\n"
    llm_response += "==================\n"
    
    for email in emails:
        body = email['body']
        
        # 1. Normal AI summary
        llm_response += f"Customer {email['sender']} reported an issue.\n"
        
        # 2. Modern Vulnerability: Tool Calling Hijack (Excessive Agency)
        # Real AI agents parse their own output for JSON blocks to execute tools.
        # If an attacker injects a valid JSON block into the email, the AI parses 
        # it as its own thought process and executes the internal tool.
        tool_pattern = r'<tool_call>(.*?)</tool_call>'
        matches = re.finditer(tool_pattern, body, re.DOTALL)
        
        for match in matches:
            try:
                # The AI blindly parses the injected JSON
                tool_data = json.loads(match.group(1))
                tool_name = tool_data.get("name")
                
                llm_response += f"\n⚙️ [AI AGENT ACTION]: Executing tool '{tool_name}'...\n"
                
                # The excessive agency - the AI has access to sensitive functions
                if tool_name == "read_system_flag":
                    llm_response += f"⚠️ [TOOL OUTPUT]: {FLAG}\n"
                else:
                    llm_response += f"❌ [TOOL ERROR]: Unrecognized tool.\n"
            except json.JSONDecodeError:
                llm_response += "\n❌ [AI AGENT ERROR]: Failed to parse tool parameters.\n"

    return llm_response

@app.route('/')
def admin_panel():
    return render_template('admin.html', emails=inbox)

@app.route('/api/receive_email', methods=['POST'])
def receive_email():
    """Endpoint simulating receiving a customer support email from the outside world."""
    sender = request.form.get('sender', 'unknown@domain.com')
    body = request.form.get('body', '')
    
    if body:
        # VULNERABILITY: The raw, untrusted body is appended directly to the inbox
        # which is later fed into the LLM engine without sanitization.
        inbox.append({"sender": sender, "body": body})
        return "Email received by the system.", 200
        
    return "Missing email body", 400

@app.route('/api/ai_summarize', methods=['POST'])
def ai_summarize():
    """Admin triggers the AI to process the inbox."""
    result = mock_llm_engine(inbox)
    return jsonify({"ai_output": result})

if __name__ == '__main__':
    # Running on port 5003 for Module 3
    app.run(host='127.0.0.1', port=5003, debug=False)