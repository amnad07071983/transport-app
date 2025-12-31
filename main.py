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

# ================= CONFIG & INITIALIZATION =================
st.set_page_config(page_title="Logistics System Pro", layout="wide")

# ลงทะเบียนฟอนต์ (ต้องมีไฟล์ THSARABUN BOLD.ttf ในโฟลเดอร์)
try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except:
    st.error("⚠️ ไม่พบไฟล์ฟอนต์ 'THSARABUN BOLD.ttf' กรุณาอัปโหลดก่อนใช้งาน")

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INV_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

@st.cache_resource
def init_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds).open_by_key(SHEET_ID)

@st.cache_data(ttl=60)
def get_data_cached():
    client = init_sheet()
    try:
        inv = client.worksheet(INV_SHEET).get_all_records()
        items = client.worksheet(ITEM_SHEET).get_all_records()
        return pd.DataFrame(inv), pd.DataFrame(items)
    except:
        return pd.DataFrame(), pd.DataFrame()

# เชื่อมต่อ API
try:
    client = init_sheet()
    inv_df, item_df = get_data_cached()
    ws_inv = client.worksheet(INV_SHEET)
    ws_item = client.worksheet(ITEM_SHEET)
except Exception as e:
    st.error(f"การเชื่อมต่อผิดพลาด: {e}")
    inv_df, item_df = pd.DataFrame(), pd.DataFrame()

# ================= HELPER FUNCTIONS =================
def next_inv_no(df):
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
    c.setFont("ThaiFontBold", 20)
    c.drawString(2*cm, h-2*cm, "ใบกำกับขนส่งสินค้า (Transportation Invoice)")
    c.setFont("ThaiFontBold", 14)
    c.drawString(2*cm, h-3.2*cm, f"เลขที่ใบแจ้งหนี้: {inv['invoice_no']}")
    c.drawString(2*cm, h-4*cm, f"วันที่: {inv['date']}")
    c.drawString(2*cm, h-5.2*cm, f"ชื่อลูกค้า: {inv['customer']}")
    c.drawString(2*cm, h-6*cm, f"ที่อยู่: {inv['address']}")
    
    y = h - 8*cm
    c.line(2*cm, y, 19*cm, y)
    c.setFont("ThaiFontBold", 12)
    c.drawString(2.2*cm, y-0.6*cm, "รายการสินค้า")
    c.drawRightString(12*cm, y-0.6*cm, "จำนวน")
    c.drawRightString(15.5*cm, y-0.6*cm, "ราคา/หน่วย")
    c.drawRightString(19*cm, y-0.6*cm, "รวมเงิน")
    c.line(2*cm, y-0.8*cm, 19*cm, y-0.8*cm)
    
    y -= 1.5*cm
    for it in items:
        c.drawString(2.2*cm, y, str(it["product"]))
        c.drawRightString(12*cm, y, f"{it['qty']:,}")
        c.drawRightString(15.5*cm, y, f"{it['price']:,.2f}")
        c.drawRightString(19*cm, y, f"{it['amount']:,.2f}")
        y -= 0.8*cm
        
    y_sum = y - 1*cm
    c.line(13*cm, y_sum+0.8*cm, 19*cm, y_sum+0.8*cm)
    c.drawString(13.5*cm, y_sum, f"ค่าขนส่ง: {inv['shipping']:,.2f}")
    c.drawString(13.5*cm, y_sum-0.8*cm, f"ส่วนลด: {inv['discount']:,.2f}")
    c.setFont("ThaiFontBold", 16)
    c.drawString(13.5*cm, y_sum-1.8*cm, f"ยอดสุทธิ: {inv['total']:,.2f} บาท")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= SESSION STATE =================
if "invoice_items" not in st.session_state:
    st.session_state.invoice_items = []
if "form_customer" not in st.session_state: st.session_state.form_customer = ""
if "form_address" not in st.session_state: st.session_state.form_address = ""

# ================= UI =================
st.title("🚚 ระบบจัดการใบแจ้งหนี้ขนส่ง")

# --- ส่วนดึงข้อมูลเก่า (Duplicate) ---
with st.expander("🔍 ค้นหาและทำซ้ำข้อมูลเก่า"):
    if not inv_df.empty:
        options = [f"{r['invoice_no']} | {r['customer']}" for _, r in inv_df.iterrows()]
        selected = st.selectbox("เลือกเลขที่ใบแจ้งหนี้เดิม", [""] + options[::-1])
        if selected and st.button("🔄 ดึงข้อมูลมาใช้อีกครั้ง"):
            inv_no_sel = selected.split(" | ")[0]
            old_inv = inv_df[inv_df["invoice_no"] == inv_no_sel].iloc[0]
            st.session_state.form_customer = old_inv["customer"]
            st.session_state.form_address = old_inv["address"]
            # ดึงรายการสินค้าเก่า
            old_items = item_df[item_df["invoice_no"] == inv_no_sel]
            st.session_state.invoice_items = old_items.to_dict('records')
            st.rerun()
    else:
        st.info("ยังไม่มีข้อมูลประวัติ")

st.divider()

# --- ฟอร์มกรอกข้อมูล ---
c1, c2 = st.columns(2)
with c1:
    customer = st.text_input("ชื่อลูกค้า", value=st.session_state.form_customer)
    address = st.text_area("ที่อยู่", value=st.session_state.form_address)
with c2:
    shipping = st.number_input("ค่าขนส่ง", min_value=0.0, step=100.0)
    discount = st.number_input("ส่วนลด", min_value=0.0, step=100.0)

# --- จัดการรายการสินค้า ---
st.subheader("📦 รายการสินค้า")
ci1, ci2, ci3 = st.columns([3,1,1])
p_name = ci1.text_input("ชื่อสินค้า/บริการ")
p_qty = ci2.number_input("จำนวน", min_value=1, value=1)
p_price = ci3.number_input("ราคาต่อหน่วย", min_value=0.0, value=0.0)

if st.button("➕ เพิ่มสินค้า"):
    if p_name:
        st.session_state.invoice_items.append({
            "product": p_name, "qty": p_qty, "price": p_price, "amount": p_qty * p_price
        })
        st.rerun()

# --- ตารางรายการสินค้าและปุ่มลบ ---
if st.session_state.invoice_items:
    st.write("---")
    for i, item in enumerate(st.session_state.invoice_items):
        cols = st.columns([4, 1])
        cols[0].info(f"{i+1}. {item['product']} | {item['qty']:,} x {item['price']:,.2f} = {item['amount']:,.2f}")
        if cols[1].button("🗑️ ลบ", key=f"del_{i}"):
            st.session_state.invoice_items.pop(i)
            st.rerun()

    subtotal = sum(i["amount"] for i in st.session_state.invoice_items)
    grand_total = subtotal + shipping - discount
    st.write(f"### ยอดรวมสุทธิ: {grand_total:,.2f} บาท")

    # --- ปุ่มบันทึกและพิมพ์ ---
    if st.button("✅ บันทึกและพิมพ์ PDF", type="primary"):
        with st.spinner("กำลังประมวลผล..."):
            new_no = next_inv_no(inv_df)
            date_now = datetime.now().strftime("%d/%m/%Y")
            
            # บันทึกลง Google Sheets
            ws_inv.append_row([new_no, date_now, customer, address, subtotal, 0, shipping, discount, grand_total])
            for it in st.session_state.invoice_items:
                ws_item.append_row([new_no, it["product"], it["qty"], it["price"], it["amount"]])
            
            # สร้าง PDF
            inv_data = {"invoice_no": new_no, "date": date_now, "customer": customer, "address": address, "shipping": shipping, "discount": discount, "total": grand_total}
            pdf_file = create_pdf(inv_data, st.session_state.invoice_items)
            
            st.success(f"บันทึกสำเร็จ! เลขที่: {new_no}")
            st.download_button("📥 ดาวน์โหลด PDF", pdf_file, f"{new_no}.pdf", "application/pdf")
            
            # ล้างค่า
            st.session_state.invoice_items = []
            st.session_state.form_customer = ""
            st.session_state.form_address = ""
            st.cache_data.clear()
