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

try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except:
    st.error("⚠️ ไม่พบไฟล์ฟอนต์ THSARABUN BOLD.ttf")

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INV_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

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
def get_data_cached():
    client = init_sheet()
    inv = client.worksheet(INV_SHEET).get_all_records()
    items = client.worksheet(ITEM_SHEET).get_all_records()
    return pd.DataFrame(inv), pd.DataFrame(items)

client = init_sheet()
inv_df, item_df = get_data_cached()
ws_inv = client.worksheet(INV_SHEET)
ws_item = client.worksheet(ITEM_SHEET)

# ================= 2. SESSION STATE =================
transport_fields = [
    "doc_status", "car_id", "driver_name", "pay_status",
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
    for f in transport_fields:
        st.session_state[f"form_{f}"] = ""
    st.session_state.form_doc_status = "Active"
    st.session_state.form_pay_status = "ค้างชำระ"

if "invoice_items" not in st.session_state:
    reset_form()

# ================= 3. HELPERS =================
def next_inv_no(df):
    if df.empty:
        return "INV-0001"
    last = df["invoice_no"].iloc[-1]
    return f"INV-{int(last.split('-')[1])+1:04d}"

def create_pdf(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    c.setFont("ThaiFontBold", 16)
    c.drawString(2*cm, h-1.5*cm, inv.get("comp_name",""))
    c.setFont("ThaiFontBold", 10)
    c.drawString(2*cm, h-2.1*cm, inv.get("comp_address",""))
    c.drawString(2*cm, h-2.6*cm, inv.get("comp_tax_id",""))

    c.setFont("ThaiFontBold", 18)
    c.drawRightString(19*cm, h-1.5*cm, inv.get("comp_doc_title",""))

    y = h-5*cm
    c.setFont("ThaiFontBold", 11)
    for it in items:
        c.drawString(2*cm, y, it["product"])
        c.drawRightString(19*cm, y, f"{it['amount']:,.2f}")
        y -= 0.6*cm

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= 4. UI =================
st.title("🚚 ระบบจัดการใบแจ้งหนี้ขนส่ง (ไฟล์เดียว)")

with st.expander("🔍 ค้นหาเอกสารย้อนหลัง"):
    if not inv_df.empty:
        selected = st.selectbox(
            "เลือก",
            [""] + [f"{r.invoice_no} | {r.customer}" for _, r in inv_df.iterrows()][::-1]
        )

        if selected:
            no = selected.split(" | ")[0]
            old_inv = inv_df[inv_df.invoice_no == no].iloc[0].to_dict()
            old_items = item_df[item_df.invoice_no == no].to_dict("records")

            if st.button("🔄 ดึงมาแก้ไข"):
                for f in transport_fields:
                    st.session_state[f"form_{f}"] = old_inv.get(f,"")
                st.session_state.form_customer = old_inv["customer"]
                st.session_state.form_address = old_inv["address"]
                st.session_state.invoice_items = old_items
                st.rerun()

            pdf = create_pdf(old_inv, old_items)
            st.download_button("📥 PDF", pdf, f"{no}.pdf")

st.divider()

st.subheader("📝 รายการสินค้า")
if st.button("➕ เพิ่มตัวอย่าง"):
    st.session_state.invoice_items.append(
        {"product":"ค่าขนส่ง", "amount":1000}
    )

if st.button("💾 บันทึก"):
    new_no = next_inv_no(inv_df)
    ws_inv.append_row([new_no, datetime.now().strftime("%d/%m/%Y")])
    for it in st.session_state.invoice_items:
        ws_item.append_row([new_no, it["product"], it["amount"]])
    st.success("บันทึกแล้ว")
