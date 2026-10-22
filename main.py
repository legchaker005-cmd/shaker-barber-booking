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

# Helper function to check admin PIN
def verify_admin_pin(x_admin_pin: str = Header(None)):
    if x_admin_pin != "1234":
        raise HTTPException(status_code=401, detail="رمز PIN غير صحيح!")
    return True

# --- PUBLIC CLIENT ENDPOINTS ---

@app.get("/api/availability/{booking_date}")
def get_availability(booking_date: str):
    # 1. Check if date is blocked
    blocked = supabase.table("blocked_days").select("*").eq("blocked_date", booking_date).execute()
    if blocked.data:
        return {
            "is_blocked": True,
            "blocked_reason": blocked.data[0].get("reason", "عطلة"),
            "booked_times": []
        }
    
    # 2. Get booked slots
    bookings = supabase.table("bookings").select("booking_time").eq("booking_date", booking_date).execute()
    booked_times = [b["booking_time"] for b in bookings.data] if bookings.data else []
    
    return {
        "is_blocked": False,
        "blocked_reason": None,
        "booked_times": booked_times
    }

@app.post("/api/bookings")
def create_booking(booking: BookingRequest):
    # Check if date is blocked
    blocked = supabase.table("blocked_days").select("*").eq("blocked_date", booking.booking_date).execute()
    if blocked.data:
        raise HTTPException(status_code=400, detail="عذراً، هذا اليوم مغلق ولا يمكن الحجز فيه.")

    # Check if time slot is taken
    existing = supabase.table("bookings").select("*")\
        .eq("booking_date", booking.booking_date)\
        .eq("booking_time", booking.booking_time).execute()
    
    if existing.data:
        raise HTTPException(status_code=400, detail="عذراً، هذا الموعد تم حجزه للتو!")

    # Insert Booking
    res = supabase.table("bookings").insert(booking.dict()).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="حدث خطأ أثناء حفظ الحجز.")
        
    return {"message": "تم تأكيد حجزك بنجاح! ننتظرك في الموعد."}

# --- ADMIN ENDPOINTS ---

@app.get("/api/admin/stats")
def get_admin_stats(authorized: bool = Depends(verify_admin_pin)):
    bookings_res = supabase.table("bookings").select("*").execute()
    blocked_res = supabase.table("blocked_days").select("*").execute()
    
    all_bookings = bookings_res.data or []
    
    # Prices map for revenue calculation
    price_map = {
        "تدرج احترافي Fade": 350,
        "قص شعر عصري": 250,
        "تحديد وحلاقة اللحية": 150
    }
    
    total_revenue = sum(price_map.get(b.get("service_name"), 0) for b in all_bookings)
    
    return {
        "total_bookings": len(all_bookings),
        "total_revenue": total_revenue,
        "total_blocked_days": len(blocked_res.data or [])
    }

@app.get("/api/admin/bookings")
def get_admin_bookings(authorized: bool = Depends(verify_admin_pin)):
    res = supabase.table("bookings").select("*").order("booking_date", desc=False).order("booking_time", desc=False).execute()
    return res.data or []

@app.post("/api/admin/manual-booking")
def create_manual_booking(booking: BookingRequest, authorized: bool = Depends(verify_admin_pin)):
    # Direct insert for admin
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

# Static & HTML Routes
@app.get("/admin")
def serve_admin_page():
    return FileResponse("admin.html")

@app.get("/")
def serve_index_page():
    return FileResponse("index.html")

app.mount("/", StaticFiles(directory=".", html=True), name="static")
