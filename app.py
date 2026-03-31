from flask import Flask, render_template, request, redirect, session, flash # type: ignore
import os
import smtplib
import random
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from werkzeug.utils import secure_filename # type: ignore
from dotenv import load_dotenv # type: ignore

from supabase import create_client, Client # type: ignore

load_dotenv()

# Safely parse Supabase credentials to prevent parsing errors on Render (e.g. from accidental quotes)
url = os.environ.get("SUPABASE_URL", "").strip().strip('"').strip("'")
key = os.environ.get("SUPABASE_KEY", "").strip().strip('"').strip("'")
supabase: Client = create_client(url, key)

# GMAIL SMTP SETUP
GMAIL_USER = os.environ.get("GMAIL_SMTP_USER", "").strip()
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_SMTP_PASSWORD", "").strip()

# ADMIN CREDENTIALS (loaded from .env) - LEGACY, use get_admin_credentials() instead
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@wearandcare.com").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WearCare@2026").strip()

def get_admin_credentials():
    """Get admin credentials from .env file (dynamic loading)"""
    import re
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    admin_email = "admin@wearandcare.com"
    admin_password = "WearCare@2026"
    
    try:
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                content = f.read()
                # Extract ADMIN_EMAIL
                email_match = re.search(r'^ADMIN_EMAIL=(.+)$', content, re.MULTILINE)
                if email_match:
                    admin_email = email_match.group(1).strip().strip('"').strip("'")
                # Extract ADMIN_PASSWORD
                password_match = re.search(r'^ADMIN_PASSWORD=(.+)$', content, re.MULTILINE)
                if password_match:
                    admin_password = password_match.group(1).strip().strip('"').strip("'")
    except Exception as e:
        print(f"Error reading admin credentials from .env: {e}")
    
    return admin_email, admin_password

def send_otp_email(to_email, otp_code, action_text="Verification"):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("Warning: Gmail credentials not configured in .env. Email skipped.")
        return
        
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Wear & Care <{GMAIL_USER}>"
        msg['To'] = to_email
        msg['Subject'] = f"{action_text} OTP - Wear & Care"
        
        body = f"Hello,\n\nYour 6-digit OTP for {action_text} is: {otp_code}\n\nPlease enter this code on the website to proceed.\n\nBest Regards,\nThe Wear & Care Team"
        msg.attach(MIMEText(body, 'plain'))
        
        # Add a 10-second timeout to prevent Gunicorn worker freezing if Gmail blocks Render IPs
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"OTP email successfully sent to {to_email}")
    except smtplib.SMTPException as e:
        print(f"SMTP Protocol Error: {str(e)}")
    except Exception as e:
        print(f"Failed to send OTP via Gmail SMTP: {str(e)}")

app = Flask(__name__)
# Ensure the secret key falls back securely if none is provided via Render ENV
app.secret_key = os.environ.get("SECRET_KEY", "wearcare-dev-random-string-1234")

# Global error handlers to surface 500 errors gracefully
@app.errorhandler(500)
def handle_500(e):
    import traceback
    return f"<h1>Internal Server Error</h1><p>Please check Render logs.</p><pre style='background:#f4f4f4;padding:10px'>{traceback.format_exc()}</pre>", 500

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    return f"<h1>Unhandled Exception</h1><pre style='background:#f4f4f4;padding:10px'>{traceback.format_exc()}</pre>", 500


UPLOAD_FOLDER = "static/uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# TUPLE HELPERS FOR TEMPLATE COMPATIBILITY
def dict_to_donation_tuple(d):
    return (
        d.get('id'),                # 0
        d.get('user_name'),         # 1
        d.get('cloth_type'),        # 2
        d.get('size'),              # 3
        d.get('condition_status'),  # 4
        d.get('address'),           # 5
        d.get('image'),             # 6
        d.get('status'),            # 7
        d.get('user_id'),           # 8
        d.get('phone'),             # 9
        1 if d.get('is_free') else 0, # 10
        d.get('price'),             # 11
        d.get('created_at'),        # 12
        d.get('updated_at')         # 13
    )

def dict_to_user_tuple(u):
    return (
        u.get('id'),           # 0
        u.get('name'),         # 1
        u.get('email'),        # 2
        u.get('created_at'),   # 3
        u.get('is_flagged', False),   # 4
        u.get('flag_reason', '')      # 5
    )

def dict_to_request_tuple(pr):
    d = pr.get('donations', {})
    u = pr.get('users', {})
    return (
        pr.get('id'), pr.get('status'), pr.get('created_at'),
        d.get('id'), d.get('cloth_type'), d.get('size'), d.get('condition_status'),
        u.get('name'), u.get('email')
    )

# LOGIN REQUIRED
def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect("/login")
        return view_func(*args, **kwargs)
    return wrapper

# ADMIN REQUIRED
def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect("/admin-login")
        return view_func(*args, **kwargs)
    return wrapper

def normalize_email(email):
    return (email or "").strip().lower()

# HOME
@app.route('/')
def home():
    return render_template("index.html", active_page="home", user_id=session.get("user_id"))

# REGISTER
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = normalize_email(request.form.get('email'))
        password = request.form.get('password')

        if not name or not email or not password:
            return render_template("register.html", error="Please fill all fields")

        # Check if email is already registered in the database to prevent duplicate signups
        try:
            existing_user = supabase.table('users').select('id').eq('email', email).execute()
            if existing_user.data:
                return render_template("register.html", error="An account with this email already exists. Please log in.")
        except Exception:
            pass # ignore errors if the db check temporarily fails

        # Generate Custom 6-Digit OTP
        otp = str(random.randint(100000, 999999))
        session['signup_otp'] = otp
        session['signup_email'] = email
        session['signup_password'] = password
        session['signup_name'] = name
        
        # Send via our completely custom Gmail logic
        send_otp_email(email, otp, "Account Registration")
        
        return redirect(f"/verify-otp?email={email}")

    return render_template("register.html")

# USER LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password") or ""
        otp = request.form.get("otp")
        
        # Step 1: If only email provided, generate and send OTP
        if email and not otp and not password:
            try:
                # Check if user exists in Supabase
                res = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": "temp_check_" + str(random.randint(10000, 99999))
                })
            except Exception as e:
                # Expected to fail, just checking if user exists
                if "Invalid login credentials" not in str(e):
                    return render_template("login.html", error="User not found. Please register first.")
            
            # Generate 6-digit OTP
            login_otp = str(random.randint(100000, 999999))
            session['login_otp'] = login_otp
            session['login_email'] = email
            session['login_password'] = password
            
            # Send OTP via email
            send_otp_email(email, login_otp, "Login")
            
            return redirect(f"/verify-login-otp?email={email}")
        
        # Step 2: Verify OTP and login
        if email and otp:
            expected_otp = session.get('login_otp')
            expected_email = session.get('login_email')
            
            if str(otp) == str(expected_otp) and email == expected_email:
                try:
                    # Get user from Supabase by email
                    res = supabase.table('users').select('*').eq('email', email).execute()
                    if res.data and len(res.data) > 0:
                        user_data = res.data[0]
                        session["user_id"] = user_data.get('id')
                        session["user_name"] = user_data.get('name', 'User')
                        session["user_email"] = email
                        session["is_admin"] = False
                        
                        # Clear OTP session
                        session.pop('login_otp', None)
                        session.pop('login_email', None)
                        session.pop('login_password', None)
                        
                        return redirect("/dashboard")
                    else:
                        return render_template("verify_login_otp.html", email=email, error="User not found.")
                except Exception as e:
                    return render_template("verify_login_otp.html", email=email, error=f"Login failed: {str(e)}")
            else:
                return render_template("verify_login_otp.html", email=email, error="Invalid 6-digit OTP code.")

    return render_template("login.html")

# VERIFY LOGIN OTP
@app.route('/verify-login-otp', methods=['GET', 'POST'])
def verify_login_otp():
    if request.method == 'POST':
        email = request.form.get('email') or ""
        otp = request.form.get('otp')
        
        expected_otp = session.get('login_otp')
        expected_email = session.get('login_email')
        
        if str(otp) == str(expected_otp) and email == expected_email:
            try:
                # Get user from Supabase by email
                res = supabase.table('users').select('*').eq('email', email).execute()
                if res.data and len(res.data) > 0:
                    user_data = res.data[0]
                    session["user_id"] = user_data.get('id')
                    session["user_name"] = user_data.get('name', 'User')
                    session["user_email"] = email
                    session["is_admin"] = False
                    
                    # Clear OTP session
                    session.pop('login_otp', None)
                    session.pop('login_email', None)
                    
                    flash("Login successful!", "success")
                    return redirect("/dashboard")
                else:
                    return render_template("verify_login_otp.html", email=email, error="User not found.")
            except Exception as e:
                return render_template("verify_login_otp.html", email=email, error=f"Login failed: {str(e)}")
        else:
            return render_template("verify_login_otp.html", email=email, error="Invalid 6-digit OTP code.")
    
    email = request.args.get('email', '')
    return render_template("verify_login_otp.html", email=email)

# VERIFY OTP
@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        email = request.form.get('email') or ""
        otp = request.form.get('otp')
        
        expected_otp = session.get('signup_otp')
        expected_email = session.get('signup_email')
        
        if str(otp) == str(expected_otp) and email == expected_email:
            try:
                signup_password = str(session.get('signup_password') or "")
                signup_name = str(session.get('signup_name') or "")
                supabase.auth.sign_up({
                    "email": email,
                    "password": signup_password,
                    "options": {"data": {"name": signup_name}}
                })
                session.pop('signup_otp', None)
                flash("Account verified and created successfully! Please log in.", "success")
                return redirect("/login")
            except Exception as e:
                return render_template("verify_otp.html", error=f"Verified OTP but Supabase failed: {str(e)}")
        else:
            return render_template("verify_otp.html", error="Invalid 6-digit OTP code.")

    return render_template("verify_otp.html")

# FORGOT PASSWORD
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        
        # Generate custom OTP in Flask
        otp = str(random.randint(100000, 999999))
        session['reset_otp'] = otp
        session['reset_email'] = email
        
        # Send strictly 6 digit OTP via custom Gmail
        send_otp_email(email, otp, "Password Reset")
        
        return redirect(f"/reset-password?email={email}")

    return render_template("forgot_password.html")

# RESET PASSWORD
@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        otp = request.form.get("otp")
        new_password = request.form.get("password")
        
        expected_otp = session.get("reset_otp")
        expected_email = session.get("reset_email")
        
        if str(otp) == str(expected_otp) and email == expected_email:
            try:
                # Use custom RPC command to update password directly
                supabase.rpc("reset_password", {"target_email": email, "new_password": new_password}).execute()
                
                # Clear reset session
                session.pop('reset_otp', None)
                session.pop('reset_email', None)
                
                flash("Password updated successfully! Please log in.", "success")
                return redirect("/login")
            except Exception as e:
                print(f"Password update failed: {e}")
                return render_template("reset_password.html", error="Failed to update password correctly.")
        else:
            return render_template("reset_password.html", error="Invalid OTP code matched.")

    return render_template("reset_password.html")

# ADMIN LOGIN
@app.route('/admin-login', methods=['GET','POST'])
def admin_login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        
        # Get current admin credentials from .env (dynamic loading)
        admin_email, admin_password = get_admin_credentials()

        if email == admin_email.lower() and password == admin_password:
            session["user_id"] = "admin"
            session["user_name"] = "Admin"
            session["is_admin"] = True
            flash("Welcome back, Admin!", "success")
            return redirect("/admin")
        
        return render_template("admin_login.html", error="Invalid admin email or password.")
    return render_template("admin_login.html")

# ADMIN SETTINGS - Change email / password
@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    success = None
    error = None

    if request.method == 'POST':
        action = request.form.get('action')
        # Get current credentials from .env
        current_email, current_password = get_admin_credentials()

        if action == 'change_email':
            new_email = (request.form.get('new_email') or '').strip().lower()
            confirm_pass = request.form.get('confirm_password') or ''
            if confirm_pass != current_password:
                error = "Current password is incorrect."
            elif not new_email:
                error = "Please enter a valid email."
            else:
                # Update .env file
                _update_env('ADMIN_EMAIL', new_email)
                success = f"Admin email updated to {new_email}. You can now login with the new email."

        elif action == 'change_password':
            current_pass = request.form.get('current_password') or ''
            new_pass = request.form.get('new_password') or ''
            confirm_new = request.form.get('confirm_new_password') or ''
            if current_pass != current_password:
                error = "Current password is incorrect."
            elif len(new_pass) < 6:
                error = "New password must be at least 6 characters."
            elif new_pass != confirm_new:
                error = "New passwords do not match."
            else:
                # Update .env file
                _update_env('ADMIN_PASSWORD', new_pass)
                success = "Admin password updated successfully! You can login with the new password."

    # Get current credentials for display
    current_email, current_password = get_admin_credentials()
    
    return render_template('admin_settings.html',
                           admin_email=current_email,
                           success=success, error=error)

def _update_env(key, value):
    """Update a key in the .env file."""
    import re
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    try:
        with open(env_path, 'r') as f:
            content = f.read()
        pattern = rf'^{re.escape(key)}=.*$'
        new_line = f'{key}={value}'
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
        else:
            content += f'\n{new_line}\n'
        with open(env_path, 'w') as f:
            f.write(content)
    except Exception as e:
        print(f'Could not update .env: {e}')

# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# DONATE
@app.route('/donate', methods=['GET', 'POST'])
@login_required
def donate():
    if request.method == "POST":
        form_name = request.form.get("name") or ""
        user_name = form_name.strip() or session.get("user_name")
        cloth = request.form.get("cloth")
        
        size_select = request.form.get("size_select")
        size_custom = request.form.get("size_custom")
        size = size_custom.strip() if size_select == "Other" and size_custom else size_select
        
        condition = request.form.get("condition")
        address = request.form.get("address")
        phone = (request.form.get("phone") or "").strip()

        if not size:
            return render_template("donate.html", error="Please specify a valid size.")

        if not phone:
            return render_template("donate.html", error="Please enter your phone number")

        donation_type = (request.form.get("donation_type") or "free").strip().lower()
        is_free = True if donation_type != "paid" else False
        price_raw = (request.form.get("price") or "").strip()
        price = None
        if not is_free:
            try:
                price_val = float(price_raw)
                if price_val <= 0:
                    raise ValueError("Price must be positive")
                price = round(price_val, 2)  # type: ignore
            except Exception:
                return render_template("donate.html", error="Please enter a valid price for Paid listings")

        images = request.files.getlist("image")
        image_list = []

        for img in images[:3]: # Limit to 3 max
            if img and img.filename:
                # Prepend timestamp to avoid overrides of identical filenames
                filename = img.filename
                safe_name = f"{int(time.time())}_{secure_filename(filename)}"
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                img.save(os.path.join(app.config['UPLOAD_FOLDER'], safe_name))
                image_list.append(safe_name)

        if len(image_list) == 0:
            return render_template("donate.html", error="Please upload at least 1 clear photo of the item.")
            
        image_name = ",".join(image_list)

        data = {
            "user_id": session.get("user_id"),
            "user_name": user_name,
            "cloth_type": cloth,
            "size": size,
            "condition_status": condition,
            "address": address,
            "image": image_name,
            "status": "Pending",
            "is_free": is_free,
            "price": price,
            "phone": phone
        }

        try:
            supabase.table("donations").insert(data).execute()
            return render_template("donate.html", success="Donation submitted successfully")
        except Exception as e:
            return render_template("donate.html", error=f"Database error: {str(e)}")

    return render_template("donate.html")

# DASHBOARD
@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session.get("user_id")
    
    # Donations
    d_res = supabase.table("donations").select("*").eq("user_id", user_id).order('id', desc=True).execute()
    data = [dict_to_donation_tuple(d) for d in d_res.data]

    # Notifications
    notifications = []
    popup_notification = None
    try:
        n_res = supabase.table("notifications").select("id, message, created_at, read_at").eq("user_id", user_id).order('id', desc=True).limit(10).execute()
        
        unread_res = supabase.table("notifications").select("id, message, created_at").eq("user_id", user_id).is_("read_at", "null").order('id', desc=True).limit(1).execute()
        unread = unread_res.data[0] if unread_res.data else None
        
        if unread:
            popup_notification = {"id": unread['id'], "message": unread['message'], "created_at": unread['created_at']}
            supabase.table("notifications").update({"read_at": "now()"}).eq("id", unread['id']).execute()

        for n in n_res.data:
            notifications.append((n.get('id'), n.get('message'), n.get('created_at'), n.get('read_at')))
    except Exception:
        pass

    # Incoming Requests
    incoming_requests = []
    try:
        pr_res = supabase.table('purchase_requests').select(
            'id, status, created_at, '
            'donations!inner(id, cloth_type, size, condition_status, user_id), '
            'users!buyer_user_id(name, email)'
        ).eq('donations.user_id', user_id).order('id', desc=True).execute()
        
        incoming_requests = [dict_to_request_tuple(pr) for pr in pr_res.data]
    except Exception:
        pass

    # My Requests
    my_requests = []
    try:
        mr_res = supabase.table('purchase_requests').select(
            'id, status, created_at, '
            'donations!inner(id, cloth_type, size, condition_status, user_id, users!user_id(name, email))'
        ).eq('buyer_user_id', user_id).order('id', desc=True).execute()
        
        for mr in mr_res.data:
            d = mr.get('donations', {})
            donor_u = d.get('users', {})
            my_requests.append((
                mr.get('id'), mr.get('status'), mr.get('created_at'),
                d.get('id'), d.get('cloth_type'), d.get('size'), d.get('condition_status'),
                donor_u.get('name'), donor_u.get('email')
            ))
    except Exception:
        pass

    return render_template(
        "dashboard.html",
        donations=data,
        notifications=notifications,
        incoming_requests=incoming_requests,
        my_requests=my_requests,
        popup_notification=popup_notification
    )

# ADMIN PANEL
@app.route('/admin')
@admin_required
def admin():
    # Donations
    don_res = supabase.table("donations").select("*").order('id', desc=True).execute()
    data = [dict_to_donation_tuple(d) for d in don_res.data]
    all_donations_raw = don_res.data

    # Users
    user_res = supabase.table("users").select("*").order('created_at', desc=True).execute()
    users_raw = user_res.data

    # Purchase Requests
    try:
        pr_res = supabase.table("purchase_requests").select("*, donations(cloth_type), users!purchase_requests_buyer_user_id_fkey(name)").order('id', desc=True).execute()
        purchase_requests = []
        for r in pr_res.data:
            entry = dict(r)
            entry['cloth_type'] = r.get('donations', {}).get('cloth_type') if r.get('donations') else None
            entry['buyer_name'] = r.get('users', {}).get('name') if r.get('users') else None
            purchase_requests.append(entry)
    except Exception:
        pr_res = supabase.table("purchase_requests").select("*").order('id', desc=True).execute()
        purchase_requests = pr_res.data
    all_requests_raw = pr_res.data if hasattr(pr_res, 'data') else purchase_requests

    # --- Smart behavior stats per user ---
    # Build lookup: user_id -> stats
    user_stats = {}
    for u in users_raw:
        uid = u.get('id')
        # count donations
        donations_count = sum(1 for d in all_donations_raw if d.get('user_id') == uid)
        rejected_donations = sum(1 for d in all_donations_raw if d.get('user_id') == uid and d.get('status') == 'Rejected')
        # no-phone donations
        no_phone_donations = sum(1 for d in all_donations_raw if d.get('user_id') == uid and not d.get('phone'))
        # requests made
        requests_made = sum(1 for r in all_requests_raw if r.get('buyer_user_id') == uid)
        # rejected requests
        rejected_requests = sum(1 for r in all_requests_raw if r.get('buyer_user_id') == uid and r.get('status') == 'Rejected')

        # Auto-risk score (0 = safe, higher = more suspicious)
        risk_score = 0
        risk_reasons = []

        if rejected_donations > 0:
            risk_score += rejected_donations * 2
            risk_reasons.append(f"{rejected_donations} donation(s) rejected by admin")
        if no_phone_donations > 0 and donations_count > 0:
            risk_score += no_phone_donations
            risk_reasons.append(f"{no_phone_donations} donation(s) submitted without phone number")
        if requests_made >= 5 and rejected_requests >= 3:
            risk_score += 3
            risk_reasons.append(f"High rejection rate on requests ({rejected_requests}/{requests_made})")
        if requests_made >= 10:
            risk_score += 2
            risk_reasons.append(f"Unusually high number of requests ({requests_made})")

        # Manual flag overrides auto-score
        is_flagged = u.get('is_flagged', False)
        flag_reason = u.get('flag_reason', '')

        user_stats[uid] = {
            'donations_count': donations_count,
            'rejected_donations': rejected_donations,
            'requests_made': requests_made,
            'rejected_requests': rejected_requests,
            'risk_score': risk_score,
            'risk_reasons': risk_reasons,
            'is_flagged': is_flagged,
            'flag_reason': flag_reason,
        }

    users = [dict_to_user_tuple(u) for u in users_raw]

    return render_template("admin.html", donations=data, users=users,
                           purchase_requests=purchase_requests,
                           user_stats=user_stats, active_page="admin")

@app.route('/listings')
def listings():
    user_id = session.get("user_id")
    
    # Get query parameters
    search = request.args.get('search', '').strip().lower()
    cloth_type = request.args.get('cloth_type', '').strip()
    size_filter = request.args.get('size', '').strip()
    condition = request.args.get('condition', '').strip()
    price_type = request.args.get('price_type', '').strip()  # 'free' or 'paid'
    sort_by = request.args.get('sort_by', 'newest')
    page = int(request.args.get('page', 1))
    items_per_page = 12
    
    try:
        # Get all donations first (Supabase limitations)
        if user_id and not session.get("is_admin"):
            res = supabase.table("donations").select("*").neq("user_id", user_id).execute()
        else:
            res = supabase.table("donations").select("*").execute()
        
        donations = res.data if res.data else []
        
        # Filter by search term (searching in cloth_type, condition, and donor name)
        if search:
            donations = [d for d in donations if 
                search in (d.get('cloth_type', '') or '').lower() or
                search in (d.get('condition_status', '') or '').lower() or
                search in (d.get('user_name', '') or '').lower()
            ]
        
        # Filter by cloth type
        if cloth_type:
            donations = [d for d in donations if (d.get('cloth_type', '') or '') == cloth_type]
        
        # Filter by size
        if size_filter:
            donations = [d for d in donations if (d.get('size', '') or '') == size_filter]
        
        # Filter by condition
        if condition:
            donations = [d for d in donations if (d.get('condition_status', '') or '') == condition]
        
        # Filter by price type
        if price_type == 'free':
            donations = [d for d in donations if d.get('is_free', True)]
        elif price_type == 'paid':
            donations = [d for d in donations if not d.get('is_free', True)]
        
        # Sort
        if sort_by == 'newest':
            donations.sort(key=lambda x: x.get('id', 0), reverse=True)
        elif sort_by == 'oldest':
            donations.sort(key=lambda x: x.get('id', 0))
        elif sort_by == 'price_low':
            donations.sort(key=lambda x: x.get('price', 0) if x.get('price') else float('inf'))
        elif sort_by == 'price_high':
            donations.sort(key=lambda x: x.get('price', 0) if x.get('price') else 0, reverse=True)
        
        # Pagination
        total_items = len(donations)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        paginated_donations = donations[start_idx:end_idx]
        
        data = [dict_to_donation_tuple(d) for d in paginated_donations]
        
        # Define comprehensive filter options
        # Predefined options that will always be available
        predefined_cloth_types = [
            'T-Shirt', 'Shirt', 'Jeans', 'Dress', 'Skirt', 'Jacket', 'Coat', 'Sweater',
            'Hoodie', 'Pants', 'Shorts', 'Top', 'Blouse', 'Suit', 'Blazer',
            'Vest', 'Cardigan', 'Leggings', 'Saree', 'Kurta', 'Other'
        ]
        predefined_sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'Free Size']
        predefined_conditions = ['Like New', 'Good', 'Average', 'Fair', 'Worn']
        
        # Get unique values from actual donations
        db_cloth_types = sorted(set(d.get('cloth_type', '') for d in donations if d.get('cloth_type')))
        db_sizes = sorted(set(d.get('size', '') for d in donations if d.get('size')))
        db_conditions = sorted(set(d.get('condition_status', '') for d in donations if d.get('condition_status')))
        
        # Merge predefined options with database values
        all_cloth_types = sorted(set(predefined_cloth_types + db_cloth_types))
        all_sizes = sorted(set(predefined_sizes + db_sizes))
        all_conditions = sorted(set(predefined_conditions + db_conditions))
        
        return render_template("listings.html", 
                             donations=data, 
                             active_page="listings",
                             current_page=page,
                             total_pages=total_pages,
                             total_items=total_items,
                             cloth_types=all_cloth_types,
                             sizes=all_sizes,
                             conditions=all_conditions,
                             search=search,
                             cloth_type=cloth_type,
                             size_filter=size_filter,
                             condition=condition,
                             price_type=price_type,
                             sort_by=sort_by)
    except Exception as e:
        return render_template("listings.html", donations=[], active_page="listings", error=str(e))

@app.route('/requests')
@login_required
def requests_page():
    user_id = session.get("user_id")
    incoming_requests = []
    try:
        pr_res = supabase.table('purchase_requests').select(
            'id, status, created_at, '
            'donations!inner(id, cloth_type, size, condition_status, user_id), '
            'users!buyer_user_id(name, email)'
        ).eq('donations.user_id', user_id).order('id', desc=True).execute()
        
        incoming_requests = [dict_to_request_tuple(pr) for pr in pr_res.data]
    except Exception:
        pass
    
    return render_template("requests.html", incoming_requests=incoming_requests, active_page="requests")

# ADMIN: USERS LIST
@app.route('/admin/users')
@admin_required
def admin_users():
    res = supabase.table("users").select("*").order('created_at', desc=True).execute()
    users = [dict_to_user_tuple(u) for u in res.data]
    return render_template("admin_users.html", users=users, active_page="admin")

# ADMIN: EDIT USER
@app.route('/admin/users/<user_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = normalize_email(request.form.get("email"))
        # Password editing omitted for Supabase admin endpoint restrictions
        # (Could use auth admin API but simpler to just edit public profile)
        
        if not name or not email:
            flash("Name and email are required.", "warning")
            return redirect(f"/admin/users/{user_id}/edit")

        supabase.table("users").update({"name": name, "email": email}).eq("id", user_id).execute()
        flash("User updated successfully.", "success")
        return redirect("/admin/users")

    res = supabase.table("users").select("*").eq("id", user_id).execute()
    if not res.data:
        flash("User not found.", "warning")
        return redirect("/admin/users")
        
    user = dict_to_user_tuple(res.data[0])
    return render_template("admin_user_edit.html", user=user, active_page="admin")

# ADMIN: DELETE USER
@app.route('/admin/users/<user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    # Deleting from public.users will cascade or might need auth admin API
    # Assuming public.users ON DELETE CASCADE is NOT on auth.users backwards.
    # To truly delete a user, we should delete via auth endpoints or let public.user be deleted.
    supabase.table("users").delete().eq("id", user_id).execute()
    flash("User deleted.", "success")
    return redirect("/admin")

# ADMIN: FLAG USER as Suspicious
@app.route('/admin/users/<user_id>/flag', methods=['POST'])
@admin_required
def admin_flag_user(user_id):
    reason = (request.form.get('reason') or 'Suspicious activity').strip()
    try:
        supabase.table("users").update({
            "is_flagged": True,
            "flag_reason": reason
        }).eq("id", user_id).execute()
        flash(f"User flagged as suspicious: {reason}", "warning")
    except Exception as e:
        # Column might not exist yet - handle gracefully
        flash(f"Could not flag user. Make sure 'is_flagged' and 'flag_reason' columns exist in Supabase users table. Error: {str(e)}", "danger")
    return redirect("/admin")

# ADMIN: UNFLAG USER (mark as safe)
@app.route('/admin/users/<user_id>/unflag', methods=['POST'])
@admin_required
def admin_unflag_user(user_id):
    try:
        supabase.table("users").update({
            "is_flagged": False,
            "flag_reason": ""
        }).eq("id", user_id).execute()
        flash("User cleared — marked as safe.", "success")
    except Exception as e:
        flash(f"Could not unflag user: {str(e)}", "danger")
    return redirect("/admin")

# ADMIN: EDIT DONATION/LISTING
@app.route('/admin/donations/<int:donation_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_donation(donation_id):
    if request.method == "POST":
        user_name = (request.form.get("user_name") or "").strip()
        cloth = (request.form.get("cloth") or "").strip()
        size = (request.form.get("size") or "").strip()
        condition = (request.form.get("condition") or "").strip()
        address = (request.form.get("address") or "").strip()
        status = (request.form.get("status") or "Pending").strip()

        listing_type = (request.form.get("donation_type") or "free").strip().lower()
        is_free = True if listing_type != "paid" else False
        price_raw = (request.form.get("price") or "").strip()
        price = None
        if not is_free:
            try:
                price_val = float(price_raw)
                if price_val <= 0:
                    raise ValueError("Price must be positive")
                price = round(price_val, 2)  # type: ignore
            except Exception:
                flash("Please enter a valid price for Paid listings.", "warning")
                return redirect(f"/admin/donations/{donation_id}/edit")

        if not user_name or not cloth or not size or not condition or not address:
            flash("All fields are required.", "warning")
            return redirect(f"/admin/donations/{donation_id}/edit")

        update_data = {
            "user_name": user_name, "cloth_type": cloth, "size": size,
            "condition_status": condition, "address": address, "status": status,
            "is_free": is_free, "price": price
        }
        supabase.table("donations").update(update_data).eq("id", donation_id).execute()
        flash("Listing updated successfully.", "success")
        return redirect("/admin")

    res = supabase.table("donations").select("*").eq("id", donation_id).execute()
    if not res.data:
        flash("Listing not found.", "warning")
        return redirect("/admin")
        
    donation = dict_to_donation_tuple(res.data[0])
    return render_template("admin_donation_edit.html", donation=donation, active_page="admin")

# ADMIN: DELETE DONATION/LISTING
@app.route('/admin/donations/<int:donation_id>/delete', methods=['POST'])
@admin_required
def admin_delete_donation(donation_id):
    supabase.table("donations").delete().eq("id", donation_id).execute()
    flash("Listing deleted.", "success")
    return redirect("/admin")

# ADMIN: Purchase Request Approve
@app.route('/admin/requests/<int:request_id>/approve', methods=['POST'])
@admin_required
def admin_approve_request(request_id):
    try:
        pr_res = supabase.table("purchase_requests").select("donation_id, buyer_user_id").eq("id", request_id).execute()
        if pr_res.data:
            donation_id = pr_res.data[0]['donation_id']
            buyer_user_id = pr_res.data[0]['buyer_user_id']
            supabase.table("purchase_requests").update({"status": "Approved"}).eq("id", request_id).execute()
            try:
                supabase.table("notifications").insert({"user_id": buyer_user_id, "message": f"Your request for listing #{donation_id} has been Approved by Admin."}).execute()
            except Exception:
                pass
            flash("Request approved.", "success")
        else:
            flash("Request not found.", "warning")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    return redirect("/admin#requests")

# ADMIN: Purchase Request Reject
@app.route('/admin/requests/<int:request_id>/reject', methods=['POST'])
@admin_required
def admin_reject_request(request_id):
    try:
        pr_res = supabase.table("purchase_requests").select("donation_id, buyer_user_id").eq("id", request_id).execute()
        if pr_res.data:
            donation_id = pr_res.data[0]['donation_id']
            buyer_user_id = pr_res.data[0]['buyer_user_id']
            supabase.table("purchase_requests").update({"status": "Rejected"}).eq("id", request_id).execute()
            try:
                supabase.table("notifications").insert({"user_id": buyer_user_id, "message": f"Your request for listing #{donation_id} has been Rejected by Admin."}).execute()
            except Exception:
                pass
            flash("Request rejected.", "success")
        else:
            flash("Request not found.", "warning")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    return redirect("/admin#requests")

# ADMIN: Purchase Request Delete
@app.route('/admin/requests/<int:request_id>/delete', methods=['POST'])
@admin_required
def admin_delete_request(request_id):
    try:
        supabase.table("purchase_requests").delete().eq("id", request_id).execute()
        flash("Request deleted.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    return redirect("/admin#requests")

# BUY/REQUEST
@app.route('/request/<int:donation_id>')
@login_required
def request_listing(donation_id):
    if session.get("is_admin"):
        return redirect("/admin")

    res = supabase.table("donations").select("*").eq("id", donation_id).execute()
    if not res.data:
        flash("Listing not found.", "warning")
        return redirect("/listings")
        
    d = dict_to_donation_tuple(res.data[0])
    
    status = d[7]
    image_str = d[6] or ""
    
    if status == "Rejected":
        flash("This listing is rejected and not available.", "warning")
        return redirect("/listings")

    is_free = True if d[10] == 1 else False
    price = d[11]
    
    request_status = None
    request_sent = False
    req_res = supabase.table("purchase_requests").select("status").eq("donation_id", donation_id).eq("buyer_user_id", session.get("user_id")).order('id', desc=True).limit(1).execute()
    if req_res.data:
        request_sent = True
        request_status = req_res.data[0]['status']

    # Get donor contact info if request is approved
    phone = None
    email = None
    if request_status == "Approved":
        # Phone is stored in donations table at d[9]
        phone = d[9] if d[9] else None
        donor_user_id = res.data[0].get('user_id')
        if donor_user_id:
            try:
                donor_res = supabase.table("users").select("email").eq("id", donor_user_id).execute()
                if donor_res.data:
                    email = donor_res.data[0].get('email')
            except Exception:
                pass

    return render_template(
        "request.html",
        donation_id=donation_id,
        donor_name=d[1],
        cloth=d[2],
        size=d[3],
        condition=d[4],
        status=status,
        image_str=image_str,
        is_free=is_free,
        price=price,
        request_sent=request_sent,
        request_status=request_status,
        phone=phone,
        email=email
    )

@app.route('/send-request/<int:donation_id>', methods=['POST'])
@login_required
def send_request(donation_id):
    if session.get("is_admin"):
        return redirect("/admin")

    res = supabase.table("donations").select("*").eq("id", donation_id).execute()
    if not res.data:
        flash("Listing not found.", "warning")
        return redirect("/listings")
        
    donor_user_id = res.data[0].get('user_id')

    req_res = supabase.table("purchase_requests").select("id").eq("donation_id", donation_id).eq("buyer_user_id", session.get("user_id")).execute()
    if req_res.data:
        flash("You have already requested this item.", "info")
        return redirect(f"/request/{donation_id}")

    supabase.table("purchase_requests").insert({
        "donation_id": donation_id,
        "buyer_user_id": session.get("user_id"),
        "status": "Pending"
    }).execute()

    try:
        supabase.table("notifications").insert({"user_id": session.get("user_id"), "message": f"Your request for listing #{donation_id} has been sent to the donor for approval."}).execute()
        if donor_user_id:
            supabase.table("notifications").insert({"user_id": donor_user_id, "message": f"You received a new request for listing #{donation_id}. Approve or Reject from your Requests page."}).execute()
    except Exception:
        pass

    flash("Request sent successfully!", "success")
    return redirect(f"/request/{donation_id}")

@app.route('/donor/requests/<int:request_id>/approve', methods=['POST'])
@login_required
def donor_approve_request(request_id):
    if session.get("is_admin"):
        return redirect("/admin")

    try:
        pr_res = supabase.table("purchase_requests").select("donation_id, buyer_user_id, donations!inner(user_id)").eq("id", request_id).execute()
        if not pr_res.data or pr_res.data[0]['donations']['user_id'] != session.get("user_id"):
            flash("Not authorized.", "warning")
            return redirect("/dashboard")

        row = pr_res.data[0]
        donation_id = row['donation_id']
        buyer_user_id = row['buyer_user_id']
        
        supabase.table("purchase_requests").update({"status": "Approved"}).eq("id", request_id).execute()
        supabase.table("notifications").insert({"user_id": buyer_user_id, "message": f"Your request for listing #{donation_id} has been Approved by the donor."}).execute()
        flash("Request approved.", "success")
    except Exception:
        flash("Error processing request.", "warning")

    return redirect("/dashboard")

@app.route('/donor/requests/<int:request_id>/reject', methods=['POST'])
@login_required
def donor_reject_request(request_id):
    if session.get("is_admin"):
        return redirect("/admin")

    try:
        pr_res = supabase.table("purchase_requests").select("donation_id, buyer_user_id, donations!inner(user_id)").eq("id", request_id).execute()
        if not pr_res.data or pr_res.data[0]['donations']['user_id'] != session.get("user_id"):
            flash("Not authorized.", "warning")
            return redirect("/dashboard")

        row = pr_res.data[0]
        donation_id = row['donation_id']
        buyer_user_id = row['buyer_user_id']
        
        supabase.table("purchase_requests").update({"status": "Rejected"}).eq("id", request_id).execute()
        supabase.table("notifications").insert({"user_id": buyer_user_id, "message": f"Your request for listing #{donation_id} has been Rejected by the donor."}).execute()
        flash("Request rejected.", "success")
    except Exception:
        flash("Error processing request.", "warning")

    return redirect("/dashboard")

# APPROVE DONATION
@app.route('/approve/<int:donation_id>')
@admin_required
def approve(donation_id):
    res = supabase.table("donations").select("user_id").eq("id", donation_id).execute()
    user_id = res.data[0]['user_id'] if res.data else None
    
    supabase.table("donations").update({"status": "Approved"}).eq("id", donation_id).execute()
    
    if user_id:
        try:
            supabase.table("notifications").insert({"user_id": user_id, "message": "Your donation/listing has been Approved."}).execute()
        except:
            pass

    return redirect("/admin")

# REJECT DONATION
@app.route('/reject/<int:donation_id>')
@admin_required
def reject(donation_id):
    res = supabase.table("donations").select("user_id").eq("id", donation_id).execute()
    user_id = res.data[0]['user_id'] if res.data else None
    
    supabase.table("donations").update({"status": "Rejected"}).eq("id", donation_id).execute()
    
    if user_id:
        try:
            supabase.table("notifications").insert({"user_id": user_id, "message": "Your donation/listing has been Rejected."}).execute()
        except:
            pass

    return redirect("/admin")

if __name__ == "__main__":
    app.run(debug=True)