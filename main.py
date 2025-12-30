import stream伴lit as st
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

# ================= FONT (THAI) =================
FONT_PATH = os.path.join(os.path.dirname(__file__), "ArialUnicodeMS.ttf")
pdfmetrics.registerFont(TTFont("ARIAL", FONT_PATH))

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
st.session_state.setdefault("preview", False)
st.session_state.setdefault("edit_invoice", None)

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

    c.setFont("ARIAL", 18)
    c.drawString(2*cm, h-2*cm, "ใบกำกับขนส่งสินค้า")

    c.setFont("ARIAL", 12)
    c.drawString(2*cm, h-3.5*cm, f"Invoice: {inv['invoice_no']}")
    c.drawString(2*cm, h-4.3*cm, f"วันที่: {inv['date']}")
    c.drawString(2*cm, h-5.5*cm, f"ลูกค้า: {inv['customer']}")
    c.drawString(2*cm, h-6.3*cm, f"ที่อยู่: {inv['address']}")

    y = h - 8*cm
    c.setFont("ARIAL", 11)
    c.drawString(2*cm, y, "รายการ")
    c.drawRightString(11*cm, y, "จำนวน")
    c.drawRightString(14*cm, y, "ราคา")
    c.drawRightString(18*cm, y, "รวม")

    y -= 0.7*cm
    for it in items:
        c.drawString(2*cm, y, it["name"])
        c.drawRightString(11*cm, y, str(it["qty"]))
        c.drawRightString(14*cm, y, f"{it['price']:,.2f}")
        c.drawRightString(18*cm, y, f"{it['amount']:,.2f}")
        y -= 0.6*cm

    y -= 0.5*cm
    c.setFont("ARIAL", 12)
    c.drawRightString(14*cm, y, "รวมทั้งสิ้น")
    c.drawRightString(18*cm, y, f"{inv['total']:,.2f} บาท")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= UI =================
st.title("🚚 ระบบใบกำกับขนส่งสินค้า")

if not inv_df.empty:
    st.info(f"🔢 Invoice ล่าสุด: {inv_df['invoice_no'].iloc[-1]}")

# ===== SEARCH =====
search = st.text_input("🔍 ค้นหา Invoice")
show_df = inv_df
if search:
    show_df = inv_df[inv_df["invoice_no"].str.contains(search, case=False)]

# ===== OPEN / DUPLICATE =====
st.subheader("📂 Invoice ที่บันทึกแล้ว")
sel = st.selectbox("เลือก Invoice", [""] + show_df["invoice_no"].tolist())

if sel:
    inv = inv_df[inv_df["invoice_no"] == sel].iloc[0]
    its = item_df[item_df["invoice_no"] == sel].to_dict("records")

    colA, colB = st.columns(2)

    if colA.button("📄 Duplicate Invoice"):
        st.session_state.items = [
            {
                "name": r["product"],
                "qty": int(r["qty"]),
                "price": float(r["price"]),
                "amount": float(r["amount"])
            } for r in its
        ]
        st.session_state.customer = inv["customer"]
        st.session_state.address = inv["address"]
        st.session_state.edit_invoice = None
        st.rerun()

    if colB.button("🧾 Export PDF"):
        pdf = pdf_invoice(inv.to_dict(), [
            {"name": r["product"], "qty": r["qty"], "price": r["price"], "amount": r["amount"]}
            for r in its
        ])
        st.download_button("⬇️ ดาวน์โหลด PDF", pdf, f"{sel}.pdf")

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

shipping = st.number_input("ค่าขนส่ง", min_value=0.0, value=0.0)
discount = st.number_input("ส่วนลด", min_value=0.0, value=0.0)

# ===== ITEMS =====
st.subheader("📦 รายการสินค้า")
c1,c2,c3 = st.columns(3)
name = c1.text_input("สินค้า")
qty = c2.number_input("จำนวน", min_value=1, value=1)
price = c3.number_input("ราคา", min_value=0.0, value=0.0)

if st.button("➕ เพิ่มสินค้า") and name:
    st.session_state.items.append({
        "name": name,
        "qty": int(qty),
        "price": float(price),
        "amount": float(qty * price)
    })

if st.session_state.items:
    df_items = pd.DataFrame(st.session_state.items)
    st.dataframe(df_items, use_container_width=True)

    idx = st.selectbox("เลือกรายการแก้ไข", range(len(st.session_state.items)))
    e1,e2,e3 = st.columns(3)

    q = e1.number_input("แก้ไขจำนวน", min_value=1, value=int(st.session_state.items[idx]["qty"]))
    p = e2.number_input("แก้ไขราคา", min_value=0.0, value=float(st.session_state.items[idx]["price"]))

    if e3.button("💾 อัปเดต"):
        st.session_state.items[idx]["qty"] = int(q)
        st.session_state.items[idx]["price"] = float(p)
        st.session_state.items[idx]["amount"] = float(q*p)
        st.rerun()

    if e3.button("🗑 ลบ"):
        st.session_state.items.pop(idx)
        st.rerun()

# ===== TOTAL =====
subtotal = sum(i["amount"] for i in st.session_state.items)
vat = subtotal * 0.07
total = subtotal + vat + shipping - discount

st.markdown(f"### 💰 รวมสุทธิ **{total:,.2f} บาท**")

# ===== SAVE =====
if st.button("💾 บันทึก Invoice") and st.session_state.items:
    inv_no = next_invoice_no()
    today = datetime.today().strftime("%d/%m/%Y")
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    ws_inv.append_row([
        inv_no, today, customer, address,
        subtotal, vat, shipping, discount, total, now
    ])

    for it in st.session_state.items:
        ws_item.append_row([
            inv_no, it["name"], it["qty"], it["price"], it["amount"]
        ])

    st.success(f"✅ บันทึก {inv_no} เรียบร้อย")
    st.session_state.items = []
    st.cache_resource.clear()
    st.rerun()
