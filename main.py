from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import typing
import os
import json

app = FastAPI(title="SHAKER BARBER API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BookingCreate(BaseModel):
    client_name: str
    client_phone: str
    service_name: str
    booking_date: str
    booking_time: str
    notes: typing.Optional[str] = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "bookings.json")

# قراءة الحجوزات من الملف الدائم
def load_bookings():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

# حفظ الحجوزات في الملف الدائم
def save_bookings(bookings):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(bookings, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving DB: {e}")

@app.get("/", response_class=HTMLResponse)
def read_root():
    file_path = os.path.join(BASE_DIR, "index.html")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>ملف index.html غير موجود في المستودع</h1>"

@app.get("/admin", response_class=HTMLResponse)
def read_admin():
    file_path = os.path.join(BASE_DIR, "admin.html")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>ملف admin.html غير موجود في المستودع</h1>"

@app.post("/api/bookings", status_code=status.HTTP_201_CREATED)
def create_booking(booking: BookingCreate):
    bookings = load_bookings()
    
    # 1. منع حجزين في نفس الوقت ونفس اليوم
    for b in bookings:
        if b["booking_date"] == booking.booking_date and b["booking_time"] == booking.booking_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"توقيت ({booking.booking_time}) محجوز بالكامل في يوم ({booking.booking_date})، اختر توقيتاً آخر."
            )
            
    # 2. منع التكرار بنفس الاسم بنفس اليوم
    for b in bookings:
        if b["client_name"].strip().lower() == booking.client_name.strip().lower() and b["booking_date"] == booking.booking_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"يوجد حجز مسبق باسم ({booking.client_name}) في يوم ({booking.booking_date})!"
            )
            
    new_booking = booking.dict()
    new_booking["id"] = (max([b["id"] for b in bookings], default=0) + 1)
    new_booking["status"] = "مؤكد"
    
    bookings.append(new_booking)
    save_bookings(bookings)
    
    return {"success": True, "message": "تم تأكيد الحجز وحفظه بنجاح!", "data": new_booking}

@app.get("/api/bookings")
def get_all_bookings():
    return load_bookings()

@app.delete("/api/bookings/{booking_id}")
def delete_booking(booking_id: int):
    bookings = load_bookings()
    bookings = [b for b in bookings if b["id"] != booking_id]
    save_bookings(bookings)
    return {"success": True, "message": "تم حذف الحجز بنجاح"}
