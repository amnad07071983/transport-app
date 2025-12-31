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

# ================= SESSION STATE (For Duplicate & Form) =================
# สร้างรายการฟิลด์ที่ต้องการเพิ่มตามรูปภาพ
transport_fields = [
    "Car ID", "Driver Name", "Payment Status", "Date Out", "Time Out",
    "Date In", "Time In", "Ref Tax ID", "Ref Receipt ID", "Seal No",
    "Pay Term", "Ship Method", "Driver License", "Receiver Name",
    "Issuer Name", "Sender Name", "Checker Name", "Remark"
]

if "invoice_items" not in st.session_state: st.session_state.invoice_items = []
for field in ["Customer", "Address"] + transport_fields:
    key = f"form_{field.lower().replace(' ', '_')}"
    if key not in st.session_state: st.session_state[key] = ""

# ================= HELPER FUNCTIONS =================
def next_inv_no(df):
    if df.empty or "invoice_no" not in df.columns: return "INV-0001"
    last = df["invoice_no"].iloc[-1]
    try:
        num = int(str(last).split('-')[1])
        return f"INV-{num + 1:04d}"
    except: return "INV-0001"

# ================= UI =================
st.title("🚚 ระบบจัดการใบแจ้งหนี้ขนส่ง (Full Version)")

# --- ส่วนดึงข้อมูลเก่า (Duplicate) ---
with st.expander("🔍 ค้นหาและทำซ้ำข้อมูลเก่า"):
    if not inv_df.empty:
        options = [f"{r['invoice_no']} | {r['customer']}" for _, r in inv_df.iterrows()]
        selected = st.selectbox("เลือกรายการเดิม", [""] + options[::-1])
        if selected and st.button("🔄 ดึงข้อมูลเดิมมาใช้"):
            sel_no = selected.split(" | ")[0]
            old_inv = inv_df[inv_df["invoice_no"] == sel_no].iloc[0]
            # ดึงข้อมูลทุกฟิลด์กลับเข้า Session
            st.session_state.form_customer = old_inv.get("customer", "")
            st.session_state.form_address = old_inv.get("address", "")
            for field in transport_fields:
                key = f"form_{field.lower().replace(' ', '_')}"
                st.session_state[key] = old_inv.get(field.lower().replace(' ', '_'), "")
            # ดึงรายการสินค้า
            old_items = item_df[item_df["invoice_no"] == sel_no]
            st.session_state.invoice_items = old_items.to_dict('records')
            st.rerun()

st.divider()

# --- ฟอร์มกรอกข้อมูลส่วนหัว (เพิ่มคอลัมน์ใหม่) ---
st.subheader("📝 ข้อมูลทั่วไปและข้อมูลการขนส่ง")
c1, c2, c3 = st.columns(3)
with c1:
    customer = st.text_input("ชื่อลูกค้า", value=st.session_state.form_customer)
    address = st.text_area("ที่อยู่", value=st.session_state.form_address)
    car_id = st.text_input("Car ID (ทะเบียนรถ)", value=st.session_state.form_car_id)
    driver_name = st.text_input("Driver Name (คนขับ)", value=st.session_state.form_driver_name)
with c2:
    pay_status = st.selectbox("Payment Status", ["ค้างชำระ", "ชำระแล้ว"], index=0)
    date_out = st.text_input("Date Out", value=st.session_state.form_date_out)
    time_out = st.text_input("Time Out", value=st.session_state.form_time_out)
    seal_no = st.text_input("Seal No", value=st.session_state.form_seal_no)
with c3:
    shipping = st.number_input("ค่าขนส่ง", min_value=0.0)
    discount = st.number_input("ส่วนลด", min_value=0.0)
    ship_method = st.text_input("Ship Method", value=st.session_state.form_ship_method)
    remark = st.text_area("Remark (หมายเหตุ)", value=st.session_state.form_remark)

# --- จัดการรายการสินค้า (Add/Delete) ---
st.subheader("📦 รายการสินค้า")
ci1, ci2, ci3 = st.columns([3,1,1])
p_name = ci1.text_input("ชื่อสินค้า")
p_qty = ci2.number_input("จำนวน", min_value=1)
p_price = ci3.number_input("ราคา/หน่วย", min_value=0.0)

if st.button("➕ เพิ่มรายการ"):
    if p_name:
        st.session_state.invoice_items.append({"product": p_name, "qty": p_qty, "price": p_price, "amount": p_qty*p_price})
        st.rerun()

if st.session_state.invoice_items:
    for i, item in enumerate(st.session_state.invoice_items):
        col_list = st.columns([4, 1])
        col_list[0].info(f"{i+1}. {item['product']} | {item['qty']:,} x {item['price']:,.2f} = {item['amount']:,.2f}")
        if col_list[1].button("🗑️ ลบ", key=f"del_{i}"):
            st.session_state.invoice_items.pop(i)
            st.rerun()

    total = sum(i['amount'] for i in st.session_state.invoice_items) + shipping - discount
    st.write(f"### ยอดสุทธิ: {total:,.2f} บาท")

    if st.button("✅ บันทึกและพิมพ์ PDF", type="primary"):
        new_no = next_inv_no(inv_df)
        date_now = datetime.now().strftime("%d/%m/%Y")
        
        # บันทึกลง Sheet (รวมคอลัมน์ใหม่)
        data_to_save = [new_no, date_now, customer, address, total-shipping+discount, 0, shipping, discount, total]
        # เพิ่มข้อมูลขนส่งต่อท้ายตามลำดับ
        data_to_save += [car_id, driver_name, pay_status, date_out, time_out, "", "", "", "", seal_no, "", ship_method, "", "", "", "", "", remark]
        
        ws_inv.append_row(data_to_save)
        for it in st.session_state.invoice_items:
            ws_item.append_row([new_no, it['product'], it['qty'], it['price'], it['amount']])
        
        st.success(f"บันทึกสำเร็จ: {new_no}")
        st.cache_data.clear()
