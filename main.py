import streamlit as st
import streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# ================= CONFIG =================
st.set_page_config("Transportation Invoice", layout="wide")

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

# ================= SESSION =================
st.session_state.setdefault("invoice_items", [])
st.session_state.setdefault("edit_invoice_no", None)
st.session_state.setdefault("preview", False)

# ================= UTIL =================
def next_invoice_no():
    if inv_df.empty:
        return "INV-0001"
    last = inv_df["invoice_no"].iloc[-1]
    n = int(last.split("-")[1]) + 1
    return f"INV-{n:04d}"

def pdf_invoice(inv, items):
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
        c.drawString(2*cm, y, it["name"])
        c.drawRightString(11*cm, y, str(it["qty"]))
        c.drawRightString(14*cm, y, f"{it['price']:,.2f}")
        c.drawRightString(18*cm, y, f"{it['amount']:,.2f}")
        y -= 0.6*cm

    c.drawRightString(18*cm, y-1*cm, f"TOTAL {inv['total']:,.2f} บาท")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= UI =================
st.title("🚚 ระบบใบกำกับขนส่งสินค้า")

if not inv_df.empty:
    st.info(f"🔢 Invoice ล่าสุด: {inv_df['invoice_no'].iloc[-1]}")

# ===== OPEN / DUPLICATE =====
st.subheader("📂 Invoice เดิม")
old = st.selectbox("เลือก Invoice", [""] + inv_df["invoice_no"].tolist())

if old:
    row = inv_df[inv_df["invoice_no"] == old].iloc[0]

    if st.button("📄 Duplicate"):
        st.session_state.customer = row["customer"]
        st.session_state.address = row["address"]
        st.session_state.invoice_items = (
            item_df[item_df["invoice_no"] == old]
            .to_dict("records")
        )
        st.session_state.edit_invoice_no = None
        st.rerun()

    if st.button("🖨 PDF"):
        pdf = pdf_invoice(
            row.to_dict(),
            item_df[item_df["invoice_no"] == old].to_dict("records")
        )
        st.download_button("⬇️ Download", pdf, f"{old}.pdf")

# ===== AUTO FOCUS =====
components.html("""
<script>
setTimeout(()=>{
 const el = window.parent.document.querySelector('input[aria-label="ชื่อลูกค้า"]');
 if(el) el.focus();
},100);
</script>
""", height=0)

# ===== FORM =====
customer = st.text_input("ชื่อลูกค้า", value=st.session_state.get("customer",""))
address = st.text_area("ที่อยู่", value=st.session_state.get("address",""))

shipping = st.number_input("🚚 ค่าขนส่ง", value=0.0)
discount = st.number_input("🔻 ส่วนลด", value=0.0)

st.subheader("📦 รายการสินค้า")
c1,c2,c3 = st.columns(3)
name = c1.text_input("สินค้า")
qty = c2.number_input("จำนวน", 1, value=1)
price = c3.number_input("ราคา", 0.0)

if st.button("➕ เพิ่ม"):
    if name:
        st.session_state.invoice_items.append({
            "name": name,
            "qty": qty,
            "price": price,
            "amount": qty * price
        })

if st.session_state.invoice_items:
    df = pd.DataFrame(st.session_state.invoice_items)
    st.dataframe(df, use_container_width=True)

subtotal = sum(i["amount"] for i in st.session_state.invoice_items)
vat = subtotal * 0.07
total = subtotal + vat + shipping - discount

st.markdown(f"### 💰 รวมสุทธิ {total:,.2f} บาท")

# ===== PREVIEW =====
if st.button("🧾 Preview"):
    st.session_state.preview = True

if st.session_state.preview:
    st.subheader("🧾 Preview Invoice")
    st.dataframe(pd.DataFrame(st.session_state.invoice_items))

    if st.button("✅ ยืนยันบันทึก"):
        inv_no = next_invoice_no()
        today = datetime.today().strftime("%d/%m/%Y")
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        ws_inv.append_row([
            inv_no, today, customer, address,
            subtotal, vat, shipping, discount, total, now
        ])

        for it in st.session_state.invoice_items:
            ws_item.append_row([
                inv_no, it["name"], it["qty"], it["price"], it["amount"]
            ])

        st.success(f"✅ บันทึก {inv_no} เรียบร้อย")
        st.session_state.invoice_items = []
        st.session_state.preview = False
        st.rerun()
