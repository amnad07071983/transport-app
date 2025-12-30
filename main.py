import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# ================== CONFIG ==================
st.set_page_config(page_title="Transportation Invoice", layout="wide")

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INVOICE_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

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
ws_inv = sheet.worksheet(INVOICE_SHEET)
ws_item = sheet.worksheet(ITEM_SHEET)

# ================== SESSION STATE (SAFE INIT) ==================
def ensure_list(key):
    if key not in st.session_state or not isinstance(st.session_state[key], list):
        st.session_state[key] = []

def ensure_value(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

ensure_list("items")
ensure_value("edit_invoice_no", None)
ensure_value("customer", "")
ensure_value("address", "")
ensure_value("shipping", 0.0)
ensure_value("discount", 0.0)

# ================== AUTO INVOICE ==================
def generate_invoice_no():
    rows = ws_inv.get_all_values()
    if len(rows) <= 1:
        return "INV-0001"
    last = rows[-1][0]
    try:
        num = int(last.split("-")[1]) + 1
    except Exception:
        num = len(rows)
    return f"INV-{num:04d}"

# ================== PDF ==================
def generate_pdf(invoice, items):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, h-2*cm, "TRANSPORTATION INVOICE")

    c.setFont("Helvetica", 10)
    c.drawString(2*cm, h-3*cm, f"Invoice No: {invoice['invoice_no']}")
    c.drawString(2*cm, h-3.7*cm, f"Date: {invoice['date']}")

    c.drawString(2*cm, h-5*cm, f"Customer: {invoice['customer']}")
    c.drawString(2*cm, h-5.7*cm, f"Address: {invoice['address']}")

    y = h - 7*cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2*cm, y, "สินค้า")
    c.drawRightString(11*cm, y, "จำนวน")
    c.drawRightString(14*cm, y, "ราคา")
    c.drawRightString(18*cm, y, "รวม")

    c.setFont("Helvetica", 10)
    y -= 0.7*cm
    for it in items:
        c.drawString(2*cm, y, it["name"])
        c.drawRightString(11*cm, y, str(it["qty"]))
        c.drawRightString(14*cm, y, f"{it['price']:,.2f}")
        c.drawRightString(18*cm, y, f"{it['amount']:,.2f}")
        y -= 0.6*cm

    y -= 0.4*cm
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(14*cm, y, "Subtotal")
    c.drawRightString(18*cm, y, f"{invoice['subtotal']:,.2f}")

    y -= 0.6*cm
    c.drawRightString(14*cm, y, "VAT 7%")
    c.drawRightString(18*cm, y, f"{invoice['vat']:,.2f}")

    y -= 0.6*cm
    c.drawRightString(14*cm, y, "Shipping")
    c.drawRightString(18*cm, y, f"{invoice['shipping']:,.2f}")

    y -= 0.6*cm
    c.drawRightString(14*cm, y, "Discount")
    c.drawRightString(18*cm, y, f"{invoice['discount']:,.2f}")

    y -= 0.8*cm
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(14*cm, y, "TOTAL")
    c.drawRightString(18*cm, y, f"{invoice['total']:,.2f} บาท")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# ================== LOAD DATA ==================
raw_inv = ws_inv.get_all_records()
inv_df = pd.DataFrame(raw_inv) if raw_inv else pd.DataFrame()

if not inv_df.empty:
    inv_df.columns = inv_df.columns.str.strip().str.lower()

if "invoice_no" not in inv_df.columns:
    inv_df = pd.DataFrame(columns=[
        "invoice_no","date","customer","address",
        "subtotal","vat","shipping","discount","total","created_at"
    ])

item_df = pd.DataFrame(ws_item.get_all_records())
if not item_df.empty:
    item_df.columns = item_df.columns.str.strip().str.lower()

# ================== UI ==================
st.title("🚚 ระบบใบกำกับขนส่งสินค้า")

# ===== OPEN OLD INVOICE =====
st.subheader("📂 เปิด / พิมพ์ Invoice เก่า")

selected_inv = st.selectbox(
    "เลือก Invoice",
    [""] + inv_df["invoice_no"].astype(str).tolist()
)

if selected_inv:
    inv_row = inv_df[inv_df["invoice_no"] == selected_inv].iloc[0]

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📥 โหลดมาแก้ไข"):
            st.session_state.edit_invoice_no = selected_inv
            st.session_state.customer = inv_row["customer"]
            st.session_state.address = inv_row["address"]
            st.session_state.shipping = float(inv_row["shipping"])
            st.session_state.discount = float(inv_row["discount"])
            st.session_state.items = []

            for _, it in item_df[item_df["invoice_no"] == selected_inv].iterrows():
                st.session_state.items.append({
                    "name": it["product"],
                    "qty": int(it["qty"]),
                    "price": float(it["price"]),
                    "amount": float(it["amount"])
                })
            st.rerun()

    with col2:
        if st.button("🖨 พิมพ์ Invoice"):
            items = item_df[item_df["invoice_no"] == selected_inv][
                ["product","qty","price","amount"]
            ].rename(columns={"product":"name"}).to_dict("records")

            pdf = generate_pdf(inv_row.to_dict(), items)
            st.download_button("⬇️ ดาวน์โหลด PDF", pdf, f"{selected_inv}.pdf")

# ===== FORM =====
st.subheader("📝 สร้าง / แก้ไข Invoice")

customer = st.text_input("ชื่อลูกค้า", value=st.session_state.customer)
address = st.text_area("ที่อยู่", value=st.session_state.address)
shipping = st.number_input("🚚 ค่าขนส่ง", value=float(st.session_state.shipping))
discount = st.number_input("🔻 ส่วนลด", value=float(st.session_state.discount))

# ===== ITEMS =====
st.subheader("📦 รายการสินค้า")
pname = st.text_input("ชื่อสินค้า")
qty = st.number_input("จำนวน", min_value=1, value=1)
price = st.number_input("ราคา/หน่วย", min_value=0.0)

if st.button("➕ เพิ่มสินค้า"):
    ensure_list("items")
    if pname:
        st.session_state.items.append({
            "name": pname,
            "qty": int(qty),
            "price": float(price),
            "amount": float(qty * price)
        })

if st.session_state.items:
    st.dataframe(pd.DataFrame(st.session_state.items))

subtotal = sum(i["amount"] for i in st.session_state.items)
vat = subtotal * 0.07
total = subtotal + vat + shipping - discount

st.markdown(f"### 💰 รวมสุทธิ: **{total:,.2f} บาท**")

# ===== SAVE =====
if st.button("💾 บันทึก Invoice"):
    invoice_no = st.session_state.edit_invoice_no or generate_invoice_no()
    today = datetime.today().strftime("%d/%m/%Y")
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    if st.session_state.edit_invoice_no:
        ws_inv.delete_rows(inv_df[inv_df["invoice_no"] == invoice_no].index[0] + 2)
        for i in range(len(ws_item.get_all_values())-1, 0, -1):
            if ws_item.get_all_values()[i][0] == invoice_no:
                ws_item.delete_rows(i+1)

    ws_inv.append_row([
        invoice_no, today, customer, address,
        subtotal, vat, shipping, discount, total, now
    ])

    for it in st.session_state.items:
        ws_item.append_row([
            invoice_no, it["name"], it["qty"], it["price"], it["amount"]
        ])

    st.session_state.items = []
    st.session_state.edit_invoice_no = None
    st.success(f"✅ บันทึก {invoice_no} เรียบร้อย")
