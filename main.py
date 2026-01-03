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
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"

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
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

try:
    client = init_sheet()
    inv_df, item_df = get_data_cached()
    ws_inv = client.worksheet(INV_SHEET)
    ws_item = client.worksheet(ITEM_SHEET)
except:
    inv_df, item_df = pd.DataFrame(), pd.DataFrame()

# ================= 2. SESSION STATE & FORM RESET =================
# เรียงลำดับตาม Google Sheets: A=invoice_no, B=date, C=customer, D=address, E=subtotal, F=vat, G=shipping, H=discount, I=total...
transport_fields = [
    "doc_status", "car_id", "driver_name", "payment_status", "date_out", "time_out",
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
    st.session_state.form_subtotal = 0.0 # เพิ่มใหม่
    st.session_state.form_total = 0.0    # เพิ่มใหม่
    st.session_state.editing_no = None  
    st.session_state.last_saved_data = None
    for field in transport_fields:
        st.session_state[f"form_{field}"] = ""
    st.session_state.form_doc_status = "รอดำเนินการ"
    st.session_state.form_payment_status = "ค้างชำระ"

if "invoice_items" not in st.session_state:
    reset_form()

# ================= 3. CORE FUNCTIONS (PDF & LOGIC) =================
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
    c.setFont("ThaiFontBold", 24) 
    c.drawString(2*cm, h-1.5*cm, str(inv.get('comp_name', '')))
    c.setFont("ThaiFontBold", 14)
    c.drawString(2*cm, h-2.3*cm, f"ที่อยู่: {inv.get('comp_address', '')}")
    c.drawString(2*cm, h-3.1*cm, f"เลขประจำตัวผู้เสียภาษี: {inv.get('comp_tax_id', '')}  |  โทร: {inv.get('comp_phone', '')}")
    c.setFont("ThaiFontBold", 26)
    c.drawRightString(19*cm, h-1.5*cm, str(inv.get('comp_doc_title', 'ใบกำกับขนส่ง')))
    c.setFont("ThaiFontBold", 15)
    c.drawRightString(19*cm, h-2.4*cm, f"เลขที่: {inv.get('invoice_no','')}")
    c.drawRightString(19*cm, h-3.2*cm, f"วันที่: {inv.get('date','')}")
    c.setFont("ThaiFontBold", 16)
    c.drawString(2*cm, h-4.5*cm, f"ชื่อลูกค้า: {inv.get('customer','')}")
    c.setFont("ThaiFontBold", 14)
    c.drawString(2*cm, h-5.3*cm, f"ที่อยู่: {inv.get('address','')}")
    c.drawString(2*cm, h-6.1*cm, f"Ref Tax ID: {inv.get('ref_tax_id','-')} | Ref Receipt: {inv.get('ref_receipt_id','-')}")
    transport_data = [
        [f"ทะเบียนรถ: {inv.get('car_id','')}", f"ออก: {inv.get('date_out','')} {inv.get('time_out','')}", f"สถานะบิล: {inv.get('doc_status','')}"],
        [f"ชื่อคนขับ: {inv.get('driver_name','')}", f"เข้า: {inv.get('date_in','')} {inv.get('time_in','')}", f"การชำระ: {inv.get('pay_status','')}"],
        [f"ใบขับขี่: {inv.get('driver_license','')}", f"วิธีขนส่ง: {inv.get('ship_method','')}", f"Seal No: {inv.get('seal_no','')}"],
        [f"เงื่อนไขชำระ: {inv.get('pay_term','')}", "", ""]
    ]
    t_trans = Table(transport_data, colWidths=[6*cm, 6*cm, 5*cm])
    t_trans.setStyle(TableStyle([('FONT', (0,0), (-1,-1), 'ThaiFontBold', 12), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    t_trans.wrapOn(c, 2*cm, h-9*cm)
    t_trans.drawOn(c, 2*cm, h-9*cm)
    item_header = [["ลำดับ", "รายการสินค้า/บริการ", "หน่วย", "จำนวน", "ราคา/หน่วย", "รวมเงิน"]]
    item_rows = []
    total_qty = 0
    for i, it in enumerate(items):
        qty = it.get('qty', 0)
        item_rows.append([i+1, it.get("product", ""), it.get("unit", ""), f"{qty:,}", f"{float(it.get('price', 0)):,.2f}", f"{float(it.get('amount', 0)):,.2f}"])
        total_qty += qty
    item_rows.append(["", "ยอดรวมจำนวนทั้งสิ้น", "", f"{total_qty:,}", "", ""])
    t_items = Table(item_header + item_rows, colWidths=[1.2*cm, 7.8*cm, 2*cm, 2*cm, 2*cm, 2*cm])
    t_items.setStyle(TableStyle([('FONT', (0,0), (-1,0), 'ThaiFontBold', 14), ('FONT', (0,1), (-1,-1), 'ThaiFontBold', 13), ('ALIGN', (0,0), (0,-1), 'CENTER'), ('ALIGN', (5,0), (5,-1), 'RIGHT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LINEBELOW', (0,0), (-1,0), 1, colors.black), ('LINEBELOW', (0,-2), (-1,-2), 0.5, colors.grey), ('FONT', (0,-1), (-1,-1), 'ThaiFontBold', 13)]))
    tw, th = t_items.wrapOn(c, 2*cm, h-17*cm)
    t_y = h - 10.5*cm - th
    t_items.drawOn(c, 2*cm, t_y)
    curr_y = t_y - 1.2*cm
    c.setFont("ThaiFontBold", 13)
    c.drawString(2.2*cm, curr_y, f"หมายเหตุ: {inv.get('remark','-')}")
    c.drawRightString(16*cm, curr_y, "ค่าขนส่ง:")
    c.drawRightString(19*cm, curr_y, f"{float(inv.get('shipping', 0)):,.2f}")
    c.drawRightString(16*cm, curr_y-0.8*cm, "ภาษี (VAT):")
    c.drawRightString(19*cm, curr_y-0.8*cm, f"{float(inv.get('vat', 0)):,.2f}")
    c.drawRightString(16*cm, curr_y-1.6*cm, "ส่วนลด:")
    c.drawRightString(19*cm, curr_y-1.6*cm, f"{float(inv.get('discount', 0)):,.2f}")
    c.setFont("ThaiFontBold", 18)
    c.line(13*cm, curr_y-1.9*cm, 19*cm, curr_y-1.9*cm)
    c.drawRightString(16*cm, curr_y-2.8*cm, "ยอดสุทธิ:")
    c.drawRightString(19*cm, curr_y-2.8*cm, f"{float(inv.get('total', 0)):,.2f} บาท")
    sig_y = 3.5*cm
    labels = [("ผู้รับสินค้า", inv.get('receiver_name','')), ("ผู้ส่งสินค้า", inv.get('sender_name','')), ("ผู้ตรวจสอบ", inv.get('checker_name','')), ("ผู้ออกบิล", inv.get('issuer_name',''))]
    for i, (lab, val) in enumerate(labels):
        x = 2*cm + (i * 4.3*cm)
        c.line(x, sig_y, x+3.5*cm, sig_y)
        c.setFont("ThaiFontBold", 12)
        c.drawCentredString(x+1.75*cm, sig_y-0.7*cm, f"({val if val else '.......................'})")
        c.drawCentredString(x+1.75*cm, sig_y-1.4*cm, lab)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

def create_pdf_v2(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("ThaiFontBold", 24)
    c.drawString(2*cm, h-1.5*cm, str(inv.get('comp_name', '')))
    c.setFont("ThaiFontBold", 14)
    c.drawString(2*cm, h-2.3*cm, f"ที่อยู่: {inv.get('comp_address', '')}")
    c.drawString(2*cm, h-3.0*cm, f"เลขประจำตัวผู้เสียภาษี: {inv.get('comp_tax_id', '')}  |  โทร: {inv.get('comp_phone', '')}")
    c.setFont("ThaiFontBold", 26)
    c.drawRightString(19*cm, h-1.5*cm, str(inv.get('comp_doc_title', 'ใบกำกับขนส่ง')))
    c.setFont("ThaiFontBold", 15)
    c.drawRightString(19*cm, h-2.4*cm, f"เลขที่: {inv.get('invoice_no','')}")
    c.drawRightString(19*cm, h-3.1*cm, f"วันที่: {inv.get('date','')}")
    c.setFont("ThaiFontBold", 16)
    c.drawString(2*cm, h-4.5*cm, f"ชื่อลูกค้า: {inv.get('customer','')}")
    c.setFont("ThaiFontBold", 14)
    c.drawString(2*cm, h-5.3*cm, f"ที่อยู่: {inv.get('address','')}")
    c.drawString(2*cm, h-6.1*cm, f"Ref Tax ID: {inv.get('ref_tax_id','-')} | Ref Receipt: {inv.get('ref_receipt_id','-')}")
    transport_data = [
        [f"ทะเบียนรถ: {inv.get('car_id','')}", f"ออก: {inv.get('date_out','')} {inv.get('time_out','')}", f"สถานะบิล: {inv.get('doc_status','')}"],
        [f"ชื่อคนขับ: {inv.get('driver_name','')}", f"เข้า: {inv.get('date_in','')} {inv.get('time_in','')}", f"การชำระ: {inv.get('pay_status','')}"],
        [f"ใบขับขี่: {inv.get('driver_license','')}", f"วิธีขนส่ง: {inv.get('ship_method','')}", f"Seal No: {inv.get('seal_no','')}"],
        [f"เงื่อนไขชำระ: {inv.get('pay_term','')}", "", ""]
    ]
    t_trans = Table(transport_data, colWidths=[6*cm, 6*cm, 5*cm])
    t_trans.setStyle(TableStyle([('FONT', (0,0), (-1,-1), 'ThaiFontBold', 12), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    t_trans.wrapOn(c, 2*cm, h-9.5*cm)
    t_trans.drawOn(c, 2*cm, h-9.5*cm)
    item_header = [["ลำดับ", "รายการสินค้า/บริการ", "หน่วย", "จำนวน"]]
    item_rows = []
    total_qty = 0
    for i, it in enumerate(items):
        qty = it.get('qty', 0)
        item_rows.append([i+1, it.get("product", ""), it.get("unit", ""), f"{qty:,}"])
        total_qty += qty
    item_rows.append(["", "ยอดรวมจำนวนทั้งสิ้น", "", f"{total_qty:,}"])
    t_items = Table(item_header + item_rows, colWidths=[1.5*cm, 10.5*cm, 2.5*cm, 2.5*cm])
    t_items.setStyle(TableStyle([('FONT', (0,0), (-1,0), 'ThaiFontBold', 15), ('FONT', (0,1), (-1,-1), 'ThaiFontBold', 14), ('ALIGN', (0,0), (0,-1), 'CENTER'), ('ALIGN', (3,0), (3,-1), 'RIGHT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LINEBELOW', (0,0), (-1,0), 1, colors.black), ('LINEBELOW', (0,-1), (-1,-1), 1, colors.black)]))
    tw, th = t_items.wrapOn(c, 2*cm, h-18*cm)
    t_y = h - 11.0*cm - th
    t_items.drawOn(c, 2*cm, t_y)
    curr_y = t_y - 1.2*cm
    c.setFont("ThaiFontBold", 13)
    c.drawString(2.2*cm, curr_y, f"หมายเหตุ: {inv.get('remark','-')}")
    sig_y = 3.5*cm
    labels = [("ผู้รับสินค้า", inv.get('receiver_name','')), ("ผู้ส่งสินค้า", inv.get('sender_name','')), ("ผู้ตรวจสอบ", inv.get('checker_name','')), ("ผู้ออกบิล", inv.get('issuer_name',''))]
    for i, (lab, val) in enumerate(labels):
        x = 2*cm + (i * 4.3*cm)
        c.line(x, sig_y, x+3.5*cm, sig_y)
        c.setFont("ThaiFontBold", 12)
        c.drawCentredString(x+1.75*cm, sig_y-0.7*cm, f"({val if val else '.......................'})")
        c.drawCentredString(x+1.75*cm, sig_y-1.4*cm, lab)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= 4. MAIN UI =================
st.markdown("## 🚚 ใบกำกับขนส่งสินค้า") # ใหญ่กลาง
st.link_button("📊 ฐานข้อมูล", SHEET_URL, use_container_width=True, type="secondary")

with st.expander("🔍 ค้นหาและจัดการประวัติเอกสาร"):
    if not inv_df.empty:
        options = [f"{r['invoice_no']} | {r.get('comp_name','N/A')} | {r['customer']} | วันที่: {r['date']}" for _, r in inv_df.iterrows()]
        selected = st.selectbox("เลือกรายการประวัติ", [""] + options[::-1])
        if selected:
            sel_no = selected.split(" | ")[0]
            old_inv = inv_df[inv_df["invoice_no"] == sel_no].iloc[0].to_dict()
            old_items = item_df[item_df["invoice_no"] == sel_no].to_dict('records')
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("🔄 สร้างรายการซ้ำ"):
                    reset_form()
                    st.session_state.form_customer = old_inv.get("customer", "")
                    st.session_state.form_address = old_inv.get("address", "")
                    st.session_state.form_shipping = float(old_inv.get("shipping", 0))
                    st.session_state.form_discount = float(old_inv.get("discount", 0))
                    st.session_state.form_vat = float(old_inv.get("vat", 0))
                    st.session_state.form_subtotal = float(old_inv.get("subtotal", 0)) # โหลดค่า subtotal
                    st.session_state.form_total = float(old_inv.get("total", 0))       # โหลดค่า total
                    for f in transport_fields: st.session_state[f"form_{f}"] = str(old_inv.get(f, ""))
                    st.session_state.invoice_items = old_items
                    st.rerun()
            with c2:
                if st.button("📝 ดึงข้อมูลมาแก้ไข"):
                    st.session_state.editing_no = sel_no
                    st.session_state.form_customer = old_inv.get("customer", "")
                    st.session_state.form_address = old_inv.get("address", "")
                    st.session_state.form_shipping = float(old_inv.get("shipping", 0))
                    st.session_state.form_discount = float(old_inv.get("discount", 0))
                    st.session_state.form_vat = float(old_inv.get("vat", 0))
                    st.session_state.form_subtotal = float(old_inv.get("subtotal", 0)) # โหลดค่า subtotal
                    st.session_state.form_total = float(old_inv.get("total", 0))       # โหลดค่า total
                    for f in transport_fields: st.session_state[f"form_{f}"] = str(old_inv.get(f, ""))
                    st.session_state.invoice_items = old_items
                    st.success(f"กำลังแก้ไขบิลเลขที่: {sel_no}")
                    st.rerun()
            with c3: st.download_button(f"📥 PDF {sel_no}", create_pdf(old_inv, old_items), f"{sel_no}.pdf", use_container_width=True)
            with c4: st.download_button(f"📥 PDF V2 {sel_no}", create_pdf_v2(old_inv, old_items), f"{sel_no}_v2.pdf", use_container_width=True)
    else: st.info("ยังไม่มีข้อมูลในระบบ")

st.divider()

if st.session_state.editing_no:
    st.warning(f"🚨 กำลังอยู่ในโหมดแก้ไขเอกสารเลขที่: {st.session_state.editing_no}")
    if st.button("❌ ยกเลิกการแก้ไข"):
        reset_form()
        st.rerun()

st.subheader("📝 รายละเอียดเอกสาร")
tab1, tab2, tab3, tab4 = st.tabs(["👤 1.ข้อมูลลูกค้า", "🚛 2.การขนส่ง", "📦 3.ตรวจสอบ", "🏢 4.ข้อมูลบริษัท"])

with tab1:
    col1, col2 = st.columns(2)
    customer = col1.text_input("ชื่อลูกค้า", value=st.session_state.form_customer)
    address = col1.text_area("ที่อยู่ลูกค้า", value=st.session_state.form_address)
    doc_status = col2.selectbox("สถานะเอกสาร", ["รอดำเนินการ", "ยกเลิก", "ใช้งาน"], index=["รอดำเนินการ", "ยกเลิก", "ใช้งาน"].index(st.session_state.form_doc_status) if st.session_state.form_doc_status in ["รอดำเนินการ", "ยกเลิก", "ใช้งาน"] else 0)
    pay_status = col2.selectbox("สถานะการชำระ", ["ค้างชำระ", "ชำระแล้ว"], index=["ค้างชำระ", "ชำระแล้ว"].index(st.session_state.form_payment_status) if st.session_state.form_payment_status in ["ค้างชำระ", "ชำระแล้ว"] else 0)
    pay_term = col2.text_input("เงื่อนไขการชำระเงิน", value=st.session_state.form_pay_term)

with tab2:
    col3, col4, col5 = st.columns(3)
    car_id = col3.text_input("ทะเบียนรถ", value=st.session_state.form_car_id)
    driver_name = col3.text_input("ชื่อคนขับ", value=st.session_state.form_driver_name)
    driver_license = col3.text_input("ใบขับขี่", value=st.session_state.form_driver_license)
    date_out = col4.text_input("วันที่ออก (DD/MM/YYYY)", value=st.session_state.form_date_out)
    time_out = col4.text_input("เวลาออก", value=st.session_state.form_time_out)
    seal_no = col4.text_input("Seal No.", value=st.session_state.form_seal_no)
    date_in = col5.text_input("วันที่เข้า (DD/MM/YYYY)", value=st.session_state.form_date_in)
    time_in = col5.text_input("เวลาเข้า", value=st.session_state.form_time_in)
    ship_method = col5.text_input("วิธีการขนส่ง", value=st.session_state.form_ship_method)

with tab3:
    col6, col7, col8 = st.columns(3)
    ref_tax_id = col6.text_input("อ้างอิง Tax ID", value=st.session_state.form_ref_tax_id)
    ref_receipt_id = col6.text_input("อ้างอิง Receipt ID", value=st.session_state.form_ref_receipt_id)
    receiver_name = col7.text_input("ชื่อผู้รับสินค้า", value=st.session_state.form_receiver_name)
    issuer_name = col7.text_input("ชื่อผู้ออกบิล", value=st.session_state.form_issuer_name)
    sender_name = col8.text_input("ชื่อผู้ส่งสินค้า", value=st.session_state.form_sender_name)
    checker_name = col8.text_input("ชื่อผู้ตรวจสอบ", value=st.session_state.form_checker_name)
    remark = st.text_area("หมายเหตุเพิ่มเติม", value=st.session_state.form_remark)

with tab4:
    c_col1, c_col2 = st.columns(2)
    comp_name = c_col1.text_input("ชื่อบริษัท (หัว PDF)", value=st.session_state.form_comp_name)
    comp_tax_id = c_col1.text_input("เลขประจำตัวผู้เสียภาษีบริษัท", value=st.session_state.form_comp_tax_id)
    comp_doc_title = c_col1.text_input("ชื่อประเภทเอกสาร", value=st.session_state.form_comp_doc_title)
    comp_phone = c_col2.text_input("เบอร์โทรศัพท์บริษัท", value=st.session_state.form_comp_phone)
    comp_address = c_col2.text_area("ที่อยู่บริษัท", value=st.session_state.form_comp_address)

st.subheader("📦 บันทึกรายการสินค้า")
ci1, ci1_5, ci2, ci3 = st.columns([3, 1, 1, 1])
p_name = ci1.text_input("ชื่อสินค้า/บริการ")
p_unit = ci1_5.text_input("หน่วย")
p_qty = ci2.number_input("จำนวน", min_value=1)
p_price = ci3.number_input("ราคา/หน่วย", min_value=0.0)

if st.button("➕ เพิ่มรายการสินค้า"):
    if p_name:
        st.session_state.invoice_items.append({"product": p_name, "unit": p_unit, "qty": p_qty, "price": p_price, "amount": p_qty*p_price})
        st.rerun()

if st.session_state.invoice_items:
    for i, item in enumerate(st.session_state.invoice_items):
        cl = st.columns([5, 1])
        cl[0].info(f"{i+1}. {item['product']} ({item['qty']} {item['unit']}) - {item['amount']:,.2f}")
        if cl[1].button("🗑️", key=f"del_{i}"):
            st.session_state.invoice_items.pop(i)
            st.rerun()
    subtotal = sum(i['amount'] for i in st.session_state.invoice_items)
    f1, f2, f3 = st.columns(3)
    vat = f1.number_input("ภาษี (VAT)", value=st.session_state.form_vat)
    shipping = f2.number_input("ค่าขนส่ง", value=st.session_state.form_shipping)
    discount = f3.number_input("ส่วนลด", value=st.session_state.form_discount)
    grand_total = subtotal + vat + shipping - discount
    st.write(f"### ยอดรวมสุทธิ: {grand_total:,.2f} บาท")

# --- ส่วนบันทึกและแสดงปุ่ม PDF ---
btn_col1, btn_col2 = st.columns(2)

# ** ฟังก์ชันรวบรวมข้อมูลให้ลำดับตรงกับ Google Sheets **
def get_final_data(inv_no, date_val):
    return {
        "invoice_no": inv_no,
        "date": date_val,
        "customer": customer,
        "address": address,
        "subtotal": subtotal, # คอลัมน์ E
        "vat": vat,           # คอลัมน์ F
        "shipping": shipping, # คอลัมน์ G
        "discount": discount, # คอลัมน์ H
        "total": grand_total,  # คอลัมน์ I
        "doc_status": doc_status,
        "car_id": car_id,
        "driver_name": driver_name,
        "pay_status": pay_status,
        "date_out": date_out,
        "time_out": time_out,
        "date_in": date_in,
        "time_in": time_in,
        "ref_tax_id": ref_tax_id,
        "ref_receipt_id": ref_receipt_id,
        "seal_no": seal_no,
        "pay_term": pay_term,
        "ship_method": ship_method,
        "driver_license": driver_license,
        "receiver_name": receiver_name,
        "issuer_name": issuer_name,
        "sender_name": sender_name,
        "checker_name": checker_name,
        "remark": remark,
        "comp_name": comp_name,
        "comp_address": comp_address,
        "comp_tax_id": comp_tax_id,
        "comp_phone": comp_phone,
        "comp_doc_title": comp_doc_title
    }

if not st.session_state.editing_no:
    if btn_col1.button("💾 บันทึกข้อมูลใหม่", type="primary", use_container_width=True):
        if not customer or not comp_name: st.error("กรุณากรอกชื่อลูกค้าและข้อมูลบริษัทให้ครบถ้วน")
        else:
            with st.spinner("กำลังบันทึก..."):
                new_no = next_inv_no(inv_df)
                date_now = datetime.now().strftime("%d/%m/%Y")
                data_pdf = get_final_data(new_no, date_now)
                
                ws_inv.append_row(list(data_pdf.values()))
                for it in st.session_state.invoice_items: ws_item.append_row([new_no, it['product'], it.get('unit',''), it['qty'], it['price'], it['amount']])
                
                st.session_state.last_saved_data = {"inv": data_pdf, "items": list(st.session_state.invoice_items)}
                st.success(f"บันทึกสำเร็จ: {new_no}")
                st.cache_data.clear()
else:
    if btn_col1.button("✅ บันทึกการแก้ไข", type="primary", use_container_width=True):
        with st.spinner("กำลังอัปเดต..."):
            edit_no = st.session_state.editing_no
            cell = ws_inv.find(edit_no)
            row_idx = cell.row
            date_val = old_inv.get('date', datetime.now().strftime("%d/%m/%Y"))
            data_pdf = get_final_data(edit_no, date_val)
            
            # อัปเดตทั้งแถวเพื่อให้ลำดับข้อมูลถูกต้องตามคอลัมน์ A-AG
            ws_inv.update(f'A{row_idx}:AG{row_idx}', [list(data_pdf.values())])
            
            all_items = ws_item.get_all_values()
            new_item_sheet_data = [row for row in all_items if row[0] != edit_no]
            for it in st.session_state.invoice_items:
                new_item_sheet_data.append([edit_no, it['product'], it.get('unit',''), it['qty'], it['price'], it['amount']])
            ws_item.clear()
            ws_item.update('A1', new_item_sheet_data)
            
            st.session_state.last_saved_data = {"inv": data_pdf, "items": list(st.session_state.invoice_items)}
            st.success(f"อัปเดต {edit_no} สำเร็จ!")
            st.cache_data.clear()

if btn_col2.button("🧹 ล้างฟอร์ม", use_container_width=True):
    reset_form()
    st.rerun()

if st.session_state.last_saved_data:
    st.divider()
    st.subheader("📥 ดาวน์โหลดเอกสารที่เพิ่งบันทึก")
    pdf_inv = st.session_state.last_saved_data["inv"]
    pdf_items = st.session_state.last_saved_data["items"]
    p_col1, p_col2 = st.columns(2)
    p_col1.download_button("📥 PDF V1", create_pdf(pdf_inv, pdf_items), f"{pdf_inv['invoice_no']}_V1.pdf", use_container_width=True, type="secondary")
    p_col2.download_button("📥 PDF V2", create_pdf_v2(pdf_inv, pdf_items), f"{pdf_inv['invoice_no']}_V2.pdf", use_container_width=True, type="secondary")
