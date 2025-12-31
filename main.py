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
st.set_page_config(page_title="Logistics Invoice System Pro", layout="wide")

# ลงทะเบียนฟอนต์ภาษาไทย (ต้องมีไฟล์ .ttf ในโปรเจกต์)
try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except:
    st.error("⚠️ ไม่พบไฟล์ฟอนต์ 'THSARABUN BOLD.ttf' กรุณาตรวจสอบการอัปโหลดไฟล์")

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

# เชื่อมต่อ Google Sheets
try:
    client = init_sheet()
    inv_df, item_df = get_data_cached()
    ws_inv = client.worksheet(INV_SHEET)
    ws_item = client.worksheet(ITEM_SHEET)
except:
    inv_df, item_df = pd.DataFrame(), pd.DataFrame()

# ================= 2. SESSION STATE & FORM RESET =================
def reset_form():
    st.session_state.invoice_items = []
    st.session_state.form_customer = ""
    st.session_state.form_address = ""
    st.session_state.form_shipping = 0.0
    st.session_state.form_discount = 0.0
    st.session_state.form_vat = 0.0
    # เคลียร์ฟิลด์อื่นๆ ทั้งหมด
    fields_to_clear = [
        "car_id", "driver_name", "date_out", "time_out", "date_in", "time_in",
        "ref_tax_id", "ref_receipt_id", "seal_no", "pay_term", "ship_method",
        "driver_license", "receiver_name", "issuer_name", "sender_name",
        "checker_name", "remark"
    ]
    for field in fields_to_clear:
        st.session_state[f"form_{field}"] = ""

if "invoice_items" not in st.session_state:
    reset_form()

# ================= 3. PDF GENERATOR =================
def create_pdf(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    
    # Header
    c.setFont("ThaiFontBold", 20)
    c.drawString(1.5*cm, h-1.5*cm, "ใบกำกับขนส่งสินค้า / Transportation Invoice")
    c.setFont("ThaiFontBold", 12)
    c.drawRightString(19.5*cm, h-1.5*cm, f"เลขที่ (No.): {inv.get('invoice_no','')}")
    c.drawRightString(19.5*cm, h-2.1*cm, f"วันที่ (Date): {inv.get('date','')}")

    # Section 1: Customer Info
    c.setFont("ThaiFontBold", 12)
    c.drawString(1.5*cm, h-3*cm, f"ลูกค้า: {inv.get('customer','')}")
    c.setFont("ThaiFontBold", 10)
    c.drawString(1.5*cm, h-3.6*cm, f"ที่อยู่: {inv.get('address','')}")
    c.drawString(1.5*cm, h-4.2*cm, f"Tax ID: {inv.get('ref_tax_id','-')} | Receipt ID: {inv.get('ref_receipt_id','-')}")

    # Section 2: Transport Box
    c.rect(1.5*cm, h-8*cm, 18*cm, 3.3*cm)
    c.setFont("ThaiFontBold", 10)
    # Column 1
    c.drawString(2*cm, h-5.2*cm, f"ทะเบียนรถ: {inv.get('car_id','')}")
    c.drawString(2*cm, h-5.8*cm, f"คนขับ: {inv.get('driver_name','')}")
    c.drawString(2*cm, h-6.4*cm, f"ใบขับขี่: {inv.get('driver_license','')}")
    c.drawString(2*cm, h-7*cm, f"การชำระ: {inv.get('pay_term','')}")
    # Column 2
    c.drawString(7.5*cm, h-5.2*cm, f"วันที่ออก: {inv.get('date_out','')} {inv.get('time_out','')}")
    c.drawString(7.5*cm, h-5.8*cm, f"วันที่เข้า: {inv.get('date_in','')} {inv.get('time_in','')}")
    c.drawString(7.5*cm, h-6.4*cm, f"วิธีขนส่ง: {inv.get('ship_method','')}")
    c.drawString(7.5*cm, h-7*cm, f"Seal No: {inv.get('seal_no','')}")
    # Column 3
    c.drawString(13.5*cm, h-5.2*cm, f"สถานะบิล: {inv.get('doc_status','')}")
    c.drawString(13.5*cm, h-5.8*cm, f"สถานะจ่ายเงิน: {inv.get('pay_status','')}")

    # Section 3: Table Header
    y = h - 9*cm
    c.setFont("ThaiFontBold", 11)
    c.drawString(1.7*cm, y, "ลำดับ")
    c.drawString(3*cm, y, "รายการสินค้า/บริการ")
    c.drawRightString(11*cm, y, "หน่วยนับ")
    c.drawRightString(13.5*cm, y, "จำนวน")
    c.drawRightString(16.5*cm, y, "ราคา/หน่วย")
    c.drawRightString(19.5*cm, y, "รวมเงิน")
    c.line(1.5*cm, y-0.2*cm, 19.5*cm, y-0.2*cm)

    # Table Items
    y -= 0.8*cm
    c.setFont("ThaiFontBold", 10)
    for i, it in enumerate(items):
        c.drawString(1.7*cm, y, str(i+1))
        c.drawString(3*cm, y, str(it.get("product", "")))
        c.drawRightString(11*cm, y, str(it.get("unit", "")))
        c.drawRightString(13.5*cm, y, f"{it.get('qty', 0):,}")
        c.drawRightString(16.5*cm, y, f"{float(it.get('price', 0)):,.2f}")
        c.drawRightString(19.5*cm, y, f"{float(it.get('amount', 0)):,.2f}")
        y -= 0.6*cm
        if y < 4*cm: c.showPage(); y = h - 2*cm

    # Section 4: Summary
    y_sum = y - 1*cm
    c.line(13*cm, y_sum+0.4*cm, 19.5*cm, y_sum+0.4*cm)
    c.drawString(13.5*cm, y_sum, "ราคารวมสินค้า:")
    c.drawRightString(19.5*cm, y_sum, f"{float(inv.get('subtotal', 0)):,.2f}")
    c.drawString(13.5*cm, y_sum-0.6*cm, "ค่าขนส่ง:")
    c.drawRightString(19.5*cm, y_sum-0.6*cm, f"{float(inv.get('shipping', 0)):,.2f}")
    c.drawString(13.5*cm, y_sum-1.2*cm, "ภาษี (VAT):")
    c.drawRightString(19.5*cm, y_sum-1.2*cm, f"{float(inv.get('vat', 0)):,.2f}")
    c.drawString(13.5*cm, y_sum-1.8*cm, "ส่วนลด:")
    c.drawRightString(19.5*cm, y_sum-1.8*cm, f"{float(inv.get('discount', 0)):,.2f}")
    c.setFont("ThaiFontBold", 14)
    c.drawString(13.5*cm, y_sum-2.6*cm, "ยอดรวมสุทธิ:")
    c.drawRightString(19.5*cm, y_sum-2.6*cm, f"{float(inv.get('total', 0)):,.2f} บาท")

    # Section 5: Signature
    y_sign = 2.5*cm
    c.setFont("ThaiFontBold", 9)
    signs = [
        (2*cm, f"ผู้รับสินค้า: {inv.get('receiver_name','-')}"),
        (6.5*cm, f"ผู้ส่งสินค้า: {inv.get('sender_name','-')}"),
        (11*cm, f"ผู้ตรวจสอบ: {inv.get('checker_name','-')}"),
        (15.5*cm, f"ผู้ออกบิล: {inv.get('issuer_name','-')}")
    ]
    for x, txt in signs:
        c.drawString(x, y_sign, "(____________________)")
        c.drawString(x, y_sign-0.5*cm, txt)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= 4. UI - ENTRY FORM =================
st.title("🚚 Logistics System Pro (28 Fields)")

tab1, tab2, tab3 = st.tabs(["👤 ข้อมูลลูกค้า", "🚛 การขนส่ง", "📦 การตรวจสอบ"])

with tab1:
    c1, c2 = st.columns(2)
    customer = c1.text_input("ชื่อลูกค้า", value=st.session_state.form_customer)
    address = c1.text_area("ที่อยู่", value=st.session_state.form_address)
    doc_status = c2.selectbox("สถานะเอกสาร", ["Active", "Cancelled"], index=0)
    pay_status = c2.selectbox("สถานะการจ่ายเงิน", ["ค้างชำระ", "ชำระแล้ว"], index=0)
    pay_term = c2.text_input("เงื่อนไขการชำระ", value=st.session_state.get("form_pay_term", ""))

with tab2:
    c3, c4, c5 = st.columns(3)
    car_id = c3.text_input("ทะเบียนรถ", value=st.session_state.get("form_car_id", ""))
    driver_name = c3.text_input("ชื่อคนขับ", value=st.session_state.get("form_driver_name", ""))
    driver_license = c3.text_input("ใบขับขี่", value=st.session_state.get("form_driver_license", ""))
    date_out = c4.text_input("วันที่ออก", value=st.session_state.get("form_date_out", ""))
    time_out = c4.text_input("เวลาออก", value=st.session_state.get("form_time_out", ""))
    seal_no = c4.text_input("Seal No.", value=st.session_state.get("form_seal_no", ""))
    date_in = c5.text_input("วันที่เข้า", value=st.session_state.get("form_date_in", ""))
    time_in = c5.text_input("เวลาเข้า", value=st.session_state.get("form_time_in", ""))
    ship_method = c5.text_input("วิธีขนส่ง", value=st.session_state.get("form_ship_method", ""))

with tab3:
    c6, c7, c8 = st.columns(3)
    ref_tax_id = c6.text_input("อ้างอิง Tax ID", value=st.session_state.get("form_ref_tax_id", ""))
    ref_receipt_id = c6.text_input("อ้างอิง Receipt ID", value=st.session_state.get("form_ref_receipt_id", ""))
    receiver_name = c7.text_input("ชื่อผู้รับสินค้า", value=st.session_state.get("form_receiver_name", ""))
    issuer_name = c7.text_input("ชื่อผู้ออกบิล", value=st.session_state.get("form_issuer_name", ""))
    sender_name = c8.text_input("ชื่อผู้ส่งสินค้า", value=st.session_state.get("form_sender_name", ""))
    checker_name = c8.text_input("ชื่อผู้ตรวจสอบ", value=st.session_state.get("form_checker_name", ""))
    remark = st.text_area("หมายเหตุ", value=st.session_state.get("form_remark", ""))

# Items Section
st.subheader("📦 รายการสินค้า")
ci1, ci1_5, ci2, ci3 = st.columns([3, 1, 1, 1])
p_name = ci1.text_input("ชื่อสินค้า/บริการ", key="p_input")
p_unit = ci1_5.text_input("หน่วยนับ", placeholder="เช่น กล่อง", key="u_input")
p_qty = ci2.number_input("จำนวน", min_value=1, key="q_input")
p_price = ci3.number_input("ราคา/หน่วย", min_value=0.0, key="pr_input")

if st.button("➕ เพิ่มรายการ"):
    if p_name:
        st.session_state.invoice_items.append({
            "product": p_name, "unit": p_unit, "qty": p_qty, "price": p_price, "amount": p_qty*p_price
        })
        st.rerun()

if st.session_state.invoice_items:
    st.write("---")
    for i, item in enumerate(st.session_state.invoice_items):
        cl = st.columns([4, 1])
        cl[0].info(f"{i+1}. {item['product']} | {item['qty']} {item.get('unit','')} x {item['price']:,.2f} = {item['amount']:,.2f}")
        if cl[1].button("🗑️ ลบ", key=f"del_{i}"):
            st.session_state.invoice_items.pop(i)
            st.rerun()

    subtotal = sum(i['amount'] for i in st.session_state.invoice_items)
    f1, f2, f3 = st.columns(3)
    vat = f1.number_input("ภาษี (VAT)", value=0.0)
    shipping = f2.number_input("ค่าขนส่ง", value=0.0)
    discount = f3.number_input("ส่วนลด", value=0.0)
    grand_total = subtotal + vat + shipping - discount
    st.write(f"### ยอดสุทธิ: {grand_total:,.2f} บาท")

# ================= 5. SAVE & RESET =================
if st.button("✅ บันทึกและออก PDF", type="primary"):
    if not customer:
        st.warning("กรุณากรอกชื่อลูกค้า")
    else:
        with st.spinner("กำลังบันทึก..."):
            def next_inv_no(df):
                if df.empty or "invoice_no" not in df.columns: return "INV-0001"
                last = df["invoice_no"].iloc[-1]
                try:
                    num = int(str(last).split('-')[1])
                    return f"INV-{num + 1:04d}"
                except: return "INV-0001"

            new_no = next_inv_no(inv_df)
            date_now = datetime.now().strftime("%d/%m/%Y")
            
            # บันทึก Invoices (28 คอลัมน์)
            final_row = [
                new_no, date_now, customer, address, subtotal, vat, shipping, discount, grand_total,
                doc_status, car_id, driver_name, pay_status, date_out, time_out, date_in, time_in,
                ref_tax_id, ref_receipt_id, seal_no, pay_term, ship_method, driver_license,
                receiver_name, issuer_name, sender_name, checker_name, remark
            ]

            try:
                ws_inv.append_row(final_row)
                for it in st.session_state.invoice_items:
                    ws_item.append_row([new_no, it['product'], it.get('unit',''), it['qty'], it['price'], it['amount']])

                pdf_data = {
                    "invoice_no": new_no, "date": date_now, "customer": customer, "address": address,
                    "subtotal": subtotal, "shipping": shipping, "vat": vat, "discount": discount, "total": grand_total,
                    "car_id": car_id, "driver_name": driver_name, "pay_status": pay_status, "doc_status": doc_status,
                    "date_out": date_out, "time_out": time_out, "date_in": date_in, "time_in": time_in,
                    "ref_tax_id": ref_tax_id, "ref_receipt_id": ref_receipt_id, "seal_no": seal_no,
                    "pay_term": pay_term, "ship_method": ship_method, "driver_license": driver_license,
                    "receiver_name": receiver_name, "issuer_name": issuer_name, "sender_name": sender_name,
                    "checker_name": checker_name, "remark": remark
                }
                pdf_file = create_pdf(pdf_data, st.session_state.invoice_items)

                st.success(f"บันทึกสำเร็จ เลขที่ {new_no}")
                st.download_button("📥 ดาวน์โหลด PDF", pdf_file, f"{new_no}.pdf", "application/pdf")
                
                st.cache_data.clear()
                reset_form()
                st.info("ล้างฟอร์มเรียบร้อย")
            except Exception as e:
                st.error(f"Error: {e}")
