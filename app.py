from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "wearcare-dev"

UPLOAD_FOLDER = "static/uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# DATABASE CONNECTION
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="wearcare"
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

        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user:
            return render_template("register.html", error="Email already exists")

        hashed = generate_password_hash(password)

        cursor.execute(
            "INSERT INTO users(name,email,password) VALUES(%s,%s,%s)",
            (name, email, hashed)
        )

        db.commit()
        cursor.close()
        db.close()

        return redirect("/login")

    return render_template("register.html")


# USER LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == "POST":

        email = normalize_email(request.form.get("email"))
        password = request.form.get("password")

        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "SELECT id,name,email,password FROM users WHERE email=%s",
            (email,)
        )

        user = cursor.fetchone()

        if not user:
            return render_template("login.html", error="Invalid email or password")

        user_id, name, email, hashed_password = user

        if not check_password_hash(hashed_password, password):
            return render_template("login.html", error="Invalid email or password")

        session["user_id"] = user_id
        session["user_name"] = name
        session["user_email"] = email
        session["is_admin"] = False

        cursor.close()
        db.close()

        return redirect("/dashboard")

    return render_template("login.html")


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
        size = request.form.get("size")
        condition = request.form.get("condition")
        address = request.form.get("address")
        phone = (request.form.get("phone") or "").strip()

        if not phone:
            return render_template("donate.html", error="Please enter your phone number")

        donation_type = (request.form.get("donation_type") or "free").strip().lower()
        is_free = 1 if donation_type != "paid" else 0
        price_raw = (request.form.get("price") or "").strip()
        price = None
        if is_free == 0:
            try:
                price_val = float(price_raw)
                if price_val <= 0:
                    raise ValueError("Price must be positive")
                price = round(price_val, 2)
            except Exception:
                return render_template("donate.html", error="Please enter a valid price for Paid listings")

        image = request.files.get("image")
        image_name = ""

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            image_name = filename
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute(
                """INSERT INTO donations
                (user_id,user_name,cloth_type,size,condition_status,address,image,status,is_free,price,phone)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (session.get("user_id"), user_name, cloth, size, condition, address, image_name, "Pending", is_free, price, phone)
            )
        except mysql.connector.Error:
            cursor.execute(
                """INSERT INTO donations
                (user_name,cloth_type,size,condition_status,address,image,status)
                VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (user_name, cloth, size, condition, address, image_name, "Pending")
            )

        db.commit()
        cursor.close()
        db.close()

        return render_template("donate.html", success="Donation submitted successfully")

    return render_template("donate.html")


# DASHBOARD
@app.route('/dashboard')
@login_required
def dashboard():

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            "SELECT * FROM donations WHERE user_id=%s ORDER BY id DESC",
            (session.get("user_id"),)
        )
        data = cursor.fetchall()
    except mysql.connector.Error:
        cursor.execute(
            "SELECT * FROM donations WHERE user_name=%s ORDER BY id DESC",
            (session.get("user_name"),)
        )
        data = cursor.fetchall()

    notifications = []
    popup_notification = None
    try:
        # Backward compatible: if read_at doesn't exist, this still works via fallback below.
        try:
            cursor.execute(
                "SELECT id, message, created_at, read_at FROM notifications WHERE user_id=%s ORDER BY id DESC LIMIT 10",
                (session.get("user_id"),)
            )
            notifications = cursor.fetchall()

            cursor.execute(
                "SELECT id, message, created_at FROM notifications WHERE user_id=%s AND read_at IS NULL ORDER BY id DESC LIMIT 1",
                (session.get("user_id"),)
            )
            unread = cursor.fetchone()
            if unread:
                popup_notification = {"id": unread[0], "message": unread[1], "created_at": unread[2]}
                cursor.execute("UPDATE notifications SET read_at=NOW() WHERE id=%s", (unread[0],))
                db.commit()
        except mysql.connector.Error:
            cursor.execute(
                "SELECT id, message, created_at FROM notifications WHERE user_id=%s ORDER BY id DESC LIMIT 10",
                (session.get("user_id"),)
            )
            notifications = cursor.fetchall()
    except mysql.connector.Error:
        notifications = []

    incoming_requests = []
    try:
        cursor.execute(
            """
            SELECT pr.id, pr.status, pr.created_at,
                   d.id, d.cloth_type, d.size, d.condition_status,
                   u.name, u.email
            FROM purchase_requests pr
            JOIN donations d ON d.id = pr.donation_id
            JOIN users u ON u.id = pr.buyer_user_id
            WHERE d.user_id = %s
            ORDER BY pr.id DESC
            """,
            (session.get("user_id"),)
        )
        incoming_requests = cursor.fetchall()
    except mysql.connector.Error:
        incoming_requests = []

    my_requests = []
    try:
        cursor.execute(
            """
            SELECT pr.id, pr.status, pr.created_at,
                   d.id, d.cloth_type, d.size, d.condition_status,
                   du.name, du.email
            FROM purchase_requests pr
            JOIN donations d ON d.id = pr.donation_id
            JOIN users du ON du.id = d.user_id
            WHERE pr.buyer_user_id = %s
            ORDER BY pr.id DESC
            """,
            (session.get("user_id"),)
        )
        my_requests = cursor.fetchall()
    except mysql.connector.Error:
        my_requests = []

    cursor.close()
    db.close()

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

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM donations")
    data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("admin.html", donations=data)


@app.route('/listings')
def listings():

    db = get_db()
    cursor = db.cursor()

    # Show only donations from OTHER users (not your own)
    user_id = session.get("user_id")
    if user_id and not session.get("is_admin"):
        cursor.execute("SELECT * FROM donations WHERE user_id != %s OR user_id IS NULL ORDER BY id DESC", (user_id,))
    else:
        cursor.execute("SELECT * FROM donations ORDER BY id DESC")
    data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("listings.html", donations=data, active_page="listings")


@app.route('/requests')
@login_required
def requests_page():
    db = get_db()
    cursor = db.cursor()

    incoming_requests = []
    try:
        cursor.execute(
            """
            SELECT pr.id, pr.status, pr.created_at,
                   d.id, d.cloth_type, d.size, d.condition_status,
                   u.name, u.email
            FROM purchase_requests pr
            JOIN donations d ON d.id = pr.donation_id
            JOIN users u ON u.id = pr.buyer_user_id
            WHERE d.user_id = %s
            ORDER BY pr.id DESC
            """,
            (session.get("user_id"),)
        )
        incoming_requests = cursor.fetchall()
    except mysql.connector.Error:
        incoming_requests = []

    cursor.close()
    db.close()

    return render_template("requests.html", incoming_requests=incoming_requests, active_page="requests")


# ADMIN: USERS LIST
@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute("SELECT id,name,email,created_at FROM users ORDER BY id DESC")
        users = cursor.fetchall()
    except mysql.connector.Error:
        cursor.execute("SELECT id,name,email FROM users ORDER BY id DESC")
        rows = cursor.fetchall()
        users = [(r[0], r[1], r[2], None) for r in rows]

    cursor.close()
    db.close()

    return render_template("admin_users.html", users=users, active_page="admin")


# ADMIN: EDIT USER
@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = normalize_email(request.form.get("email"))
        new_password = request.form.get("password") or ""

        if not name or not email:
            flash("Name and email are required.", "warning")
            return redirect(f"/admin/users/{user_id}/edit")

        cursor.execute("SELECT id FROM users WHERE email=%s AND id<>%s", (email, user_id))
        if cursor.fetchone():
            flash("Email already exists for another user.", "warning")
            return redirect(f"/admin/users/{user_id}/edit")

        if new_password.strip() != "":
            hashed = generate_password_hash(new_password)
            cursor.execute(
                "UPDATE users SET name=%s,email=%s,password=%s WHERE id=%s",
                (name, email, hashed, user_id)
            )
        else:
            cursor.execute(
                "UPDATE users SET name=%s,email=%s WHERE id=%s",
                (name, email, user_id)
            )

        db.commit()
        flash("User updated successfully.", "success")
        cursor.close()
        db.close()
        return redirect("/admin/users")

    try:
        cursor.execute("SELECT id,name,email,created_at FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()
    except mysql.connector.Error:
        cursor.execute("SELECT id,name,email FROM users WHERE id=%s", (user_id,))
        row = cursor.fetchone()
        user = (row[0], row[1], row[2], None) if row else None

    cursor.close()
    db.close()

    if not user:
        flash("User not found.", "warning")
        return redirect("/admin/users")

    return render_template("admin_user_edit.html", user=user, active_page="admin")


# ADMIN: DELETE USER
@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    db.commit()

    cursor.close()
    db.close()

    flash("User deleted.", "success")
    return redirect("/admin/users")


# ADMIN: EDIT DONATION/LISTING
@app.route('/admin/donations/<int:donation_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_donation(donation_id):
    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        user_name = (request.form.get("user_name") or "").strip()
        cloth = (request.form.get("cloth") or "").strip()
        size = (request.form.get("size") or "").strip()
        condition = (request.form.get("condition") or "").strip()
        address = (request.form.get("address") or "").strip()
        status = (request.form.get("status") or "Pending").strip()

        listing_type = (request.form.get("donation_type") or "free").strip().lower()
        is_free = 1 if listing_type != "paid" else 0
        price_raw = (request.form.get("price") or "").strip()
        price = None
        if is_free == 0:
            try:
                price_val = float(price_raw)
                if price_val <= 0:
                    raise ValueError("Price must be positive")
                price = round(price_val, 2)
            except Exception:
                flash("Please enter a valid price for Paid listings.", "warning")
                return redirect(f"/admin/donations/{donation_id}/edit")

        if not user_name or not cloth or not size or not condition or not address:
            flash("All fields are required.", "warning")
            return redirect(f"/admin/donations/{donation_id}/edit")

        try:
            cursor.execute(
                """UPDATE donations
                   SET user_name=%s, cloth_type=%s, size=%s, condition_status=%s, address=%s,
                       status=%s, is_free=%s, price=%s
                   WHERE id=%s""",
                (user_name, cloth, size, condition, address, status, is_free, price, donation_id)
            )
        except mysql.connector.Error:
            cursor.execute(
                """UPDATE donations
                   SET user_name=%s, cloth_type=%s, size=%s, condition_status=%s, address=%s,
                       status=%s
                   WHERE id=%s""",
                (user_name, cloth, size, condition, address, status, donation_id)
            )

        db.commit()
        flash("Listing updated successfully.", "success")
        cursor.close()
        db.close()
        return redirect("/admin")

    cursor.execute("SELECT * FROM donations WHERE id=%s", (donation_id,))
    donation = cursor.fetchone()

    cursor.close()
    db.close()

    if not donation:
        flash("Listing not found.", "warning")
        return redirect("/admin")

    return render_template("admin_donation_edit.html", donation=donation, active_page="admin")


# ADMIN: DELETE DONATION/LISTING
@app.route('/admin/donations/<int:donation_id>/delete', methods=['POST'])
@admin_required
def admin_delete_donation(donation_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM donations WHERE id=%s", (donation_id,))
    db.commit()

    cursor.close()
    db.close()

    flash("Listing deleted.", "success")
    return redirect("/admin")


# BUY/REQUEST (only logged-in users, not admin)
@app.route('/request/<int:donation_id>')
@login_required
def request_listing(donation_id):
    if session.get("is_admin"):
        return redirect("/admin")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM donations WHERE id=%s", (donation_id,))
    d = cursor.fetchone()

    if not d:
        cursor.close()
        db.close()
        flash("Listing not found.", "warning")
        return redirect("/listings")

    status = d[7] if len(d) > 7 else "Pending"
    image = d[6] if len(d) > 6 else ""
    if status == "Rejected":
        cursor.close()
        db.close()
        flash("This listing is rejected and not available.", "warning")
        return redirect("/listings")

    is_free = True
    price = None
    phone = None
    try:
        is_free = True if (len(d) > 10 and (d[10] == 1 or d[10] is True)) else False
        price = d[11] if len(d) > 11 else None
        phone = d[12] if len(d) > 12 else None
    except Exception:
        is_free = True

    # Check if request already exists
    request_status = None
    request_sent = False
    try:
        cursor.execute(
            "SELECT status FROM purchase_requests WHERE donation_id=%s AND buyer_user_id=%s ORDER BY id DESC LIMIT 1",
            (donation_id, session.get("user_id"))
        )
        existing = cursor.fetchone()
        if existing:
            request_sent = True
            request_status = existing[0]
    except mysql.connector.Error:
        pass

    cursor.close()
    db.close()

    return render_template(
        "request.html",
        donation_id=donation_id,
        donor_name=d[1] if len(d) > 1 else "",
        cloth=d[2] if len(d) > 2 else "",
        size=d[3] if len(d) > 3 else "",
        condition=d[4] if len(d) > 4 else "",
        status=status,
        image=image,
        is_free=is_free,
        price=price,
        request_sent=request_sent,
        request_status=request_status,
        phone=phone if request_status == "Approved" else None
    )


@app.route('/send-request/<int:donation_id>', methods=['POST'])
@login_required
def send_request(donation_id):
    if session.get("is_admin"):
        return redirect("/admin")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM donations WHERE id=%s", (donation_id,))
    d = cursor.fetchone()

    if not d:
        cursor.close()
        db.close()
        flash("Listing not found.", "warning")
        return redirect("/listings")

    # Check if request already exists
    cursor.execute(
        "SELECT id FROM purchase_requests WHERE donation_id=%s AND buyer_user_id=%s",
        (donation_id, session.get("user_id"))
    )
    if cursor.fetchone():
        cursor.close()
        db.close()
        flash("You have already requested this item.", "info")
        return redirect(f"/request/{donation_id}")

    # Create the request
    cursor.execute(
        "INSERT INTO purchase_requests(donation_id,buyer_user_id,status) VALUES(%s,%s,%s)",
        (donation_id, session.get("user_id"), "Pending")
    )

    # Notify buyer
    try:
        cursor.execute(
            "INSERT INTO notifications(user_id, message) VALUES(%s,%s)",
            (session.get("user_id"), f"Your request for listing #{donation_id} has been sent to the donor for approval.")
        )
    except mysql.connector.Error:
        pass

    # Notify donor
    try:
        cursor.execute("SELECT user_id FROM donations WHERE id=%s", (donation_id,))
        donor_row = cursor.fetchone()
        donor_user_id = donor_row[0] if donor_row else None
        if donor_user_id:
            cursor.execute(
                "INSERT INTO notifications(user_id, message) VALUES(%s,%s)",
                (donor_user_id, f"You received a new request for listing #{donation_id}. Approve or Reject from your Requests page.")
            )
    except mysql.connector.Error:
        pass

    db.commit()
    cursor.close()
    db.close()

    flash("Request sent successfully!", "success")
    return redirect(f"/request/{donation_id}")


@app.route('/donor/requests/<int:request_id>/approve', methods=['POST'])
@login_required
def donor_approve_request(request_id):
    if session.get("is_admin"):
        return redirect("/admin")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            SELECT pr.donation_id, pr.buyer_user_id, d.user_id
            FROM purchase_requests pr
            JOIN donations d ON d.id = pr.donation_id
            WHERE pr.id=%s
            """,
            (request_id,)
        )
        row = cursor.fetchone()
        if not row or row[2] != session.get("user_id"):
            flash("Not authorized.", "warning")
            cursor.close()
            db.close()
            return redirect("/dashboard")

        donation_id, buyer_user_id, _ = row
        cursor.execute("UPDATE purchase_requests SET status='Approved' WHERE id=%s", (request_id,))
        cursor.execute(
            "INSERT INTO notifications(user_id, message) VALUES(%s,%s)",
            (buyer_user_id, f"Your request for listing #{donation_id} has been Approved by the donor.")
        )
        db.commit()
        flash("Request approved.", "success")
    except mysql.connector.Error:
        flash("Request system is not available (DB not updated).", "warning")
    finally:
        cursor.close()
        db.close()

    return redirect("/dashboard")


@app.route('/donor/requests/<int:request_id>/reject', methods=['POST'])
@login_required
def donor_reject_request(request_id):
    if session.get("is_admin"):
        return redirect("/admin")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            SELECT pr.donation_id, pr.buyer_user_id, d.user_id
            FROM purchase_requests pr
            JOIN donations d ON d.id = pr.donation_id
            WHERE pr.id=%s
            """,
            (request_id,)
        )
        row = cursor.fetchone()
        if not row or row[2] != session.get("user_id"):
            flash("Not authorized.", "warning")
            cursor.close()
            db.close()
            return redirect("/dashboard")

        donation_id, buyer_user_id, _ = row
        cursor.execute("UPDATE purchase_requests SET status='Rejected' WHERE id=%s", (request_id,))
        cursor.execute(
            "INSERT INTO notifications(user_id, message) VALUES(%s,%s)",
            (buyer_user_id, f"Your request for listing #{donation_id} has been Rejected by the donor.")
        )
        db.commit()
        flash("Request rejected.", "success")
    except mysql.connector.Error:
        flash("Request system is not available (DB not updated).", "warning")
    finally:
        cursor.close()
        db.close()

    return redirect("/dashboard")


# APPROVE DONATION
@app.route('/approve/<id>')
@admin_required
def approve(id):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT user_id FROM donations WHERE id=%s", (id,))
    row = cursor.fetchone()
    user_id = row[0] if row else None

    cursor.execute("UPDATE donations SET status='Approved' WHERE id=%s", (id,))

    try:
        if user_id:
            cursor.execute(
                "INSERT INTO notifications(user_id, message) VALUES(%s,%s)",
                (user_id, "Your donation/listing has been Approved.")
            )
    except mysql.connector.Error:
        pass

    db.commit()

    cursor.close()
    db.close()

    return redirect("/admin")


# REJECT DONATION
@app.route('/reject/<id>')
@admin_required
def reject(id):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT user_id FROM donations WHERE id=%s", (id,))
    row = cursor.fetchone()
    user_id = row[0] if row else None

    cursor.execute("UPDATE donations SET status='Rejected' WHERE id=%s", (id,))

    try:
        if user_id:
            cursor.execute(
                "INSERT INTO notifications(user_id, message) VALUES(%s,%s)",
                (user_id, "Your donation/listing has been Rejected.")
            )
    except mysql.connector.Error:
        pass

    db.commit()

    cursor.close()
    db.close()

    return redirect("/admin")


if __name__ == "__main__":
    app.run(debug=True)