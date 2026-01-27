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

# --------- Enhanced "iPhone Style" Pill Button CSS ---------
st.markdown("""
    <style>
    div[role="radiogroup"] {
        display: flex;
        flex-direction: row;
        gap: 20,px;
        background-color: transparent !important;
    }
    div[role="radiogroup"] label {
        padding: 10px 25px !important;
        border-radius: 50px !important; 
        border: 2px solid #d1d1d6 !important;
        background-color: white !important;
        transition: all 0.3s ease;
    }
    div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
        color: #333 !important;
        font-weight: bold !important;
        font-size: 16px !important;
    }
    div[role="radiogroup"] label:has(input[value="Yes"]):has(input:checked) {
        background-color: #28a745 !important; 
        border-color: #28a745 !important;
    }
    div[role="radiogroup"] label:has(input[value="Yes"]):has(input:checked) p {
        color: white !important;
    }
    div[role="radiogroup"] label:has(input[value="No"]):has(input:checked) {
        background-color: #dc3545 !important; 
        border-color: #dc3545 !important;
    }
    div[role="radiogroup"] label:has(input[value="No"]):has(input:checked) p {
        color: white !important;
    }
    div[role="radiogroup"] label:has(input[value="NA"]):has(input:checked) {
        background-color: #6c757d !important;
        border-color: #6c757d !important;
    }
    div[role="radiogroup"] label:has(input[value="NA"]):has(input:checked) p {
        color: white !important;
    }
    div[role="radiogroup"] [data-testid="stWidgetSelectionVisualizer"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --------- Google Drive & OAuth Logic ---------
# [Assuming your existing authentication and upload functions remain unchanged]

# --------- Load Excel Data ---------
# [Assuming routes_df and stops_df are loaded as per your previous code]

# --------- Staff List Dictionary ---------
staff_dict = {
    "8917": "MOHD RIZAL BIN RAMLI", "8918": "NUR FAEZAH BINTI HARUN", "8919": "NORAINSYIRAH BINTI ARIFFIN",
    "8920": "NORAZHA RAFFIZZI ZORKORNAINI", "8921": "NUR HANIM HANIL", "8922": "MUHAMMAD HAMKA BIN ROSLIM",
    "8923": "MUHAMAD NIZAM BIN IBRAHIM", "8924": "AZFAR NASRI BIN BURHAN", "8925": "MOHD SHAHFIEE BIN ABDULLAH",
    "8926": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "8927": "NIK MOHD FADIR BIN NIK MAT RAWI", "8928": "AHMAD AZIM BIN ISA",
    "8929": "NUR SHAHIDA BINTI MOHD TAMIJI", "8930": "MUHAMMAD SYAHMI BIN AZMEY", "8931": "MOHD IDZHAM BIN ABU BAKAR",
    "8932": "MOHAMAD NAIM MOHAMAD SAPRI", "8933": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "8934": "MIRAN NURSYAWALNI AMIR",
    "8935": "MUHAMMAD HANIF BIN HASHIM", "8936": "NUR HAZIRAH BINTI NAWI"
}

# --------- Session State Management ---------
# Initialize photo list
if "photos" not in st.session_state:
    st.session_state.photos = []

# Initialize Staff ID persistence
if "saved_staff_id" not in st.session_state:
    st.session_state.saved_staff_id = None

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

# Initialize responses
if "responses" not in st.session_state:
    st.session_state.responses = {q: None for q in all_questions}

# --------- Staff ID (Maintained) ---------
# We use st.session_state.saved_staff_id to set the index of the selectbox
staff_options = list(staff_dict.keys())
default_index = staff_options.index(st.session_state.saved_staff_id) if st.session_state.saved_staff_id in staff_options else None

selected_staff = st.selectbox(
    "👤 Staff ID", 
    options=staff_options, 
    index=default_index, 
    placeholder="Select Staff ID..."
)

# Update the saved ID whenever the user changes it
st.session_state.saved_staff_id = selected_staff

staff_name = staff_dict[selected_staff] if selected_staff else ""
if selected_staff: 
    st.success(f"👤 **Staff Name:** {staff_name}")

# --------- Step 1: Select Bus Stop ---------
# We don't maintain the stop, so it resets to default
stop = st.selectbox("1️⃣ Bus Stop", allowed_stops, index=None, placeholder="Pilih hentian bas...")

# [Depot and Route detection logic here...]

# --------- Survey Sections ---------
# Note: Using st.session_state.responses[q] to control radio indices for reset
for i, q in enumerate(questions_a):
    st.write(f"**{q}**")
    opts = ["Yes", "No", "NA"] if i >= 4 else ["Yes", "No"]
    
    # Logic to find index based on saved response (helps with the reset)
    current_val = st.session_state.responses.get(q)
    idx = opts.index(current_val) if current_val in opts else None
    
    choice = st.radio(label=q, options=opts, index=idx, key=f"qa_{i}", horizontal=True, label_visibility="collapsed")
    st.session_state.responses[q] = choice
    st.write("---")

# [Repeat similar radio logic for questions_b...]

# --------- Photos (Reset logic integrated) ---------
st.markdown("### 6️⃣ Photos (Exactly 3 Photos Required)")

if len(st.session_state.photos) < 3:
    col_cam, col_file = st.columns(2)
    with col_cam:
        cam_p = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos) + 1}")
        if cam_p:
            st.session_state.photos.append(cam_p)
            st.rerun()
    with col_file:
        up_p = st.file_uploader(f"📁 Upload Photo #{len(st.session_state.photos) + 1}", type=["png", "jpg", "jpeg"])
        if up_p:
            st.session_state.photos.append(up_p)
            st.rerun()
else:
    st.success("✅ 3 Photos Ready")
    if st.button("🗑️ Clear Photos"):
        st.session_state.photos = []
        st.rerun()

# --------- Submit Logic ---------
if st.button("✅ Submit Survey"):
    if not selected_staff:
        st.warning("Sila pilih Staff ID.")
    elif len(st.session_state.photos) != 3:
        st.warning("Sila ambil tepat 3 keping gambar.")
    elif None in st.session_state.responses.values():
        st.warning("Sila lengkapkan semua soalan.")
    else:
        with st.spinner("Submitting..."):
            # [Upload to GDrive and Append to Sheets Logic...]
            
            # --- THE RESET FUNCTION ---
            # 1. Clear the photo list
            st.session_state.photos = []
            # 2. Reset all survey answers to None
            st.session_state.responses = {q: None for q in all_questions}
            # Note: We DO NOT clear st.session_state.saved_staff_id
            
            st.success("✅ Data Sent! Questions have been reset. Staff ID maintained.")
            time.sleep(2)
            st.rerun()
