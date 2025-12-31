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
st.set_page_config(page_title="Transportation Invoice Pro", layout="wide")

# --- ลงทะเบียนฟอนต์ภาษาไทย ---
try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except Exception as e:
    st.error(f"⚠️ ไม่พบไฟล์ฟอนต์: 'THSARABUN BOLD.ttf' (Error: {e})")

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
defaults = {
    "invoice_items": [],
    "customer": "",
    "address": "",
    "shipping": 0.0,
    "discount": 0.0,
    "my_company": "ชื่อบริษัทของคุณ",
    "my_address": "ที่อยู่บริษัทของคุณ...",
    "my_phone": "08x-xxxxxxx",
    "car_id": "",
    "driver_name": "",
    "pay_status": "ค้างชำระ"
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

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
    
    # --- 1. Header (ข้อมูลบริษัทเรา) ---
    c.setFont("ThaiFontBold", 18)
    c.drawString(2*cm, h-2*cm, st.session_state.my_company)
    c.setFont("ThaiFontBold", 12)
    c.drawString(2*cm, h-2.6*cm, f"ที่อยู่: {st.session_state.my_address}")
    c.drawString(2*cm, h-3.1*cm, f"โทร: {st.session_state.my_phone}")
    
    c.setFont("ThaiFontBold", 20)
    c.drawRightString(19*cm, h-2*cm, "ใบกำกับขนส่งสินค้า")
    c.setFont("ThaiFontBold", 12)
    c.drawRightString(19*cm, h-2.6*cm, f"เลขที่: {inv['invoice_no']}")
    c.drawRightString(19*cm, h-3.1*cm, f"วันที่: {inv['date']}")
    
    c.line(2*cm, h-3.5*cm, 19*cm, h-3.5*cm)

    # --- 2. ข้อมูลลูกค้า & ข้อมูลขนส่ง ---
    c.setFont("ThaiFontBold", 14)
    c.drawString(2*cm, h-4.3*cm, f"ชื่อลูกค้า: {inv['customer']}")
    
    # ข้อมูลรถและคนขับ (เพิ่มใหม่)
    c.drawString(13*cm, h-4.3*cm, f"ทะเบียนรถ: {inv.get('car_id', '-')}")
    c.drawString(13*cm, h-4.9*cm, f"พนักงานขับรถ: {inv.get('driver_name', '-')}")
    
    text_obj = c.beginText(2*cm, h-4.9*cm)
    text_obj.setFont("ThaiFontBold", 12)
    text_obj.textLines(f"ที่อยู่ลูกค้า: {inv['address']}")
    c.drawText(text_obj)

    # --- 3. ตารางสินค้า ---
    y = h - 7*cm
    c.setFont("ThaiFontBold", 14)
    c.drawString(2*cm, y, "รายการสินค้า")
    c.drawRightString(12*cm, y, "จำนวน")
    c.drawRightString(15.5*cm, y, "ราคา/หน่วย")
    c.drawRightString(19*cm, y, "รวมเงิน")
    c.line(2*cm, y-0.2*cm, 19*cm, y-0.2*cm)
    
    y -= 0.8*cm
    for it in items:
        if y < 4*cm:
            c.showPage()
            c.setFont("ThaiFontBold", 14)
            y = h - 2*cm
        c.drawString(2*cm, y, str(it["product"]))
        c.drawRightString(12*cm, y, f"{it['qty']:,}")
        c.drawRightString(15.5*cm, y, f"{float(it['price']):,.2f}")
        c.drawRightString(19*cm, y, f"{float(it['amount']):,.2f}")
        y -= 0.7*cm

    # --- 4. สรุปเงิน ---
    y_box = y - 0.5*cm
    c.line(13*cm, y_box, 19*cm, y_box)
    y = y_box - 0.6*cm
    c.setFont("ThaiFontBold", 12)
    c.drawRightString(16*cm, y, "ค่าขนส่ง:")
    c.drawRightString(19*cm, y, f"{float(inv['shipping']):,.2f}")
    y -= 0.6*cm
    c.drawRightString(16*cm, y, "ส่วนลด:")
    c.drawRightString(19*cm, y, f"{float(inv['discount']):,.2f}")
    y -= 0.8*cm
    c.setFont("ThaiFontBold", 16)
    c.drawRightString(16*cm, y, "ยอดสุทธิ:")
    c.drawRightString(19*cm, y, f"{float(inv['total']):,.2f} บาท")
    
    # สถานะ (เพิ่มใหม่ใน PDF)
    c.setFont("ThaiFontBold", 12)
    c.drawString(2*cm, y, f"สถานะการชำระเงิน: {inv.get('status', 'ค้างชำระ')}")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= UI =================
st.title("🚚 ระบบใบกำกับขนส่งสินค้า Professional")

# --- Tab Menu ---
tab1, tab2 = st.tabs(["📝 ออกใบกำกับสินค้า", "⚙️ ตั้งค่าบริษัท"])

with tab2:
    st.subheader("🏢 ข้อมูลหัวกระดาษบริษัท (Header Profile)")
    st.session_state.my_company = st.text_input("ชื่อบริษัท/ร้าน", st.session_state.my_company)
    st.session_state.my_address = st.text_area("ที่อยู่บริษัท", st.session_state.my_address)
    st.session_state.my_phone = st.text_input("เบอร์โทรศัพท์", st.session_state.my_phone)
    st.info("💡 ข้อมูลนี้จะไปปรากฏที่หัวกระดาษของ PDF ทุกใบ")

with tab1:
    # --- ส่วนค้นหา ---
    with st.expander("🔍 ค้นหา / ทำซ้ำ Invoice เก่า"):
        if not inv_df.empty:
            invoice_options = [f"{row['invoice_no']} | {row['date']} | {row['customer']}" for _, row in inv_df.iterrows()]
            selected_label = st.selectbox("เลือก Invoice", [""] + invoice_options[::-1])
            if selected_label:
                selected_no = selected_label.split(" | ")[0]
                inv_data = inv_df[inv_df["invoice_no"] == selected_no].iloc[0]
                its_data = item_df[item_df["invoice_no"] == selected_no]
                
                col_a, col_b = st.columns(2)
                if col_a.button("📄 Duplicate ลงฟอร์ม"):
                    st.session_state.customer = inv_data["customer"]
                    st.session_state.address = inv_data.get("address", "")
                    st.session_state.shipping = float(inv_data.get("shipping", 0))
                    st.session_state.discount = float(inv_data.get("discount", 0))
                    st.session_state.invoice_items = its_data.to_dict("records")
                    st.rerun()
                if col_b.button("🖨 Export PDF ต้นฉบับ"):
                    pdf = create_pdf(inv_data.to_dict(), its_data.to_dict("records"))
                    st.download_button("⬇ Download PDF", pdf, f"{selected_no}.pdf")

    # --- ข้อมูลลูกค้า & ขนส่ง ---
    st.subheader("🧾 ข้อมูลลูกค้า & ขนส่ง")
    c_cust1, c_cust2 = st.columns(2)
    with c_cust1:
        st.session_state.customer = st.text_input("ชื่อลูกค้า", value=st.session_state.customer)
        st.session_state.address = st.text_area("ที่อยู่ลูกค้า", value=st.session_state.address)
    with c_cust2:
        st.session_state.car_id = st.text_input("ทะเบียนรถ", value=st.session_state.car_id)
        st.session_state.driver_name = st.text_input("ชื่อคนขับ", value=st.session_state.driver_name)
        st.session_state.pay_status = st.selectbox("สถานะการจ่ายเงิน", ["ค้างชำระ", "ชำระแล้ว"])

    # --- การเงิน ---
    st.subheader("💰 ค่าบริการ")
    c_pay1, c_pay2 = st.columns(2)
    st.session_state.shipping = c_pay1.number_input("🚚 ค่าขนส่ง", value=float(st.session_state.shipping))
    st.session_state.discount = c_pay2.number_input("🔻 ส่วนลด", value=float(st.session_state.discount))

    # --- เพิ่มสินค้า ---
    st.subheader("📦 รายการสินค้า")
    c1, c2, c3 = st.columns([3, 1, 1])
    new_name = c1.text_input("ชื่อรายการ")
    new_qty = c2.number_input("จำนวน", min_value=1, value=1)
    new_price = c3.number_input("ราคาต่อหน่วย", min_value=0.0, value=0.0)

    if st.button("➕ เพิ่มรายการ"):
        if new_name:
            st.session_state.invoice_items.append({
                "product": new_name, "qty": int(new_qty),
                "price": float(new_price), "amount": float(new_qty * new_price)
            })
            st.rerun()

    if st.session_state.invoice_items:
        df_display = pd.DataFrame(st.session_state.invoice_items)
        st.table(df_display)
        if st.button("🗑 ล้างรายการทั้งหมด"):
            st.session_state.invoice_items = []
            st.rerun()

    # --- รวมสุทธิ ---
    subtotal = sum(item["amount"] for item in st.session_state.invoice_items)
    vat = subtotal * 0.07
    total = subtotal + vat + st.session_state.shipping - st.session_state.discount
    st.markdown(f"### ยอดรวมสุทธิ: {total:,.2f} บาท")

    # --- บันทึก ---
    if st.button("✅ บันทึกและออก Invoice", type="primary"):
        if not st.session_state.invoice_items:
            st.error("กรุณาเพิ่มสินค้าก่อน")
        else:
            with st.spinner("กำลังบันทึกไปยัง Google Sheets..."):
                inv_no = next_invoice_no()
                today = datetime.today().strftime("%d/%m/%Y")
                
                # บันทึกข้อมูล (เพิ่มทะเบียนรถ, คนขับ, สถานะ)
                ws_inv.append_row([
                    inv_no, today, st.session_state.customer, 
                    st.session_state.address, subtotal, vat, 
                    st.session_state.shipping, st.session_state.discount, total, 
                    datetime.now().strftime("%H:%M:%S"),
                    st.session_state.car_id, st.session_state.driver_name, st.session_state.pay_status
                ])
                
                for it in st.session_state.invoice_items:
                    ws_item.append_row([inv_no, it["product"], it["qty"], it["price"], it["amount"]])
                
                st.success(f"บันทึก {inv_no} เรียบร้อย!")
                st.session_state.invoice_items = []
                st.cache_resource.clear()
                st.rerun()
