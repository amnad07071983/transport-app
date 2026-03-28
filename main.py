import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import io
import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm, inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

# ================= 1. CONFIG & INITIALIZATION =================
st.set_page_config(page_title="JP - Logistics System", layout="wide")

FONT_NAME = 'Helvetica-Bold'
try:
    if os.path.exists('THSARABUN BOLD.ttf'):
        pdfmetrics.registerFont(TTFont('ThaiFontBold', 'THSARABUN BOLD.ttf'))
        FONT_NAME = 'ThaiFontBold'
except:
    pass

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INV_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"
INV_KEY = "invoice_no"

@st.cache_resource
def init_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds).open_by_key(SHEET_ID)

try:
    client = init_sheet()
    ws_inv = client.worksheet(INV_SHEET)
    ws_item = client.worksheet(ITEM_SHEET)
    
    @st.cache_data(ttl=5)
    def get_data_cached():
        inv = ws_inv.get_all_records()
        items = ws_item.get_all_records()
        return pd.DataFrame(inv), pd.DataFrame(items)
    
    inv_df, item_df = get_data_cached()
except Exception as e:
    st.error(f"❌ Connection Error: {e}")
    st.stop()

transport_fields = [
    "ผู้รับสินค้า-ชื่อ", "ผู้รับสินค้า-ที่อยู่", "ผู้รับสินค้า-เลขผู้เสียภาษี", "ผู้รับสินค้า-เบอร์โทร",
    "คลังรับผลิตภัณฑ์-ชื่อ", "คลังรับผลิตภัณฑ์-เลขผู้เสียภาษี", "คลังรับผลิตภัณฑ์-ที่อยู่",
    "ผู้รับผลิตภัณฑ์-ชื่อ", "ผู้รับผลิตภัณฑ์-เลขผู้เสียภาษี", "ผู้รับผลิตภัณฑ์-ที่อยู่", "ผู้รับผลิตภัณฑ์-หมายเลขตั๋ว",
    "ผู้ดำเนินการขนส่ง-ชื่อ", "ผู้ดำเนินการขนส่ง-เลขผู้เสียภาษี", "ผู้ดำเนินการขนส่ง-ที่อยู่", "ผู้ดำเนินการขนส่ง-เบอร์โทร",
    "ผู้ดำเนินการขนส่ง-ประเภทผู้รับจ้าง", "ผู้ดำเนินการขนส่ง-ใบอนุญาต",
    "ข้อมูลพนักงานขับรถ-ชื่อ", "ข้อมูลพนักงานขับรถ-เลขใบขับขี่", "ข้อมูลพนักงานขับรถ-เบอร์โทร", "ข้อมูลพนักงานขับรถ-ทะเบียนรถ",
    "ข้อมูลพนักงานขับรถ-วิธีขนส่ง", "ข้อมูลพนักงานขับรถ-วันออกเดินทาง", "ข้อมูลพนักงานขับรถ-เวลาออกเดินทาง",
    "ข้อมูลพนักงานขับรถ-วันที่ถึงปลายทาง", "ข้อมูลพนักงานขับรถ-เวลาที่ถึงปลายทาง",
    "การยืนยันและรับสินค้า-ผู้ออกเอกสาร", "การยืนยันและรับสินค้า-พนักงานขับรถ", "การยืนยันและรับสินค้า-ผู้รับสินค้า",
    "ผู้จำหน่าย-ชื่อ", "ผู้จำหน่าย-ที่อยู่", "ผู้จำหน่าย-เลขผู้เสียภาษี", "ผู้จำหน่าย-เบอร์โทร",
    "ผู้จำหน่าย-ชื่อเอกสาร", "ผู้จำหน่าย-อธิบายเพิ่ม"
]

# ================= 2. SESSION STATE =================
if "invoice_items" not in st.session_state: st.session_state.invoice_items = []
if "editing_no" not in st.session_state: st.session_state.editing_no = None
if "pdf_buffer" not in st.session_state: st.session_state.pdf_buffer = None
if "form_date" not in st.session_state: st.session_state.form_date = datetime.now().strftime("%d/%m/%Y")

for f in transport_fields:
    if f"in_{f}" not in st.session_state: st.session_state[f"in_{f}"] = ""

def reset_form_action():
    st.session_state.invoice_items = []
    st.session_state.editing_no = None
    st.session_state.pdf_buffer = None
    st.session_state.form_date = datetime.now().strftime("%d/%m/%Y")
    for f in transport_fields: st.session_state[f"in_{f}"] = ""

# ================= 3. PDF GENERATOR =================
def generate_pdf_file(inv_no, items, data_dict=None):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    
    page_labels = [
        "แผ่นที่ 1 - ต้นฉบับ - ผู้รับน้ำมัน (ปลายทาง)", 
        "แผ่นที่ 2 - สำเนา - พนักงานขับรถ / ผู้ขนส่ง", 
        "แผ่นที่ 3 - สำเนา - ฝ่ายบัญชี / ส่วนกลางผู้ส่ง", 
        "แผ่นที่ 4 - สำเนา - คลังน้ำมัน (ต้นทาง)"
    ]

    def get_val(key, default=""):
        if data_dict: return str(data_dict.get(key, default))
        return st.session_state.get(f"in_{key}", default)

    for idx, label in enumerate(page_labels):
        # --- ลายน้ำตัวเลขจางพิเศษ (0.03) ---
        c.saveState()
        c.setFont(FONT_NAME, 200)
        c.setFillAlpha(0.05) 
        c.drawRightString(19*cm, h-10*cm, f"{idx + 1}")
        c.restoreState()

        c.setFont(FONT_NAME, 10)
        c.drawString(1.5*cm, h-0.8*cm, label)

        try:
            if os.path.exists('p1.png'):
                c.saveState()
                c.setFillAlpha(0.2)
                img_size = 10*cm
                c.drawImage('p1.png', (w-img_size)/2, ((h-img_size)/2)-(1.5*inch), width=img_size, height=img_size, mask='auto')
                c.restoreState()
        except: pass

        c.setFont(FONT_NAME, 14)
        c.drawString(1.5*cm, h-1.5*cm, "1.ผู้จำหน่าย")
        
        c.setFont(FONT_NAME, 11)
        c.drawString(1.5*cm, h-2.1*cm, f"{get_val('ผู้จำหน่าย-ชื่อ')}")
        c.drawString(1.5*cm, h-2.6*cm, f"{get_val('ผู้จำหน่าย-ที่อยู่')}")
        c.drawString(1.5*cm, h-3.1*cm, f"โทร.{get_val('ผู้จำหน่าย-เบอร์โทร')}")
        c.drawString(1.5*cm, h-3.6*cm, f"เลขประจำตัวผู้เสียภาษี {get_val('ผู้จำหน่าย-เลขผู้เสียภาษี')}")

        c.setFont(FONT_NAME, 18)
        c.drawRightString(19.5*cm, h-1.7*cm, f"{get_val('ผู้จำหน่าย-ชื่อเอกสาร', 'ใบกำกับขนส่งน้ำมัน')}")
        c.setFont(FONT_NAME, 12)
        c.drawRightString(19.5*cm, h-2.2*cm, f"{get_val('ผู้จำหน่าย-อธิบายเพิ่ม')}")
        
        header_x_right = 13*cm + (1 * inch)
        c.drawString(header_x_right, h-3.1*cm, f"เลขที่ : {inv_no}")
        c.drawString(header_x_right, h-3.6*cm, f"วันที่ : {data_dict.get('date') if data_dict else st.session_state.get('form_date', '')}")

        c.line(1*cm, h-4.0*cm, 20*cm, h-4.0*cm)

        c.setFont(FONT_NAME, 14)
        c.drawString(1.2*cm, h-4.7*cm, "  2.คลังรับน้ำมัน (ต้นทาง)")
        c.setFont(FONT_NAME, 11)
        c.drawString(1.5*cm, h-5.3*cm, f"ชื่อคลัง : {get_val('คลังรับผลิตภัณฑ์-ชื่อ')}")
        c.drawString(1.5*cm, h-5.8*cm, f"ที่อยู่ : {get_val('คลังรับผลิตภัณฑ์-ที่อยู่')}")
        c.drawString(1.5*cm, h-6.3*cm, f"เลขประจำตัวผู้เสียภาษี : {get_val('คลังรับผลิตภัณฑ์-เลขผู้เสียภาษี')}")

        c.setFont(FONT_NAME, 14)
        c.drawString(1.5*cm, h-7.0*cm, "3.ตั๋วขนย้ายน้ำมัน")
        c.setFont(FONT_NAME, 11)
        c.drawString(1.5*cm, h-7.6*cm, f"ชื่อเจ้าของตั๋ว : {get_val('ผู้รับผลิตภัณฑ์-ชื่อ')}")
        c.drawString(1.5*cm, h-8.1*cm, f"ที่อยู่ : {get_val('ผู้รับผลิตภัณฑ์-ที่อยู่')}")
        c.drawString(1.5*cm, h-8.6*cm, f"เลขประจำตัวผู้เสียภาษี : {get_val('ผู้รับผลิตภัณฑ์-เลขผู้เสียภาษี')}")
        c.drawString(1.5*cm, h-9.1*cm, f"ตั๋วขนย้ายเลขที่ : {get_val('ผู้รับผลิตภัณฑ์-หมายเลขตั๋ว')}")
        
        c.setFont(FONT_NAME, 14)
        c.drawString(1.5*cm, h-9.8*cm, "4.ผู้รับน้ำมัน (ปลายทาง)")
        c.setFont(FONT_NAME, 11)
        c.drawString(1.5*cm, h-10.4*cm, f"ชื่อผู้รับน้ำมัน : {get_val('ผู้รับสินค้า-ชื่อ')}")
        c.drawString(1.5*cm, h-10.9*cm, f"ที่อยู่ : {get_val('ผู้รับสินค้า-ที่อยู่')}")
        c.drawString(1.5*cm, h-11.4*cm, f"เลขประจำตัวผู้เสียภาษี : {get_val('ผู้รับสินค้า-เลขผู้เสียภาษี')}")

        c.line(1*cm, h-11.9*cm, 20*cm, h-11.9*cm)

        c.setFont(FONT_NAME, 14)
        c.drawString(1.2*cm, h-12.4*cm, "  5.ข้อมูลการขนส่ง")
        c.setFont(FONT_NAME, 11)
        
        c.drawString(1.5*cm, h-13.0*cm, f"ผู้ดำเนินการขนส่ง : {get_val('ผู้ดำเนินการขนส่ง-ชื่อ')}")
        c.drawString(1.5*cm, h-13.5*cm, f"เลขประจำตัวผู้เสียภาษี : {get_val('ผู้ดำเนินการขนส่ง-เลขผู้เสียภาษี')}")
        c.drawString(1.5*cm, h-14.0*cm, f"ที่อยู่ : {get_val('ผู้ดำเนินการขนส่ง-ที่อยู่')}")
        c.drawString(1.5*cm, h-14.5*cm, f"เบอร์โทร : {get_val('ผู้ดำเนินการขนส่ง-เบอร์โทร')}")
        c.drawString(1.5*cm, h-15.0*cm, f"ประเภทผู้รับจ้าง : {get_val('ผู้ดำเนินการขนส่ง-ประเภทผู้รับจ้าง')}")
        c.drawString(1.5*cm, h-15.5*cm, f"ใบอนุญาต : {get_val('ผู้ดำเนินการขนส่ง-ใบอนุญาต')}")
        
        x_col2 = 11*cm + (1.5 * inch)
        c.drawString(x_col2, h-13.0*cm, f"พนักงานขับรถ : {get_val('ข้อมูลพนักงานขับรถ-ชื่อ')}")
        c.drawString(x_col2, h-13.5*cm, f"เลขใบขับขี่ : {get_val('ข้อมูลพนักงานขับรถ-เลขใบขับขี่')}")
        c.drawString(x_col2, h-14.0*cm, f"เบอร์โทร : {get_val('ข้อมูลพนักงานขับรถ-เบอร์โทร')}")
        c.drawString(x_col2, h-14.5*cm, f"ทะเบียนรถ : {get_val('ข้อมูลพนักงานขับรถ-ทะเบียนรถ')}")
        c.drawString(x_col2, h-15.0*cm, f"วิธีขนส่ง : {get_val('ข้อมูลพนักงานขับรถ-วิธีขนส่ง')}")
        c.drawString(x_col2, h-15.5*cm, f"วันออกเดินทาง : {get_val('ข้อมูลพนักงานขับรถ-วันออกเดินทาง')}")
        c.drawString(x_col2, h-16.0*cm, f"เวลาออกเดินทาง : {get_val('ข้อมูลพนักงานขับรถ-เวลาออกเดินทาง')}")
        c.drawString(x_col2, h-16.5*cm, f"วันที่ถึงปลายทาง : {get_val('ข้อมูลพนักงานขับรถ-วันที่ถึงปลายทาง')}")
        c.drawString(x_col2, h-17.0*cm, f"เวลาที่ถึงปลายทาง : {get_val('ข้อมูลพนักงานขับรถ-เวลาที่ถึงปลายทาง')}")

        c.line(1*cm, h-17.5*cm, 20*cm, h-17.5*cm)

        c.setFont(FONT_NAME, 14)
        c.drawString(1.2*cm, h-18.0*cm, "  6.รายละเอียดน้ำมันเชื้อเพลิง")
        
        header = [["ลำดับ", "ช่องถัง", "ซีล", "รายการน้ำมัน", "หน่วย", "จำนวน"]]
        data_rows = []
        total_qty = 0.0
        for i, it in enumerate(items):
            try:
                qv = float(str(it.get('qty', '0')).replace(',', ''))
                total_qty += qv
                f_qty = "{:,.0f}".format(qv)
            except: f_qty = it.get('qty', '')
            data_rows.append([i+1, it.get('tank',''), it.get('seal',''), it.get('product',''), it.get('unit',''), f_qty])
        
        while len(data_rows) < 4: data_rows.append(["","","","","",""])
        data_rows.append(["", "", "", "รวมทั้งสิ้น", "", "{:,.0f}".format(total_qty)])

        t = Table(header + data_rows, colWidths=[1.2*cm, 2.5*cm, 3.5*cm, 6.8*cm, 2*cm, 3*cm])
        t.setStyle(TableStyle([('FONT', (0,0), (-1,-1), FONT_NAME, 10),('GRID', (0,0), (-1,-1), 0.5, colors.black),('ALIGN', (0,0), (-1,-1), 'CENTER'), ('ALIGN', (3, -1), (3, -1), 'RIGHT'), ('SPAN', (3, -1), (4, -1))]))
        t.wrapOn(c, 1*cm, h-22.0*cm); t.drawOn(c, 1*cm, h-22.0*cm)

        c.line(1*cm, h-22.5*cm, 20*cm, h-22.5*cm)

        c.setFont(FONT_NAME, 14)
        c.drawString(1.2*cm, h-23.0*cm, "  7.การยืนยันและรับสินค้า")
        c.setFont(FONT_NAME, 11)
        c.drawString(1.5*cm, h-23.8*cm, "ข้าพเจ้าได้รับสินค้าตามรายการข้างต้นในสภาพเรียบร้อย ถูกต้องตามจำนวนและหมายเลขซีลที่ระบุไว้")

        sig_y = (h - 26.6*cm)
        c.setFont(FONT_NAME, 12)
        c.drawCentredString(4.5*cm, sig_y, "..................................")
        c.drawCentredString(10.5*cm, sig_y, "..................................")
        c.drawCentredString(16.5*cm, sig_y, "..................................")
        
        c.drawCentredString(4.5*cm, sig_y-0.6*cm, f"( {get_val('การยืนยันและรับสินค้า-ผู้ออกเอกสาร')} )")
        c.drawCentredString(10.5*cm, sig_y-0.6*cm, f"( {get_val('การยืนยันและรับสินค้า-พนักงานขับรถ')} )")
        c.drawCentredString(16.5*cm, sig_y-0.6*cm, f"( {get_val('การยืนยันและรับสินค้า-ผู้รับสินค้า')} )")
        
        c.setFont(FONT_NAME, 11)
        c.drawCentredString(4.5*cm, sig_y-1.2*cm, "ผู้ออกใบกำกับขนส่งน้ำมัน")
        c.drawCentredString(4.5*cm, sig_y-1.7*cm, "วันที่ : ..................................")
        
        c.drawCentredString(10.5*cm, sig_y-1.2*cm, "ผู้ดำเนินการขนส่งน้ำมัน")
        c.drawCentredString(10.5*cm, sig_y-1.7*cm, "วันที่ : ..................................")
        
        c.drawCentredString(16.5*cm, sig_y-1.2*cm, "ผู้รับสินค้า")
        c.drawCentredString(16.5*cm, sig_y-1.7*cm, "วันที่ : ..................................")

        c.rect(1*cm, 1*cm, 19*cm, h-2*cm)
        c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ================= 4. MAIN UI =================
st.title("🚚 ใบกำกับขนส่ง JP PARTNER")

with st.expander("🔍 ค้นหา/แก้ไข/พิมพ์บิลเก่า"):
    if not inv_df.empty:
        options = [f"{r[INV_KEY]} | {r.get('ผู้รับสินค้า-ชื่อ', '')}" for _, r in inv_df.iterrows()]
        selected = st.selectbox("เลือกบิล", [""] + options[::-1])
        if selected:
            sel_no = selected.split(" | ")[0]
            col_a, col_b, col_c = st.columns(3)
            row_data = inv_df[inv_df[INV_KEY] == sel_no].iloc[0].to_dict()
            it_rows = item_df[item_df["invoice_no"] == sel_no].to_dict('records')
            if col_a.button("📝 โหลดมาแก้ไข"):
                st.session_state.editing_no = sel_no
                st.session_state.form_date = str(row_data.get('date', st.session_state.form_date))
                for f in transport_fields: st.session_state[f"in_{f}"] = str(row_data.get(f, ""))
                st.session_state.invoice_items = [{"product": i.get('product',''), "unit": i.get('unit',''), "qty": i.get('qty',''), "tank": str(i.get('tank','')), "seal": str(i.get('seal',''))} for i in it_rows]
                st.session_state.pdf_buffer = generate_pdf_file(sel_no, st.session_state.invoice_items)
                st.rerun()
            if col_b.button("🔄 โหลดมาสร้างซ้ำ"):
                st.session_state.editing_no = None
                for f in transport_fields: st.session_state[f"in_{f}"] = str(row_data.get(f, ""))
                st.session_state.invoice_items = [{"product": i.get('product',''), "unit": i.get('unit',''), "qty": i.get('qty',''), "tank": str(i.get('tank','')), "seal": str(i.get('seal',''))} for i in it_rows]
                st.session_state.pdf_buffer = None
                st.rerun()
            quick_pdf = generate_pdf_file(sel_no, it_rows, data_dict=row_data)
            col_c.download_button("📥 ดาวน์โหลด PDF (ทันที)", data=quick_pdf, file_name=f"Invoice_{sel_no}.pdf", mime="application/pdf")

tabs = st.tabs(["📦 ข้อมูล-ต้นทาง-ปลายทาง", "🚛 ผู้ขนส่ง", "⛽ สินค้าที่ขนย้าย", "🏢 ผู้จัดจำหน่าย"])
with tabs[0]:
    for f in transport_fields[0:11]: st.text_input(f, key=f"in_{f}")
with tabs[1]:
    for f in transport_fields[11:26]: st.text_input(f, key=f"in_{f}")
with tabs[2]:
    ca, cb, cc, cd, ce = st.columns([3,1,1,2,2])
    p_n = ca.text_input("รายการ", key="t_n")
    p_u = cb.text_input("หน่วย", value="ลิตร", key="t_u")
    p_q = cc.text_input("จำนวน", key="t_q")
    p_p = cd.text_input("ช่องถัง", key="t_p")
    p_a = ce.text_input("ซีล", key="t_a")
    if st.button("➕ เพิ่มรายการสินค้า"):
        if p_n and p_q:
            st.session_state.invoice_items.append({"product":p_n, "unit":p_u, "qty":p_q, "tank":p_p, "seal":p_a})
            st.rerun()
    st.markdown("---")
    if st.session_state.invoice_items:
        df_items = pd.DataFrame(st.session_state.invoice_items)
        edited_df = st.data_editor(df_items, num_rows="dynamic", use_container_width=True, key="logistics_editor")
        if not edited_df.equals(df_items): st.session_state.invoice_items = edited_df.to_dict('records')
        if st.button("🗑️ ล้างรายการสินค้าทั้งหมด"): st.session_state.invoice_items = []; st.rerun()

with tabs[3]:
    st.session_state.form_date = st.text_input("วันที่", value=st.session_state.form_date)
    for f in transport_fields[26:]: st.text_input(f, key=f"in_{f}")

if st.button("💾 บันทึกและอัปเดต PDF", type="primary", use_container_width=True):
    def get_next_no():
        prefix = f"INV-{datetime.now().year}-{datetime.now().month:02d}"
        if inv_df.empty: return f"{prefix}-0001"
        curr = inv_df[inv_df[INV_KEY].astype(str).str.startswith(prefix)]
        if curr.empty: return f"{prefix}-0001"
        last_val = str(curr[INV_KEY].iloc[-1]).split('-')[-1]
        return f"{prefix}-{int(last_val)+1:04d}"
    
    final_no = st.session_state.editing_no if st.session_state.editing_no else get_next_no()
    if st.session_state.editing_no:
        try:
            for ws in [ws_inv, ws_item]:
                found = ws.findall(final_no)
                for cell in reversed(found): ws.delete_rows(cell.row)
        except: pass
    ws_inv.append_row([final_no, st.session_state.form_date] + [st.session_state[f"in_{f}"] for f in transport_fields])
    for it in st.session_state.invoice_items:
        ws_item.append_row([final_no, it['product'], it['unit'], it['qty'], it['tank'], it['seal']])
    st.session_state.pdf_buffer = generate_pdf_file(final_no, st.session_state.invoice_items)
    st.session_state.editing_no = final_no
    st.cache_data.clear(); st.rerun()

if st.session_state.pdf_buffer:
    st.download_button("📥 ดาวน์โหลด PDF", data=st.session_state.pdf_buffer, file_name=f"Invoice_{st.session_state.editing_no}.pdf", mime="application/pdf", use_container_width=True)
    if st.button("🆕 เริ่มบิลใหม่"): reset_form_action(); st.rerun()
