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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ================= FONT (THAI) =================
pdfmetrics.registerFont(TTFont("TH", "THSarabunNew.ttf"))

# ================= CONFIG =================
st.set_page_config(page_title="Transportation Invoice", layout="wide")

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INV_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

# ================= GOOGLE SHEET =================
@st.cache_resource
def init_sheet():
scope = [
https://spreadsheets.google.com/feeds,
https://www.googleapis.com/auth/drive,
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

# ================= SESSION =================
st.session_state.setdefault("invoice_items", [])
st.session_state.setdefault("preview", False)

# ================= UTIL =================
def next_invoice_no():
if inv_df.empty:
return "INV-0001"
last = inv_df["invoice_no"].iloc[-1]
n = int(last.split("-")[1]) + 1
return f"INV-{n:04d}"

def add_item():
name = st.session_state.get("pname", "")
qty = int(st.session_state.get("pqty", 1))
price = float(st.session_state.get("pprice", 0.0))

if name:
st.session_state.invoice_items.append({
name: name,
qty: qty,
price: price,
amount: qty * price
})
st.session_state.pname = ""
st.session_state.pqty = 1
st.session_state.pprice = 0.0

def create_pdf(inv, items):
buf = io.BytesIO()
c = canvas.Canvas(buf, pagesize=A4)
w, h = A4

c.setFont("TH", 18)
c.drawString(2*cm, h-2*cm, "ใบกำกับขนส่งสินค้า")

c.setFont("TH", 14)
c.drawString(2*cm, h-3.2*cm, f"เลขที่: {inv['invoice_no']}")
c.drawString(2*cm, h-4*cm, f"วันที่: {inv['date']}")

c.drawString(2*cm, h-5.2*cm, f"ลูกค้า: {inv['customer']}")
c.drawString(2*cm, h-6*cm, f"ที่อยู่: {inv['address']}")

y = h - 7.5*cm
c.drawString(2*cm, y, "สินค้า")
c.drawRightString(12*cm, y, "จำนวน")
c.drawRightString(15*cm, y, "ราคา")
c.drawRightString(19*cm, y, "รวม")
y -= 0.7*cm

for it in items:
c.drawString(2*cm, y, it["name"])
c.drawRightString(12*cm, y, str(it["qty"]))
c.drawRightString(15*cm, y, f"{it['price']:,.2f}")
c.drawRightString(19*cm, y, f"{it['amount']:,.2f}")
y -= 0.6*cm

c.setFont("TH", 16)
c.drawRightString(19*cm, y-1*cm, f"รวมทั้งสิ้น {inv['total']:,.2f} บาท")

c.showPage()
c.save()
buf.seek(0)
return buf

# ================= UI =================
st.title("🚚 ระบบใบกำกับขนส่งสินค้า")

if not inv_df.empty:
st.info(f"🔢 Invoice ล่าสุด: {inv_df['invoice_no'].iloc[-1]}")

# ===== AUTO FOCUS =====
components.html("""
<script>
setTimeout(()=> {
const el = window.parent.document.querySelector('input[aria-label="ชื่อลูกค้า"]');
if(el) el.focus();
}, 100);
</script>
""", height=0)

# ===== FORM =====
customer = st.text_input(ชื่อลูกค้า"")"
address = st.text_area("ที่อยู่")

shipping = st.number_input("🚚 ค่าขนส่ง", min_value=0.0, value=0.0)
discount = st.number_input("🔻 ส่วนลด", min_value=0.0, value=0.0)

# ===== ADD ITEM =====
st.subheader("📦 เพิ่มสินค้า")
c1, c2, c3 = st.columns(3)
c1.text_input("สินค้า", key="pname")
c2.number_input("จำนวน", min_value=1, value=1, step=1, key="pqty")
c3.number_input("ราคา", min_value=0.0, value=0.0, step=1.0, key="pprice")

st.button("➕ เพิ่มสินค้า", on_click=add_item)

# ===== EDIT / DELETE =====
if st.session_state.invoice_items:
st.subheader("✏️ แก้ไข / ลบสินค้า")

df_items = pd.DataFrame(st.session_state.invoice_items)
st.dataframe(df_items, use_container_width=True)

idx = st.selectbox(
เลือกรายการ,
range(len(st.session_state.invoice_items)),
format_func=lambda i: st.session_state.invoice_items[i]["name"]
)

col1, col2, col3 = st.columns(3)
q = col1.number_input(
จำนวน,
min_value=1,
step=1,
value=int(st.session_state.invoice_items[idx]["qty"])
)
p = col2.number_input(
ราคา,
min_value=0.0,
step=1.0,
value=float(st.session_state.invoice_items[idx]["price"])
)

if col3.button("💾 อัปเดต"):
st.session_state.invoice_items[idx]["qty"] = q
st.session_state.invoice_items[idx]["price"] = p
st.session_state.invoice_items[idx]["amount"] = q * p
st.rerun()

if col3.button("🗑 ลบ"):
st.session_state.invoice_items.pop(idx)
st.rerun()

# ===== CALC =====
subtotal = sum(i["amount"] for i in st.session_state.invoice_items)
vat = subtotal * 0.07
total = subtotal + vat + shipping - discount

st.markdown(f"### 💰 รวมสุทธิ **{total:,.2f} บาท**")

# ===== PREVIEW & SAVE =====
if st.button("🧾 Preview Invoice") and st.session_state.invoice_items:
st.session_state.preview = True

if st.session_state.preview:
st.subheader("🧾 Preview")
st.dataframe(pd.DataFrame(st.session_state.invoice_items))

if st.button("📄 Export PDF"):
inv_data = {
invoice_no: next_invoice_no(),
date: datetime.today().strftime("%d/%m/%Y"),
customer: customer,
address: address,
total: total
}
pdf = create_pdf(inv_data, st.session_state.invoice_items)
st.download_button(
⬇ ดาวน์โหลด PDF,
pdf,
file_name=f"{inv_data['invoice_no']}.pdf",
mime="application/pdf"
)

if st.button("✅ บันทึก Invoice"):
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
st.cache_resource.clear()
st.rerun()
