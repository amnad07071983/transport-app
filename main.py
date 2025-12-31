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

# ลงทะเบียนฟอนต์ภาษาไทย
try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except:
    st.error("⚠️ ไม่พบไฟล์ฟอนต์ 'THSARABUN BOLD.ttf' ในโฟลเดอร์หลัก")

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
transport_fields = [
    "doc_status", "car_id", "driver_name", "payment_status", "date_out", "time_out",
    "date_in", "time_in", "ref_tax_id", "ref_receipt_id", "seal_no",
    "pay_term", "ship_method", "driver_license", "receiver_name",
    "issuer_name", "sender_name", "checker_name", "remark"
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

# ================= 3. HELPER FUNCTIONS =================
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
    c.drawString(2*cm, h-3.2*cm, f"เลขที่: {inv.get('invoice_no','')}")
    c.drawString(2*cm, h-4*cm, f"วันที่: {inv.get('date','')}")
    c.drawString(2*cm, h-5.2*cm, f"ชื่อลูกค้า: {inv.get('customer','')}")
    c.drawString(2*cm, h-6*cm, f"ที่อยู่: {inv.get('address','')}")

    y = h - 8*cm
    c.line(2*cm, y, 19*cm, y)
    c.setFont("ThaiFontBold", 12)
    c.drawString(2.2*cm, y-0.6*cm, "รายการสินค้า")
    c.drawRightString(11*cm, y-0.6*cm, "หน่วย")
    c.drawRightString(13.5*cm, y-0.6*cm, "จำนวน")
    c.drawRightString(16*cm, y-0.6*cm, "ราคา/หน่วย")
    c.drawRightString(19*cm, y-0.6*cm, "รวมเงิน")
    c.line(2*cm, y-0.8*cm, 19*cm, y-0.8*cm)

    y -= 1.5*cm
    for it in items:
        c.drawString(2.2*cm, y, str(it.get("product", "")))
        c.drawRightString(11*cm, y, str(it.get("unit", "")))
        c.drawRightString(13.5*cm, y, f"{it.get('qty', 0):,}")
        c.drawRightString(16*cm, y, f"{float(it.get('price', 0)):,.2f}")
        c.drawRightString(19*cm, y, f"{float(it.get('amount', 0)):,.2f}")
        y -= 0.8*cm

    y_sum = y - 1*cm
    c.line(13*cm, y_sum+0.8*cm, 19*cm, y_sum+0.8*cm)
    c.setFont("ThaiFontBold", 13)
    c.drawString(13.5*cm, y_sum, f"ค่าขนส่ง: {float(inv.get('shipping', 0)):,.2f}")
    c.drawString(13.5*cm, y_sum-0.8*cm, f"ภาษี (VAT): {float(inv.get('vat', 0)):,.2f}")
    c.drawString(13.5*cm, y_sum-1.6*cm, f"ส่วนลด: {float(inv.get('discount', 0)):,.2f}")
    c.setFont("ThaiFontBold", 16)
    c.drawString(13.5*cm, y_sum-2.6*cm, f"ยอดสุทธิ: {float(inv.get('total', 0)):,.2f} บาท")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= 4. UI - MAIN =================
st.title("🚚 ระบบจัดการใบแจ้งหนี้ขนส่ง (Full 28 Columns)")

with st.expander("🔍 ค้นหา/พิมพ์ PDF ย้อนหลัง"):
    if not inv_df.empty:
        options = [f"{r['invoice_no']} | {r['customer']}" for _, r in inv_df.iterrows()]
        selected = st.selectbox("เลือกประวัติ", [""] + options[::-1])
        if selected:
            sel_no = selected.split(" | ")[0]
            old_inv = inv_df[inv_df["invoice_no"] == sel_no].iloc[0].to_dict()
            old_items = item_df[item_df["invoice_no"] == sel_no].to_dict('records')
            if st.button("🔄 ดึงข้อมูลกลับมาแก้ไข"):
                st.session_state.form_customer = old_inv.get("customer", "")
                st.session_state.form_address = old_inv.get("address", "")
                st.session_state.form_shipping = float(old_inv.get("shipping", 0))
                st.session_state.form_discount = float(old_inv.get("discount", 0))
                st.session_state.form_vat = float(old_inv.get("vat", 0))
                for field in transport_fields:
                    st.session_state[f"form_{field}"] = str(old_inv.get(field, ""))
                st.session_state.invoice_items = old_items
                st.rerun()
            pdf_old = create_pdf(old_inv, old_items)
            st.download_button(f"📥 Download PDF {sel_no}", pdf_old, f"{sel_no}.pdf")
    else:
        st.info("ยังไม่มีข้อมูล")

st.divider()

# --- ENTRY FORM ---
st.subheader("📝 รายละเอียดใบขนส่ง (28 Columns)")
tab1, tab2, tab3 = st.tabs(["👤 ข้อมูลลูกค้า", "🚛 การขนส่ง", "📦 การตรวจสอบ"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        customer = st.text_input("3. ชื่อลูกค้า", value=st.session_state.form_customer)
        address = st.text_area("4. ที่อยู่", value=st.session_state.form_address)
    with col2:
        doc_status = st.selectbox("10. สถานะเอกสาร", ["Active", "Cancelled", "Completed"], index=0)
        pay_status = st.selectbox("13. สถานะการชำระเงิน", ["ค้างชำระ", "ชำระแล้ว"], index=0 if st.session_state.form_payment_status != "ชำระแล้ว" else 1)
        pay_term = st.text_input("21. เงื่อนไขการชำระ", value=st.session_state.form_pay_term)

with tab2:
    col3, col4, col5 = st.columns(3)
    with col3:
        car_id = st.text_input("11. ทะเบียนรถ", value=st.session_state.form_car_id)
        driver_name = st.text_input("12. ชื่อคนขับ", value=st.session_state.form_driver_name)
        driver_license = st.text_input("23. ใบขับขี่", value=st.session_state.form_driver_license)
    with col4:
        date_out = st.text_input("14. วันที่ออก", value=st.session_state.form_date_out)
        time_out = st.text_input("15. เวลาออก", value=st.session_state.form_time_out)
        seal_no = st.text_input("20. Seal No.", value=st.session_state.form_seal_no)
    with col5:
        date_in = st.text_input("16. วันที่เข้า", value=st.session_state.form_date_in)
        time_in = st.text_input("17. เวลาเข้า", value=st.session_state.form_time_in)
        ship_method = st.text_input("22. วิธีการขนส่ง", value=st.session_state.form_ship_method)

with tab3:
    col6, col7, col8 = st.columns(3)
    with col6:
        ref_tax_id = st.text_input("18. อ้างอิง Tax ID", value=st.session_state.form_ref_tax_id)
        ref_receipt_id = st.text_input("19. อ้างอิง Receipt ID", value=st.session_state.form_ref_receipt_id)
    with col7:
        receiver_name = st.text_input("24. ชื่อผู้รับสินค้า", value=st.session_state.form_receiver_name)
        issuer_name = st.text_input("25. ชื่อผู้ออกบิล", value=st.session_state.form_issuer_name)
    with col8:
        sender_name = st.text_input("26. ชื่อผู้ส่งสินค้า", value=st.session_state.form_sender_name)
        checker_name = st.text_input("27. ชื่อผู้ตรวจสอบ", value=st.session_state.form_checker_name)
    remark = st.text_area("28. หมายเหตุ", value=st.session_state.form_remark)

st.subheader("📦 รายการสินค้า")
ci1, ci1_5, ci2, ci3 = st.columns([3, 1, 1, 1])
p_name = ci1.text_input("ชื่อสินค้า/บริการ", key="p_input")
p_unit = ci1_5.text_input("หน่วยนับ", placeholder="เช่น กล่อง", key="u_input")
p_qty = ci2.number_input("จำนวน", min_value=1, key="q_input")
p_price = ci3.number_input("ราคา/หน่วย", min_value=0.0, key="pr_input")

if st.button("➕ เพิ่มรายการสินค้า"):
    if p_name:
        st.session_state.invoice_items.append({
            "product": p_name, "unit": p_unit, "qty": p_qty, "price": p_price, "amount": p_qty*p_price
        })
        st.rerun()

if st.session_state.invoice_items:
    st.write("---")
    for i, item in enumerate(st.session_state.invoice_items):
        cl = st.columns([4, 1])
        # บรรทัดด้านล่างนี้ต้องย่อหน้าให้ตรงกับ if ด้านบน
        cl[0].info(f"{i+1}. {item['product']} | {item['qty']} {item.get('unit', '')} x {item['price']:,.2f} = {item['amount']:,.2f}")
        if cl[1].button("🗑️ ลบ", key=f"del_{i}"):
            st.session_state.invoice_items.pop(i)
            st.rerun()

    subtotal = sum(i['amount'] for i in st.session_state.invoice_items)
    f1, f2, f3 = st.columns(3)
    vat = f1.number_input("6. ภาษี (VAT)", value=st.session_state.form_vat)
    shipping = f2.number_input("7. ค่าขนส่ง", value=st.session_state.form_shipping)
    discount = f3.number_input("8. ส่วนลด", value=st.session_state.form_discount)
    grand_total = subtotal + vat + shipping - discount
    st.write(f"### 9. ยอดรวมสุทธิ: {grand_total:,.2f} บาท")

# ================= 5. SAVE & AUTO RESET =================
if st.button("✅ บันทึกข้อมูลและรับ PDF", type="primary"):
    if not customer:
        st.warning("กรุณากรอกชื่อลูกค้า")
    else:
        with st.spinner("กำลังบันทึกและสร้าง PDF..."):
            new_no = next_inv_no(inv_df)
            date_now = datetime.now().strftime("%d/%m/%Y")
            
            # 28 คอลัมน์สำหรับ Invoices
            final_row = [
                new_no, date_now, customer, address, subtotal, vat, shipping, discount, grand_total,
                doc_status, car_id, driver_name, pay_status, date_out, time_out, date_in, time_in,
                ref_tax_id, ref_receipt_id, seal_no, pay_term, ship_method, driver_license,
                receiver_name, issuer_name, sender_name, checker_name, remark
            ]

            try:
                # บันทึกลง Google Sheets
                ws_inv.append_row(final_row)
                for it in st.session_state.invoice_items:
                    # บันทึกลง InvoiceItems (เพิ่ม Unit)
                    ws_item.append_row([new_no, it['product'], it.get('unit',''), it['qty'], it['price'], it['amount']])

                # สร้าง PDF
                pdf_data = {
                    "invoice_no": new_no, "date": date_now, "customer": customer, "address": address,
                    "shipping": shipping, "vat": vat, "discount": discount, "total": grand_total
                }
                pdf_file = create_pdf(pdf_data, st.session_state.invoice_items)

                st.success(f"บันทึกสำเร็จ: {new_no}")
                st.download_button("📥 คลิกเพื่อดาวน์โหลด PDF", pdf_file, f"{new_no}.pdf", "application/pdf")
                
                # --- AUTO RESET LOGIC ---
                st.cache_data.clear()
                reset_form()
                st.info("ล้างข้อมูลในฟอร์มเรียบร้อยแล้ว พร้อมเริ่มรายการใหม่")
                # ------------------------

            except Exception as e:
                st.error(f"Error: {e}")
