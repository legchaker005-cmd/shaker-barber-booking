from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from supabase import create_client, Client
from datetime import datetime
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

class BlockSlotRequest(BaseModel):
    blocked_date: str
    blocked_time: str
    reason: Optional[str] = "استراحة"

class AddPointRequest(BaseModel):
    client_phone: str

class UpdateLoyaltyRequest(BaseModel):
    points: int
    total_rewards: Optional[int] = 0

class WorkingHourRequest(BaseModel):
    day_of_week: str
    start_time_1: str
    end_time_1: str
    has_break: bool = False
    start_time_2: Optional[str] = ""
    end_time_2: Optional[str] = ""

# Admin PIN Verification (4628)
def verify_admin_pin(x_admin_pin: str = Header(None)):
    pin = str(x_admin_pin).strip() if x_admin_pin else ""
    if pin != "6482":
        raise HTTPException(status_code=401, detail="رمز PIN غير صحيح!")
    return True

def generate_time_slots(start_str: str, end_str: str, step_minutes: int = 70): # <--- غيرناها إلى 70 دقيقة
    if not start_str or not end_str:
        return []
    try:
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        curr = sh * 60 + sm
        end = eh * 60 + em
        slots = []
        while curr <= end:
            h = curr // 60
            m = curr % 60
            slots.append(f"{h:02d}:{m:02d}")
            curr += step_minutes
        return slots
    except Exception:
        return []

def get_slots_for_date(booking_date: str):
    dt = datetime.strptime(booking_date, "%Y-%m-%d")
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_key = day_names[dt.weekday()]
    is_weekend = dt.weekday() in [5, 6]
    group_key = "weekend" if is_weekend else "weekday"

    wh_res = supabase.table("working_hours").select("*").execute()
    wh_map = {item["day_of_week"]: item for item in (wh_res.data or [])}

    config = wh_map.get(day_key) or wh_map.get(group_key)
    if config:
        slots = generate_time_slots(config.get("start_time_1", ""), config.get("end_time_1", ""))
        if config.get("has_break") and config.get("start_time_2") and config.get("end_time_2"):
            slots += generate_time_slots(config.get("start_time_2"), config.get("end_time_2"))
        return slots

    # Default fallback schedule
    if is_weekend:
        return ["11:00", "11:55", "12:50", "13:45", "14:40", "17:00", "17:55", "18:50", "19:45", "20:40", "21:35", "22:30"]
    return ["18:00", "18:55", "19:50", "20:45", "21:40", "22:35"]

# --- PUBLIC ENDPOINTS ---

@app.get("/api/availability/{booking_date}")
def get_availability(booking_date: str):
    available_slots = get_slots_for_date(booking_date)

    blocked = supabase.table("blocked_days").select("*").eq("blocked_date", booking_date).execute()
    if blocked.data:
        return {
            "is_blocked": True,
            "blocked_reason": blocked.data[0].get("reason", "عطلة"),
            "available_slots": available_slots,
            "booked_times": [],
            "blocked_slots": []
        }
    
    bookings = supabase.table("bookings").select("booking_time").eq("booking_date", booking_date).execute()
    booked_times = [b["booking_time"] for b in bookings.data] if bookings.data else []
    
    slots = supabase.table("blocked_slots").select("blocked_time").eq("blocked_date", booking_date).execute()
    blocked_slots = [s["blocked_time"] for s in slots.data] if slots.data else []
    
    return {
        "is_blocked": False,
        "blocked_reason": None,
        "available_slots": available_slots,
        "booked_times": booked_times,
        "blocked_slots": blocked_slots
    }

@app.post("/api/bookings")
def create_booking(booking: BookingRequest):
    blocked = supabase.table("blocked_days").select("*").eq("blocked_date", booking.booking_date).execute()
    if blocked.data:
        raise HTTPException(status_code=400, detail="عذراً، هذا اليوم مغلق ولا يمكن الحجز فيه.")

    slot_blocked = supabase.table("blocked_slots").select("*")\
        .eq("blocked_date", booking.booking_date)\
        .eq("booking_time", booking.booking_time).execute()
    if slot_blocked.data:
        raise HTTPException(status_code=400, detail="عذراً، هذه الساعة غير متاحة للحجز حالياً.")

    existing = supabase.table("bookings").select("*")\
        .eq("booking_date", booking.booking_date)\
        .eq("booking_time", booking.booking_time).execute()
    
    if existing.data:
        raise HTTPException(status_code=400, detail="عذراً، هذا الموعد تم حجزه للتو!")

    res = supabase.table("bookings").insert(booking.dict()).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="حدث خطأ أثناء حفظ الحجز.")
        
    card = supabase.table("loyalty_cards").select("*").eq("client_phone", booking.client_phone).execute()
    if not card.data:
        supabase.table("loyalty_cards").insert({
            "client_phone": booking.client_phone,
            "client_name": booking.client_name,
            "points": 0,
            "total_rewards": 0
        }).execute()

    return {"message": "تم تأكيد حجزك بنجاح!"}

@app.get("/api/loyalty/{client_phone}")
def get_loyalty_card(client_phone: str):
    res = supabase.table("loyalty_cards").select("*").eq("client_phone", client_phone).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="بطاقة الولاء غير موجودة لهذا الرقم!")
    return res.data[0]

# --- ADMIN ENDPOINTS ---

@app.get("/api/admin/working-hours")
def get_working_hours(authorized: bool = Depends(verify_admin_pin)):
    res = supabase.table("working_hours").select("*").execute()
    return res.data or []

@app.post("/api/admin/working-hours")
def update_working_hours(data: WorkingHourRequest, authorized: bool = Depends(verify_admin_pin)):
    existing = supabase.table("working_hours").select("*").eq("day_of_week", data.day_of_week).execute()
    if existing.data:
        supabase.table("working_hours").update(data.dict()).eq("day_of_week", data.day_of_week).execute()
    else:
        supabase.table("working_hours").insert(data.dict()).execute()
    return {"message": "تم تحديث ساعات العمل بنجاح!"}

@app.delete("/api/admin/working-hours/{day_of_week}")
def reset_working_hours(day_of_week: str, authorized: bool = Depends(verify_admin_pin)):
    supabase.table("working_hours").delete().eq("day_of_week", day_of_week).execute()
    return {"message": "تم إعادة ضبط الساعات للوضع الافتراضي."}

@app.get("/api/admin/stats")
def get_admin_stats(authorized: bool = Depends(verify_admin_pin)):
    bookings_res = supabase.table("bookings").select("*").execute()
    blocked_res = supabase.table("blocked_days").select("*").execute()
    cards_res = supabase.table("loyalty_cards").select("*").execute()
    
    all_bookings = bookings_res.data or []
    price_map = {
        "حلاقة شعر ولحية": 350,
        "حلاقة شعر": 250,
        "حلاقة لحية": 150,
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
    return {"message": "تم إضافة الحجز اليدوي بنجاح!"}

@app.delete("/api/admin/bookings/{booking_id}")
def delete_booking(booking_id: int, authorized: bool = Depends(verify_admin_pin)):
    supabase.table("bookings").delete().eq("id", booking_id).execute()
    return {"message": "تم إلغاء الحجز بنجاح."}

@app.get("/api/admin/blocked-days")
def get_blocked_days(authorized: bool = Depends(verify_admin_pin)):
    res = supabase.table("blocked_days").select("*").order("blocked_date", desc=False).execute()
    return res.data or []

@app.post("/api/admin/block-day")
def block_day(data: BlockDayRequest, authorized: bool = Depends(verify_admin_pin)):
    supabase.table("blocked_days").insert(data.dict()).execute()
    return {"message": "تم إغلاق اليوم بنجاح."}

@app.delete("/api/admin/unblock-day/{blocked_id}")
def unblock_day(blocked_id: int, authorized: bool = Depends(verify_admin_pin)):
    supabase.table("blocked_days").delete().eq("id", blocked_id).execute()
    return {"message": "تم إعادة فتح اليوم بنجاح."}

@app.post("/api/admin/toggle-slot-block")
def toggle_slot_block(data: BlockSlotRequest, authorized: bool = Depends(verify_admin_pin)):
    existing = supabase.table("blocked_slots").select("*")\
        .eq("blocked_date", data.blocked_date)\
        .eq("blocked_time", data.blocked_time).execute()
    
    if existing.data:
        supabase.table("blocked_slots").delete()\
            .eq("blocked_date", data.blocked_date)\
            .eq("blocked_time", data.blocked_time).execute()
        return {"message": f"تم فتح الساعة {data.blocked_time} بنجاح!", "blocked": False}
    else:
        supabase.table("blocked_slots").insert(data.dict()).execute()
        return {"message": f"تم إغلاق الساعة {data.blocked_time} بنجاح!", "blocked": True}

@app.get("/api/admin/loyalty/cards")
def get_all_loyalty_cards(authorized: bool = Depends(verify_admin_pin)):
    res = supabase.table("loyalty_cards").select("*").order("id", desc=True).execute()
    return res.data or []

@app.put("/api/admin/loyalty/cards/{card_id}")
def update_loyalty_card(card_id: int, data: UpdateLoyaltyRequest, authorized: bool = Depends(verify_admin_pin)):
    supabase.table("loyalty_cards").update({"points": data.points, "total_rewards": data.total_rewards}).eq("id", card_id).execute()
    return {"message": "تم التحديث بنجاح!"}

@app.delete("/api/admin/loyalty/cards/{card_id}")
def delete_loyalty_card(card_id: int, authorized: bool = Depends(verify_admin_pin)):
    supabase.table("loyalty_cards").delete().eq("id", card_id).execute()
    return {"message": "تم الحذف بنجاح."}

@app.post("/api/admin/loyalty/add-point")
def add_loyalty_point(data: AddPointRequest, authorized: bool = Depends(verify_admin_pin)):
    res = supabase.table("loyalty_cards").select("*").eq("client_phone", data.client_phone).execute()
    if not res.data:
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

    supabase.table("loyalty_cards").update({"points": new_points, "total_rewards": total_rewards}).eq("client_phone", data.client_phone).execute()
    msg = "🎉 مبروك! الزبون أتم 5 حلاقات والحلاقة 6 مجانية!" if reward_unlocked else f"تم إضافة نقطة بنجاح! النقاط: {new_points}/5"
    return {"message": msg, "points": new_points, "reward": reward_unlocked}

# Serve HTML Files
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
