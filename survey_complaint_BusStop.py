import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
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

# --------- 1. DEFINE DATA FIRST (Fixes NameError) ---------
# This must be defined BEFORE the selectbox is called
allowed_stops = [
    "AJ106 LRT AMPANG", "DAMANSARA INTAN", "ECOSKY RESIDENCE", "FAKULTI KEJURUTERAAN (UTARA)",
    "FAKULTI PERNIAGAAN DAN PERAKAUNAN", "FAKULTI UNDANG-UNDANG", "KILANG PLASTIK EKSPEDISI EMAS (OPP)",
    "KJ477 UTAR", "KJ560 SHELL SG LONG (OPP)", "KL107 LRT MASJID JAMEK", "KL1082 SK Methodist",
    "KL117 BSN LEBUH AMPANG", "KL1217 ILP KUALA LUMPUR", "KL2247 KOMERSIAL KIP", "KL377 WISMA SISTEM",
    "KOMERSIAL BURHANUDDIN (2)", "MASJID CYBERJAYA 10", "MRT SRI DELIMA PINTU C", "PERUMAHAN TTDI",
    "PJ312 Medan Selera Seksyen 19", "PJ476 MASJID SULTAN ABDUL AZIZ", "PJ721 ONE UTAMA NEW WING",
    "PPJ384 AURA RESIDENCE", "SA12 APARTMENT BAIDURI (OPP)", "SA26 PERUMAHAN SEKSYEN 11",
    "SCLAND EMPORIS", "SJ602 BANDAR BUKIT PUCHONG BP1", "SMK SERI HARTAMAS", "SMK SULTAN ABD SAMAD (TIMUR)"
]
allowed_stops.sort()

staff_dict = {
    "8917": "MOHD RIZAL BIN RAMLI", "8918": "NUR FAEZAH BINTI HARUN", "8919": "NORAINSYIRAH BINTI ARIFFIN",
    "8920": "NORAZHA RAFFIZZI ZORKORNAINI", "8921": "NUR HANIM HANIL", "8922": "MUHAMMAD HAMKA BIN ROSLIM",
    "8923": "MUHAMAD NIZAM BIN IBRAHIM", "8924": "AZFAR NASRI BIN BURHAN", "8925": "MOHD SHAHFIEE BIN ABDULLAH",
    "8926": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "8927": "NIK MOHD FADIR BIN NIK MAT RAWI", "8928": "AHMAD AZIM BIN ISA",
    "8929": "NUR SHAHIDA BINTI MOHD TAMIJI", "8930": "MUHAMMAD SYAHMI BIN AZMEY", "8931": "MOHD IDZHAM BIN ABU BAKAR",
    "8932": "MOHAMAD NAIM MOHAMAD SAPRI", "8933": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "8934": "MIRAN NURSYAWALNI AMIR",
    "8935": "MUHAMMAD HANIF BIN HASHIM", "8936": "NUR HAZIRAH BINTI NAWI"
}

questions_a = [
    "1. BC menggunakan telefon bimbit?", "2. BC memperlahankan/memberhentikan bas?",
    "3. BC memandu di lorong 1 (kiri)?", "4. Bas penuh dengan penumpang?",
    "5. BC tidak mengambil penumpang? (NA jika tiada)", "6. BC berlaku tidak sopan? (NA jika tiada)"
]

questions_b = [
    "7. Hentian terlindung dari pandangan BC?", "8. Hentian terhalang oleh kenderaan parkir?",
    "9. Persekitaran bahaya untuk bas berhenti?", "10. Terdapat pembinaan berhampiran?",
    "11. Mempunyai bumbung?", "12. Mempunyai tiang?", "13. Mempunyai petak hentian?",
    "14. Mempunyai layby?", "15. Terlindung dari pandangan BC? (Gerai/Pokok)",
    "16. Pencahayaan baik?", "17. Penumpang beri isyarat menahan? (NA jika tiada)",
    "18. Penumpang leka/tidak peka? (NA jika tiada)", "19. Penumpang tiba lewat?",
    "20. Penumpang menunggu di luar kawasan hentian?"
]
all_questions = questions_a + questions_b

# --------- 2. SESSION STATE (Persistence Logic) ---------
if "photos" not in st.session_state:
    st.session_state.photos = []

# This keeps the Staff ID even after reset
if "persistent_staff_id" not in st.session_state:
    st.session_state.persistent_staff_id = None

if "responses" not in st.session_state:
    st.session_state.responses = {q: None for q in all_questions}

# --------- 3. UI: STAFF SELECTION ---------
staff_options = list(staff_dict.keys())
# Find the index of the previously selected ID so it stays selected
try:
    current_index = staff_options.index(st.session_state.persistent_staff_id)
except ValueError:
    current_index = None

staff_id = st.selectbox(
    "👤 Staff ID", 
    options=staff_options, 
    index=current_index, 
    placeholder="Select Staff ID..."
)

# Save the selection to session state immediately
st.session_state.persistent_staff_id = staff_id

if staff_id:
    st.success(f"👤 **Staff Name:** {staff_dict[staff_id]}")

# --------- 4. SURVEY FORM ---------
# Resetting the 'stop' selectbox to index=None is handled by st.rerun() after submission
stop = st.selectbox("1️⃣ Bus Stop", allowed_stops, index=None, placeholder="Pilih hentian bas...")

# [Insert your Radio Buttons for Questions A & B here using st.session_state.responses]

# --------- 5. CAMERA & UPLOAD (3 Photos) ---------
st.markdown("### 6️⃣ Photos (Exactly 3 Required)")
if len(st.session_state.photos) < 3:
    c1, c2 = st.columns(2)
    with c1:
        cam = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos) + 1}")
        if cam:
            st.session_state.photos.append(cam)
            st.rerun()
    with c2:
        up = st.file_uploader(f"📁 Upload Photo #{len(st.session_state.photos) + 1}", type=["jpg", "png"])
        if up:
            st.session_state.photos.append(up)
            st.rerun()

# --------- 6. SUBMIT & RESET FUNCTION ---------
if st.button("✅ Submit Survey"):
    if not staff_id or not stop or len(st.session_state.photos) != 3:
        st.warning("Please complete all fields and 3 photos.")
    else:
        with st.spinner("Uploading..."):
            # ... [Your GDrive upload and Sheets logic here] ...
            
            # THE RESET:
            # We clear photos and responses, but DO NOT touch st.session_state.persistent_staff_id
            st.session_state.photos = []
            st.session_state.responses = {q: None for q in all_questions}
            
            st.success("✅ Submitted! Questions reset, Staff ID maintained.")
            time.sleep(2)
            st.rerun() # This refreshes the page with the staff ID still there
