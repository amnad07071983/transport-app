import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import io

# ===== PDF =====
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# ================== CONFIG ==================
st.set_page_config(page_title="Transportation Invoice", layout="wide")

SHEET_ID = "PUT_YOUR_GOOGLE_SHEET_ID_HERE"
SHEET_NAME = "RawData"

# ================== GOOGLE SHEET ==================
@st.cache_resource
def init_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

sheet = init_gsheet()
ws = sheet.worksheet(SHEET_NAME)

# ================== PDF FUNCTION ==================
def generate_pdf(data):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # ===== Header =====
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, height - 2 * cm, "TRANSPORTATION INVOICE")

    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, height - 3 * cm, f"Invoice No: {data['invoice_no']}")
    c.drawString(2 * cm, height - 3.7 * cm, f"Date: {data['invoice_date']}")

    # ===== Customer =====
    c.drawString(2 * cm, height - 5 * cm, f"Customer: {data['customer_name']}")
    c.drawString(2 * cm, height - 5.7 * cm, f"Address: {data['customer_address']}")

    # ===== Table Header =====
    y = height - 7 * cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, y, "Product")
    c.drawString(9 * cm, y, "Qty")
    c.drawString(11 * cm, y, "Price")
    c.drawString(14 * cm, y, "Amount")

    # ===== Table Data =====
    c.setFont("Helvetica", 10)
    y -= 0.8 * cm
    c.drawString(2 * cm, y, data["product_name"])
    c.drawString(9 * cm, y, str(data["quantity"]))
    c.drawString(11 * cm, y, f"{data['price']:,.2f}")
    c.drawString(14 * cm, y, f"{data['amount']:,.2f}")

    # ===== Total =====
    y -= 2 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(11 * cm, y, "Total")
    c.drawString(14 * cm, y, f"{data['amount']:,.2f} บาท")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# ================== HEADER ==================
st.title("🚚 ระบบใบกำกับขนส่งสินค้า")

# ================== FORM ==================
st.subheader("📝 กรอกข้อมูลใบกำกับขนส่ง")

with st.form("invoice_form"):
    c1, c2 = st.columns(2)

    with c1:
        invoice_no = st.text_input("เลขที่ใบกำกับ")
        invoice_date = st.date_input("วันที่ใบกำกับ", value=datetime.today())
        customer_name = st.text_input("ชื่อลูกค้า")
        customer_address = st.text_area("ที่อยู่ลูกค้า")

    with c2:
        product_name = st.text_input("ชื่อสินค้า")
        quantity = st.number_input("จำนวน", min_value=1, value=1)
        price = st.number_input("ราคา/หน่วย", min_value=0.0, value=0.0)

    submit = st.form_submit_button("💾 บันทึกข้อมูล")

# ================== SAVE ==================
if submit:
    amount = quantity * price
    created_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    ws.append_row([
        invoice_no,
        invoice_date.strftime("%d/%m/%Y"),
        customer_name,
        customer_address,
        product_name,
        quantity,
        price,
        amount,
        created_at
    ])

    st.success("✅ บันทึกข้อมูลเรียบร้อย")

    pdf_data = {
        "invoice_no": invoice_no,
        "invoice_date": invoice_date.strftime("%d/%m/%Y"),
        "customer_name": customer_name,
        "customer_address": customer_address,
        "product_name": product_name,
        "quantity": quantity,
        "price": price,
        "amount": amount
    }

    st.download_button(
        "🖨 ดาวน์โหลด PDF",
        generate_pdf(pdf_data),
        file_name=f"invoice_{invoice_no}.pdf",
        mime="application/pdf"
    )

st.divider()

# ================== TABLE ==================
st.subheader("📊 ข้อมูลใบกำกับทั้งหมด")

data = ws.get_all_records()
if data:
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)
else:
    st.info("ยังไม่มีข้อมูล")
