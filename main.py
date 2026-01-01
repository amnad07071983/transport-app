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

# ลงทะเบียนฟอนต์ภาษาไทย (ต้องมีไฟล์ .ttf ในโฟลเดอร์เดียวกับโค้ด)
try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except:
    st.error("⚠️ ไม่พบไฟล์ฟอนต์ 'THSARABUN BOLD.ttf' กรุณาตรวจสอบไฟล์ในเซิร์ฟเวอร์")

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
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

# เชื่อมต่อข้อมูล
try:
    client = init_sheet()
    inv_df, item_df = get_data_cached()
    ws_inv = client.worksheet(INV_SHEET)
    ws_item = client.worksheet(ITEM_SHEET)
except:
    inv_df, item_df = pd.DataFrame(), pd.DataFrame()

# ================= 2. SESSION STATE & FORM RESET =================
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
    for field in transport_fields:
        st.session_state[f"form_{field}"] = ""
    st.session_state.form_doc_status = "Active"
    st.session_state.form_payment_status = "ค้างชำระ"

if "invoice_items" not in st.session_state:
    reset_form()

# ================= 3. CORE FUNCTIONS (NEW PDF DESIGN) =================
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
    
    # Theme Colors
    primary_color = colors.hexColor("#1B4F72") # น้ำเงินเข้ม
    bg_light = colors.hexColor("#F2F4F4")

    # --- Header: Company Branding ---
    c.setFillColor(primary_color)
    c.rect(0, h-3.2*cm, w, 3.2*cm, fill=1, stroke=0)
    
    c.setFillColor(colors.white)
    c.setFont("ThaiFontBold", 20)
    c.drawString(1.5*cm, h-1.2*cm, str(inv.get('comp_name', '')))
    
    c.setFont("ThaiFontBold", 10)
    c.drawString(1.5*cm, h-1.9*cm, f"ที่อยู่: {inv.get('comp_address', '')}")
    c.drawString(1.5*cm, h-2.4*cm, f"เลขประจำตัวผู้เสียภาษี: {inv.get('comp_tax_id', '')}  |  โทร: {inv.get('comp_phone', '')}")

    # Document Title Box
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.white)
    c.roundRect(14*cm, h-2.8*cm, 5.5*cm, 2.3*cm, 5, fill=1, stroke=1)
    
    c.setFillColor(primary_color)
    c.setFont("ThaiFontBold", 18)
    c.drawCentredString(16.75*cm, h-1.5*cm, str(inv.get('comp_doc_title', 'ใบกำกับขนส่ง')))
    c.setFont("ThaiFontBold", 11)
    c.drawCentredString(16.75*cm, h-2.2*cm, f"เลขที่: {inv.get('invoice_no','')} | วันที่: {inv.get('date','')}")

    # --- Customer & Logistics Info ---
    c.setFillColor(colors.black)
    c.setStrokeColor(primary_color)
    c.setLineWidth(1)
    c.roundRect(1.5*cm, h-7*cm, 18*cm, 3.2*cm, 5, stroke=1, fill=0)
    
    c.setFont("ThaiFontBold", 12)
    c.drawString(2*cm, h-4.4*cm, f"ลูกค้า (Customer): {inv.get('customer','')}")
    c.setFont("ThaiFontBold", 10)
    c.drawString(2*cm, h-5.1*cm, f"ที่อยู่: {inv.get('address','')}")
    c.drawString(2*cm, h-5.8*cm, f"Ref Tax ID: {inv.get('ref_tax_id','-')} | Ref Receipt: {inv.get('ref_receipt_id','-')}")

    # Transport Details Table
    transport_data = [
        [f"ทะเบียนรถ: {inv.get('car_id','')}", f"ออก: {inv.get('date_out','')} {inv.get('time_out','')}", f"สถานะบิล: {inv.get('doc_status','')}"],
        [f"คนขับ: {inv.get('driver_name','')}", f"เข้า: {inv.get('date_in','')} {inv.get('time_in','')}", f"การชำระ: {inv.get('pay_status','')}"],
        [f"ใบขับขี่: {inv.get('driver_license','')}", f"วิธีขนส่ง: {inv.get('ship_method','')}", f"Seal No: {inv.get('seal_no','-')}"]
    ]
    t_trans = Table(transport_data, colWidths=[6*cm, 6*cm, 6*cm])
    t_trans.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), 'ThaiFontBold', 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    t_trans.wrapOn(c, 1.5*cm, h-9.5*cm)
    t_trans.drawOn(c, 1.5*cm, h-9.5*cm)

    # --- Product Table ---
    item_header = [["ลำดับ", "รายการสินค้า/บริการ", "หน่วย", "จำนวน", "ราคา/หน่วย", "รวมเงิน"]]
    item_rows = []
    for i, it in enumerate(items):
        item_rows.append([i+1, it.get("product", ""), it.get("unit", ""), f"{it.get('qty', 0):,}", 
                          f"{float(it.get('price', 0)):,.2f}", f"{float(it.get('amount', 0)):,.2f}"])
    
    # ปรับแต่งตารางมาตรฐาน
    t_items = Table(item_header + item_rows, colWidths=[1.2*cm, 8.8*cm, 2*cm, 2*cm, 2*cm, 2*cm])
    t_items.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), 'ThaiFontBold', 10),
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (3,0), (5,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, bg_light])
    ]))
    tw, th = t_items.wrapOn(c, 1.5*cm, h-20*cm)
    t_y = h - 10.5*cm - th
    t_items.drawOn(c, 1.5*cm, t_y)

    # --- Financial Summary ---
    curr_y = t_y - 0.8*cm
    c.setFont("ThaiFontBold", 10)
    c.drawString(1.5*cm, curr_y, f"หมายเหตุ: {inv.get('remark','-')}")
    
    # Summary Box
    c.setStrokeColor(primary_color)
    c.rect(13.5*cm, curr_y - 3*cm, 6*cm, 3.2*cm, stroke=1, fill=0)
    
    label_x = 16.5*cm
    val_x = 19.2*cm
    c.drawRightString(label_x, curr_y - 0.6*cm, "ค่าขนส่ง:")
    c.drawRightString(val_x, curr_y - 0.6*cm, f"{float(inv.get('shipping', 0)):,.2f}")
    c.drawRightString(label_x, curr_y - 1.2*cm, "ภาษี (VAT):")
    c.drawRightString(val_x, curr_y - 1.2*cm, f"{float(inv.get('vat', 0)):,.2f}")
    c.drawRightString(label_x, curr_y - 1.8*cm, "ส่วนลด:")
    c.drawRightString(val_x, curr_y - 1.8*cm, f"{float(inv.get('discount', 0)):,.2f}")
    
    c.setFont("ThaiFontBold", 14)
    c.setFillColor(primary_color)
    c.drawRightString(label_x, curr_y - 2.6*cm, "ยอดสุทธิ:")
    c.drawRightString(val_x, curr_y - 2.6*cm, f"{float(inv.get('total', 0)):,.2f} บาท")

    # --- Signatures ---
    sig_y = 2.5*cm
    c.setFillColor(colors.black)
    labels = [("ผู้รับสินค้า", inv.get('receiver_name','')), ("ผู้ส่งสินค้า", inv.get('sender_name','')), 
              ("ผู้ตรวจสอบ", inv.get('checker_name','')), ("ผู้ออกบิล", inv.get('issuer_name',''))]
    for i, (lab, val) in enumerate(labels):
        x = 1.5*cm + (i * 4.6*cm)
        c.line(x, sig_y, x+4*cm, sig_y)
        c.setFont("ThaiFontBold", 9)
        c.drawCentredString(x+2*cm, sig_y-0.5*cm, f"({val if val else '.......................'})")
        c.drawCentredString(x+2*cm, sig_y-1.0*cm, lab)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= 4. MAIN UI =================
st.title("🚚 ระบบจัดการใบแจ้งหนี้และขนส่งสินค้า")

# ส่วนค้นหาและพิมพ์ PDF ย้อนหลัง
with st.expander("🔍 ค้นหาและจัดการประวัติเอกสาร"):
    if not inv_df.empty:
        options = [f"{r['invoice_no']} | {r['customer']}" for _, r in inv_df.iterrows()]
        selected = st.selectbox("เลือกรายการประวัติ", [""] + options[::-1])
        if selected:
            sel_no = selected.split(" | ")[0]
            old_inv = inv_df[inv_df["invoice_no"] == sel_no].iloc[0].to_dict()
            old_items = item_df[item_df["invoice_no"] == sel_no].to_dict('records')
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔄 ดึงข้อมูลกลับมาแก้ไข"):
                    st.session_state.form_customer = old_inv.get("customer", "")
                    st.session_state.form_address = old_inv.get("address", "")
                    st.session_state.form_shipping = float(old_inv.get("shipping", 0))
                    st.session_state.form_discount = float(old_inv.get("discount", 0))
                    st.session_state.form_vat = float(old_inv.get("vat", 0))
                    for f in transport_fields: st.session_state[f"form_{f}"] = str(old_inv.get(f, ""))
                    st.session_state.invoice_items = old_items
                    st.rerun()
            with c2:
                st.download_button(f"📥 ดาวน์โหลด PDF {sel_no}", create_pdf(old_inv, old_items), f"{sel_no}.pdf")
    else:
        st.info("ยังไม่มีข้อมูลในระบบ")

st.divider()

# --- ส่วนของการกรอกข้อมูล ---
st.subheader("📝 สร้างใบขนส่งใหม่")
tab1, tab2, tab3, tab4 = st.tabs(["👤 ข้อมูลลูกค้า", "🚛 การขนส่ง", "📦 ตรวจสอบ/ลายเซ็น", "🏢 ข้อมูลบริษัท"])

with tab1:
    col1, col2 = st.columns(2)
    customer = col1.text_input("ชื่อลูกค้า", value=st.session_state.form_customer)
    address = col1.text_area("ที่อยู่ลูกค้า", value=st.session_state.form_address)
    doc_status = col2.selectbox("สถานะเอกสาร", ["Active", "Cancelled", "Completed"], index=0)
    pay_status = col2.selectbox("สถานะการชำระ", ["ค้างชำระ", "ชำระแล้ว"], index=0)
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
    comp_doc_title = c_col1.text_input("ชื่อประเภทเอกสาร (เช่น ใบกำกับขนส่ง)", value=st.session_state.form_comp_doc_title)
    comp_phone = c_col2.text_input("เบอร์โทรศัพท์บริษัท", value=st.session_state.form_comp_phone)
    comp_address = c_col2.text_area("ที่อยู่บริษัท", value=st.session_state.form_comp_address)

st.subheader("📦 รายการสินค้า")
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

if st.button("💾 บันทึกและออกเอกสาร", type="primary"):
    if not customer or not comp_name:
        st.error("กรุณากรอกชื่อลูกค้าและข้อมูลบริษัทให้ครบถ้วน")
    else:
        with st.spinner("กำลังประมวลผล..."):
            new_no = next_inv_no(inv_df)
            date_now = datetime.now().strftime("%d/%m/%Y")
            # บันทึกลง Google Sheets
            ws_inv.append_row([new_no, date_now, customer, address, subtotal, vat, shipping, discount, grand_total, doc_status, car_id, driver_name, pay_status, date_out, time_out, date_in, time_in, ref_tax_id, ref_receipt_id, seal_no, pay_term, ship_method, driver_license, receiver_name, issuer_name, sender_name, checker_name, remark, comp_name, comp_address, comp_tax_id, comp_phone, comp_doc_title])
            for it in st.session_state.invoice_items:
                ws_item.append_row([new_no, it['product'], it.get('unit',''), it['qty'], it['price'], it['amount']])
            
            pdf_data = {"invoice_no": new_no, "date": date_now, "customer": customer, "address": address, "shipping": shipping, "vat": vat, "discount": discount, "total": grand_total, "ref_tax_id": ref_tax_id, "ref_receipt_id": ref_receipt_id, "car_id": car_id, "driver_name": driver_name, "driver_license": driver_license, "date_out": date_out, "time_out": time_out, "date_in": date_in, "time_in": time_in, "seal_no": seal_no, "ship_method": ship_method, "pay_term": pay_term, "doc_status": doc_status, "pay_status": pay_status, "receiver_name": receiver_name, "sender_name": sender_name, "checker_name": checker_name, "issuer_name": issuer_name, "remark": remark, "comp_name": comp_name, "comp_address": comp_address, "comp_tax_id": comp_tax_id, "comp_phone": comp_phone, "comp_doc_title": comp_doc_title}
            st.success(f"บันทึกสำเร็จ: {new_no}")
            st.download_button("📥 ดาวน์โหลด PDF", create_pdf(pdf_data, st.session_state.invoice_items), f"{new_no}.pdf")
            st.cache_data.clear()
            reset_form()
