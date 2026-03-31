# Wear & Care - Render Deployment Guide

## Problem
App works locally but fails on Render with "internal server error" on register/login.

**Root Cause**: Environment variables not set on Render.

---

## Solution: Set Environment Variables on Render

### Step 1: Go to Your Render Dashboard
- Open [https://dashboard.render.com](https://dashboard.render.com)
- Click your deployed service (Web Service)
- Go to **Settings** tab

### Step 2: Add Environment Variables

Scroll to **"Environment"** section and add these variables:

| Variable | Value | Where to get it |
|----------|-------|-----------------|
| `SUPABASE_URL` | `https://[your-project].supabase.co` | [Supabase Dashboard](https://supabase.com/dashboard) → Settings → API → URL |
| `SUPABASE_KEY` | Your anon/public key | Supabase Dashboard → Settings → API → `anon` / `public` key |
| `GMAIL_SMTP_USER` | Your Gmail address | e.g., `your.email@gmail.com` |
| `GMAIL_SMTP_PASSWORD` | Your Gmail App Password | [Generate here](https://myaccount.google.com/apppasswords) (NOT your main password) |
| `SECRET_KEY` | Random long string | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |

### Step 3: Deploy
- After adding all variables, click **"Deploy"** or push code to trigger auto-deploy.
- Render will restart the service with new environment variables.

---

## Detailed Steps for Each Variable

### 1. Get Supabase Credentials
1. Go to [supabase.com](https://supabase.com) and open your project
2. Click **Settings** (bottom left)
3. Click **API**
4. Copy:
   - **URL**: `SUPABASE_URL`
   - **anon public**: `SUPABASE_KEY`

### 2. Setup Gmail for OTP
1. Enable 2-factor authentication on your Gmail account
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Select **Mail** and **Windows Computer**
4. Copy the 16-character password
   - `GMAIL_SMTP_USER`: Your Gmail (e.g., `rushekesh@gmail.com`)
   - `GMAIL_SMTP_PASSWORD`: The 16-char password

### 3. Generate a Secret Key
Run this in your terminal:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Copy the output (32+ character random string) → `SECRET_KEY`

---

## After Deployment: Test the Login Flow

1. Open your Render link (e.g., `https://wear-care-xyz.onrender.com`)
2. Click **"Create Account"**
3. Fill in:
   - Name: Test User
   - Email: testuser@example.com
   - Password: Test123Password
4. Click **"Create Account"** → should send OTP to email
5. Check email inbox → copy OTP
6. Enter OTP → account created
7. Login with same credentials → should go to Dashboard

---

## Common Issues & Fixes

### Issue: "Failed to send OTP via Gmail SMTP"
**Fix**: Verify in Render environment:
- `GMAIL_SMTP_USER` is exactly your Gmail address
- `GMAIL_SMTP_PASSWORD` is the 16-char App Password (not your main password)
- Gmail 2-factor is enabled

### Issue: "Database connection error"
**Fix**: Verify Supabase environment:
- `SUPABASE_URL` starts with `https://` and ends with `.supabase.co`
- `SUPABASE_KEY` is a valid 40+ character string (should start with `eyJ...`)
- No extra spaces before/after

### Issue: Render keeps crashing
**Fix**: Check logs:
- Go to **Logs** tab on Render service
- Look for errors like `ModuleNotFoundError`, `ImportError`
- Verify `requirements.txt` has all dependencies:
  ```
  flask==2.3.0
  supabase==2.0.0
  python-dotenv==1.0.0
  ```

---

## Quick Checklist

- [ ] Supabase project created and has `users` table
- [ ] Render environment variables set (all 5 variables)
- [ ] Gmail App Password generated (not main password)
- [ ] Render service redeployed after setting variables
- [ ] Tested registration → OTP send → login flow
- [ ] Checked Render logs for errors

---

## Help

If still having issues:
1. **Check Render Logs**: Your service → **Logs** tab
2. **Check Supabase Status**: [supabase.com/status](https://supabase.com/status)
3. **Test locally first**: Copy `.env.example` → `.env`, fill real values, run `python app.py`
