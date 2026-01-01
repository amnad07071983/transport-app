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
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

# ================= 1. CONFIG & INITIALIZATION =================
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

# ================= 2. SESSION STATE =================
# รายชื่อฟิลด์ให้ตรงกับคอลัมน์ใน Sheet
transport_fields = [
    "doc_status", "car_id", "driver_name", "pay_status", "date_out", "time_out",
    "date_in", "time_in", "ref_tax_id", "ref_receipt_id", "seal_no",
    "pay_term", "ship_method", "driver_license", "receiver_name",
    "issuer_name", "sender_name", "checker_name", "remark",
    "comp_name", "comp_address", "comp_tax_id", "comp_phone", "comp_doc_title"
]

def reset_form():
    st.session_state.invoice_items = []
    st.session_state.form_customer = ""
    st.session_state.form_address = ""
    st.session_state.form_shipping = 0.0
    st.session_state.form_discount = 0.0
    st.session_state.form_vat = 0.0
    for field in transport_fields:
        st.session_state[f"form_{field}"] = ""

if "invoice_items" not in st.session_state:
    reset_form()

# ================= 3. PDF FUNCTION =================
def create_pdf(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    
    # 1. หัวเอกสาร (ข้อมูลบริษัท)
    c.setFont("ThaiFontBold", 16)
    c.drawString(2*cm, h-1.5*cm, str(inv.get('comp_name', '')))
    c.setFont("ThaiFontBold", 10)
    c.drawString(2*cm, h-2.1*cm, f"ที่อยู่: {inv.get('comp_address', '')}")
    c.drawString(2*cm, h-2.6*cm, f"Tax ID: {inv.get('comp_tax_id', '')} | โทร: {inv.get('comp_phone', '')}")
    
    c.rect(13*cm, h-2.8*cm, 6*cm, 1.6*cm)
    c.setFont("ThaiFontBold", 16)
    c.drawCentredString(16*cm, h-1.9*cm, str(inv.get('comp_doc_title', 'ใบขนส่งสินค้า')))
    c.setFont("ThaiFontBold", 10)
    c.drawCentredString(16*cm, h-2.5*cm, f"เลขที่: {inv.get('invoice_no','')} | วันที่: {inv.get('date','')}")

    # 2. ข้อมูลลูกค้า
    c.rect(2*cm, h-5.2*cm, 17*cm, 2.2*cm)
    c.setFont("ThaiFontBold", 11)
    c.drawString(2.3*cm, h-3.5*cm, f"ลูกค้า: {inv.get('customer','')}")
    c.drawString(2.3*cm, h-4.1*cm, f"ที่อยู่: {inv.get('address','')}")
    c.drawString(2.3*cm, h-4.8*cm, f"Ref Tax: {inv.get('ref_tax_id','-')} | Ref Receipt: {inv.get('ref_receipt_id','-')}")

    # 3. ตารางรายการสินค้า
    data = [["ลำดับ", "รายการ", "หน่วย", "จำนวน", "ราคา/หน่วย", "รวมเงิน"]]
    for i, it in enumerate(items):
        data.append([
            i+1, it.get('product',''), it.get('unit',''),
            f"{it.get('qty',0):,}", f"{float(it.get('price',0)):,.2f}", f"{float(it.get('amount',0)):,.2f}"
        ])
    
    t = Table(data, colWidths=[1*cm, 8*cm, 2*cm, 2*cm, 2*cm, 2*cm])
    t.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), 'ThaiFontBold', 10),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (3,0), (-1,-1), 'RIGHT')
    ]))
    tw, th = t.wrapOn(c, 2*cm, h-10*cm)
    t.drawOn(c, 2*cm, h-10*cm-th)

    # 4. ท้ายเอกสาร (ลายเซ็น)
    sig_y = 3*cm
    c.line(2*cm, sig_y, 5*cm, sig_y)
    c.drawCentredString(3.5*cm, sig_y-0.5*cm, "ผู้รับสินค้า")
    c.line(16*cm, sig_y, 19*cm, sig_y)
    c.drawCentredString(17.5*cm, sig_y-0.5*cm, "ผู้ออกเอกสาร")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= 4. UI =================
st.title("🚚 ระบบขนส่ง (Fix Bug)")

with st.expander("🔍 ค้นหาข้อมูลเก่า"):
    if not inv_df.empty:
        options = [f"{r['invoice_no']} | {r['customer']}" for _, r in inv_df.iterrows()]
        selected = st.selectbox("เลือกรายการ", [""] + options[::-1])
        if selected:
            sel_no = selected.split(" | ")[0]
            old_inv = inv_df[inv_df["invoice_no"] == sel_no].iloc[0].to_dict()
            old_items = item_df[item_df["invoice_no"] == sel_no].to_dict('records')
            
            if st.button("🔄 ดึงข้อมูลมาแก้ไข/Duplicate"):
                st.session_state.form_customer = old_inv.get("customer", "")
                st.session_state.form_address = old_inv.get("address", "")
                st.session_state.form_shipping = float(old_inv.get("shipping", 0))
                st.session_state.form_discount = float(old_inv.get("discount", 0))
                st.session_state.form_vat = float(old_inv.get("vat", 0))
                
                # ดึงข้อมูลบริษัทและขนส่ง (ป้องกันข้อมูลไม่มา)
                for f in transport_fields:
                    st.session_state[f"form_{f}"] = str(old_inv.get(f, ""))
                
                # ดึงข้อมูลสินค้า (ป้องกัน KeyError 'unit')
                st.session_state.invoice_items = []
                for it in old_items:
                    st.session_state.invoice_items.append({
                        "product": it.get("product", ""),
                        "unit": it.get("unit", ""), # ใช้ .get ป้องกัน Error
                        "qty": it.get("qty", 0),
                        "price": it.get("price", 0),
                        "amount": it.get("amount", 0)
                    })
                st.rerun()

st.divider()

# ฟอร์มกรอกข้อมูล
t1, t2, t3 = st.tabs(["ลูกค้า/บริษัท", "สินค้า", "การขนส่ง"])
with t1:
    customer = st.text_input("ชื่อลูกค้า", value=st.session_state.form_customer)
    address = st.text_area("ที่อยู่", value=st.session_state.form_address)
    st.subheader("ข้อมูลบริษัท (หัว PDF)")
    c_name = st.text_input("ชื่อบริษัท", value=st.session_state.form_comp_name)
    c_addr = st.text_area("ที่อยู่บริษัท", value=st.session_state.form_comp_address)
    c_tax = st.text_input("เลขผู้เสียภาษี", value=st.session_state.form_comp_tax_id)
    c_title = st.text_input("ชื่อเอกสาร", value=st.session_state.form_comp_doc_title)
    c_phone = st.text_input("เบอร์โทร", value=st.session_state.form_comp_phone)

with t2:
    # ส่วนเพิ่มสินค้า
    col_p1, col_p2, col_p3 = st.columns([3,1,1])
    p_in = col_p1.text_input("ชื่อสินค้า")
    u_in = col_p2.text_input("หน่วย")
    q_in = col_p3.number_input("จำนวน", min_value=1)
    if st.button("➕ เพิ่ม"):
        st.session_state.invoice_items.append({"product": p_in, "unit": u_in, "qty": q_in, "price": 0, "amount": 0})
        st.rerun()
    
    # แสดงรายการสินค้าที่เพิ่มแล้ว
    for i, item in enumerate(st.session_state.invoice_items):
        u_val = item.get('unit', '') # ป้องกัน Error จุดเดิม
        st.info(f"{i+1}. {item['product']} ({item['qty']} {u_val})")

with t3:
    car = st.text_input("ทะเบียนรถ", value=st.session_state.form_car_id)
    driver = st.text_input("คนขับ", value=st.session_state.form_driver_name)

if st.button("💾 บันทึกและรับ PDF", type="primary"):
    # โค้ดบันทึกลง Sheet และสร้าง PDF...
    st.success("บันทึกสำเร็จ (ตัวอย่าง)")
