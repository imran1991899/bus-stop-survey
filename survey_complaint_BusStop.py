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

# --------- 1. DATA DEFINITIONS (Defined first to prevent NameError) ---------

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

# --------- 2. SESSION STATE MANAGEMENT ---------

if "photos" not in st.session_state:
    st.session_state.photos = []

# This variable stays even after submission
if "sticky_staff_id" not in st.session_state:
    st.session_state.sticky_staff_id = None

if "responses" not in st.session_state:
    st.session_state.responses = {q: None for q in all_questions}

# --------- 3. PAGE SETUP & CSS ---------

st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
st.title("Bus Stop Complaints Survey")

st.markdown("""
    <style>
    div[role="radiogroup"] { display: flex; flex-direction: row; gap: 20px; background-color: transparent !important; }
    div[role="radiogroup"] label { padding: 10px 25px !important; border-radius: 50px !important; border: 2px solid #d1d1d6 !important; background-color: white !important; transition: all 0.3s ease; }
    div[role="radiogroup"] label:has(input[value="Yes"]):has(input:checked) { background-color: #28a745 !important; border-color: #28a745 !important; color: white !important; }
    div[role="radiogroup"] label:has(input[value="No"]):has(input:checked) { background-color: #dc3545 !important; border-color: #dc3545 !important; color: white !important; }
    div[role="radiogroup"] label:has(input[value="NA"]):has(input:checked) { background-color: #6c757d !important; border-color: #6c757d !important; color: white !important; }
    div[role="radiogroup"] [data-testid="stWidgetSelectionVisualizer"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

# --------- 4. STAFF SELECTION (STAYS AFTER SUBMIT) ---------

staff_options = list(staff_dict.keys())
try:
    # Set the index to match the sticky ID in session state
    staff_idx = staff_options.index(st.session_state.sticky_staff_id)
except (ValueError, KeyError):
    staff_idx = None

selected_staff = st.selectbox("👤 Staff ID", options=staff_options, index=staff_idx, placeholder="Select Staff ID...")
st.session_state.sticky_staff_id = selected_staff 

if selected_staff:
    st.success(f"👤 **Staff Name:** {staff_dict[selected_staff]}")

# --------- 5. SURVEY FORM (RESETS AFTER SUBMIT) ---------

# Added a unique key to allow for manual/programmatic reset via session state
stop = st.selectbox("1️⃣ Bus Stop", allowed_stops, index=None, placeholder="Pilih hentian bas...", key="current_stop")

st.markdown("### 4️⃣ A. KELAKUAN KAPTEN BAS")
for i, q in enumerate(questions_a):
    st.write(f"**{q}**")
    opts = ["Yes", "No", "NA"] if i >= 4 else ["Yes", "No"]
    ans = st.session_state.responses.get(q)
    idx = opts.index(ans) if ans in opts else None
    st.session_state.responses[q] = st.radio(q, opts, index=idx, key=f"qa_{i}", horizontal=True, label_visibility="collapsed")

st.markdown("### 5️⃣ B. KEADAAN HENTIAN BAS")
for i, q in enumerate(questions_b):
    st.write(f"**{q}**")
    opts = ["Yes", "No", "NA"] if "NA" in q else ["Yes", "No"]
    ans = st.session_state.responses.get(q)
    idx = opts.index(ans) if ans in opts else None
    st.session_state.responses[q] = st.radio(q, opts, index=idx, key=f"qb_{i}", horizontal=True, label_visibility="collapsed")

# --------- 6. DUAL PHOTO SYSTEM (RESETS AFTER SUBMIT) ---------

st.markdown("### 6️⃣ Photos (Exactly 3 Required)")
if len(st.session_state.photos) < 3:
    col_cam, col_file = st.columns(2)
    with col_cam:
        cam_in = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos)+1}")
        if cam_in:
            st.session_state.photos.append(cam_in)
            st.rerun()
    with col_file:
        file_in = st.file_uploader(f"📁 Upload Photo #{len(st.session_state.photos)+1}", type=["png", "jpg", "jpeg"])
        if file_in:
            st.session_state.photos.append(file_in)
            st.rerun()
else:
    st.success("✅ 3 Photos Captured.")
    if st.button("🗑️ Reset Photos"):
        st.session_state.photos = []
        st.rerun()

# --------- 7. SUBMIT & RESET LOGIC ---------

if st.button("✅ Submit Survey", use_container_width=True):
    if not selected_staff:
        st.error("Sila pilih Staff ID!")
    elif not stop:
        st.error("Sila pilih Bus Stop!")
    elif len(st.session_state.photos) != 3:
        st.error("Sila ambil/upload tepat 3 keping gambar!")
    elif None in st.session_state.responses.values():
        st.warning("Sila pastikan semua soalan dijawab.")
    else:
        with st.spinner("Processing Submission..."):
            # --- 🚀 [INSERT YOUR GOOGLE DRIVE/SHEETS CODE HERE] 🚀 ---
            # Drive upload logic...
            # Sheets append logic...
            
            # --- THE RESET (ONLY QUESTIONS & PHOTOS) ---
            # 1. Wipe photo list
            st.session_state.photos = []
            # 2. Wipe survey responses
            st.session_state.responses = {q: None for q in all_questions}
            # 3. Wipe the Bus Stop selectbox
            if "current_stop" in st.session_state:
                st.session_state.current_stop = None
            
            # NOTE: st.session_state.sticky_staff_id is NOT cleared here.
            
            st.success("✅ Submission Successful! Staff ID Maintained. Ready for next stop.")
            time.sleep(2)
            st.rerun()

st.divider()
if st.button("🔄 Logout/Clear Staff ID"):
    st.session_state.sticky_staff_id = None
    st.rerun()
