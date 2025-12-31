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

# --- จุดลงทะเบียนฟอนต์ภาษาไทย ---
try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except Exception as e:
    st.error(f"⚠️ ไม่พบไฟล์ฟอนต์: 'THSARABUN BOLD.ttf' ในโฟลเดอร์โปรเจกต์ (Error: {e})")

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INV_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

# ================= GOOGLE SHEET =================
@st.cache_resource
def init_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
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

def create_pdf(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("ThaiFontBold", 20)
    c.drawString(2*cm, h-2*cm, "ใบกำกับขนส่งสินค้า (Transportation Invoice)")
    c.setFont("ThaiFontBold", 14)
    c.drawString(2*cm, h-3.2*cm, f"เลขที่ใบแจ้งหนี้ (Invoice No.): {inv['invoice_no']}")
    c.drawString(2*cm, h-4.0*cm, f"วันที่ (Date): {inv['date']}")
    c.drawString(2*cm, h-5.2*cm, f"ชื่อลูกค้า (Customer): {inv['customer']}")
    text_obj = c.beginText(2*cm, h-6.0*cm)
    text_obj.setFont("ThaiFontBold", 14)
    text_obj.textLines(f"ที่อยู่ (Address): {inv['address']}")
    c.drawText(text_obj)
    y = h - 8.5*cm
    c.setFont("ThaiFontBold", 14)
    c.drawString(2*cm, y, "รายการสินค้า (Product Description)")
    c.drawRightString(12*cm, y, "จำนวน (Qty)")
    c.drawRightString(15.5*cm, y, "ราคา/หน่วย")
    c.drawRightString(19*cm, y, "รวมเงิน (Amount)")
    c.line(2*cm, y-0.2*cm, 19*cm, y-0.2*cm)
    y -= 0.8*cm
    for it in items:
        if y < 3*cm:
            c.showPage()
            c.setFont("ThaiFontBold", 14)
            y = h - 2*cm
        c.drawString(2*cm, y, str(it["product"]))
        c.drawRightString(12*cm, y, f"{it['qty']:,}")
        c.drawRightString(15.5*cm, y, f"{float(it['price']):,.2f}")
        c.drawRightString(19*cm, y, f"{float(it['amount']):,.2f}")
        y -= 0.7*cm
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

# --- ส่วนที่หายไป (เพิ่มกลับมาให้แล้ว) ---
with st.expander("🔍 ค้นหา / ทำซ้ำ Invoice เก่า"):
    selected = st.selectbox("เลือก Invoice", [""] + inv_df["invoice_no"].tolist() if not inv_df.empty else [""])
    if selected:
        inv_data = inv_df[inv_df["invoice_no"] == selected].iloc[0]
        its_data = item_df[item_df["invoice_no"] == selected]
        col_a, col_b = st.columns(2)
        if col_a.button("📄 Duplicate ลงฟอร์ม"):
            st.session_state.customer = inv_data["customer"]
            st.session_state.address = inv_data["address"]
            st.session_state.shipping = float(inv_data["shipping"])
            st.session_state.discount = float(inv_data["discount"])
            st.session_state.invoice_items = its_data.to_dict("records")
            st.rerun()
        if col_b.button("🖨 Export PDF ต้นฉบับ"):
            pdf = create_pdf(inv_data.to_dict(), its_data.to_dict("records"))
            st.download_button("⬇ Download PDF", pdf, f"{selected}.pdf")

st.subheader("🧾 ข้อมูลลูกค้า")
col1, col2 = st.columns(2)
with col1:
    st.session_state.customer = st.text_input("ชื่อลูกค้า", value=st.session_state.customer)
    st.session_state.address = st.text_area("ที่อยู่", value=st.session_state.address)
with col2:
    st.session_state.shipping = st.number_input("🚚 ค่าขนส่ง", value=float(st.session_state.shipping))
    st.session_state.discount = st.number_input("🔻 ส่วนลด", value=float(st.session_state.discount))

st.subheader("📦 เพิ่มสินค้า")
c1, c2, c3 = st.columns([3, 1, 1])
new_name = c1.text_input("ชื่อสินค้า/รายการ")
new_qty = c2.number_input("จำนวน", min_value=1, value=1)
new_price = c3.number_input("ราคา", min_value=0.0, value=0.0)

if st.button("➕ เพิ่มรายการสินค้า"):
    if new_name:
        st.session_state.invoice_items.append({
            "product": new_name, "qty": int(new_qty),
            "price": float(new_price), "amount": float(new_qty * new_price)
        })
        st.rerun()

if st.session_state.invoice_items:
    st.divider()
    df_display = pd.DataFrame(st.session_state.invoice_items)
    st.table(df_display)
    if st.button("🗑 ล้างรายการทั้งหมด"):
        st.session_state.invoice_items = []
        st.rerun()

subtotal = sum(item["amount"] for item in st.session_state.invoice_items)
vat = subtotal * 0.07
total = subtotal + vat + st.session_state.shipping - st.session_state.discount

st.divider()
st.markdown(f"### 💰 ยอดรวมสุทธิ {total:,.2f} บาท")

if st.button("✅ บันทึก Invoice และล้างฟอร์ม", type="primary"):
    if not st.session_state.invoice_items:
        st.error("กรุณาเพิ่มสินค้าก่อนบันทึก")
    else:
        with st.spinner("กำลังบันทึก..."):
            inv_no = next_invoice_no()
            today = datetime.today().strftime("%d/%m/%Y")
            ws_inv.append_row([inv_no, today, st.session_state.customer, st.session_state.address, subtotal, vat, st.session_state.shipping, st.session_state.discount, total, datetime.now().strftime("%H:%M:%S")])
            for it in st.session_state.invoice_items:
                ws_item.append_row([inv_no, it["product"], it["qty"], it["price"], it["amount"]])
            st.success(f"บันทึก {inv_no} สำเร็จ!")
            st.session_state.invoice_items = []; st.session_state.customer = ""; st.session_state.address = ""
            st.cache_resource.clear()
            st.rerun()
