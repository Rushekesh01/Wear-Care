import codecs
with codecs.open('app.py', 'r', 'utf-8') as f:
    data = f.read()

start_idx = data.find('# VERIFY OTP')
end_idx = data.find('# ADMIN LOGIN')

new_code = '''# VERIFY OTP
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
                res = supabase.auth.sign_up({
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
        import random
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
                return render_template("reset_password.html", error="Failed to update password correctly.")
        else:
            return render_template("reset_password.html", error="Invalid OTP code matched.")

    return render_template("reset_password.html")

'''

if start_idx != -1 and end_idx != -1:
    new_data = data[:int(start_idx)] + new_code + data[int(end_idx):]
    with codecs.open('app.py', 'w', 'utf-8') as f:
        f.write(new_data)
