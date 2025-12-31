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
st.set_page_config(page_title="Logistics Pro (Optimized)", layout="wide")

# Register Thai Font
try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except Exception as e:
    st.error(f"⚠️ ไม่พบไฟล์ฟอนต์: 'THSARABUN BOLD.ttf'")

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INV_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

# ================= GOOGLE SHEET & CACHING =================
@st.cache_resource
def init_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds).open_by_key(SHEET_ID)

@st.cache_data(ttl=120)  # จำข้อมูลไว้ 2 นาทีเพื่อป้องกัน Quota 429
def get_cached_data():
    client = init_sheet()
    inv_data = client.worksheet(INV_SHEET).get_all_records()
    item_data = client.worksheet(ITEM_SHEET).get_all_records()
    return pd.DataFrame(inv_data), pd.DataFrame(item_data)

try:
    sheet_client = init_sheet()
    inv_df, item_df = get_cached_data()
    ws_inv = sheet_client.worksheet(INV_SHEET)
    ws_item = sheet_client.worksheet(ITEM_SHEET)
except Exception as e:
    st.error(f"การเชื่อมต่อ Google Sheets ติดปัญหา: {e}")
    inv_df, item_df = pd.DataFrame(), pd.DataFrame()

# ================= SESSION STATE =================
defaults = {
    "invoice_items": [], "customer": "", "address": "", "shipping": 0.0, "discount": 0.0,
    "my_company": "ชื่อบริษัทของคุณ", "my_address": "ที่อยู่บริษัทของคุณ...", "my_phone": "08x-xxxxxxx",
    "car_id": "", "driver_name": "", "pay_status": "ค้างชำระ",
    "date_out": "", "time_out": "", "date_in": "", "time_in": "",
    "ref_tax_id": "", "ref_rec_id": "", "seal_no": "", "pay_term": "เงินสด",
    "ship_method": "รถบรรทุก", "driver_license": "", "receiver_name": "",
    "issuer_name": "", "sender_name": "", "checker_name": "", "remark": ""
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ================= PDF CREATOR =================
def create_pdf(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("ThaiFontBold", 16)
    c.drawString(2*cm, h-1.5*cm, st.session_state.my_company)
    c.setFont("ThaiFontBold", 20)
    c.drawRightString(19*cm, h-1.5*cm, "ใบกำกับขนส่งสินค้า")
    c.setFont("ThaiFontBold", 11)
    c.drawString(2*cm, h-2.1*cm, f"ที่อยู่: {st.session_state.my_address} โทร: {st.session_state.my_phone}")
    c.drawRightString(19*cm, h-2.1*cm, f"เลขที่: {inv['invoice_no']}  วันที่: {inv['date']}")
    c.line(2*cm, h-2.3*cm, 19*cm, h-2.3*cm)
    
    # Details Section
    c.setFont("ThaiFontBold", 11)
    c.drawString(2*cm, h-3*cm, f"ลูกค้า: {inv['customer']}")
    c.drawString(11*cm, h-3*cm, f"ทะเบียนรถ: {inv.get('car_id','')} | คนขับ: {inv.get('driver_name','')}")
    c.drawString(2*cm, h-3.6*cm, f"ที่อยู่จัดส่ง: {inv.get('address','')[:70]}")
    c.drawString(11*cm, h-3.6*cm, f"เลขใบขับขี่: {inv.get('driver_license','')}")
    
    c.drawString(2*cm, h-4.3*cm, f"ออก: {inv.get('date_out','')} {inv.get('time_out','')} | ถึง: {inv.get('date_in','')} {inv.get('time_in','')}")
    c.drawString(11*cm, h-4.3*cm, f"Seal No: {inv.get('seal_no','')} | ขนส่งโดย: {inv.get('ship_method','')}")
    
    c.drawString(2*cm, h-4.9*cm, f"อ้างอิงภาษี: {inv.get('ref_tax_id','')} | อ้างอิงใบเสร็จ: {inv.get('ref_rec_id','')}")
    c.drawString(11*cm, h-4.9*cm, f"เงื่อนไขชำระ: {inv.get('pay_term','')} | สถานะ: {inv.get('pay_status','')}")

    # Table
    y = h - 6*cm
    c.setFont("ThaiFontBold", 12)
    c.drawString(2*cm, y, "รายการสินค้า")
    c.drawRightString(19*cm, y, "รวมเงิน")
    c.line(2*cm, y-0.2*cm, 19*cm, y-0.2*cm)
    y -= 0.7*cm
    for it in items:
        c.drawString(2*cm, y, f"{it['product']} (x{it['qty']})")
        c.drawRightString(19*cm, y, f"{float(it['amount']):,.2f}")
        y -= 0.6*cm
        
    y_sum = y - 1*cm
    c.setFont("ThaiFontBold", 14)
    c.drawRightString(16*cm, y_sum, "ยอดรวมสุทธิ:")
    c.drawRightString(19*cm, y_sum, f"{float(inv.get('total',0)):,.2f} บาท")
    
    c.save()
    buf.seek(0)
    return buf

# ================= UI =================
st.title("🚚 ระบบจัดการการขนส่ง (Fixed Quota)")

tab1, tab2 = st.tabs(["📝 ออกใบกำกับ", "⚙️ ตั้งค่า"])

with tab2:
    st.session_state.my_company = st.text_input("ชื่อบริษัท", st.session_state.my_company)
    st.session_state.my_address = st.text_area("ที่อยู่", st.session_state.my_address)
    st.session_state.my_phone = st.text_input("โทร", st.session_state.my_phone)

with tab1:
    with st.expander("🔍 ดูประวัติ / Duplicate (ลดการดึงข้อมูล API)"):
        if not inv_df.empty:
            invoice_options = [f"{r['invoice_no']} | {r['customer']}" for _, r in inv_df.iterrows()]
            selected = st.selectbox("เลือกรายการ", [""] + invoice_options[::-1])
            if selected and st.button("📄 โหลดข้อมูล"):
                sel_no = selected.split(" | ")[0]
                row = inv_df[inv_df["invoice_no"] == sel_no].iloc[0]
                for k in defaults.keys():
                    if k in row: st.session_state[k] = row[k]
                st.rerun()
        else:
            st.info("ไม่มีข้อมูลในระบบ หรือ API กำลังรีเซ็ต Quota")

    # Form Fields
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.customer = st.text_input("ชื่อลูกค้า", st.session_state.customer)
        st.session_state.address = st.text_area("ที่อยู่", st.session_state.address)
        st.session_state.car_id = st.text_input("ทะเบียนรถ", st.session_state.car_id)
        st.session_state.driver_name = st.text_input("คนขับ", st.session_state.driver_name)
    with c2:
        st.session_state.date_out = st.text_input("วันที่ออก (วว/ดด/ปป)", st.session_state.date_out)
        st.session_state.time_out = st.text_input("เวลาออก", st.session_state.time_out)
        st.session_state.pay_status = st.selectbox("สถานะ", ["ค้างชำระ", "ชำระแล้ว"])
        st.session_state.remark = st.text_area("หมายเหตุ", st.session_state.remark)

    # Item Table with Delete Function
    st.subheader("📦 รายการสินค้า")
    ci1, ci2, ci3 = st.columns([3,1,1])
    p_name = ci1.text_input("ชื่อสินค้า")
    p_qty = ci2.number_input("จำนวน", min_value=1, value=1)
    p_price = ci3.number_input("ราคา", min_value=0.0, value=0.0)
    
    if st.button("➕ เพิ่ม"):
        if p_name:
            st.session_state.invoice_items.append({"product": p_name, "qty": p_qty, "price": p_price, "amount": p_qty*p_price})
            st.rerun()

    if st.session_state.invoice_items:
        for i, item in enumerate(st.session_state.invoice_items):
            col_t1, col_t2 = st.columns([0.9, 0.1])
            col_t1.info(f"{i+1}. {item['product']} | {item['qty']} x {item['price']:,.2f} = {item['amount']:,.2f}")
            if col_t2.button("🗑️", key=f"del_{i}"):
                st.session_state.invoice_items.pop(i)
                st.rerun()

        total = sum(i['amount'] for i in st.session_state.invoice_items) + st.session_state.shipping - st.session_state.discount
        st.write(f"### รวมสุทธิ: {total:,.2f} บาท")

        if st.button("✅ บันทึกและรับ PDF", type="primary"):
            inv_no = next_invoice_no()
            now = datetime.now()
            # จัดข้อมูลให้ครบ 28 คอลัมน์ตาม Google Sheet
            full_data = [
                inv_no, now.strftime("%d/%m/%Y"), st.session_state.customer, st.session_state.address,
                sum(i['amount'] for i in st.session_state.invoice_items), 0, st.session_state.shipping, 
                st.session_state.discount, total, now.strftime("%H:%M:%S"),
                st.session_state.car_id, st.session_state.driver_name, st.session_state.pay_status,
                st.session_state.date_out, st.session_state.time_out, st.session_state.date_in, st.session_state.time_in,
                st.session_state.ref_tax_id, st.session_state.ref_rec_id, st.session_state.seal_no,
                st.session_state.pay_term, st.session_state.ship_method, st.session_state.driver_license,
                st.session_state.receiver_name, st.session_state.issuer_name, st.session_state.sender_name,
                st.session_state.checker_name, st.session_state.remark
            ]
            ws_inv.append_row(full_data)
            for it in st.session_state.invoice_items:
                ws_item.append_row([inv_no, it['product'], it['qty'], it['price'], it['amount']])
            
            st.success(f"บันทึก {inv_no} สำเร็จ!")
            st.cache_data.clear() # ล้าง Cache เพื่อให้เห็นข้อมูลใหม่ในการดึงครั้งหน้า
            
            # Generate PDF
            pdf = create_pdf({"invoice_no": inv_no, "date": now.strftime("%d/%m/%Y"), "customer": st.session_state.customer, "total": total}, st.session_state.invoice_items)
            st.download_button("📥 ดาวน์โหลดใบกำกับสินค้า (PDF)", pdf, f"{inv_no}.pdf", "application/pdf")
