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
# รายชื่อฟิลด์ทั้งหมดตามลำดับโครงสร้าง 28 คอลัมน์
transport_fields = [
    "car_id", "driver_name", "payment_status", "date_out", "time_out",
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
    for field in transport_fields:
        st.session_state[f"form_{field}"] = ""
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
    c.drawString(2*cm, h-3.2*cm, f"เลขที่ใบแจ้งหนี้: {inv.get('invoice_no','')}")
    c.drawString(2*cm, h-4*cm, f"วันที่: {inv.get('date','')}")
    c.drawString(2*cm, h-5.2*cm, f"ชื่อลูกค้า: {inv.get('customer','')}")
    c.drawString(2*cm, h-6*cm, f"ที่อยู่: {inv.get('address','')}")

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
    c.setFont("ThaiFontBold", 13)
    c.drawString(13.5*cm, y_sum, f"ค่าขนส่ง: {float(inv.get('shipping', 0)):,.2f}")
    c.drawString(13.5*cm, y_sum-0.8*cm, f"ส่วนลด: {float(inv.get('discount', 0)):,.2f}")
    c.setFont("ThaiFontBold", 16)
    c.drawString(13.5*cm, y_sum-1.8*cm, f"ยอดสุทธิ: {float(inv.get('total', 0)):,.2f} บาท")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= 4. UI - HISTORY =================
st.title("🚚 ระบบจัดการใบแจ้งหนี้ขนส่ง (All-in-One)")

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
                    st.session_state.form_shipping = float(old_inv.get("shipping", 0))
                    st.session_state.form_discount = float(old_inv.get("discount", 0))
                    for field in transport_fields:
                        st.session_state[f"form_{field}"] = str(old_inv.get(field, ""))
                    old_items = item_df[item_df["invoice_no"] == sel_no]
                    st.session_state.invoice_items = old_items.to_dict('records')
                    st.rerun()
            with col_b2:
                old_inv_data = inv_df[inv_df["invoice_no"] == sel_no].iloc[0].to_dict()
                old_items_data = item_df[item_df["invoice_no"] == sel_no].to_dict('records')
                pdf_old = create_pdf(old_inv_data, old_items_data)
                st.download_button(f"📄 ดาวน์โหลด PDF เลขที่ {sel_no}", pdf_old, f"{sel_no}.pdf", "application/pdf")
    else:
        st.info("ไม่มีข้อมูลในระบบ")

st.divider()

# ================= 5. UI - MAIN FORM =================
st.subheader("📝 ข้อมูลลูกค้าและขนส่ง")
c1, c2, c3 = st.columns(3)
with c1:
    customer = st.text_input("ชื่อลูกค้า", value=st.session_state.form_customer)
    address = st.text_area("ที่อยู่", value=st.session_state.form_address)
    car_id = st.text_input("ทะเบียนรถ (Car ID)", value=st.session_state.form_car_id)
with c2:
    driver_name = st.text_input("ชื่อคนขับ", value=st.session_state.form_driver_name)
    pay_status = st.selectbox("สถานะการชำระเงิน", ["ค้างชำระ", "ชำระแล้ว"],
                              index=0 if st.session_state.form_payment_status != "ชำระแล้ว" else 1)
    date_out = st.text_input("วันที่ออก (Date Out)", value=st.session_state.form_date_out)
    time_out = st.text_input("เวลาออก (Time Out)", value=st.session_state.form_time_out)
with c3:
    shipping = st.number_input("ค่าขนส่ง", value=st.session_state.form_shipping, min_value=0.0)
    discount = st.number_input("ส่วนลด", value=st.session_state.form_discount, min_value=0.0)
    seal_no = st.text_input("Seal No.", value=st.session_state.form_seal_no)
    remark = st.text_area("หมายเหตุ (Remark)", value=st.session_state.form_remark)

st.subheader("📦 รายการสินค้า")
ci1, ci2, ci3 = st.columns([3,1,1])
p_name = ci1.text_input("ชื่อสินค้า/บริการ", key="p_input")
p_qty = ci2.number_input("จำนวน", min_value=1, key="q_input")
p_price = ci3.number_input("ราคา/หน่วย", min_value=0.0, key="pr_input")

if st.button("➕ เพิ่มรายการสินค้า"):
    if p_name:
        st.session_state.invoice_items.append({"product": p_name, "qty": p_qty, "price": p_price, "amount": p_qty*p_price})
        st.rerun()

if st.session_state.invoice_items:
    st.write("---")
    for i, item in enumerate(st.session_state.invoice_items):
        col_list = st.columns([4, 1])
        col_list[0].info(f"{i+1}. {item['product']} | {item['qty']:,} x {item['price']:,.2f} = {item['amount']:,.2f}")
        if col_list[1].button("🗑️ ลบ", key=f"del_{i}"):
            st.session_state.invoice_items.pop(i)
            st.rerun()
    subtotal = sum(i['amount'] for i in st.session_state.invoice_items)
    grand_total = subtotal + shipping - discount
    st.write(f"### ยอดรวมสุทธิ: {grand_total:,.2f} บาท")

# ================= 6. SAVE (28 Columns) =================
if st.button("✅ บันทึกข้อมูลและรับ PDF", type="primary"):
    with st.spinner("กำลังบันทึก..."):
        new_no = next_inv_no(inv_df)
        date_now = datetime.now().strftime("%d/%m/%Y")
        
        # จัดเรียง 28 คอลัมน์ให้ตรงตามหัวข้อที่คุณแจ้ง
        row_data = [
            new_no,             # 1. invoice_no
            date_now,           # 2. date
            customer,           # 3. customer
            address,            # 4. address
            subtotal if st.session_state.invoice_items else 0, # 5. subtotal
            0,                  # 6. vat
            shipping,           # 7. shipping
            discount,           # 8. discount
            grand_total if st.session_state.invoice_items else 0, # 9. total
            "Active",           # 10. doc_status
            car_id,             # 11. car_id
            driver_name,        # 12. driver_name
            pay_status,         # 13. payment_status
            date_out,           # 14. date_out
            time_out,           # 15. time_out
            st.session_state.get("form_date_in", ""), # 16. date_in
            st.session_state.get("form_time_in", ""), # 17. time_in
            st.session_state.get("form_ref_tax_id", ""), # 18. ref_tax_id
            st.session_state.get("form_ref_receipt_id", ""), # 19. ref_receipt_id
            seal_no,            # 20. seal_no
            st.session_state.get("form_pay_term", ""), # 21. pay_term
            st.session_state.get("form_ship_method", ""), # 22. ship_method
            st.session_state.get("form_driver_license", ""), # 23. driver_license
            st.session_state.get("form_receiver_name", ""), # 24. receiver_name
            st.session_state.get("form_issuer_name", ""), # 25. issuer_name
            st.session_state.get("form_sender_name", ""), # 26. sender_name
            st.session_state.get("form_checker_name", ""), # 27. checker_name
            remark              # 28. remark
        ]

        ws_inv.append_row(row_data)
        for it in st.session_state.invoice_items:
            ws_item.append_row([new_no, it['product'], it['qty'], it['price'], it['amount']])

        pdf_file = create_pdf({"invoice_no": new_no, "date": date_now, "customer": customer, "address": address, "shipping": shipping, "discount": discount, "total": grand_total}, st.session_state.invoice_items)
        st.success(f"บันทึกสำเร็จ: {new_no}")
        st.download_button("📥 โหลด PDF", pdf_file, f"{new_no}.pdf", "application/pdf")
        st.cache_data.clear()
        reset_form()
        st.rerun()
