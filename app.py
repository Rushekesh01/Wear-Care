from flask import Flask, render_template, request, redirect, session
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
    return render_template("index.html", active_page="home")


# REGISTER
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form.get('name')
        email = normalize_email(request.form.get('email'))
        password = request.form.get('password')

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

        return redirect("/dashboard")

    return render_template("login.html")


# ADMIN LOGIN
@app.route('/admin-login', methods=['GET','POST'])
def admin_login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        if email == "admin@wearcare.com" and password == "admin123":

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

        user_name = session.get("user_name")

        cloth = request.form.get("cloth")
        size = request.form.get("size")
        condition = request.form.get("condition")
        address = request.form.get("address")

        image = request.files.get("image")
        image_name = ""

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            image_name = filename
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            """INSERT INTO donations
            (user_name,cloth_type,size,condition_status,address,image,status)
            VALUES(%s,%s,%s,%s,%s,%s,%s)""",
            (user_name, cloth, size, condition, address, image_name, "Pending")
        )

        db.commit()

        return render_template("donate.html", success="Donation submitted")

    return render_template("donate.html")


# DASHBOARD
@app.route('/dashboard')
@login_required
def dashboard():

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT * FROM donations WHERE user_name=%s",
        (session.get("user_name"),)
    )

    data = cursor.fetchall()

    return render_template(
        "dashboard.html",
        donations=data
    )


# ADMIN PANEL
@app.route('/admin')
@admin_required
def admin():

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM donations")
    data = cursor.fetchall()

    return render_template(
        "admin.html",
        donations=data
    )


# APPROVE DONATION
@app.route('/approve/<id>')
@admin_required
def approve(id):

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "UPDATE donations SET status='Approved' WHERE id=%s",
        (id,)
    )

    db.commit()

    return redirect("/admin")


# REJECT DONATION
@app.route('/reject/<id>')
@admin_required
def reject(id):

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "UPDATE donations SET status='Rejected' WHERE id=%s",
        (id,)
    )

    db.commit()

    return redirect("/admin")


if __name__ == "__main__":
    app.run(debug=True)