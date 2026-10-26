from flask import Flask, request, render_template, redirect, url_for, session

app = Flask(__name__)
# In a real app, this should be kept secret. Used here to sign session cookies.
app.secret_key = "insecure_demo_key"

# The challenge flag
FLAG = "HNS{csrf_account_takeover_success}"

# Mock database simulating user data
db = {
    "admin": {
        "password": "password123",
        "email": "admin@original-domain.com"
    }
}

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    # Basic authentication
    if username in db and db[username]['password'] == password:
        session['username'] = username 
        return redirect(url_for('dashboard'))
    
    return "Invalid credentials", 401

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    user_email = db[session['username']]['email']
    return render_template('dashboard.html', username=session['username'], email=user_email)

# The Vulnerable Endpoint
@app.route('/update_email', methods=['POST'])
def update_email():
    if 'username' not in session:
        return "Unauthorized: Please log in first.", 401
    
    new_email = request.form.get('email')
    if new_email:
        username = session['username']
        db[username]['email'] = new_email
        return f"Success! Email updated to: {new_email} <br><br> <a href='/dashboard'>Back to Dashboard</a>"
    
    return "Missing email parameter", 400

# The Flag Exfiltration Endpoint
@app.route('/retrieve_flag', methods=['GET'])
def retrieve_flag():
    """
    Public endpoint. Requires no authentication.
    If the attacker successfully changed the admin's email via CSRF, 
    they can query this endpoint with their injected email to get the flag.
    """
    requested_email = request.args.get('email', '')
    
    if not requested_email:
        return "Please provide an email parameter.", 400
        
    if requested_email == db["admin"]["email"]:
        return {"flag": FLAG, "message": "Account ownership verified via email."}
        
    return {"error": "Email does not match the admin account."}, 403

if __name__ == '__main__':
    # Running on port 5000
    app.run(host='127.0.0.1', port=5000, debug=False)