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
    return gspread.authorize(creds).open_by_key(SHEET_ID)

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
    n = int(inv_df["invoice_no"].iloc[-1].split("-")[1]) + 1
    return f"INV-{n:04d}"

def col(row, *names):
    for n in names:
        if n in row:
            return row[n]
    return 0

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

    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(18*cm, y-1*cm, f"TOTAL {inv['total']:,.2f} บาท")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= UI =================
st.title("🚚 ระบบใบกำกับขนส่งสินค้า")

# ===== SEARCH =====
search = st.text_input("🔍 ค้นหา Invoice")
show_df = inv_df
if search:
    show_df = inv_df[inv_df["invoice_no"].str.contains(search, case=False)]

st.dataframe(show_df, use_container_width=True)

# ===== DUPLICATE / EDIT =====
sel = st.selectbox("📂 เลือก Invoice", [""] + show_df["invoice_no"].tolist())

if sel:
    inv = inv_df[inv_df["invoice_no"] == sel].iloc[0]
    its = item_df[item_df["invoice_no"] == sel]

    if st.button("📄 Duplicate Invoice"):
        st.session_state.items = [
            {
                "name": col(r, "name", "product", "item_name"),
                "qty": int(col(r, "qty", "quantity")),
                "price": float(col(r, "price", "unit_price")),
                "amount": float(col(r, "amount", "total"))
            }
            for _, r in its.iterrows()
        ]
        st.session_state.customer = inv["customer"]
        st.session_state.address = inv["address"]
        st.session_state.edit_invoice = None
        st.rerun()

    if st.button("✏️ แก้ไข Invoice"):
        st.session_state.edit_invoice = sel
        st.session_state.items = [
            {
                "name": col(r, "name", "product"),
                "qty": int(col(r, "qty")),
                "price": float(col(r, "price")),
                "amount": float(col(r, "amount"))
            }
            for _, r in its.iterrows()
        ]
        st.session_state.customer = inv["customer"]
        st.session_state.address = inv["address"]
        st.rerun()

    if st.button("🧾 PDF"):
        pdf = pdf_invoice(inv.to_dict(), st.session_state.items)
        st.download_button("⬇️ Download PDF", pdf, f"{sel}.pdf")

# ===== FORM =====
components.html("""
<script>
setTimeout(()=> {
  const el = window.parent.document.querySelector('input[aria-label="ชื่อลูกค้า"]');
  if(el) el.focus();
},100);
</script>
""", height=0)

customer = st.text_input("ชื่อลูกค้า", st.session_state.get("customer",""))
address = st.text_area("ที่อยู่", st.session_state.get("address",""))

shipping = float(st.number_input("🚚 ค่าขนส่ง", value=0.0))
discount = float(st.number_input("🔻 ส่วนลด", value=0.0))

# ===== ADD ITEM =====
st.subheader("📦 เพิ่มสินค้า")
c1,c2,c3 = st.columns(3)
name = c1.text_input("สินค้า")
qty = int(c2.number_input("จำนวน", min_value=1, value=1))
price = float(c3.number_input("ราคา", min_value=0.0))

if st.button("➕ เพิ่มสินค้า"):
    st.session_state.items.append({
        "name": name,
        "qty": qty,
        "price": price,
        "amount": qty * price
    })

# ===== EDIT ITEMS =====
if st.session_state.items:
    df = pd.DataFrame(st.session_state.items)
    st.dataframe(df, use_container_width=True)

    idx = st.selectbox(
        "เลือกรายการ",
        range(len(st.session_state.items)),
        format_func=lambda i: st.session_state.items[i]["name"]
    )

    q = int(st.number_input("แก้ไขจำนวน", min_value=1, value=int(st.session_state.items[idx]["qty"])))
    p = float(st.number_input("แก้ไขราคา", min_value=0.0, value=float(st.session_state.items[idx]["price"])))

    if st.button("💾 อัปเดต"):
        st.session_state.items[idx].update(
            qty=q,
            price=p,
            amount=q*p
        )
        st.rerun()

    if st.button("🗑 ลบ"):
        st.session_state.items.pop(idx)
        st.rerun()

# ===== CALC =====
subtotal = sum(i["amount"] for i in st.session_state.items)
vat = subtotal * 0.07
total = subtotal + vat + shipping - discount

st.markdown(f"### 💰 รวมสุทธิ **{total:,.2f} บาท**")

# ===== SAVE =====
if st.button("🧾 Preview"):
    st.session_state.preview = True

if st.session_state.preview:
    if st.button("✅ บันทึก Invoice"):
        inv_no = st.session_state.edit_invoice or next_invoice_no()
        today = datetime.today().strftime("%d/%m/%Y")
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        if st.session_state.edit_invoice:
            row = inv_df[inv_df["invoice_no"] == inv_no].index[0] + 2
            ws_inv.delete_rows(row)
            for i in range(len(ws_item.get_all_values()),1,-1):
                if ws_item.cell(i,1).value == inv_no:
                    ws_item.delete_rows(i)

        ws_inv.append_row([inv_no,today,customer,address,subtotal,vat,shipping,discount,total,now])
        for it in st.session_state.items:
            ws_item.append_row([inv_no,it["name"],it["qty"],it["price"],it["amount"]])

        st.success(f"✅ บันทึก {inv_no} เรียบร้อย")
        st.session_state.items = []
        st.session_state.preview = False
        st.cache_resource.clear()
        st.rerun()
