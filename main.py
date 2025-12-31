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

# ลงทะเบียนฟอนต์ภาษาไทย (ต้องมีไฟล์ font ในโฟลเดอร์เดียวกัน)
try:
    pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
except:
    st.error("⚠️ ไม่พบไฟล์ฟอนต์ 'THSARABUN BOLD.ttf'")

SHEET_ID = "1ZdTeTeDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INV_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

@st.cache_resource
def init_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds).open_by_key(SHEET_ID)

@st.cache_data(ttl=10)
def get_data_cached():
    client = init_sheet()
    try:
        inv = client.worksheet(INV_SHEET).get_all_records()
        items = client.worksheet(ITEM_SHEET).get_all_records()
        return pd.DataFrame(inv), pd.DataFrame(items)
    except:
        return pd.DataFrame(), pd.DataFrame()

# เชื่อมต่อ Google Sheets
client = init_sheet()
inv_df, item_df = get_data_cached()
ws_inv = client.worksheet(INV_SHEET)
ws_item = client.worksheet(ITEM_SHEET)

# ================= 2. SESSION STATE & RESET =================
# รายการฟิลด์ขนส่ง (18 ฟิลด์)
transport_fields = [
    "car_id", "driver_name", "payment_status", "date_out", "time_out",
    "date_in", "time_in", "ref_tax_id", "ref_receipt_id", "seal_no",
    "pay_term", "ship_method", "driver_license", "receiver_name",
    "issuer_name", "sender_name", "checker_name", "remark"
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
    for field in transport_fields:
        st.session_state[f"form_{field}"] = ""

if "invoice_items" not in st.session_state:
    reset_form()

# ================= 3. HELPER FUNCTIONS =================
def next_inv_no(df):
    if df.empty or "invoice_no" not in df.columns: return "INV-0001"
    last = df["invoice_no"].iloc[-1]
    try:
        num = int(str(last).split('-')[1])
        return f"INV-{num + 1:04d}"
    except: return "INV-0001"

def create_pdf(inv, items):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("ThaiFontBold", 20)
    c.drawString(2*cm, h-2*cm, "ใบกำกับขนส่งสินค้า (Transportation Invoice)")
    c.setFont("ThaiFontBold", 14)
    c.drawString(2*cm, h-3.2*cm, f"เลขที่: {inv.get('invoice_no','')}")
    c.drawString(2*cm, h-4*cm, f"วันที่: {inv.get('date','')}")
    c.drawString(2*cm, h-5.2*cm, f"ลูกค้า: {inv.get('customer','')}")
    c.drawString(15*cm, h-3.2*cm, f"สถานะ: {inv.get('doc_status','ใช้งาน')}")
    
    y = h - 7*cm
    c.line(2*cm, y, 19*cm, y)
    c.drawString(2.2*cm, y-0.6*cm, "รายการสินค้า")
    c.drawRightString(19*cm, y-0.6*cm, "รวมเงิน")
    c.line(2*cm, y-0.8*cm, 19*cm, y-0.8*cm)
    
    y -= 1.5*cm
    for it in items:
        c.drawString(2.2*cm, y, f"{it.get('product','')} ({it.get('qty',0)} x {it.get('price',0):,.2f})")
        c.drawRightString(19*cm, y, f"{float(it.get('amount',0)):,.2f}")
        y -= 0.8*cm
        
    y_sum = y - 1*cm
    c.setFont("ThaiFontBold", 16)
    c.drawRightString(19*cm, y_sum, f"ยอดสุทธิรวม: {float(inv.get('total',0)):,.2f} บาท")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= 4. UI - SEARCH & EDIT =================
st.title("🚚 ระบบจัดการใบแจ้งหนี้ขนส่ง (Full Version)")

with st.expander("🔍 ค้นหาเพื่อแก้ไข / ทำซ้ำ / พิมพ์ PDF"):
    if not inv_df.empty:
        # แสดงสถานะในตัวเลือกด้วย
        options = [f"{r['invoice_no']} | {r['customer']} | {r.get('doc_status','ใช้งาน')}" for _, r in inv_df.iterrows()]
        selected = st.selectbox("เลือกรายการประวัติ", [""] + options[::-1])
        
        if selected:
            sel_no = selected.split(" | ")[0]
            col_b1, col_b2 = st.columns(2)
            
            with col_b1:
                if st.button("📝 เรียกข้อมูลมาแก้ไข (Update)"):
                    old_inv = inv_df[inv_df["invoice_no"] == sel_no].iloc[0]
                    st.session_state.edit_mode = True
                    st.session_state.current_inv_no = sel_no
                    st.session_state.form_customer = old_inv.get("customer", "")
                    st.session_state.form_address = old_inv.get("address", "")
                    st.session_state.form_doc_status = old_inv.get("doc_status", "ใช้งาน")
                    st.session_state.form_shipping = float(old_inv.get("shipping", 0))
                    st.session_state.form_discount = float(old_inv.get("discount", 0))
                    for field in transport_fields:
                        st.session_state[f"form_{field}"] = str(old_inv.get(field, ""))
                    
                    old_items = item_df[item_df["invoice_no"] == sel_no]
                    st.session_state.invoice_items = old_items.to_dict('records')
                    st.rerun()
            
            with col_b2:
                # พิมพ์จากข้อมูลเดิมในฐานข้อมูล
                old_inv_dict = inv_df[inv_df["invoice_no"] == sel_no].iloc[0].to_dict()
                old_items_list = item_df[item_df["invoice_no"] == sel_no].to_dict('records')
                pdf_old = create_pdf(old_inv_dict, old_items_list)
                st.download_button(f"📄 ดาวน์โหลด PDF ({sel_no})", pdf_old, f"{sel_no}.pdf", "application/pdf")
    else:
        st.info("ยังไม่มีข้อมูลในฐานข้อมูล")

st.divider()

# ================= 5. MAIN FORM UI =================
if st.session_state.edit_mode:
    st.warning(f"正在แก้ไขข้อมูลเลขที่: {st.session_state.current_inv_no}")
    if st.button("➕ เปลี่ยนเป็นสร้างใบใหม่ (Reset)"):
        reset_form()
        st.rerun()

st.subheader("📝 ข้อมูลลูกค้าและสถานะ")
c1, c2, c3 = st.columns(3)
with c1:
    customer = st.text_input("ชื่อลูกค้า", value=st.session_state.form_customer)
    address = st.text_area("ที่อยู่", value=st.session_state.form_address)
    doc_status = st.selectbox("สถานะเอกสาร", ["ใช้งาน", "ยกเลิก"], 
                               index=0 if st.session_state.form_doc_status == "ใช้งาน" else 1)
with c2:
    car_id = st.text_input("ทะเบียนรถ (Car ID)", value=st.session_state.form_car_id)
    driver_name = st.text_input("คนขับ", value=st.session_state.form_driver_name)
    pay_status = st.selectbox("การชำระเงิน", ["ค้างชำระ", "ชำระแล้ว"], 
                              index=0 if st.session_state.form_payment_status != "ชำระแล้ว" else 1)
with c3:
    shipping = st.number_input("ค่าขนส่ง", value=st.session_state.form_shipping, min_value=0.0)
    discount = st.number_input("ส่วนลด", value=st.session_state.form_discount, min_value=0.0)
    remark = st.text_area("หมายเหตุ", value=st.session_state.form_remark)

st.subheader("📦 รายการสินค้า")
ci1, ci2, ci3 = st.columns([3,1,1])
p_name = ci1.text_input("ชื่อสินค้า", key="p_name")
p_qty = ci2.number_input("จำนวน", min_value=1, key="p_qty")
p_price = ci3.number_input("ราคา/หน่วย", min_value=0.0, key="p_price")

if st.button("➕ เพิ่มรายการสินค้า"):
    if p_name:
        st.session_state.invoice_items.append({"product": p_name, "qty": p_qty, "price": p_price, "amount": p_qty*p_price})
        st.rerun()

if st.session_state.invoice_items:
    st.write("---")
    for i, item in enumerate(st.session_state.invoice_items):
        col_it = st.columns([4, 1])
        col_it[0].info(f"{i+1}. {item['product']} | {item['qty']} x {item['price']:,.2f} = {item['amount']:,.2f}")
        if col_it[1].button("🗑️ ลบ", key=f"del_{i}"):
            st.session_state.invoice_items.pop(i)
            st.rerun()

    subtotal = sum(i['amount'] for i in st.session_state.invoice_items)
    grand_total = subtotal + shipping - discount
    st.write(f"### ยอดสุทธิรวม: {grand_total:,.2f} บาท")

    # ================= 6. SAVE & UPDATE LOGIC =================
    if st.button("✅ บันทึกข้อมูลและรับ PDF", type="primary"):
        with st.spinner("กำลังบันทึกข้อมูลลงระบบ..."):
            # กำหนดเลขที่ INV (ใช้ของเดิมถ้าเป็นโหมดแก้ไข)
            target_no = st.session_state.current_inv_no if st.session_state.edit_mode else next_inv_no(inv_df)
            date_now = datetime.now().strftime("%d/%m/%Y")
            
            # เตรียมข้อมูล Header (เพิ่ม doc_status เข้าไปด้วย)
            header_row = [target_no, date_now, customer, address, subtotal, 0, shipping, discount, grand_total, doc_status]
            header_row += [car_id, driver_name, pay_status, st.session_state.form_date_out, st.session_state.form_time_out, "", "", "", "", st.session_state.form_seal_no, "", st.session_state.form_ship_method, "", "", "", "", "", remark]
            
            if st.session_state.edit_mode:
                # 1. แก้ไขบรรทัดเดิมใน Sheet Invoices
                cell = ws_inv.find(target_no)
                ws_inv.update(f'A{cell.row}', [header_row])
                
                # 2. ลบรายการสินค้าเดิมออกทั้งหมดของ INV นี้
                item_cells = ws_item.findall(target_no)
                if item_cells:
                    # ลบจากล่างขึ้นบนเพื่อไม่ให้ index เคลื่อน
                    rows_to_delete = sorted([c.row for c in item_cells], reverse=True)
                    for r in rows_to_delete:
                        ws_item.delete_rows(r)
            else:
                # เพิ่มบรรทัดใหม่
                ws_inv.append_row(header_row)

            # 3. บันทึกรายการสินค้าใหม่ (ทั้งกรณีสร้างใหม่และแก้ไข)
            for it in st.session_state.invoice_items:
                ws_item.append_row([target_no, it['product'], it['qty'], it['price'], it['amount']])
            
            # สร้าง PDF สำหรับดาวน์โหลดทันที
            pdf_out = create_pdf({"invoice_no": target_no, "date": date_now, "customer": customer, "address": address, "total": grand_total, "doc_status": doc_status}, st.session_state.invoice_items)
            
            st.success(f"บันทึกเรียบร้อย: {target_no}")
            st.download_button("📥 คลิกที่นี่เพื่อดาวน์โหลด PDF", pdf_out, f"{target_no}.pdf", "application/pdf")
            
            # ล้างค่าและรีเซ็ต
            st.cache_data.clear()
            reset_form()
            st.info("ระบบรีเซ็ตหน้าฟอร์มเรียบร้อย")
