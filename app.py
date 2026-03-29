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
url = os.environ.get("SUPABASE_URL", "")
key = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(url, key)

# GMAIL SMTP SETUP
GMAIL_USER = os.environ.get("GMAIL_SMTP_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_SMTP_PASSWORD", "")

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
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"OTP email successfully sent to {to_email}")
    except Exception as e:
        print(f"Failed to send OTP via Gmail SMTP: {str(e)}")

app = Flask(__name__)
app.secret_key = "wearcare-dev"

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
    return (u.get('id'), u.get('name'), u.get('email'), u.get('created_at'))

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

        try:
            res = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            user = res.user
            if not user:
                return render_template("login.html", error="Login failed, no user returned.")
            session["user_id"] = user.id
            session["user_name"] = user.user_metadata.get("name", "User") if user.user_metadata else "User"
            session["user_email"] = user.email
            session["is_admin"] = False
            
            # Send the welcome email on their actual first confirmed login if you wish, 
            # but since they successfully confirmed their OTP, Supabase sends their token natively.
            
            return redirect("/dashboard")
        except Exception as e:
            msg = str(e)
            if "Email not confirmed" in msg:
                return redirect(f"/verify-otp?email={email}")
            return render_template("login.html", error="Invalid email or password (or unconfirmed account)")

    return render_template("login.html")

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
        email = request.form.get("email")
        password = request.form.get("password")

        if email == "admin@rushi.com" and password == "admin123":
            session["user_id"] = "admin"
            session["user_name"] = "Admin"
            session["is_admin"] = True
            return redirect("/admin")
        
        return render_template("admin_login.html", error="Invalid admin credentials")
    return render_template("admin_login.html")

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
    res = supabase.table("donations").select("*").order('id', desc=True).execute()
    data = [dict_to_donation_tuple(d) for d in res.data]
    return render_template("admin.html", donations=data)

@app.route('/listings')
def listings():
    user_id = session.get("user_id")
    if user_id and not session.get("is_admin"):
        res = supabase.table("donations").select("*").neq("user_id", user_id).order('id', desc=True).execute()
    else:
        res = supabase.table("donations").select("*").order('id', desc=True).execute()
        
    data = [dict_to_donation_tuple(d) for d in res.data]
    return render_template("listings.html", donations=data, active_page="listings")

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
    return redirect("/admin/users")

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

    phone = d[11] if request_status == "Approved" else None

    return render_template(
        "request.html",
        donation_id=donation_id,
        donor_name=d[2],
        cloth=d[3],
        size=d[4],
        condition=d[5],
        status=status,
        image_str=image_str,
        is_free=is_free,
        price=price,
        request_sent=request_sent,
        request_status=request_status,
        phone=phone
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