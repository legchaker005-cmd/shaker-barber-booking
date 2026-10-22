from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import typing
import os

app = FastAPI(title="نظام حجز مواعيد الحلاقة - شاكر")

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

class StatusUpdate(BaseModel):
    status: str

# ذاكرة مؤقتة للحجوزات
fake_db_bookings = []

# الحصول على المسار الصحيح للمجلد الحالي
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. صفحة الحجز للزبائن
@app.get("/", response_class=HTMLResponse)
def read_root():
    file_path = os.path.join(BASE_DIR, "index.html")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>يرجى التأكد من وجود ملف index.html في المستودع</h1>"

# 2. صفحة لوحة التحكم الإدارية لشاكر
@app.get("/admin", response_class=HTMLResponse)
def read_admin():
    file_path = os.path.join(BASE_DIR, "admin.html")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>يرجى التأكد من وجود ملف admin.html في المستودع</h1>"

# 3. إنشاء حجز جديد
@app.post("/api/bookings", status_code=status.HTTP_201_CREATED)
def create_booking(booking: BookingCreate):
    new_booking = booking.dict()
    new_booking["id"] = len(fake_db_bookings) + 1
    new_booking["status"] = "مؤكد"
    fake_db_bookings.append(new_booking)
    return {"success": True, "message": "تم تأكيد الحجز بنجاح!", "data": new_booking}

# 4. جلب جميع الحجوزات
@app.get("/api/bookings")
def get_all_bookings():
    return fake_db_bookings

# 5. تحديث حالة الحجز (مكتمل / ملغي)
@app.patch("/api/bookings/{booking_id}")
def update_booking_status(booking_id: int, update: StatusUpdate):
    for b in fake_db_bookings:
        if b["id"] == booking_id:
            b["status"] = update.status
            return {"success": True, "data": b}
    raise HTTPException(status_code=404, detail="الحجز غير موجود")

# 6. حذف حجز
@app.delete("/api/bookings/{booking_id}")
def delete_booking(booking_id: int):
    global fake_db_bookings
    fake_db_bookings = [b for b in fake_db_bookings if b["id"] != booking_id]
    return {"success": True, "message": "تم حذف الحجز بنجاح"}
