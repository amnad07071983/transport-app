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
st.set_page_config(page_title="Logistics Invoice System", layout="wide")

try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except Exception as e:
    st.error(f"⚠️ ไม่พบไฟล์ฟอนต์: 'THSARABUN BOLD.ttf' (Error: {e})")

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INV_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

# ================= GOOGLE SHEET =================
@st.cache_resource
def init_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

try:
    sheet = init_sheet()
    ws_inv = sheet.worksheet(INV_SHEET)
    ws_item = sheet.worksheet(ITEM_SHEET)
    inv_df = pd.DataFrame(ws_inv.get_all_records())
    item_df = pd.DataFrame(ws_item.get_all_records())
except Exception as e:
    st.error(f"การเชื่อมต่อ Google Sheets ผิดพลาด: {e}")
    inv_df = pd.DataFrame()
    item_df = pd.DataFrame()

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

# ================= UTIL =================
def next_invoice_no():
    if inv_df.empty or "invoice_no" not in inv_df.columns: return "INV-0001"
    last = inv_df["invoice_no"].iloc[-1]
    try:
        last_num = int(last.split('-')[1])
        return f"INV-{last_num + 1:04d}"
    except: return "INV-0001"

def create_pdf(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    
    # Header
    c.setFont("ThaiFontBold", 16)
    c.drawString(2*cm, h-1.5*cm, st.session_state.my_company)
    c.setFont("ThaiFontBold", 20)
    c.drawRightString(19*cm, h-1.5*cm, "ใบกำกับขนส่งสินค้า")
    
    c.setFont("ThaiFontBold", 11)
    c.drawString(2*cm, h-2.1*cm, f"ที่อยู่: {st.session_state.my_address} โทร: {st.session_state.my_phone}")
    c.drawRightString(19*cm, h-2.1*cm, f"เลขที่: {inv['invoice_no']}  วันที่เอกสาร: {inv['date']}")
    c.line(2*cm, h-2.3*cm, 19*cm, h-2.3*cm)

    # ข้อมูลการจัดส่งและอ้างอิง
    c.setFont("ThaiFontBold", 11)
    c.drawString(2*cm, h-2.9*cm, f"ลูกค้า: {inv['customer']}")
    c.drawString(11*cm, h-2.9*cm, f"ทะเบียนรถ: {inv.get('car_id','')} | คนขับ: {inv.get('driver_name','')}")
    c.drawString(11*cm, h-3.4*cm, f"เลขใบขับขี่: {inv.get('driver_license','')}")
    c.drawString(2*cm, h-3.4*cm, f"ที่อยู่: {inv.get('address','')[:60]}")
    c.drawString(2*cm, h-4.1*cm, f"ออกเดินทาง: {inv.get('date_out','')} {inv.get('time_out','')}")
    c.drawString(6.5*cm, h-4.1*cm, f"ถึงที่หมาย: {inv.get('date_in','')} {inv.get('time_in','')}")
    c.drawString(11*cm, h-4.1*cm, f"ซีลหมายเลข: {inv.get('seal_no','')}")
    c.drawString(2*cm, h-4.6*cm, f"อ้างอิงใบกำกับภาษี: {inv.get('ref_tax_id','')}")
    c.drawString(6.5*cm, h-4.6*cm, f"อ้างอิงใบเสร็จ: {inv.get('ref_rec_id','')}")
    c.drawString(11*cm, h-4.6*cm, f"ขนส่งโดย: {inv.get('ship_method','')}")
    c.drawString(15.5*cm, h-4.6*cm, f"ชำระโดย: {inv.get('pay_term','')}")

    # ตารางสินค้า
    y = h - 5.5*cm
    c.setFont("ThaiFontBold", 12)
    c.drawString(2*cm, y, "รายการสินค้า")
    c.drawRightString(12*cm, y, "จำนวน")
    c.drawRightString(15.5*cm, y, "ราคา/หน่วย")
    c.drawRightString(19*cm, y, "รวมเงิน")
    c.line(2*cm, y-0.2*cm, 19*cm, y-0.2*cm)
    
    y -= 0.6*cm
    for it in items:
        c.drawString(2*cm, y, str(it["product"]))
        c.drawRightString(12*cm, y, f"{it['qty']:,}")
        c.drawRightString(15.5*cm, y, f"{float(it['price']):,.2f}")
        c.drawRightString(19*cm, y, f"{float(it['amount']):,.2f}")
        y -= 0.5*cm

    # สรุปเงิน
    y_sum = y - 0.5*cm
    c.setFont("ThaiFontBold", 11)
    c.drawRightString(16*cm, y_sum, "ค่าขนส่ง:")
    c.drawRightString(19*cm, y_sum, f"{float(inv.get('shipping',0)):,.2f}")
    c.drawRightString(16*cm, y_sum-0.5*cm, "ส่วนลด:")
    c.drawRightString(19*cm, y_sum-0.5*cm, f"{float(inv.get('discount',0)):,.2f}")
    c.setFont("ThaiFontBold", 14)
    c.drawRightString(16*cm, y_sum-1.1*cm, "ยอดรวมสุทธิ:")
    c.drawRightString(19*cm, y_sum-1.1*cm, f"{float(inv.get('total',0)):,.2f} บาท")
    
    c.setFont("ThaiFontBold", 10)
    c.drawString(2*cm, y_sum, f"หมายเหตุ: {inv.get('remark','')}")

    # ลายเซ็น
    y_sig = 3*cm
    for x, name, label in [(3.75, inv.get('sender_name',''), "ผู้ส่งสินค้า"),
                           (8.25, inv.get('checker_name',''), "ผู้ตรวจสอบ"),
                           (12.75, inv.get('receiver_name',''), "ผู้รับสินค้า"),
                           (17.25, inv.get('issuer_name',''), "ผู้ออกเอกสาร")]:
        c.line((x-1.75)*cm, y_sig, (x+1.75)*cm, y_sig)
        c.drawCentredString(x*cm, y_sig-0.4*cm, f"( {name} )")
        c.drawCentredString(x*cm, y_sig-0.8*cm, label)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= UI =================
st.title("🚚 ระบบจัดการการขนส่งและใบกำกับสินค้า")

tab1, tab2 = st.tabs(["📝 ออกใบกำกับสินค้า", "⚙️ ตั้งค่าบริษัท"])

with tab2:
    st.subheader("🏢 ข้อมูลหัวกระดาษบริษัท")
    st.session_state.my_company = st.text_input("ชื่อบริษัท/ร้าน", st.session_state.my_company)
    st.session_state.my_address = st.text_area("ที่อยู่บริษัท", st.session_state.my_address)
    st.session_state.my_phone = st.text_input("เบอร์โทรศัพท์", st.session_state.my_phone)

with tab1:
    with st.expander("🔍 ค้นหา / Duplicate Invoice เก่า"):
        if not inv_df.empty:
            invoice_options = [f"{row['invoice_no']} | {row['customer']}" for _, row in inv_df.iterrows()]
            selected_label = st.selectbox("เลือก Invoice", [""] + invoice_options[::-1])
            if selected_label:
                selected_no = selected_label.split(" | ")[0]
                inv_data = inv_df[inv_df["invoice_no"] == selected_no].iloc[0]
                if st.button("📄 โหลดข้อมูลลงฟอร์ม"):
                    for key in defaults.keys():
                        if key in inv_data: st.session_state[key] = inv_data[key]
                    st.rerun()

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("👤 ข้อมูลลูกค้า")
        st.session_state.customer = st.text_input("ชื่อลูกค้า", value=st.session_state.customer)
        st.session_state.address = st.text_area("ที่อยู่จัดส่ง", value=st.session_state.address)
        st.session_state.receiver_name = st.text_input("ชื่อผู้รับสินค้า", value=st.session_state.receiver_name)
    with col_b:
        st.subheader("🚛 ข้อมูลการขนส่ง")
        c_car1, c_car2 = st.columns(2)
        st.session_state.car_id = c_car1.text_input("ทะเบียนรถ", value=st.session_state.car_id)
        st.session_state.driver_name = c_car2.text_input("ชื่อคนขับ", value=st.session_state.driver_name)
        st.session_state.driver_license = st.text_input("เลขใบขับขี่", value=st.session_state.driver_license)
        st.session_state.seal_no = st.text_input("หมายเลขซีล (Seal No.)", value=st.session_state.seal_no)

    st.divider()
    col_c, col_d = st.columns(2)
    with col_c:
        st.subheader("⏰ วัน-เวลา เดินทาง")
        c_t1, c_t2 = st.columns(2)
        st.session_state.date_out = c_t1.text_input("วันที่รถออก (วว/ดด/ปป)", value=st.session_state.date_out)
        st.session_state.time_out = c_t2.text_input("เวลารถออก", value=st.session_state.time_out)
        st.session_state.date_in = c_t1.text_input("วันที่รถถึง", value=st.session_state.date_in)
        st.session_state.time_in = c_t2.text_input("เวลารถถึง", value=st.session_state.time_in)
    with col_d:
        st.subheader("📄 เอกสารและเงื่อนไข")
        st.session_state.ref_tax_id = st.text_input("อ้างถึงเลขใบกำกับภาษี", value=st.session_state.ref_tax_id)
        st.session_state.ref_rec_id = st.text_input("อ้างถึงเลขใบเสร็จรับเงิน", value=st.session_state.ref_rec_id)
        st.session_state.pay_term = st.selectbox("เงื่อนไขการชำระเงิน", ["เงินสด", "โอนเงิน", "เครดิต 30 วัน"], index=0)
        st.session_state.ship_method = st.text_input("วิธีการจัดส่ง", value=st.session_state.ship_method)

    st.divider()
    st.subheader("👥 รายชื่อผู้รับผิดชอบ & หมายเหตุ")
    c_p1, c_p2, c_p3 = st.columns(3)
    st.session_state.sender_name = c_p1.text_input("ชื่อผู้ส่งสินค้า", value=st.session_state.sender_name)
    st.session_state.checker_name = c_p2.text_input("ชื่อผู้ตรวจสอบสินค้า", value=st.session_state.checker_name)
    st.session_state.issuer_name = c_p3.text_input("ชื่อผู้ออกเอกสาร", value=st.session_state.issuer_name)
    st.session_state.remark = st.text_area("หมายเหตุ", value=st.session_state.remark)

    st.subheader("📦 รายการสินค้า")
    c_item1, c_item2, c_item3 = st.columns([3, 1, 1])
    new_name = c_item1.text_input("ชื่อรายการสินค้า")
    new_qty = c_item2.number_input("จำนวน", min_value=1, value=1)
    new_price = c_item3.number_input("ราคา/หน่วย", min_value=0.0, value=0.0)
    if st.button("➕ เพิ่มสินค้า"):
        st.session_state.invoice_items.append({"product": new_name, "qty": int(new_qty), "price": float(new_price), "amount": float(new_qty * new_price)})
        st.rerun()

    # --- ส่วนที่แก้ไข: เพิ่มความสามารถในการลบรายการสินค้า ---
    if st.session_state.invoice_items:
        st.write("---")
        for i, item in enumerate(st.session_state.invoice_items):
            col_del1, col_del2 = st.columns([0.9, 0.1])
            col_del1.write(f"{i+1}. {item['product']} | จำนวน: {item['qty']} | ราคา: {item['price']:,.2f} | รวม: {item['amount']:,.2f}")
            if col_del2.button("🗑️", key=f"del_{i}"):
                st.session_state.invoice_items.pop(i)
                st.rerun()

        subtotal = sum(i["amount"] for i in st.session_state.invoice_items)
        total = subtotal + st.session_state.shipping - st.session_state.discount
        st.write(f"### ยอดรวมสุทธิ: {total:,.2f} บาท")

        # --- ส่วนที่แก้ไข: การบันทึกและแสดงปุ่มดาวน์โหลด PDF ---
        if st.button("✅ บันทึกและเตรียมพิมพ์ Invoice", type="primary"):
            inv_no = next_invoice_no()
            today_str = datetime.today().strftime("%d/%m/%Y")
            
            data_to_save = [
                inv_no, today_str, st.session_state.customer, st.session_state.address,
                subtotal, 0, st.session_state.shipping, st.session_state.discount, total, datetime.now().strftime("%H:%M:%S"),
                st.session_state.car_id, st.session_state.driver_name, st.session_state.pay_status,
                st.session_state.date_out, st.session_state.time_out, st.session_state.date_in, st.session_state.time_in,
                st.session_state.ref_tax_id, st.session_state.ref_rec_id, st.session_state.seal_no,
                st.session_state.pay_term, st.session_state.ship_method, st.session_state.driver_license,
                st.session_state.receiver_name, st.session_state.issuer_name, st.session_state.sender_name,
                st.session_state.checker_name, st.session_state.remark
            ]
            
            ws_inv.append_row(data_to_save)
            for it in st.session_state.invoice_items:
                ws_item.append_row([inv_no, it["product"], it["qty"], it["price"], it["amount"]])
            
            st.success(f"บันทึกข้อมูล {inv_no} เรียบร้อยแล้ว! คลิกปุ่มด้านล่างเพื่อดาวน์โหลด PDF")
            
            # สร้าง PDF ทันทีหลังบันทึก
            inv_dict = {
                "invoice_no": inv_no, "date": today_str, "customer": st.session_state.customer,
                "address": st.session_state.address, "shipping": st.session_state.shipping,
                "discount": st.session_state.discount, "total": total, "remark": st.session_state.remark,
                "car_id": st.session_state.car_id, "driver_name": st.session_state.driver_name,
                "date_out": st.session_state.date_out, "time_out": st.session_state.time_out,
                "date_in": st.session_state.date_in, "time_in": st.session_state.time_in,
                "ref_tax_id": st.session_state.ref_tax_id, "ref_rec_id": st.session_state.ref_rec_id,
                "seal_no": st.session_state.seal_no, "pay_term": st.session_state.pay_term,
                "ship_method": st.session_state.ship_method, "driver_license": st.session_state.driver_license,
                "receiver_name": st.session_state.receiver_name, "issuer_name": st.session_state.issuer_name,
                "sender_name": st.session_state.sender_name, "checker_name": st.session_state.checker_name
            }
            pdf_file = create_pdf(inv_dict, st.session_state.invoice_items)
            st.download_button(
                label="📥 ดาวน์โหลดใบกำกับสินค้า (PDF)",
                data=pdf_file,
                file_name=f"{inv_no}.pdf",
                mime="application/pdf"
            )
