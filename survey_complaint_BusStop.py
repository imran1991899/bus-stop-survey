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

# --------- 1. DATA DEFINITIONS (Defined first to prevent NameErrors) ---------

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

if "saved_staff_id" not in st.session_state:
    st.session_state.saved_staff_id = None

if "responses" not in st.session_state:
    st.session_state.responses = {q: None for q in all_questions}

# --------- 3. PAGE CONFIG & CSS ---------

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

# --------- 4. GOOGLE DRIVE FUNCTIONS ---------
# Note: Ensure client_secrets2.json is in your root directory

FOLDER_ID = "1DjtLxgyQXwgjq_N6I_-rtYcBcnWhzMGp"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]

def get_authenticated_service():
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    else:
        creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file("client_secrets2.json", scopes=SCOPES, 
                                               redirect_uri="https://bus-stop-survey-99f8wusughejfcfvrvxmyl.streamlit.app/")
            auth_url, _ = flow.authorization_url(prompt="consent")
            st.markdown(f"[Authenticate here]({auth_url})")
            st.stop()
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)

# --------- 5. UI COMPONENTS ---------

# Maintain Staff ID selection
staff_options = list(staff_dict.keys())
try:
    def_idx = staff_options.index(st.session_state.saved_staff_id)
except:
    def_idx = None

selected_staff = st.selectbox("👤 Staff ID", options=staff_options, index=def_idx, placeholder="Select Staff ID...")
st.session_state.saved_staff_id = selected_staff 

if selected_staff:
    st.success(f"👤 **Staff Name:** {staff_dict[selected_staff]}")

stop = st.selectbox("1️⃣ Bus Stop", allowed_stops, index=None, placeholder="Pilih hentian bas...")

st.markdown("### 4️⃣ A. KELAKUAN KAPTEN BAS")
for i, q in enumerate(questions_a):
    st.write(f"**{q}**")
    opts = ["Yes", "No", "NA"] if i >= 4 else ["Yes", "No"]
    curr = st.session_state.responses.get(q)
    idx = opts.index(curr) if curr in opts else None
    st.session_state.responses[q] = st.radio(q, opts, index=idx, key=f"qa_{i}", horizontal=True, label_visibility="collapsed")

st.markdown("### 5️⃣ B. KEADAAN HENTIAN BAS")
for i, q in enumerate(questions_b):
    st.write(f"**{q}**")
    opts = ["Yes", "No", "NA"] if "NA" in q else ["Yes", "No"]
    curr = st.session_state.responses.get(q)
    idx = opts.index(curr) if curr in opts else None
    st.session_state.responses[q] = st.radio(q, opts, index=idx, key=f"qb_{i}", horizontal=True, label_visibility="collapsed")

# --------- 6. PHOTOS SECTION (EXACTLY 3) ---------

st.markdown("### 6️⃣ Photos (Exactly 3 Photos Required)")
if len(st.session_state.photos) < 3:
    c1, c2 = st.columns(2)
    with c1:
        cam_p = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos)+1}")
        if cam_p:
            st.session_state.photos.append(cam_p)
            st.rerun()
    with c2:
        up_p = st.file_uploader(f"📁 Upload Photo #{len(st.session_state.photos)+1}", type=["png", "jpg", "jpeg"])
        if up_p:
            st.session_state.photos.append(up_p)
            st.rerun()
else:
    st.success("✅ 3 Photos Ready")
    if st.button("🗑️ Clear Photos"):
        st.session_state.photos = []
        st.rerun()

# --------- 7. SUBMIT LOGIC ---------

if st.button("✅ Submit Survey"):
    if not selected_staff or not stop or len(st.session_state.photos) != 3:
        st.error("Error: Please ensure Staff ID is selected, Bus Stop is chosen, and exactly 3 photos are taken.")
    elif None in st.session_state.responses.values():
        st.warning("Please answer all questions.")
    else:
        with st.spinner("Submitting to Google..."):
            try:
                # Authentication
                # drive_service, sheets_service = get_authenticated_service()
                
                # [Logic for uploading to Drive and Sheets goes here]
                # ...
                
                # --- RESET AFTER SUBMISSION ---
                st.session_state.photos = [] 
                st.session_state.responses = {q: None for q in all_questions}
                
                st.success("✅ Survey Submitted Successfully! All fields reset except Staff ID.")
                time.sleep(2)
                st.rerun()
            except Exception as e:
                st.error(f"Submission failed: {e}")

# Option to manually reset Staff ID
if st.button("🔄 Reset Staff ID"):
    st.session_state.saved_staff_id = None
    st.rerun()
