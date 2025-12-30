import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pandas as pd
from datetime import datetime
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# ================== CONFIG ==================
st.set_page_config(page_title="Transportation Invoice", layout="wide")

SHEET_ID = "1ZdTeTyDkrvR3ZbIisCJdzKRlU8jMvFvnSvtEmQR2Tzs"
INVOICE_SHEET = "Invoices"
ITEM_SHEET = "InvoiceItems"

# ================== GOOGLE AUTH ==================
@st.cache_resource
def init_services():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    gs_client = gspread.authorize(creds)
    drive_service = build("drive", "v3", credentials=creds)
    return gs_client, drive_service

gs, drive = init_services()
sheet = gs.open_by_key(SHEET_ID)
ws_inv = sheet.worksheet(INVOICE_SHEET)
ws_item = sheet.worksheet(ITEM_SHEET)

# ================== INVOICE RUNNING ==================
def generate_invoice_no():
    records = ws_inv.get_all_records()
    if not records:
        return "INV-0001"
    last = records[-1]["invoice_no"]
    num = int(last.split("-")[1]) + 1
    return f"INV-{num:04d}"

# ================== PDF ==================
def generate_pdf(invoice, items):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, h-2*cm, "TRANSPORTATION INVOICE")

    c.setFont("Helvetica", 10)
    c.drawString(2*cm, h-3*cm, f"Invoice No: {invoice['invoice_no']}")
    c.drawString(2*cm, h-3.7*cm, f"Date: {invoice['date']}")

    c.drawString(2*cm, h-5*cm, f"Customer: {invoice['customer']}")
    c.drawString(2*cm, h-5.7*cm, f"Address: {invoice['address']}")

    y = h-7*cm
    c.setFont("Helvetica-Bold",10)
    c.drawString(2*cm,y,"สินค้า")
    c.drawRightString(11*cm,y,"จำนวน")
    c.drawRightString(14*cm,y,"ราคา")
    c.drawRightString(18*cm,y,"รวม")

    c.setFont("Helvetica",10)
    y -= 0.7*cm
    for it in items:
        c.drawString(2*cm,y,it["name"])
        c.drawRightString(11*cm,y,str(it["qty"]))
        c.drawRightString(14*cm,y,f"{it['pr]()*
