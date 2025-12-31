import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# ================= CONFIG =================
st.set_page_config(page_title="Transportation Invoice", layout="wide")

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INV_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

# ================= GOOGLE SHEET =================
@st.cache_resource
def init_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

sheet = init_sheet()
ws_inv = sheet.worksheet(INV_SHEET)
ws_item = sheet.worksheet(ITEM_SHEET)

inv_df = pd.DataFrame(ws_inv.get_all_records())
item_df = pd.DataFrame(ws_item.get_all_records())

# ================= SESSION STATE =================
st.session_state.setdefault("invoice_items", [])
st.session_state.setdefault("customer", "")
st.session_state.setdefault("address", "")
st.session_state.setdefault("shipping", 0.0)
st.session_state.setdefault("discount", 0.0)

# ================= UTIL =================
def next_invoice_no():
    if inv_df.empty:
        return "INV-0001"
    last = inv_df["invoice_no"].iloc[-1]
    return f"INV-{int(last.split('-')[1]) + 1:04d}"

def create_pdf(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, h-2*cm, "TRANSPORTATION INVOICE")

    c.setFont("Helvetica", 10)
    c.drawString(2*cm, h-3*cm, f"Invoice: {inv['invoice_no']}")
    c.drawString(2*cm, h-3.7*cm, f"Date: {inv['date']}")

    c.drawString(2*cm, h-5*cm, f"Customer: {inv['customer']}")
    c.drawString(2*cm, h-5.7*cm, f"Address: {inv['address']}")

    y = h - 7*cm
    for it in items:
        c.drawString(2*cm, y, it["product"])
        c.drawRightString(12*cm, y, str(it["qty"]))
        c.drawRightString(15*cm, y, f"{it['price']:,.2f}")
        c.drawRightString(19*cm, y, f"{it['amount']:,.2f}")
        y -= 0.6*cm

    c.drawRightString(19*cm, y-1*cm, f"TOTAL {inv['total']:,.2f} บาท")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= UI =================
st.title("🚚 ระบบใบกำกับขนส่งสินค้า")

# ===== SEARCH =====
st.subheader("🔍 ค้นหา Invoice")
selected = st.selectbox(
    "เลือก Invoice",
    [""] + inv_df["invoice_no"].tolist() if not inv_df.empty else [""]
)

if selected:
    inv = inv_df[inv_df["invoice_no"] == selected].iloc[0]
    its = item_df[item_df["invoice_no"] == selected]

    if st.button("🖨 Export PDF"):
        pdf = create_pdf(inv.to_dict(), its.to_dict("records"))
        st.download_button("⬇ Download PDF", pdf, f"{selected}.pdf")

# ===== CUSTOMER =====
st.subheader("🧾 ข้อมูลลูกค้า")
st.session_state.customer = st.text_input("ชื่อลูกค้า", st.session_state.customer)
st.session_state.address = st.text_area("ที่อยู่", st.session_state.address)
st.session_state.shipping = st.number_input("🚚 ค่าขนส่ง", value=float(st.session_state.shipping))
st.session_state.discount = st.number_input("🔻 ส่วนลด", value=float(st.session_state.discount))

# ===== ADD ITEM =====
st.subheader("📦 เพิ่มสินค้า")
c1, c2, c3 = st.columns(3)
name = c1.text_input("สินค้า")
qty = c2.number_input("จำนวน", min_value=1, value=1)
price = c3.number_input("ราคา", min_value=0.0, value=0.0)

if st.button("➕ เพิ่มสินค้า") and name:
    st.session_state.invoice_items.append({
        "product": name,
        "qty": int(qty),
        "price": float(price),
        "amount": float(qty * price)
    })
    st.rerun()

# ===== TABLE =====
if st.session_state.invoice_items:
    df = pd.DataFrame(st.session_state.invoice_items)
    st.dataframe(df, use_container_width=True)

    i = st.selectbox("เลือกรายการ", df.index)
    q = st.number_input("แก้ไขจำนวน", value=int(df.loc[i, "qty"]))
    p = st.number_input("แก้ไขราคา", value=float(df.loc[i, "price"]))

    if st.button("💾 อัปเดต"):
        st.session_state.invoice_items[i].update({
            "qty": q,
            "price": p,
            "amount": q * p
        })
        st.rerun()

    if st.button("🗑 ลบ"):
        st.session_state.invoice_items.pop(i)
        st.rerun()

# ===== TOTAL =====
subtotal = sum(i["amount"] for i in st.session_state.invoice_items)
vat = subtotal * 0.07
total = subtotal + vat + st.session_state.shipping - st.session_state.discount

st.markdown(f"## 💰 รวมสุทธิ {total:,.2f} บาท")

# ===== SAVE =====
if st.button("✅ บันทึก Invoice") and st.session_state.invoice_items:
    inv_no = next_invoice_no()
    today = datetime.today().strftime("%d/%m/%Y")
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    ws_inv.append_row([
        inv_no, today,
        st.session_state.customer,
        st.session_state.address,
        subtotal, vat,
        st.session_state.shipping,
        st.session_state.discount,
        total, now
    ])

    for it in st.session_state.invoice_items:
        ws_item.append_row([
            inv_no,
            it["product"],
            it["qty"],
            it["price"],
            it["amount"]
        ])

    st.success(f"บันทึก {inv_no} สำเร็จ")
    st.session_state.invoice_items = []
    st.cache_resource.clear()
    st.rerun()
