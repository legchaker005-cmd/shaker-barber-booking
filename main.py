from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import typing

app = FastAPI(title="نظام حجز مواعيد الحلاقة - شاكر")

# تفعيل CORS للسماح بالاتصالات
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# نموذج بيانات الحجز الوارد من الزبون
class BookingCreate(BaseModel):
    client_name: str
    client_phone: str
    service_name: str
    booking_date: str
    booking_time: str
    notes: typing.Optional[str] = None

# ذاكرة مؤقتة لحفظ الحجوزات (تناسب بيئة Serverless مثل Vercel كبداية)
fake_db_bookings = []

# 1. نقطة النهاية لعرض صفحة الويب للزبائن مباشرة
@app.get("/", response_class=HTMLResponse)
def read_root():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return """
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <title>حلاقة شاكر</title>
            <style>
                body { font-family: Tahoma, sans-serif; text-align: center; padding: 50px; background: #121212; color: #fff; }
                h1 { color: #d4af37; }
            </style>
        </head>
        <body>
            <h1>مرحباً بك في نظام حجز مواعيد الحلاقة</h1>
            <p>يرجى التأكد من رفع ملف index.html في نفس المجلد مع main.py</p>
        </body>
        </html>
        """

# 2. نقطة النهاية لإنشاء حجز جديد
@app.post("/api/bookings", status_code=status.HTTP_201_CREATED)
def create_booking(booking: BookingCreate):
    new_booking = booking.dict()
    new_booking["id"] = len(fake_db_bookings) + 1
    new_booking["status"] = "مؤكد"
    
    fake_db_bookings.append(new_booking)
    
    return {
        "success": true,
        "message": "تم تأكيد حجزك بنجاح!",
        "data": new_booking
    }

# 3. نقطة النهاية لجلب جميع الحجوزات (لوحة التحكم)
@app.get("/api/bookings")
def get_all_bookings():
    return fake_db_bookings
