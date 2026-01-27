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

# --------- Custom CSS for Dynamic Colors ---------
st.markdown("""
    <style>
    /* Base style for the radio group labels (the pills) */
    div[role="radiogroup"] label {
        padding: 10px 25px !important;
        border-radius: 50px !important; 
        border: 2px solid #d1d1d6 !important;
        background-color: white !important;
        transition: all 0.3s ease;
    }

    /* Change "Yes" to GREEN when selected */
    div[role="radiogroup"] label:has(input[value="Yes"]):has(input:checked) {
        background-color: #28a745 !important; 
        border-color: #28a745 !important;
    }
    div[role="radiogroup"] label:has(input[value="Yes"]):has(input:checked) p {
        color: white !important;
    }

    /* Change "No" to RED when selected */
    div[role="radiogroup"] label:has(input[value="No"]):has(input:checked) {
        background-color: #dc3545 !important; 
        border-color: #dc3545 !important;
    }
    div[role="radiogroup"] label:has(input[value="No"]):has(input:checked) p {
        color: white !important;
    }

    /* Change "NA" to GREY when selected (Optional) */
    div[role="radiogroup"] label:has(input[value="NA"]):has(input:checked) {
        background-color: #6c757d !important;
        border-color: #6c757d !important;
    }
    div[role="radiogroup"] label:has(input[value="NA"]):has(input:checked) p {
        color: white !important;
    }

    /* Hide the original small radio circle for a cleaner pill look */
    div[role="radiogroup"] [data-testid="stWidgetSelectionVisualizer"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --------- Implementation in the App ---------

st.write("### Bus Stop Survey Questions")

# Example for Question A
q1 = "1. BC menggunakan telefon bimbit?"
st.session_state.responses[q1] = st.radio(
    label=q1,
    options=["Yes", "No", "NA"],
    index=None, # Starts with nothing selected
    horizontal=True,
    key="q1_radio"
)

st.divider()

# Example for Question B
q2 = "7. Hentian terlindung dari pandangan BC?"
st.session_state.responses[q2] = st.radio(
    label=q2,
    options=["Yes", "No"],
    index=None,
    horizontal=True,
    key="q2_radio"
)

# --------- Google Drive Folder ID ---------
FOLDER_ID = "1DjtLxgyQXwgjq_N6I_-rtYcBcnWhzMGp"

# --------- OAuth Setup ---------
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]
CLIENT_SECRETS_FILE = "client_secrets2.json"

def save_credentials(credentials):
    with open("token.pickle", "wb") as token:
        pickle.dump(credentials, token)

def load_credentials():
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            return pickle.load(token)
    return None

def get_authenticated_service():
    creds = load_credentials()
    if creds and creds.valid:
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request()); save_credentials(creds)
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, 
                                       redirect_uri="https://bus-stop-survey-99f8wusughejfcfvrvxmyl.streamlit.app/")
    query_params = st.query_params
    if "code" in query_params:
        full_url = "https://bus-stop-survey-99f8wusughejfcfvrvxmyl.streamlit.app/?" + urlencode(query_params)
        flow.fetch_token(authorization_response=full_url)
        creds = flow.credentials; save_credentials(creds)
    else:
        auth_url, _ = flow.authorization_url(prompt="consent")
        st.markdown(f"[Authenticate here]({auth_url})"); st.stop()
    return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)

drive_service, sheets_service = get_authenticated_service()

def gdrive_upload_file(file_bytes, filename, mimetype, folder_id=None):
    media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype)
    metadata = {"name": filename}
    if folder_id: metadata["parents"] = [folder_id]
    uploaded = drive_service.files().create(body=metadata, media_body=media, fields="id, webViewLink", supportsAllDrives=True).execute()
    return uploaded["webViewLink"]

def find_or_create_gsheet(name, folder_id):
    query = f"'{folder_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.spreadsheet'"
    res = drive_service.files().list(q=query, fields="files(id)").execute()
    if res.get("files"): return res["files"][0]["id"]
    file = drive_service.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.spreadsheet", "parents": [folder_id]}, fields="id").execute()
    return file["id"]

def append_row(sheet_id, row, header):
    sheet = sheets_service.spreadsheets()
    existing = sheet.values().get(spreadsheetId=sheet_id, range="A1:A1").execute()
    if "values" not in existing:
        sheet.values().update(spreadsheetId=sheet_id, range="A1", valueInputOption="RAW", body={"values": [header]}).execute()
    sheet.values().append(spreadsheetId=sheet_id, range="A1", valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": [row]}).execute()

# --------- Load Excel ---------
routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")

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

# --------- Session State ---------
if "photos" not in st.session_state:
    st.session_state.photos = []

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

if "responses" not in st.session_state:
    st.session_state.responses = {q: None for q in all_questions}

# --------- Staff ID ---------
staff_id = st.selectbox("👤 Staff ID", options=list(staff_dict.keys()), index=None, placeholder="Select Staff ID...")
staff_name = staff_dict[staff_id] if staff_id else ""
if staff_id: st.success(f"👤 **Staff Name:** {staff_name}")

# --------- Step 1: Select Bus Stop ---------
stop = st.selectbox("1️⃣ Bus Stop", allowed_stops, index=None, placeholder="Pilih hentian bas...")

current_route = ""
current_depot = ""
if stop:
    matched_stop_data = stops_df[stops_df["Stop Name"] == stop]
    matched_route_nums = matched_stop_data["Route Number"].unique()
    current_route = " / ".join(map(str, matched_route_nums))
    matched_depot_names = routes_df[routes_df["Route Number"].isin(matched_route_nums)]["Depot"].unique()
    current_depot = " / ".join(map(str, matched_depot_names))
    st.info(f"📍 **Route Number:** {current_route}  \n🏢 **Depot:** {current_depot}")

# --------- Survey Sections ---------
st.markdown("### 4️⃣ A. KELAKUAN KAPTEN BAS")
for i, q in enumerate(questions_a):
    st.write(f"**{q}**")
    options = ["Yes", "No", "NA"] if i >= 4 else ["Yes", "No"]
    choice = st.radio(label=q, options=options, index=None, key=f"qa_{i}", horizontal=True, label_visibility="collapsed")
    st.session_state.responses[q] = choice
    st.write("---")

st.markdown("### 5️⃣ B. KEADAAN HENTIAN BAS")
for i, q in enumerate(questions_b):
    st.write(f"**{q}**")
    options = ["Yes", "No", "NA"] if q in ["17. Penumpang beri isyarat menahan? (NA jika tiada)", "18. Penumpang leka/tidak peka? (NA jika tiada)"] else ["Yes", "No"]
    choice = st.radio(label=q, options=options, index=None, key=f"qb_{i}", horizontal=True, label_visibility="collapsed")
    st.session_state.responses[q] = choice
    st.write("---")

# --------- CAMERA & UPLOAD PHOTOS SECTION ---------
st.markdown("### 6️⃣ Photos (Exactly 3 Photos Required)")

# Display current photo count and a clear list
if len(st.session_state.photos) < 3:
    col_cam, col_file = st.columns(2)
    
    with col_cam:
        # Camera Input
        cam_photo = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos) + 1}")
        if cam_photo:
            st.session_state.photos.append(cam_photo)
            st.rerun()

    with col_file:
        # File Uploader
        up_photo = st.file_uploader(f"📁 Upload Photo #{len(st.session_state.photos) + 1}", type=["png", "jpg", "jpeg"])
        if up_photo:
            st.session_state.photos.append(up_photo)
            st.rerun()
else:
    st.success("✅ 3 Photos Captured/Uploaded.")
    if st.button("🗑️ Reset Photos"):
        st.session_state.photos = []
        st.rerun()

# Image Preview Logic
if st.session_state.photos:
    cols = st.columns(3)
    for i, p in enumerate(st.session_state.photos):
        cols[i].image(p, caption=f"Photo {i+1}", use_container_width=True)

# --------- Submit ---------
if st.button("✅ Submit Survey"):
    if not staff_id:
        st.warning("Sila pilih Staff ID.")
    elif not stop:
        st.warning("Sila pilih Hentian Bas.")
    elif len(st.session_state.photos) != 3:
        st.warning("Sila ambil atau muat naik tepat 3 keping gambar.")
    elif None in st.session_state.responses.values():
        st.warning("Sila lengkapkan semua soalan.")
    else:
        with st.spinner("Submitting... Please wait."):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            photo_links = []
            for i, img in enumerate(st.session_state.photos):
                link = gdrive_upload_file(img.getvalue(), f"{timestamp}_{i}.jpg", "image/jpeg", FOLDER_ID)
                photo_links.append(link)

            answers = [st.session_state.responses[q] for q in all_questions]
            row = [timestamp, staff_id, staff_name, current_depot, current_route, stop] + answers + ["; ".join(photo_links)]
            header = ["Timestamp", "Staff ID", "Staff Name", "Depot", "Route", "Bus Stop"] + all_questions + ["Photos"]

            sheet_id = find_or_create_gsheet("survey_responses", FOLDER_ID)
            append_row(sheet_id, row, header)

            st.success("✅ Submission successful!")
            st.session_state.photos = []
            st.session_state.responses = {q: None for q in all_questions}
            time.sleep(2)
            st.rerun()

