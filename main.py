from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
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

# قراءة إعدادات Supabase بأمان من متغيرات البيئة في Vercel
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://egaruwzfpdadazixfqjb.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class BookingCreate(BaseModel):
    client_name: str
    client_phone: str
    service_name: str
    booking_date: str
    booking_time: str
    notes: typing.Optional[str] = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
    try:
        # جلب الحجوزات لنفس اليوم للتحقق من عدم التضارب والتكرار
        response = supabase.table("bookings").select("*").eq("booking_date", booking.booking_date).execute()
        existing_bookings = response.data

        # 1. منع حجزين في نفس التوقيت
        for b in existing_bookings:
            if b["booking_time"] == booking.booking_time:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"توقيت ({booking.booking_time}) محجوز بالكامل في يوم ({booking.booking_date})، اختر توقيتاً آخر."
                )

        # 2. منع التكرار بنفس الاسم في نفس اليوم
        for b in existing_bookings:
            if b["client_name"].strip().lower() == booking.client_name.strip().lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"يوجد حجز مسبق باسم ({booking.client_name}) في يوم ({booking.booking_date})!"
                )

        # حفظ الحجز في قاعدة بيانات Supabase بشكل دائم
        new_booking_data = booking.dict()
        new_booking_data["status"] = "مؤكد"
        insert_res = supabase.table("bookings").insert(new_booking_data).execute()

        return {"success": True, "message": "تم تأكيد الحجز وحفظه في قاعدة البيانات بنجاح!", "data": insert_res.data}

    except HTTPException as http_e:
        raise http_e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في قاعدة البيانات: {str(e)}")

@app.get("/api/bookings")
def get_all_bookings():
    try:
        response = supabase.table("bookings").select("*").order("id", desc=False).execute()
        return response.data
    except Exception as e:
        return []

@app.delete("/api/bookings/{booking_id}")
def delete_booking(booking_id: int):
    try:
        supabase.table("bookings").delete().eq("id", booking_id).execute()
        return {"success": True, "message": "تم حذف الحجز بنجاح"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="تعذر حذف الحجز")
