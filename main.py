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

try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except:
    st.error("⚠️ ไม่พบไฟล์ฟอนต์ 'THSARABUN BOLD.ttf'")

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

try:
    client = init_sheet()
    inv_df, item_df = get_data_cached()
    ws_inv = client.worksheet(INV_SHEET)
    ws_item = client.worksheet(ITEM_SHEET)
except:
    inv_df, item_df = pd.DataFrame(), pd.DataFrame()

# ================= SESSION STATE & RESET =================
transport_fields = [
    "Car ID", "Driver Name", "Payment Status", "Date Out", "Time Out",
    "Date In", "Time In", "Ref Tax ID", "Ref Receipt ID", "Seal No",
    "Pay Term", "Ship Method", "Driver License", "Receiver Name",
    "Issuer Name", "Sender Name", "Checker Name", "Remark"
]

def reset_form():
    st.session_state.invoice_items = []
    st.session_state.form_customer = ""
    st.session_state.form_address = ""
    for field in transport_fields:
        key = f"form_{field.lower().replace(' ', '_')}"
        st.session_state[key] = ""

if "invoice_items" not in st.session_state: 
    reset_form()

# ================= HELPER FUNCTIONS =================
def next_inv_no(df):
    if df.empty or "invoice_no" not in df.columns: return "INV-0001"
    last = df["invoice_no"].iloc[-1]
    try:
        num = int(str(last).split('-')[1])
        return f"INV-{num + 1:04d}"
    except: return "INV-0001"

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
        c.drawString(2.2*cm, y, str(it.get("product", "")))
        c.drawRightString(12*cm, y, f"{it.get('qty', 0):,}")
        c.drawRightString(15.5*cm, y, f"{float(it.get('price', 0)):,.2f}")
        c.drawRightString(19*cm, y, f"{float(it.get('amount', 0)):,.2f}")
        y -= 0.8*cm
        
    y_sum = y - 1*cm
    c.line(13*cm, y_sum+0.8*cm, 19*cm, y_sum+0.8*cm)
    c.drawString(13.5*cm, y_sum, f"ค่าขนส่ง: {float(inv.get('shipping', 0)):,.2f}")
    c.drawString(13.5*cm, y_sum-0.8*cm, f"ส่วนลด: {float(inv.get('discount', 0)):,.2f}")
    c.setFont("ThaiFontBold", 16)
    c.drawString(13.5*cm, y_sum-1.8*cm, f"ยอดสุทธิ: {float(inv.get('total', 0)):,.2f} บาท")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= UI =================
st.title("🚚 ระบบจัดการใบแจ้งหนี้ขนส่ง")

# --- เพิ่มส่วนพิมพ์ข้อมูลเก่า ---
with st.expander("🔍 ค้นหา ทำซ้ำ หรือพิมพ์ PDF จากข้อมูลเก่า"):
    if not inv_df.empty:
        options = [f"{r['invoice_no']} | {r['customer']}" for _, r in inv_df.iterrows()]
        selected = st.selectbox("เลือกรายการประวัติ", [""] + options[::-1])
        
        if selected:
            sel_no = selected.split(" | ")[0]
            col_b1, col_b2 = st.columns(2)
            
            with col_b1:
                if st.button("🔄 ดึงข้อมูลมาแก้ไข/ทำซ้ำ"):
                    old_inv = inv_df[inv_df["invoice_no"] == sel_no].iloc[0]
                    st.session_state.form_customer = old_inv.get("customer", "")
                    st.session_state.form_address = old_inv.get("address", "")
                    for field in transport_fields:
                        key = f"form_{field.lower().replace(' ', '_')}"
                        st.session_state[key] = old_inv.get(field.lower().replace(' ', '_'), "")
                    old_items = item_df[item_df["invoice_no"] == sel_no]
                    st.session_state.invoice_items = old_items.to_dict('records')
                    st.rerun()
            
            with col_b2:
                # ส่วนสำหรับพิมพ์ PDF ข้อมูลเดิมทันที
                old_inv_data = inv_df[inv_df["invoice_no"] == sel_no].iloc[0].to_dict()
                old_items_data = item_df[item_df["invoice_no"] == sel_no].to_dict('records')
                pdf_old = create_pdf(old_inv_data, old_items_data)
                st.download_button(f"📄 พิมพ์ PDF เลขที่ {sel_no}", pdf_old, f"{sel_no}.pdf", "application/pdf")
    else:
        st.info("ยังไม่มีข้อมูลประวัติ")

st.divider()

# --- ส่วนฟอร์มกรอกข้อมูลและบันทึก (คงไว้ตามเดิม) ---
# ... [โค้ดส่วนฟอร์มรับค่า Customer, Address, Items และปุ่มบันทึกเหมือนเดิม] ...
# (เพื่อให้ประหยัดพื้นที่ ผมละส่วนที่ซ้ำไว้ แต่ในไฟล์จริงของคุณให้ใช้ส่วน UI เดิมต่อท้ายได้เลยครับ)
