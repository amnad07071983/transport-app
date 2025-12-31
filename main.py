import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ================= CONFIG =================
st.set_page_config(page_title="Transportation Invoice", layout="wide")

# --- จุดแก้ไขที่ 1: ลงทะเบียนฟอนต์ภาษาไทย ---
try:
    # พยายามโหลดฟอนต์ THSARABUN BOLD.ttf
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except Exception as e:
    st.error(f"ไม่พบไฟล์ฟอนต์: กรุณาตรวจสอบว่ามีไฟล์ 'THSARABUN BOLD.ttf' ในโฟลเดอร์โปรเจกต์หรือไม่? ({e})")

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INV_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

# ================= GOOGLE SHEET =================
@st.cache_resource
def init_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

try:
    sheet = init_sheet()
    ws_inv = sheet.worksheet(INV_SHEET)
    ws_item = sheet.worksheet(ITEM_SHEET)
    inv_df = pd.DataFrame(ws_inv.get_all_records())
    item_df = pd.DataFrame(ws_item.get_all_records())
except Exception as e:
    st.error(f"การเชื่อมต่อ Google Sheets ผิดพลาด: {e}")
    inv_df = pd.DataFrame()
    item_df = pd.DataFrame()

# ================= SESSION STATE =================
for key, default in [("invoice_items", []), ("customer", ""), ("address", ""), ("shipping", 0.0), ("discount", 0.0)]:
    if key not in st.session_state:
        st.session_state[key] = default

# ================= UTIL =================
def next_invoice_no():
    if inv_df.empty or "invoice_no" not in inv_df.columns:
        return "INV-0001"
    last = inv_df["invoice_no"].iloc[-1]
    try:
        last_num = int(last.split('-')[1])
        return f"INV-{last_num + 1:04d}"
    except:
        return "INV-0001"

# --- จุดแก้ไขที่ 2: เปลี่ยน Font ใน PDF เป็น ThaiFontBold ทุกจุด ---
def create_pdf(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    # หัวข้อใหญ่
    c.setFont("ThaiFontBold", 20)
    c.drawString(2*cm, h-2*cm, "ใบกำกับขนส่งสินค้า (Transportation Invoice)")

    # ข้อมูลใบแจ้งหนี้
    c.setFont("ThaiFontBold", 14)
    c.drawString(2*cm, h-3.2*cm, f"เลขที่ใบแจ้งหนี้ (Invoice No.): {inv['invoice_no']}")
    c.drawString(2*cm, h-4.0*cm, f"วันที่ (Date): {inv['date']}")

    # ข้อมูลลูกค้า
    c.drawString(2*cm, h-5.2*cm, f"ชื่อลูกค้า (Customer): {inv['customer']}")
    # จัดการที่อยู่แบบหลายบรรทัด
    text_obj = c.beginText(2*cm, h-6.0*cm)
    text_obj.setFont("ThaiFontBold", 14)
    text_obj.textLines(f"ที่อยู่ (Address): {inv['address']}")
    c.drawText(text_obj)

    # หัวตารางสินค้า
    y = h - 8.5*cm
    c.setFont("ThaiFontBold", 14)
    c.drawString(2*cm, y, "รายการสินค้า (Product Description)")
    c.drawRightString(12*cm, y, "จำนวน (Qty)")
    c.drawRightString(15.5*cm, y, "ราคา/หน่วย")
    c.drawRightString(19*cm, y, "รวมเงิน (Amount)")
    
    # เส้นใต้หัวตาราง
    c.line(2*cm, y-0.2*cm, 19*cm, y-0.2*cm)
    
    y -= 0.8*cm
    for it in items:
        if y < 3*cm: # ขึ้นหน้าใหม่
            c.showPage()
            c.setFont("ThaiFontBold", 14)
            y = h - 2*cm
        
        c.drawString(2*cm, y, str(it["product"]))
        c.drawRightString(12*cm, y, f"{it['qty']:,}")
        c.drawRightString(15.5*cm, y, f"{float(it['price']):,.2f}")
        c.drawRightString(19*cm, y, f"{float(it['amount']):,.2f}")
        y -= 0.7*cm

    # สรุปยอดเงินท้ายบิล
    c.line(13*cm, y, 19*cm, y)
    y -= 0.8*cm
    c.drawRightString(16*cm, y, "ค่าขนส่ง (Shipping):")
    c.drawRightString(19*cm, y, f"{float(inv['shipping']):,.2f}")
    y -= 0.7*cm
    c.drawRightString(16*cm, y, "ส่วนลด (Discount):")
    c.drawRightString(19*cm, y, f"{float(inv['discount']):,.2f}")
    y -= 0.8*cm
    
    c.setFont("ThaiFontBold", 16)
    c.drawRightString(16*cm, y, "ยอดสุทธิ (TOTAL):")
    c.drawRightString(19*cm, y, f"{float(inv['total']):,.2f} บาท")
    
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= UI =================
st.title("🚚 ระบบใบกำกับขนส่งสินค้า")

# ส่วน Search, Customer, Add Item และ Table (คงไว้ตามเดิมจากโค้ดล่าสุดของคุณ)
# ... (ส่วน UI อื่นๆ เหมือนเดิมทั้งหมด) ...

# ================= (สรุปส่วนบันทึกข้อมูล) =================
# เมื่อกดบันทึก โค้ดจะใช้ next_invoice_no() และสร้าง PDF โดยใช้ฟอนต์ใหม่ที่คุณตั้งค่าไว้

# คุณสามารถก๊อปปี้ส่วน UI ที่เหลือมาวางต่อได้เลยครับ
