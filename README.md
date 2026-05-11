# 👕 Wear & Care: A Clothing Donation Initiative

[![Live Demo](https://img.shields.io/badge/Live-Demo-brightgreen.svg)](https://wear-care.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Web-black.svg)](https://flask.palletsprojects.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Database-green.svg)](https://supabase.com)

**Wear & Care** is a web-based application designed to promote textile sustainability and support underprivileged communities by bridging the gap between clothing donors and those in need.

### 🌐 [Live Website: wear-care.onrender.com](https://wear-care.onrender.com)

---

## 📖 Abstract
Huge volumes of wearable clothing are discarded annually in landfills, while many individuals lack access to basic apparel. This system provides a centralized digital platform where individuals, retail brands, and organizations can list surplus or pre-loved garments. 

The platform features secure user authentication via email OTPs, image uploads, and an integrated admin module to moderate listings and monitor donation cycles. By streamlining the logistics of clothing redistribution, Wear & Care fosters a culture of circular fashion, reduces environmental waste, and strengthens community welfare.

## ✨ Features
- **Secure Authentication**: OTP-based login and registration (No passwords to remember).
- **Donate & Buy**: Users can upload items for donation or sell them at a minimal price.
- **Browse & Filter**: Request or buy items based on size, condition, and category.
- **Admin Dashboard**: Moderation of listings, user management, and CSV data export.
- **Cloud Storage**: Secure image hosting using Supabase Storage.
- **Real-time Notifications**: Buyers and sellers get notified when requests are made.

## 🛠️ Tech Stack
- **Backend:** Python, Flask
- **Frontend:** HTML5, CSS3, Bootstrap 5
- **Database & Storage:** Supabase (PostgreSQL)
- **Email Service:** Python `smtplib` (Gmail SMTP)
- **Deployment:** Render (Cloud Hosting)

---

## 🎓 Academic Details

**Semester Project – II | A.Y: 2025-26 Even Sem**  
**Domain:** Web and Application Development

### 👥 Team Members
1. **Rushekesh Ishwar Dusane** (SY-DS-106-241106112)
2. **Bhumika Shivaji Patil** (SY-DS-88-241106098)
3. **Harshada Jagdish More** (SY-DS-93-241106093)
4. **Prachi Anil Mahajan** (SY-DS-82-241106087)

**Guide Name:** Prof. Pathak Yogeshkumar Raghunath sir

### 📅 Project Timeline
| Date | Work / Milestone |
|------|------------------|
| 15 Feb 2026 | Semester project start |
| 22 Feb 2026 | Project topic finalization |
| 28 Feb 2026 | Project Interaction with Guide (Abstract) |
| 3 Mar 2026 | Implementation Progress - 1 (Front-end 1st/2nd page, Admin login page) |
| 9 Mar 2026 | Monitoring - 1 |
| 18 Mar 2026 | Implementation progress - 2 (Invitation) |
| 12 april 2026 | Final Polish, Backend Integration & Cloud Deployment |
| 27 april 2026 | backend development using python and MYSQL |
| 2 May 2026 | Admin module development |
| 10 May 2026 | Testing and debugging |
| 15 May Documentation and report preparation|





---

## 🚀 How to Run Locally

1. Clone the repository:
   ```bash
   git clone https://github.com/Rushekesh01/Wear-Care.git
   cd "Wear & Care"
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory and add your credentials:
   ```env
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   GMAIL_SMTP_USER=your_email@gmail.com
   GMAIL_SMTP_PASSWORD=your_app_password
   ADMIN_EMAIL=admin@gmail.com
   ADMIN_PASSWORD=admin123
   ```

4. Run the application:
   ```bash
   python app.py
   ```
   *The app will be available at `http://127.0.0.1:5000`*
