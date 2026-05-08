import os
import random
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Get a valid user
res = supabase.table("users").select("id, name").limit(1).execute()
if not res.data:
    print("No users found. Please create at least one user first.")
    exit(1)

user = res.data[0]
user_id = user["id"]
user_name = user["name"]

cloth_types = ["T-Shirt", "Jeans", "Jacket", "Winter Sweater", "Dress", "Formal Shirt", "Blanket", "Kids Wear"]
sizes = ["S", "M", "L", "XL", "Kids", "Free Size"]
conditions = ["New with tags", "Like New", "Good", "Fair"]
addresses = ["Mumbai, Maharashtra", "Pune, Maharashtra", "Delhi, NCR", "Bangalore, Karnataka", "Chennai, TN", "Kolkata, WB", "Hyderabad, TS"]

# Try to use placeholder images so it doesn't look completely empty
placeholder_images = [
    "1775121754_pant.webp",
    "1775128983_Clg_id_.jpg" # Just using what might be there, or empty
]

dummy_donations = []
for i in range(15):
    is_free = random.choice([True, True, True, False])
    price = 0 if is_free else random.randint(150, 1500)
    
    donation = {
        "user_id": user_id,
        "user_name": user_name,
        "cloth_type": random.choice(cloth_types),
        "size": random.choice(sizes),
        "condition_status": random.choice(conditions),
        "address": random.choice(addresses),
        "image": "", 
        "status": random.choice(["Pending", "Approved", "Approved", "Approved"]),
        "is_free": is_free,
        "price": price,
        "phone": "9876543210"
    }
    dummy_donations.append(donation)

try:
    supabase.table("donations").insert(dummy_donations).execute()
    print("Successfully added 15 dummy donations!")
except Exception as e:
    print("Error inserting data:", e)
