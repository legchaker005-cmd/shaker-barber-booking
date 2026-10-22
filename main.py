from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from supabase import create_client, Client
import os

app = FastAPI()

# Supabase Initialization
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-supabase-url.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-anon-key")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Data Models
class BookingRequest(BaseModel):
    client_name: str
    client_phone: str
    service_name: str
    booking_date: str
    booking_time: str
    notes: Optional[str] = ""

class BlockDayRequest(BaseModel):
    blocked_date: str
    reason: Optional[str] = "عطلة"

class AddPointRequest(BaseModel):
    client_phone: str

# Helper function to check admin PIN
def verify_admin_pin(x_admin_pin: str = Header(None)):
    if x_admin_pin != "1234":
        raise HTTPException(status_code=401, detail="رمز PIN غير صحيح!")
    return True

# --- PUBLIC CLIENT ENDPOINTS ---

@app.get("/api/availability/{booking_date}")
def get_availability(booking_date: str):
    blocked = supabase.table("blocked_days").select("*").eq("blocked_date", booking_date).execute()
    if blocked.data:
        return {
            "is_blocked": True,
            "blocked_reason": blocked.data[0].get("reason", "عطلة"),
            "booked_times": []
        }
    
    bookings = supabase.table("bookings").select("booking_time").eq("booking_date", booking_date).execute()
    booked_times = [b["booking_time"] for b in bookings.data] if bookings.data else []
    
    return {
        "is_blocked": False,
        "blocked_reason": None,
        "booked_times": booked_times
    }

@app.post("/api/bookings")
def create_booking(booking: BookingRequest):
    blocked = supabase.table("blocked_days").select("*").eq("blocked_date", booking.booking_date).execute()
    if blocked.data:
        raise HTTPException(status_code=400, detail="عذراً، هذا اليوم مغلق ولا يمكن الحجز فيه.")

    existing = supabase.table("bookings").select("*")\
        .eq("booking_date", booking.booking_date)\
        .eq("booking_time", booking.booking_time).execute()
    
    if existing.data:
        raise HTTPException(status_code=400, detail="عذراً، هذا الموعد تم حجزه للتو!")

    res = supabase.table("bookings").insert(booking.dict()).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="حدث خطأ أثناء حفظ الحجز.")
        
    # Ensure client has a loyalty card entry
    card = supabase.table("loyalty_cards").select("*").eq("client_phone", booking.client_phone).execute()
    if not card.data:
        supabase.table("loyalty_cards").insert({
            "client_phone": booking.client_phone,
            "client_name": booking.client_name,
            "points": 0,
            "total_rewards": 0
        }).execute()

    return {"message": "تم تأكيد حجزك بنجاح! ننتظرك في الموعد."}

# --- LOYALTY PUBLIC ENDPOINT ---

@app.get("/api/loyalty/{client_phone}")
def get_loyalty_card(client_phone: str):
    res = supabase.table("loyalty_cards").select("*").eq("client_phone", client_phone).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="بطاقة الولاء غير موجودة لهذا الرقم!")
    return res.data[0]

# --- ADMIN ENDPOINTS ---

@app.get("/api/admin/stats")
def get_admin_stats(authorized: bool = Depends(verify_admin_pin)):
    bookings_res = supabase.table("bookings").select("*").execute()
    blocked_res = supabase.table("blocked_days").select("*").execute()
    cards_res = supabase.table("loyalty_cards").select("*").execute()
    
    all_bookings = bookings_res.data or []
    
    price_map = {
        "تدرج احترافي Fade": 350,
        "قص شعر عصري": 250,
        "تحديد وحلاقة اللحية": 150
    }
    
    total_revenue = sum(price_map.get(b.get("service_name"), 0) for b in all_bookings)
    
    return {
        "total_bookings": len(all_bookings),
        "total_revenue": total_revenue,
        "total_blocked_days": len(blocked_res.data or []),
        "total_clients": len(cards_res.data or [])
    }

@app.get("/api/admin/bookings")
def get_admin_bookings(authorized: bool = Depends(verify_admin_pin)):
    res = supabase.table("bookings").select("*").order("booking_date", desc=False).order("booking_time", desc=False).execute()
    return res.data or []

@app.post("/api/admin/manual-booking")
def create_manual_booking(booking: BookingRequest, authorized: bool = Depends(verify_admin_pin)):
    res = supabase.table("bookings").insert(booking.dict()).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="فشل إضافة الحجز اليدوي.")
    return {"message": "تم إضافة الحجز اليدوي بنجاح!"}

@app.delete("/api/admin/bookings/{booking_id}")
def delete_booking(booking_id: int, authorized: bool = Depends(verify_admin_pin)):
    res = supabase.table("bookings").delete().eq("id", booking_id).execute()
    return {"message": "تم إلغاء الحجز بنجاح."}

@app.get("/api/admin/blocked-days")
def get_blocked_days(authorized: bool = Depends(verify_admin_pin)):
    res = supabase.table("blocked_days").select("*").order("blocked_date", desc=False).execute()
    return res.data or []

@app.post("/api/admin/block-day")
def block_day(data: BlockDayRequest, authorized: bool = Depends(verify_admin_pin)):
    res = supabase.table("blocked_days").insert(data.dict()).execute()
    return {"message": "تم إغلاق اليوم بنجاح."}

@app.delete("/api/admin/unblock-day/{blocked_id}")
def unblock_day(blocked_id: int, authorized: bool = Depends(verify_admin_pin)):
    res = supabase.table("blocked_days").delete().eq("id", blocked_id).execute()
    return {"message": "تم إعادة فتح اليوم بنجاح."}

# Admin Loyalty Control: Add Point via QR Scan or Phone
@app.post("/api/admin/loyalty/add-point")
def add_loyalty_point(data: AddPointRequest, authorized: bool = Depends(verify_admin_pin)):
    res = supabase.table("loyalty_cards").select("*").eq("client_phone", data.client_phone).execute()
    
    if not res.data:
        # Create new card if not existing
        card_data = {"client_phone": data.client_phone, "client_name": "زبون صالون", "points": 1, "total_rewards": 0}
        supabase.table("loyalty_cards").insert(card_data).execute()
        return {"message": "تم إنشاء بطاقة جديدة وإضافة النقطة الأولى!", "points": 1, "reward": False}
    
    card = res.data[0]
    new_points = card["points"] + 1
    total_rewards = card.get("total_rewards", 0)
    reward_unlocked = False

    if new_points >= 5:
        new_points = 0
        total_rewards += 1
        reward_unlocked = True

    supabase.table("loyalty_cards").update({
        "points": new_points,
        "total_rewards": total_rewards
    }).eq("client_phone", data.client_phone).execute()

    msg = "🎉 مبروك! الزبون أتم 5 نقاط وحصل على حلاقة مجانية!" if reward_unlocked else f"تم إضافة نقطة بنجاح! إجمالي النقاط: {new_points}/5"
    return {"message": msg, "points": new_points, "reward": reward_unlocked}

# Routes
@app.get("/loyalty")
def serve_loyalty_page():
    return FileResponse("loyalty.html")

@app.get("/admin")
def serve_admin_page():
    return FileResponse("admin.html")

@app.get("/")
def serve_index_page():
    return FileResponse("index.html")

app.mount("/", StaticFiles(directory=".", html=True), name="static")
