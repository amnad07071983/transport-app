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

# Font
try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
    TH_FONT = "ThaiFontBold"
except:
    TH_FONT = "Helvetica-Bold"
    st.warning("ไม่พบฟอนต์ THSARABUN ใช้ Helvetica แทน")

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

@st.cache_data(ttl=10)
def get_data_cached():
    client = init_sheet()
    return (
        pd.DataFrame(client.worksheet(INV_SHEET).get_all_records()),
        pd.DataFrame(client.worksheet(ITEM_SHEET).get_all_records())
    )

client = init_sheet()
inv_df, item_df = get_data_cached()
ws_inv = client.worksheet(INV_SHEET)
ws_item = client.worksheet(ITEM_SHEET)

# ================= 3. SESSION STATE =================
transport_fields = [
    "car_id", "driver_name", "payment_status",
    "date_out", "time_out", "date_in", "time_in",
    "ref_tax_id", "ref_receipt_id", "seal_no",
    "pay_term", "ship_method", "driver_license",
    "receiver_name", "issuer_name", "sender_name",
    "checker_name", "remark"
]

def reset_form():
    st.session_state.edit_mode = False
    st.session_state.current_inv_no = ""
    st.session_state.invoice_items = []
    st.session_state.form_customer = ""
    st.session_state.form_address = ""
    st.session_state.form_doc_status = "ใช้งาน"
    st.session_state.form_shipping = 0.0
    st.session_state.form_discount = 0.0
    for f in transport_fields:
        st.session_state[f"form_{f}"] = ""

if "edit_mode" not in st.session_state:
    reset_form()

# ================= 4. HELPERS =================
def next_inv_no(df):
    if df.empty:
        return "INV-0001"
    df = df.sort_values("invoice_no")
    last = df["invoice_no"].iloc[-1]
    try:
        return f"INV-{int(last.split('-')[1]) + 1:04d}"
    except:
        return "INV-0001"

def create_pdf(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    c.setFont(TH_FONT, 20)
    c.drawString(2*cm, h-2*cm, "ใบกำกับขนส่งสินค้า")

    c.setFont(TH_FONT, 14)
    c.drawString(2*cm, h-3.5*cm, f"เลขที่: {inv['invoice_no']}")
    c.drawString(2*cm, h-4.5*cm, f"วันที่: {inv['date']}")
    c.drawString(2*cm, h-5.5*cm, f"ลูกค้า: {inv['customer']}")

    y = h - 7*cm
    c.line(2*cm, y, 19*cm, y)

    for it in items:
        y -= 0.8*cm
        c.drawString(
            2.2*cm, y,
            f"{it['product']} ({it['qty']} x {it['price']:,.2f})"
        )
        c.drawRightString(19*cm, y, f"{it['amount']:,.2f}")

    y -= 1.2*cm
    c.setFont(TH_FONT, 16)
    c.drawRightString(19*cm, y, f"ยอดสุทธิ: {inv['total']:,.2f} บาท")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= 5. UI =================
st.title("🚚 ระบบจัดการใบแจ้งหนี้ขนส่ง")

with st.expander("🔍 ค้นหา / แก้ไข"):
    if not inv_df.empty:
        options = [
            f"{r['invoice_no']} | {r['customer']} | {r.get('doc_status','ใช้งาน')}"
            for _, r in inv_df.iterrows()
        ]
        sel = st.selectbox("เลือกรายการ", [""] + options[::-1])
        if sel and st.button("📝 แก้ไข"):
            sel_no = sel.split(" | ")[0]
            old = inv_df[inv_df["invoice_no"] == sel_no].iloc[0]

            st.session_state.edit_mode = True
            st.session_state.current_inv_no = sel_no
            st.session_state.form_customer = old["customer"]
            st.session_state.form_address = old["address"]
            st.session_state.form_doc_status = old["doc_status"]
            st.session_state.form_shipping = float(old["shipping"])
            st.session_state.form_discount = float(old["discount"])

            for f in transport_fields:
                st.session_state[f"form_{f}"] = old.get(f, "")

            st.session_state.invoice_items = (
                item_df[item_df["invoice_no"] == sel_no]
                .to_dict("records")
            )
            st.rerun()

# ================= 6. FORM =================
customer = st.text_input("ลูกค้า", st.session_state.form_customer)
address = st.text_area("ที่อยู่", st.session_state.form_address)

doc_status = st.selectbox(
    "สถานะ",
    ["ใช้งาน", "ยกเลิก"],
    index=0 if st.session_state.form_doc_status == "ใช้งาน" else 1
)

shipping = st.number_input("ค่าขนส่ง", value=st.session_state.form_shipping)
discount = st.number_input("ส่วนลด", value=st.session_state.form_discount)

st.subheader("📦 รายการสินค้า")
p = st.text_input("สินค้า")
q = st.number_input("จำนวน", min_value=1, step=1)
pr = st.number_input("ราคา", min_value=0.0)

if st.button("➕ เพิ่ม") and p:
    st.session_state.invoice_items.append({
        "product": p,
        "qty": q,
        "price": pr,
        "amount": q * pr
    })
    st.rerun()

subtotal = sum(i["amount"] for i in st.session_state.invoice_items)
grand_total = subtotal + shipping - discount
st.success(f"รวมสุทธิ {grand_total:,.2f} บาท")

# ================= 7. SAVE =================
if st.button("✅ บันทึก"):
    target = (
        st.session_state.current_inv_no
        if st.session_state.edit_mode
        else next_inv_no(inv_df)
    )

    today = datetime.now().strftime("%d/%m/%Y")

    header = [
        target, today, customer, address,
        subtotal, 0,  # 0 = VAT (สำรอง)
        shipping, discount,
        grand_total, doc_status
    ]

    for f in transport_fields:
        header.append(st.session_state.get(f"form_{f}", ""))

    if st.session_state.edit_mode:
        cells = ws_inv.findall(target)
        row = [c for c in cells if c.col == 1][0].row
        ws_inv.update(f"A{row}", [header])

        rows = ws_item.get_all_values()
        del_rows = [i+1 for i, r in enumerate(rows) if r and r[0] == target]
        for r in reversed(del_rows):
            ws_item.delete_rows(r)
    else:
        ws_inv.append_row(header)

    for it in st.session_state.invoice_items:
        ws_item.append_row([
            target, it["product"], it["qty"], it["price"], it["amount"]
        ])

    pdf = create_pdf(
        {"invoice_no": target, "date": today, "customer": customer, "total": grand_total},
        st.session_state.invoice_items
    )

    st.download_button("📄 ดาวน์โหลด PDF", pdf, f"{target}.pdf")
    st.success("บันทึกเรียบร้อย")
    st.cache_data.clear()
    reset_form()
