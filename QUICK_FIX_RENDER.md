# Quick Fix for Render Deployment Error

## The Problem
✗ App works locally  
✗ Fails on Render with "internal server error" on register/login

**Reason**: Supabase URL and API Key (and Gmail credentials) not configured on Render.

---

## The Fix (5 minutes)

### STEP 1: Get Supabase Credentials
Go to: https://supabase.com/dashboard

1. Click your **Wear & Care** project
2. Click **Settings** (bottom left menu)
3. Click **API** 
4. Copy these two values:
   - **Project URL** → your `SUPABASE_URL`
   - **anon public** (the long random string) → your `SUPABASE_KEY`

**Example**:
```
SUPABASE_URL = https://xyzabc123.supabase.co
SUPABASE_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### STEP 2: Get Gmail Config
Gmail account setup:
1. Enable 2-factor authentication (if not already done)
2. Go to: https://myaccount.google.com/apppasswords
3. Select **Mail** → **Windows Computer** (or device you use)
4. Copy the **16-character password** that appears

**Example**:
```
GMAIL_SMTP_USER = your.email@gmail.com
GMAIL_SMTP_PASSWORD = abcd efgh ijkl mnop
```

### STEP 3: Generate Secret Key
Run in your PC terminal:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Copy the output (e.g., `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t`)

### STEP 4: Set on Render
1. Go to: https://dashboard.render.com
2. Click your **Wear & Care** Web Service
3. Click **Settings** tab
4. Scroll to **Environment** section
5. Click **Add Environment Variable** and paste each:

```
SUPABASE_URL       = https://xyzabc123.supabase.co
SUPABASE_KEY       = eyJhbGciOiJIUzI1cCI6IkpXVCJ9...
GMAIL_SMTP_USER    = your.email@gmail.com
GMAIL_SMTP_PASSWORD = abcd efgh ijkl mnop
SECRET_KEY         = a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t
```

6. Click **Save**
7. Render will auto-redeploy

---

## Test It
1. Open your Render link: `https://wear-care-[random].onrender.com`
2. Click **Create Account**
3. Fill in fields and submit
4. Check your email for OTP
5. Enter OTP → Login → Dashboard

✓ Should work now!

---

## If Still Not Working

### Check Render Logs
1. In Render dashboard, click your service
2. Click **Logs** tab
3. Look for error messages
4. Common errors:
   - `SUPABASE_URL not set` → add the environment variable
   - `SUPABASE_KEY not set` → add the environment variable
   - `Gmail connection failed` → verify GMAIL credentials

### Verify Supabase DB
1. Go to Supabase dashboard
2. Click **SQL Editor**
3. Run:
   ```sql
   SELECT * FROM users;
   ```
4. Should show any users created (even if 0 rows, no error = good)

### Test Locally First
1. Create `.env` file in project folder:
   ```
   SUPABASE_URL=https://xyzabc123.supabase.co
   SUPABASE_KEY=eyJhbGciOiJIUzI1cCI...
   GMAIL_SMTP_USER=your.email@gmail.com
   GMAIL_SMTP_PASSWORD=abcd efgh ijkl mnop
   SECRET_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m...
   ```
2. Run: `python app.py`
3. Test at `http://127.0.0.1:5000`

---

## Summary
Environment variables were empty on Render → App couldn't connect to Supabase → "internal server error"  
**Solution**: Add 5 environment variables to Render → Redeploy → Works!
