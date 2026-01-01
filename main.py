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

# ================= 1. CONFIG =================
st.set_page_config(page_title="Logistics System Pro", layout="wide")

try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except:
    st.error("⚠️ ไม่พบไฟล์ THSARABUN BOLD.ttf")

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INV_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

# ================= 2. GOOGLE SHEET =================
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

@st.cache_data(ttl=60)
def load_data():
    sh = init_sheet()
    inv = sh.worksheet(INV_SHEET).get_all_records()
    items = sh.worksheet(ITEM_SHEET).get_all_records()
    return pd.DataFrame(inv), pd.DataFrame(items)

client = init_sheet()
ws_inv = client.worksheet(INV_SHEET)
ws_item = client.worksheet(ITEM_SHEET)
inv_df, item_df = load_data()

# ================= 3. SESSION STATE =================
transport_fields = [
    "doc_status", "car_id", "driver_name", "payment_status",
    "date_out", "time_out", "date_in", "time_in",
    "ref_tax_id", "ref_receipt_id", "seal_no",
    "pay_term", "ship_method", "driver_license",
    "receiver_name", "issuer_name", "sender_name",
    "checker_name", "remark",
    "comp_name", "comp_address", "comp_tax_id",
    "comp_phone", "comp_doc_title"
]

def reset_form():
    st.session_state.invoice_items = []
    st.session_state.form_customer = ""
    st.session_state.form_address = ""
    st.session_state.form_shipping = 0.0
    st.session_state.form_discount = 0.0
    st.session_state.form_vat = 0.0
    st.session_state.form_doc_status = "Active"
    st.session_state.form_payment_status = "ค้างชำระ"
    for f in transport_fields:
        st.session_state[f"form_{f}"] = ""

if "invoice_items" not in st.session_state:
    reset_form()

# ================= 4. HELPER =================
def next_inv_no(df):
    if df.empty:
        return "INV-0001"
    last = df["invoice_no"].iloc[-1]
    try:
        return f"INV-{int(last.split('-')[1])+1:04d}"
    except:
        return "INV-0001"

# ================= 5. PDF =================
def create_pdf(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    c.setFont("ThaiFontBold", 16)
    c.drawString(2*cm, h-1.5*cm, inv.get("comp_name",""))
    c.setFont("ThaiFontBold", 10)
    c.drawString(2*cm, h-2.2*cm, inv.get("comp_address",""))
    c.drawString(2*cm, h-2.7*cm,
        f"Tax ID: {inv.get('comp_tax_id','')} โทร {inv.get('comp_phone','')}"
    )

    c.setFont("ThaiFontBold", 20)
    c.drawRightString(19*cm, h-1.5*cm,
        inv.get("comp_doc_title","ใบกำกับขนส่ง")
    )

    c.setFont("ThaiFontBold", 12)
    c.drawRightString(19*cm, h-2.4*cm, f"เลขที่ {inv['invoice_no']}")
    c.drawRightString(19*cm, h-3.0*cm, f"วันที่ {inv['date']}")

    y = h - 4.2*cm
    c.setFont("ThaiFontBold", 11)
    c.drawString(2*cm, y, f"ลูกค้า: {inv['customer']}")
    c.drawString(2*cm, y-0.6*cm, f"ที่อยู่: {inv['address']}")

    y -= 2*cm
    c.line(2*cm, y, 19*cm, y)

    y -= 1*cm
    for it in items:
        c.drawString(2*cm, y, it["product"])
        c.drawRightString(12*cm, y, str(it["qty"]))
        c.drawRightString(15*cm, y, f"{it['price']:,.2f}")
        c.drawRightString(19*cm, y, f"{it['amount']:,.2f}")
        y -= 0.6*cm

    y -= 1*cm
    c.setFont("ThaiFontBold", 12)
    c.drawRightString(19*cm, y, f"ยอดสุทธิ {inv['total']:,.2f} บาท")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= 6. UI =================
st.title("🚚 ใบกำกับขนส่งสินค้า")

with st.expander("🔍 ค้นหา / สร้างซ้ำ"):
    if not inv_df.empty:
        options = [
            f"{r['invoice_no']} | {r['customer']}"
            for _, r in inv_df.iterrows()
        ]
        sel = st.selectbox("เลือกรายการ", [""] + options[::-1])

        if sel:
            inv_no = sel.split(" | ")[0]
            old_inv = inv_df[inv_df["invoice_no"] == inv_no].iloc[0].to_dict()
            old_items = item_df[item_df["invoice_no"] == inv_no].to_dict("records")

            if st.button("🔄 สร้างซ้ำรายการ"):
                st.session_state.form_customer = old_inv.get("customer","")
                st.session_state.form_address = old_inv.get("address","")
                st.session_state.form_shipping = float(old_inv.get("shipping",0))
                st.session_state.form_discount = float(old_inv.get("discount",0))
                st.session_state.form_vat = float(old_inv.get("vat",0))

                for f in transport_fields:
                    st.session_state[f"form_{f}"] = old_inv.get(f,"")

                st.session_state.form_doc_status = old_inv.get("doc_status","Active")
                st.session_state.form_payment_status = old_inv.get("pay_status","ค้างชำระ")

                st.session_state.invoice_items = []
                for it in old_items:
                    st.session_state.invoice_items.append({
                        "product": it["product"],
                        "unit": it.get("unit",""),
                        "qty": int(float(it["qty"])),
                        "price": float(it["price"]),
                        "amount": float(it["amount"])
                    })
                st.rerun()

            st.download_button(
                "📥 PDF เดิม",
                create_pdf(old_inv, old_items),
                f"{inv_no}.pdf"
            )

# ================= 7. FORM =================
customer = st.text_input("ลูกค้า", st.session_state.form_customer)
address = st.text_area("ที่อยู่", st.session_state.form_address)

st.subheader("📦 รายการสินค้า")
p = st.text_input("สินค้า")
q = st.number_input("จำนวน", min_value=1)
pr = st.number_input("ราคา", min_value=0.0)

if st.button("➕ เพิ่ม"):
    st.session_state.invoice_items.append({
        "product": p, "qty": q,
        "price": pr, "amount": q*pr
    })
    st.rerun()

subtotal = sum(i["amount"] for i in st.session_state.invoice_items)
vat = st.number_input("VAT", value=st.session_state.form_vat)
shipping = st.number_input("ค่าขนส่ง", value=st.session_state.form_shipping)
discount = st.number_input("ส่วนลด", value=st.session_state.form_discount)
total = subtotal + vat + shipping - discount

st.write(f"### 💰 รวม {total:,.2f} บาท")

# ================= 8. SAVE =================
if st.button("✅ บันทึก + PDF"):
    inv_no = next_inv_no(inv_df)
    today = datetime.now().strftime("%d/%m/%Y")

    ws_inv.append_row([
        inv_no, today, customer, address,
        subtotal, vat, shipping, discount, total,
        st.session_state.form_doc_status
    ])

    for it in st.session_state.invoice_items:
        ws_item.append_row([
            inv_no, it["product"], it.get("unit",""),
            it["qty"], it["price"], it["amount"]
        ])

    pdf = create_pdf({
        "invoice_no": inv_no,
        "date": today,
        "customer": customer,
        "address": address,
        "total": total
    }, st.session_state.invoice_items)

    st.download_button("📥 ดาวน์โหลด PDF", pdf, f"{inv_no}.pdf")
    reset_form()
