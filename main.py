from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import typing
import os

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

fake_db_bookings = []
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/", response_class=HTMLResponse)
def read_root():
    file_path = os.path.join(BASE_DIR, "index.html")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>ملف index.html غير موجود في المستودع</h1>"

@app.post("/api/bookings", status_code=status.HTTP_201_CREATED)
def create_booking(booking: BookingCreate):
    # 1. منع حجزين في نفس الوقت ونفس اليوم
    for b in fake_db_bookings:
        if b["booking_date"] == booking.booking_date and b["booking_time"] == booking.booking_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"توقيت ({booking.booking_time}) محجوز بالكامل في يوم ({booking.booking_date})، اختر توقيتاً آخر."
            )
            
    # 2. منع التكرار بنفس الاسم بنفس اليوم
    for b in fake_db_bookings:
        if b["client_name"].strip().lower() == booking.client_name.strip().lower() and b["booking_date"] == booking.booking_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"يوجد حجز مسبق باسم ({booking.client_name}) في يوم ({booking.booking_date})!"
            )
            
    new_booking = booking.dict()
    new_booking["id"] = len(fake_db_bookings) + 1
    new_booking["status"] = "مؤكد"
    fake_db_bookings.append(new_booking)
    return {"success": True, "message": "تم تأكيد الحجز بنجاح!", "data": new_booking}

@app.get("/api/bookings")
def get_all_bookings():
    return fake_db_bookings
