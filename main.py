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

# แนะนำ: ให้หาไฟล์ฟอนต์ภาษาไทย (เช่น THSarabunNew.ttf) มาใส่ในโฟลเดอร์เดียวกับโปรเจกต์
# pdfmetrics.registerFont(TTFont('ThaiFont', 'THSarabunNew.ttf')) 

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
    # ตรวจสอบว่ามี st.secrets["gcp_service_account"] ใน Streamlit Cloud หรือไม่
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

try:
    sheet = init_sheet()
    ws_inv = sheet.worksheet(INV_SHEET)
    ws_item = sheet.worksheet(ITEM_SHEET)
    
    # ดึงข้อมูลมาเป็น DataFrame
    inv_df = pd.DataFrame(ws_inv.get_all_records())
    item_df = pd.DataFrame(ws_item.get_all_records())
except Exception as e:
    st.error(f"การเชื่อมต่อ Google Sheets ผิดพลาด: {e}")
    inv_df = pd.DataFrame()
    item_df = pd.DataFrame()

# ================= SESSION STATE =================
if "invoice_items" not in st.session_state:
    st.session_state.invoice_items = []
if "customer" not in st.session_state:
    st.session_state.customer = ""
if "address" not in st.session_state:
    st.session_state.address = ""
if "shipping" not in st.session_state:
    st.session_state.shipping = 0.0
if "discount" not in st.session_state:
    st.session_state.discount = 0.0

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

    # หมายเหตุ: หากจะใช้ภาษาไทย ต้องใช้ c.setFont("ThaiFont", 14)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, h-2*cm, "TRANSPORTATION INVOICE")

    c.setFont("Helvetica", 10)
    c.drawString(2*cm, h-3*cm, f"Invoice: {inv['invoice_no']}")
    c.drawString(2*cm, h-3.7*cm, f"Date: {inv['date']}")

    c.drawString(2*cm, h-5*cm, f"Customer: {inv['customer']}")
    c.drawString(2*cm, h-5.7*cm, f"Address: {inv['address']}")

    y = h - 7*cm
    c.drawString(2*cm, y, "Product")
    c.drawRightString(12*cm, y, "Qty")
    c.drawRightString(15*cm, y, "Price")
    c.drawRightString(19*cm, y, "Amount")
    
    y -= 0.8*cm
    for it in items:
        if y < 2*cm: # ขึ้นหน้าใหม่ถ้าพื้นที่ไม่พอ
            c.showPage()
            y = h - 2*cm
        c.drawString(2*cm, y, str(it["product"]))
        c.drawRightString(12*cm, y, str(it["qty"]))
        c.drawRightString(15*cm, y, f"{float(it['price']):,.2f}")
        c.drawRightString(19*cm, y, f"{float(it['amount']):,.2f}")
        y -= 0.6*cm

    c.drawRightString(19*cm, y-1*cm, f"TOTAL: {inv['total']:,.2f} THB")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= UI =================
st.title("🚚 ระบบใบกำกับขนส่งสินค้า")

# ===== SEARCH / DUPLICATE =====
with st.expander("🔍 ค้นหา / ทำซ้ำ Invoice เก่า"):
    selected = st.selectbox(
        "เลือก Invoice",
        [""] + inv_df["invoice_no"].tolist() if not inv_df.empty else [""]
    )

    if selected:
        inv_data = inv_df[inv_df["invoice_no"] == selected].iloc[0]
        its_data = item_df[item_df["invoice_no"] == selected]

        col_a, col_b = st.columns(2)
        if col_a.button("📄 Duplicate (คัดลอกข้อมูลลงฟอร์ม)"):
            st.session_state.customer = inv_data["customer"]
            st.session_state.address = inv_data["address"]
            st.session_state.shipping = float(inv_data["shipping"])
            st.session_state.discount = float(inv_data["discount"])
            st.session_state.invoice_items = its_data.to_dict("records")
            st.success("โหลดข้อมูลลงฟอร์มแล้ว")
            st.rerun()

        if col_b.button("🖨 Export PDF จากต้นฉบับ"):
            pdf = create_pdf(inv_data.to_dict(), its_data.to_dict("records"))
            st.download_button("⬇ Download PDF", pdf, f"{selected}.pdf", mime="application/pdf")

# ===== CUSTOMER =====
st.subheader("🧾 ข้อมูลลูกค้า")
col1, col2 = st.columns(2)
with col1:
    st.session_state.customer = st.text_input("ชื่อลูกค้า", value=st.session_state.customer)
    st.session_state.address = st.text_area("ที่อยู่", value=st.session_state.address)
with col2:
    st.session_state.shipping = st.number_input("🚚 ค่าขนส่ง", value=float(st.session_state.shipping))
    st.session_state.discount = st.number_input("🔻 ส่วนลด", value=float(st.session_state.discount))

# ===== ADD ITEM =====
st.subheader("📦 เพิ่มสินค้า")
c1, c2, c3 = st.columns([3, 1, 1])
new_name = c1.text_input("ชื่อสินค้า/รายการ")
new_qty = c2.number_input("จำนวน", min_value=1, value=1)
new_price = c3.number_input("ราคาสินค้า", min_value=0.0, value=0.0, step=100.0)

if st.button("➕ เพิ่มรายการสินค้า"):
    if new_name:
        st.session_state.invoice_items.append({
            "product": new_name,
            "qty": int(new_qty),
            "price": float(new_price),
            "amount": float(new_qty * new_price)
        })
        st.rerun()
    else:
        st.warning("กรุณากรอกชื่อสินค้า")

# ===== TABLE =====
if st.session_state.invoice_items:
    st.divider()
    df_display = pd.DataFrame(st.session_state.invoice_items)
    st.table(df_display) # ใช้ st.table เพื่อความสวยงามในบิล

    idx = st.selectbox("แก้ไข/ลบ รายการที่:", range(len(st.session_state.invoice_items)))
    col_edit1, col_edit2, col_del = st.columns(3)
    
    with col_del:
        if st.button("🗑 ลบรายการนี้"):
            st.session_state.invoice_items.pop(idx)
            st.rerun()

# ===== TOTAL CALCULATION =====
subtotal = sum(item["amount"] for item in st.session_state.invoice_items)
vat = subtotal * 0.07
total = subtotal + vat + st.session_state.shipping - st.session_state.discount

st.divider()
st.markdown(f"### 💰 สรุปยอดเงิน")
c_total1, c_total2 = st.columns(2)
c_total1.write(f"ยอดรวมสินค้า: {subtotal:,.2f} บาท")
c_total1.write(f"ภาษี (7%): {vat:,.2f} บาท")
c_total2.markdown(f"## **รวมทั้งสิ้น {total:,.2f} บาท**")

# ===== SAVE =====
if st.button("✅ บันทึก Invoice และล้างฟอร์ม", type="primary"):
    if not st.session_state.invoice_items:
        st.error("กรุณาเพิ่มสินค้าอย่างน้อย 1 รายการ")
    else:
        with st.spinner("กำลังบันทึกข้อมูล..."):
            inv_no = next_invoice_no()
            today = datetime.today().strftime("%d/%m/%Y")
            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            # บันทึกหัวบิล
            ws_inv.append_row([
                inv_no, today,
                st.session_state.customer,
                st.session_state.address,
                subtotal, vat,
                st.session_state.shipping,
                st.session_state.discount,
                total, now
            ])

            # บันทึกรายการสินค้า
            for it in st.session_state.invoice_items:
                ws_item.append_row([
                    inv_no,
                    it["product"],
                    it["qty"],
                    it["price"],
                    it["amount"]
                ])

            st.success(f"บันทึก {inv_no} สำเร็จเรียบร้อยแล้ว!")
            
            # ล้างค่าใน Session
            st.session_state.invoice_items = []
            st.session_state.customer = ""
            st.session_state.address = ""
            st.session_state.shipping = 0.0
            st.session_state.discount = 0.0
            
            st.cache_resource.clear()
            st.rerun()
