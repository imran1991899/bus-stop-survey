import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import mimetypes
import time
import os
import pickle
from urllib.parse import urlencode

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

# --------- Page Setup ---------
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
st.title("Bus Stop Complaints Survey")

# --------- CSS: iPhone Style Pill Buttons ---------
st.markdown("""
    <style>
    div[role="radiogroup"] {
        display: flex;
        flex-direction: row;
        gap: 20px;
    }
    div[role="radiogroup"] label {
        padding: 10px 25px !important;
        border-radius: 50px !important; 
        border: 2px solid #d1d1d6 !important;
        background-color: white !important;
    }
    div[role="radiogroup"] label:has(input[value="Yes"]):has(input:checked) {
        background-color: #28a745 !important; 
        border-color: #28a745 !important;
        color: white !important;
    }
    div[role="radiogroup"] label:has(input[value="No"]):has(input:checked) {
        background-color: #dc3545 !important; 
        border-color: #dc3545 !important;
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- (Bahagian Google Drive & Data dikekalkan sama seperti kod sebelumnya) ---
# [Pastikan fungsi gdrive_upload_file, get_authenticated_service, dll. ada di sini]

# --------- Staff & Bus Stop Data ---------
staff_dict = {
    "8917": "MOHD RIZAL BIN RAMLI", "8918": "NUR FAEZAH BINTI HARUN", "8919": "NORAINSYIRAH BINTI ARIFFIN",
    "8920": "NORAZHA RAFFIZZI ZORKORNAINI", "8921": "NUR HANIM HANIL", "8922": "MUHAMMAD HAMKA BIN ROSLIM",
    "8923": "MUHAMAD NIZAM BIN IBRAHIM", "8924": "AZFAR NASRI BIN BURHAN", "8925": "MOHD SHAHFIEE BIN ABDULLAH",
    "8926": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "8927": "NIK MOHD FADIR BIN NIK MAT RAWI", "8928": "AHMAD AZIM BIN ISA",
    "8929": "NUR SHAHIDA BINTI MOHD TAMIJI", "8930": "MUHAMMAD SYAHMI BIN AZMEY", "8931": "MOHD IDZHAM BIN ABU BAKAR",
    "8932": "MOHAMAD NAIM MOHAMAD SAPRI", "8933": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "8934": "MIRAN NURSYAWALNI AMIR",
    "8935": "MUHAMMAD HANIF BIN HASHIM", "8936": "NUR HAZIRAH BINTI NAWI"
}

# --- Load Excel Data ---
try:
    routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")
except:
    st.error("Fail bus_data.xlsx tidak dijumpai.")
    st.stop()

allowed_stops = sorted(list(staff_dict.keys())) # Contoh sorting

# --------- FORM UI ---------
staff_id = st.selectbox("👤 Staff ID", options=list(staff_dict.keys()), index=None)
staff_name = staff_dict.get(staff_id, "")
if staff_id: st.success(f"Staff: {staff_name}")

stop = st.selectbox("1️⃣ Bus Stop", sorted(stops_df["Stop Name"].unique().tolist()), index=None)

# --- Survey Questions (A & B) ---
# [Kod soalan dikekalkan...]

# --------- 6️⃣ KHAS: AMBIL GAMBAR GUNA KAMERA TELEFON ---------
st.markdown("### 6️⃣ Ambil 3 Keping Gambar")
st.info("Sila gunakan butang di bawah untuk membuka kamera telefon anda.")

cam1 = st.camera_input("Gambar 1: Keadaan Bas")
cam2 = st.camera_input("Gambar 2: Keadaan Hentian")
cam3 = st.camera_input("Gambar 3: Bukti Tambahan")

all_photos = [cam1, cam2, cam3]

# --------- SUBMIT LOGIC ---------
if st.button("✅ Submit Survey"):
    # Check jika semua 3 gambar sudah diambil
    if not all(all_photos):
        st.warning("Sila ambil ketiga-tiga gambar menggunakan kamera sebelum submit.")
    elif not staff_id or not stop:
        st.warning("Sila lengkapkan maklumat Staff dan Bus Stop.")
    else:
        with st.spinner("Sedang memuat naik gambar..."):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            photo_links = []
            
            # Authenticate services
            drive_service, sheets_service = get_authenticated_service()
            
            for i, cam_file in enumerate(all_photos):
                link = gdrive_upload_file(cam_file.getvalue(), f"{staff_id}_{i}.jpg", "image/jpeg", FOLDER_ID)
                photo_links.append(link)
            
            # Simpan ke Google Sheet
            # [Kod append_row dikekalkan...]
            
            st.success("✅ Survey Berjaya Dihantar!")
            time.sleep(2)
            st.rerun()
