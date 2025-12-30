import streamlit as st
import streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import io
import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ================= CONFIG =================
st.set_page_config(page_title="Transportation Invoice", layout="wide")

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INV_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

# ================= FONT =================
FONT_PATH = os.path.join(os.path.dirname(__file__), "ARIBLK.TTF")

if not os.path.exists(FONT_PATH):
    st.error("❌ ไม่พบไฟล์ฟอนต์ ARIBLK.TTF (ต้องวางไว้โฟลเดอร์เดียวกับ main.py)")
    st.stop()

pdfmetrics.registerFont(TTFont("ARIBLK", FONT_PATH))

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

# ================= SESSION =================
st.session_state.setdefault("items", [])
st.session_state.setdefault("customer", "")
st.session_state.setdefault("address", "")

# ================= UTIL =================
def next_invoice_no():
    if inv_df.empty or "invoice_no" not in inv_df.columns:
        return "INV-0001"
    last = inv_df["invoice_no"].iloc[-1]
    n = int(last.split("-")[1]) + 1
    return f"INV-{n:04d}"

def pdf_invoice(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    c.setFont("ARIBLK", 18)
    c.drawString(2*cm, h-2*cm, "TRANSPORTATION INVOICE")

    c.setFont("ARIBLK", 11)
    c.drawString(2*cm, h-3.5*cm, f"Invoice: {inv['invoice_no']}")
    c.drawString(2*cm, h-4.3*cm, f"Date: {inv['date']}")
    c.drawString(2*cm, h-5.5*cm, f"Customer: {inv['customer']}")
    c.drawString(2*cm, h-6.3*cm, f"Address: {inv['address']}")

    y = h - 8*cm
    c.drawString(2*cm, y, "Item")
    c.drawRightString(11*cm, y, "Qty")
    c.drawRightString(14*cm, y, "Price")
    c.drawRightString(18*cm, y, "Amount")

    y -= 0.7*cm
    for it in items:
        c.drawString(2*cm, y, it["name"])
        c.drawRightString(11*cm, y, str(it["qty"]))
        c.drawRightString(14*cm, y, f"{it['price']:,.2f}")
        c.drawRightString(18*cm, y, f"{it['amount']:,.2f}")
        y -= 0.6*cm

    y -= 0.5*cm
    c.drawRightString(14*cm, y, "TOTAL")
    c.drawRightString(18*cm, y, f"{inv['total']:,.2f}")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= UI =================
st.title("🚚 Transportation Invoice System")

search = st.text_input("🔍 Search Invoice")
show_df = inv_df
if search and not inv_df.empty:
    show_df = inv_df[inv_df["invoice_no"].str.contains(search, case=False)]

sel = st.selectbox("Select Invoice", [""] + show_df["invoice_no"].tolist()) if not show_df.empty else ""

if sel:
    inv = inv_df[inv_df["invoice_no"] == sel].iloc[0]
    its = item_df[item_df["invoice_no"] == sel].to_dict("records")

    col1, col2 = st.columns(2)

    if col1.button("📄 Duplicate Invoice"):
        st.session_state.items = [
            {"name": r["product"], "qty": int(r["qty"]), "price": float(r["price"]), "amount": float(r["amount"])}
            for r in its
        ]
        st.session_state.customer = inv["customer"]
        st.session_state.address = inv["address"]
        st.rerun()

    if col2.button("🧾 Export PDF"):
        pdf = pdf_invoice(inv.to_dict(), [
            {"name": r["product"], "qty": r["qty"], "price": r["price"], "amount": r["amount"]}
            for r in its
        ])
        st.download_button("⬇️ Download PDF", pdf, f"{sel}.pdf")

# ===== FORM =====
customer = st.text_input("Customer", value=st.session_state.customer)
address = st.text_area("Address", value=st.session_state.address)

shipping = st.number_input("Shipping", min_value=0.0, value=0.0)
discount = st.number_input("Discount", min_value=0.0, value=0.0)

# ===== ITEMS =====
st.subheader("Items")
c1, c2, c3 = st.columns(3)
name = c1.text_input("Item")
qty = c2.number_input("Qty", min_value=1, value=1)
price = c3.number_input("Price", min_value=0.0, value=0.0)

if st.button("➕ Add Item") and name:
    st.session_state.items.append({
        "name": name,
        "qty": int(qty),
        "price": float(price),
        "amount": float(qty * price)
    })

if st.session_state.items:
    st.dataframe(pd.DataFrame(st.session_state.items), use_container_width=True)

subtotal = sum(i["amount"] for i in st.session_state.items)
vat = subtotal * 0.07
total = subtotal + vat + shipping - discount

st.markdown(f"### 💰 TOTAL **{total:,.2f}**")

if st.button("💾 Save Invoice") and st.session_state.items:
    inv_no = next_invoice_no()
    today = datetime.today().strftime("%d/%m/%Y")
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    ws_inv.append_row([inv_no, today, customer, address, subtotal, vat, shipping, discount, total, now])

    for it in st.session_state.items:
        ws_item.append_row([inv_no, it["name"], it["qty"], it["price"], it["amount"]])

    st.success(f"✅ Saved {inv_no}")
    st.session_state.items = []
    st.cache_resource.clear()
    st.rerun()
