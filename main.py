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
st.set_page_config(page_title="Logistics Invoice (No VAT)", layout="wide")

# ลงทะเบียนฟอนต์ภาษาไทย
try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except:
    st.error("⚠️ ไม่พบไฟล์ THSARABUN BOLD.ttf กรุณาตรวจสอบการอัปโหลดไฟล์ฟอนต์")

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INV_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

# ================= GOOGLE SHEET & CACHING =================
@st.cache_resource
def init_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds).open_by_key(SHEET_ID)

@st.cache_data(ttl=60)
def get_cached_data():
    client = init_sheet()
    try:
        inv = client.worksheet(INV_SHEET).get_all_records()
        item = client.worksheet(ITEM_SHEET).get_all_records()
        return pd.DataFrame(inv), pd.DataFrame(item)
    except:
        return pd.DataFrame(), pd.DataFrame()

# เรียกใช้ข้อมูลและเชื่อมต่อ Worksheet
try:
    client = init_sheet()
    inv_df, item_df = get_cached_data()
    ws_inv = client.worksheet(INV_SHEET)
    ws_item = client.worksheet(ITEM_SHEET)
except Exception as e:
    st.error(f"การเชื่อมต่อผิดพลาด: {e}")
    inv_df, item_df = pd.DataFrame(), pd.DataFrame()

# ================= FUNCTIONS =================
def next_invoice_no(df):
    if df.empty or "invoice_no" not in df.columns:
        return "INV-0001"
    last = df["invoice_no"].iloc[-1]
    try:
        num = int(str(last).split('-')[1])
        return f"INV-{num + 1:04d}"
    except:
        return "INV-0001"

def create_pdf(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    
    # Header
    c.setFont("ThaiFontBold", 20)
    c.drawString(2*cm, h-2*cm, "ใบกำกับขนส่งสินค้า (Transportation Invoice)")
    
    c.setFont("ThaiFontBold", 14)
    c.drawString(2*cm, h-3.2*cm, f"เลขที่ใบแจ้งหนี้ (Invoice No.): {inv['invoice_no']}")
    c.drawString(2*cm, h-4*cm, f"วันที่ (Date): {inv['date']}")
    
    c.drawString(2*cm, h-5.2*cm, f"ชื่อลูกค้า (Customer): {inv['customer']}")
    c.drawString(2*cm, h-6*cm, f"ที่อยู่ (Address): {inv['address']}")

    # Table Header
    y = h - 8*cm
    c.line(2*cm, y, 19*cm, y)
    c.setFont("ThaiFontBold", 12)
    c.drawString(2.2*cm, y-0.6*cm, "รายการสินค้า (Product Description)")
    c.drawRightString(12*cm, y-0.6*cm, "จำนวน (Qty)")
    c.drawRightString(15.5*cm, y-0.6*cm, "ราคา/หน่วย")
    c.drawRightString(19*cm, y-0.6*cm, "รวมเงิน (Amount)")
    c.line(2*cm, y-0.8*cm, 19*cm, y-0.8*cm)

    # Table Body
    y -= 1.5*cm
    for it in items:
        c.drawString(2.2*cm, y, str(it["product"]))
        c.drawRightString(12*cm, y, f"{it['qty']:,}")
        c.drawRightString(15.5*cm, y, f"{it['price']:,.2f}")
        c.drawRightString(19*cm, y, f"{it['amount']:,.2f}")
        y -= 0.8*cm

    # Summary Section (ชิดขวาตามรูปตัวอย่าง)
    y_sum = y - 1*cm
    c.line(13*cm, y_sum+0.8*cm, 19*cm, y_sum+0.8*cm)
    c.setFont("ThaiFontBold", 13)
    c.drawString(13.5*cm, y_sum, "ค่าขนส่ง (Shipping):")
    c.drawRightString(19*cm, y_sum, f"{inv['shipping']:,.2f}")
    
    c.drawString(13.5*cm, y_sum-0.8*cm, "ส่วนลด (Discount):")
    c.drawRightString(19*cm, y_sum-0.8*cm, f"{inv['discount']:,.2f}")
    
    c.setFont("ThaiFontBold", 16)
    c.drawString(13.5*cm, y_sum-1.8*cm, "ยอดสุทธิ (TOTAL):")
    c.drawRightString(19*cm, y_sum-1.8*cm, f"{inv['total']:,.2f} บาท")
    
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= SESSION STATE =================
if "invoice_items" not in st.session_state:
    st.session_state.invoice_items = []

# ================= UI =================
st.title("🚚 Transportation Invoice (No VAT)")

col1, col2 = st.columns(2)
with col1:
    customer = st.text_input("ชื่อลูกค้า", value=st.session_state.get('customer', ''), placeholder="นายอำนาจ")
    address = st.text_area("ที่อยู่", value=st.session_state.get('address', ''), placeholder="125 หมู่ 6...")
with col2:
    shipping = st.number_input("ค่าขนส่ง (Shipping)", min_value=0.0, step=100.0)
    discount = st.number_input("ส่วนลด (Discount)", min_value=0.0, step=100.0)

st.divider()

# ส่วนเพิ่มสินค้า
st.subheader("📦 เพิ่มรายการสินค้า")
c_i1, c_i2, c_i3 = st.columns([3,1,1])
p_name = c_i1.text_input("รายการสินค้า", key="input_p_name")
p_qty = c_i2.number_input("จำนวน", min_value=1, value=1000)
p_price = c_i3.number_input("ราคาต่อหน่วย", min_value=0.0, value=35.0)

if st.button("➕ เพิ่มรายการ"):
    if p_name:
        st.session_state.invoice_items.append({
            "product": p_name, "qty": p_qty, "price": p_price, "amount": p_qty * p_price
        })
        st.rerun()

# แสดงรายการในตะกร้า
if st.session_state.invoice_items:
    st.write("---")
    for i, item in enumerate(st.session_state.invoice_items):
        cols = st.columns([4, 1])
        cols[0].info(f"{i+1}. {item['product']} | {item['qty']:,} x {item['price']} = {item['amount']:,.2f}")
        if cols[1].button("🗑️", key=f"btn_del_{i}"):
            st.session_state.invoice_items.pop(i)
            st.rerun()

    subtotal = sum(i["amount"] for i in st.session_state.invoice_items)
    grand_total = subtotal + shipping - discount
    st.write(f"## ยอดรวมสุทธิ: {grand_total:,.2f} บาท")

    if st.button("✅ บันทึกข้อมูลและรับไฟล์ PDF", type="primary"):
        with st.spinner("กำลังประมวลผล..."):
            new_no = next_invoice_no(inv_df)
            date_str = datetime.now().strftime("%d/%m/%Y")
            
            # บันทึก Header (ตัดคอลัมน์ VAT ออก หรือใส่เป็น 0)
            ws_inv.append_row([
                new_no, date_str, customer, address, 
                subtotal, 0, shipping, discount, grand_total, 
                datetime.now().strftime("%H:%M:%S")
            ])
            
            # บันทึก Items
            for it in st.session_state.invoice_items:
                ws_item.append_row([new_no, it["product"], it["qty"], it["price"], it["amount"]])
            
            # สร้าง PDF
            inv_data = {
                "invoice_no": new_no, "date": date_str, "customer": customer,
                "address": address, "shipping": shipping, "discount": discount, "total": grand_total
            }
            pdf_output = create_pdf(inv_data, st.session_state.invoice_items)
            
            st.success(f"บันทึกเลขที่ {new_no} สำเร็จ!")
            st.download_button("📥 ดาวน์โหลดใบกำกับสินค้า (PDF)", pdf_output, f"{new_no}.pdf", "application/pdf")
            
            # ล้างค่าในหน้าจอ
            st.session_state.invoice_items = []
            st.cache_data.clear()
