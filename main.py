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

# ================= 2. SESSION STATE & RESET =================
# เพิ่มฟิลด์บริษัท 5 ฟิลด์ (29-33) เข้าไปในระบบ Session
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

# ================= 3. PDF GENERATOR (โครงสร้างเดิม + ฟิลด์ใหม่) =================
def create_pdf(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    
    # --- [เพิ่มใหม่] ส่วนหัวกระดาษ: ข้อมูลบริษัท (Header) ---
    c.setFont("ThaiFontBold", 16)
    c.drawString(2*cm, h-1.5*cm, inv.get('comp_name', '')) # 29
    c.setFont("ThaiFontBold", 10)
    c.drawString(2*cm, h-2.1*cm, f"ที่อยู่: {inv.get('comp_address', '')}") # 30
    c.drawString(2*cm, h-2.6*cm, f"เลขประจำตัวผู้เสียภาษี: {inv.get('comp_tax_id', '')}  โทร: {inv.get('comp_phone', '')}") # 31, 32
    
    c.setFont("ThaiFontBold", 20)
    c.drawRightString(19*cm, h-1.5*cm, inv.get('comp_doc_title', 'ใบกำกับขนส่งสินค้า')) # 33
    
    # --- โครงสร้างเดิม (ปรับพิกัด Y ลงมาเล็กน้อยเพื่อไม่ให้ทับหัวกระดาษ) ---
    c.setFont("ThaiFontBold", 12)
    c.drawRightString(19*cm, h-2.2*cm, f"เลขที่: {inv.get('invoice_no','')}")
    c.drawRightString(19*cm, h-2.8*cm, f"วันที่: {inv.get('date','')}")

    c.setFont("ThaiFontBold", 13)
    c.drawString(2*cm, h-4.2*cm, f"ชื่อลูกค้า: {inv.get('customer','')}")
    c.setFont("ThaiFontBold", 11)
    c.drawString(2*cm, h-4.8*cm, f"ที่อยู่: {inv.get('address','')}")
    c.drawString(2*cm, h-5.4*cm, f"Ref Tax ID: {inv.get('ref_tax_id','-')} | Ref Receipt: {inv.get('ref_receipt_id','-')}")

    # Transport Box (โครงสร้างเดิมเป๊ะ)
    c.rect(2*cm, h-9.2*cm, 17*cm, 3.3*cm)
    c.setFont("ThaiFontBold", 10)
    c.drawString(2.5*cm, h-6.4*cm, f"ทะเบียนรถ: {inv.get('car_id','')}")
    c.drawString(2.5*cm, h-7.0*cm, f"ชื่อคนขับ: {inv.get('driver_name','')}")
    c.drawString(2.5*cm, h-7.6*cm, f"ใบขับขี่: {inv.get('driver_license','')}")
    c.drawString(2.5*cm, h-8.2*cm, f"เงื่อนไขชำระ: {inv.get('pay_term','')}")
    c.drawString(8.5*cm, h-6.4*cm, f"ออก: {inv.get('date_out','')} {inv.get('time_out','')}")
    c.drawString(8.5*cm, h-7.0*cm, f"เข้า: {inv.get('date_in','')} {inv.get('time_in','')}")
    c.drawString(8.5*cm, h-7.6*cm, f"วิธีขนส่ง: {inv.get('ship_method','')}")
    c.drawString(8.5*cm, h-8.2*cm, f"Seal No: {inv.get('seal_no','')}")
    c.drawString(14.5*cm, h-6.4*cm, f"สถานะบิล: {inv.get('doc_status','')}")
    c.drawString(14.5*cm, h-7.0*cm, f"การชำระ: {inv.get('pay_status','')}")

    # ตารางรายการสินค้า (โครงสร้างเดิมเป๊ะ)
    y = h - 10.2*cm
    c.setFont("ThaiFontBold", 12)
    c.drawString(2.2*cm, y, "รายการสินค้า")
    c.drawRightString(11*cm, y, "หน่วย")
    c.drawRightString(13.5*cm, y, "จำนวน")
    c.drawRightString(16*cm, y, "ราคา/หน่วย")
    c.drawRightString(19*cm, y, "รวมเงิน")
    c.line(2*cm, y-0.2*cm, 19*cm, y-0.2*cm)

    y -= 0.8*cm
    c.setFont("ThaiFontBold", 11)
    for it in items:
        c.drawString(2.2*cm, y, str(it.get("product", "")))
        c.drawRightString(11*cm, y, str(it.get("unit", "")))
        c.drawRightString(13.5*cm, y, f"{it.get('qty', 0):,}")
        c.drawRightString(16*cm, y, f"{float(it.get('price', 0)):,.2f}")
        c.drawRightString(19*cm, y, f"{float(it.get('amount', 0)):,.2f}")
        y -= 0.7*cm

    # สรุปยอดเงิน (โครงสร้างเดิมเป๊ะ)
    y_sum = y - 1*cm
    c.line(13*cm, y_sum+0.8*cm, 19*cm, y_sum+0.8*cm)
    c.setFont("ThaiFontBold", 11)
    c.drawString(13.5*cm, y_sum, f"ค่าขนส่ง: {float(inv.get('shipping', 0)):,.2f}")
    c.drawString(13.5*cm, y_sum-0.6*cm, f"ภาษี (VAT): {float(inv.get('vat', 0)):,.2f}")
    c.drawString(13.5*cm, y_sum-1.2*cm, f"ส่วนลด: {float(inv.get('discount', 0)):,.2f}")
    c.setFont("ThaiFontBold", 14)
    c.drawString(13.5*cm, y_sum-2.2*cm, f"ยอดสุทธิ: {float(inv.get('total', 0)):,.2f} บาท")

    # ลายเซ็น (โครงสร้างเดิมเป๊ะ)
    c.setFont("ThaiFontBold", 10)
    c.drawString(2*cm, y_sum-0.5*cm, f"หมายเหตุ: {inv.get('remark','-')}")
    y_sign = 3.5*cm
    c.drawString(2*cm, y_sign, f"ผู้รับสินค้า: {inv.get('receiver_name','________________')}")
    c.drawString(7*cm, y_sign, f"ผู้ส่งสินค้า: {inv.get('sender_name','________________')}")
    c.drawString(11.5*cm, y_sign, f"ผู้ตรวจสอบ: {inv.get('checker_name','________________')}")
    c.drawString(15.5*cm, y_sign, f"ผู้ออกบิล: {inv.get('issuer_name','________________')}")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= 4. UI - MAIN =================
st.title("🚚 ระบบจัดการใบแจ้งหนี้ขนส่ง (33 Columns)")

# --- ENTRY FORM ---
tab1, tab2, tab3, tab4 = st.tabs(["👤 ข้อมูลลูกค้า", "🚛 การขนส่ง", "📦 การตรวจสอบ", "🏢 ข้อมูลบริษัท"])

with tab1:
    col1, col2 = st.columns(2)
    customer = col1.text_input("3. ชื่อลูกค้า", value=st.session_state.form_customer)
    address = col1.text_area("4. ที่อยู่", value=st.session_state.form_address)
    doc_status = col2.selectbox("10. สถานะเอกสาร", ["Active", "Cancelled", "Completed"], index=0)
    pay_status = col2.selectbox("13. สถานะการชำระเงิน", ["ค้างชำระ", "ชำระแล้ว"], index=0)
    pay_term = col2.text_input("21. เงื่อนไขการชำระ", value=st.session_state.form_pay_term)

with tab2:
    col3, col4, col5 = st.columns(3)
    car_id = col3.text_input("11. ทะเบียนรถ", value=st.session_state.form_car_id)
    driver_name = col3.text_input("12. ชื่อคนขับ", value=st.session_state.form_driver_name)
    driver_license = col3.text_input("23. ใบขับขี่", value=st.session_state.form_driver_license)
    date_out = col4.text_input("14. วันที่ออก", value=st.session_state.form_date_out)
    time_out = col4.text_input("15. เวลาออก", value=st.session_state.form_time_out)
    seal_no = col4.text_input("20. Seal No.", value=st.session_state.form_seal_no)
    date_in = col5.text_input("16. วันที่เข้า", value=st.session_state.form_date_in)
    time_in = col5.text_input("17. เวลาเข้า", value=st.session_state.form_time_in)
    ship_method = col5.text_input("22. วิธีการขนส่ง", value=st.session_state.form_ship_method)

with tab3:
    col6, col7, col8 = st.columns(3)
    ref_tax_id = col6.text_input("18. อ้างอิง Tax ID", value=st.session_state.form_ref_tax_id)
    ref_receipt_id = col6.text_input("19. อ้างอิง Receipt ID", value=st.session_state.form_ref_receipt_id)
    receiver_name = col7.text_input("24. ชื่อผู้รับสินค้า", value=st.session_state.form_receiver_name)
    issuer_name = col7.text_input("25. ชื่อผู้ออกบิล", value=st.session_state.form_issuer_name)
    sender_name = col8.text_input("26. ชื่อผู้ส่งสินค้า", value=st.session_state.form_sender_name)
    checker_name = col8.text_input("27. ชื่อผู้ตรวจสอบ", value=st.session_state.form_checker_name)
    remark = st.text_area("28. หมายเหตุ", value=st.session_state.form_remark)

with tab4:
    st.info("🏢 ข้อมูลบริษัทสำหรับหัวกระดาษ")
    c1, c2 = st.columns(2)
    comp_name = c1.text_input("29. บริษัท-ชื่อ", value=st.session_state.form_comp_name)
    comp_tax_id = c1.text_input("31. บริษัท-เลขประจำตัวผู้เสียภาษี", value=st.session_state.form_comp_tax_id)
    comp_doc_title = c1.text_input("33. บริษัท-ชื่อเอกสาร", value=st.session_state.form_comp_doc_title)
    comp_phone = c2.text_input("32. บริษัท-เบอร์โทร", value=st.session_state.form_comp_phone)
    comp_address = c2.text_area("30. บริษัท-ที่อยู่", value=st.session_state.form_comp_address)

# ส่วนรายการสินค้า (เหมือนเดิม)
st.subheader("📦 รายการสินค้า")
ci1, ci1_5, ci2, ci3 = st.columns([3, 1, 1, 1])
p_name = ci1.text_input("ชื่อสินค้า/บริการ", key="p_input")
p_unit = ci1_5.text_input("หน่วยนับ", key="u_input")
p_qty = ci2.number_input("จำนวน", min_value=1, key="q_input")
p_price = ci3.number_input("ราคา/หน่วย", min_value=0.0, key="pr_input")

if st.button("➕ เพิ่มรายการสินค้า"):
    if p_name:
        st.session_state.invoice_items.append({"product": p_name, "unit": p_unit, "qty": p_qty, "price": p_price, "amount": p_qty*p_price})
        st.rerun()

subtotal = sum(i['amount'] for i in st.session_state.invoice_items)
f1, f2, f3 = st.columns(3)
vat = f1.number_input("6. ภาษี (VAT)", value=st.session_state.form_vat)
shipping = f2.number_input("7. ค่าขนส่ง", value=st.session_state.form_shipping)
discount = f3.number_input("8. ส่วนลด", value=st.session_state.form_discount)
grand_total = subtotal + vat + shipping - discount

# ================= 5. SAVE & PDF =================
if st.button("✅ บันทึกข้อมูลและรับ PDF", type="primary"):
    if not customer or not comp_name:
        st.warning("กรุณากรอกชื่อลูกค้าและชื่อบริษัท")
    else:
        with st.spinner("กำลังประมวลผล..."):
            def get_next_no(df):
                if df.empty or "invoice_no" not in df.columns: return "INV-0001"
                try: return f"INV-{int(str(df['invoice_no'].iloc[-1]).split('-')[1]) + 1:04d}"
                except: return "INV-0001"
            
            new_no = get_next_no(inv_df)
            date_now = datetime.now().strftime("%d/%m/%Y")
            
            # บันทึก 33 คอลัมน์ลง Sheets
            final_row = [
                new_no, date_now, customer, address, subtotal, vat, shipping, discount, grand_total,
                doc_status, car_id, driver_name, pay_status, date_out, time_out, date_in, time_in,
                ref_tax_id, ref_receipt_id, seal_no, pay_term, ship_method, driver_license,
                receiver_name, issuer_name, sender_name, checker_name, remark,
                comp_name, comp_address, comp_tax_id, comp_phone, comp_doc_title
            ]

            ws_inv.append_row(final_row)
            for it in st.session_state.invoice_items:
                ws_item.append_row([new_no, it['product'], it.get('unit',''), it['qty'], it['price'], it['amount']])

            # ส่งข้อมูลไป PDF
            pdf_data = {
                "invoice_no": new_no, "date": date_now, "customer": customer, "address": address,
                "shipping": shipping, "vat": vat, "discount": discount, "total": grand_total,
                "ref_tax_id": ref_tax_id, "ref_receipt_id": ref_receipt_id, "car_id": car_id,
                "driver_name": driver_name, "driver_license": driver_license, "date_out": date_out,
                "time_out": time_out, "date_in": date_in, "time_in": time_in, "seal_no": seal_no,
                "ship_method": ship_method, "pay_term": pay_term, "doc_status": doc_status,
                "pay_status": pay_status, "receiver_name": receiver_name, "sender_name": sender_name,
                "checker_name": checker_name, "issuer_name": issuer_name, "remark": remark,
                "comp_name": comp_name, "comp_address": comp_address, "comp_tax_id": comp_tax_id,
                "comp_phone": comp_phone, "comp_doc_title": comp_doc_title
            }
            
            pdf_file = create_pdf(pdf_data, st.session_state.invoice_items)
            st.success(f"บันทึกสำเร็จ: {new_no}")
            st.download_button("📥 ดาวน์โหลด PDF", pdf_file, f"{new_no}.pdf")
            reset_form()
            st.cache_data.clear()
