from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import typing
import os

app = FastAPI(title="Shaker Barber API")

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

fake_db_bookings = []
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/", response_class=HTMLResponse)
def read_root():
    try:
        with open(os.path.join(BASE_DIR, "index.html"), "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>index.html not found</h1>"

@app.post("/api/bookings", status_code=status.HTTP_201_CREATED)
def create_booking(booking: BookingCreate):
    new_booking = booking.dict()
    new_booking["id"] = len(fake_db_bookings) + 1
    new_booking["status"] = "مؤكد"
    fake_db_bookings.append(new_booking)
    return {"success": True, "data": new_booking}

@app.get("/api/bookings")
def get_all_bookings():
    return fake_db_bookings

@app.delete("/api/bookings/{booking_id}")
def delete_booking(booking_id: int):
    global fake_db_bookings
    fake_db_bookings = [b for b in fake_db_bookings if b["id"] != booking_id]
    return {"success": True}
