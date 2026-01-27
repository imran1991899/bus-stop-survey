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
st.set_page_config(page_title="Bus Stop Survey", layout="centered")

# --------- APPLE LIGHT THEME CSS ---------
st.markdown("""
    <style>
    /* Global App Background */
    .stApp {
        background-color: #F5F5F7 !important;
        color: #1D1D1F !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }

    /* Headers */
    h1, h2, h3 {
        color: #1D1D1F !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }

    /* iOS Segmented Control Style for Radio Buttons */
    div[role="radiogroup"] {
        background-color: #E3E3E8 !important; 
        padding: 4px !important;
        border-radius: 12px !important;
        gap: 4px !important;
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        margin-top: 15px !important; /* Pushes the gray box down from the question */
        margin-bottom: 20px !important;
    }

    /* Hide standard radio circles */
    [data-testid="stWidgetSelectionVisualizer"] {
        display: none !important;
    }

    /* Individual Radio Item Label */
    div[role="radiogroup"] label {
        background-color: transparent !important;
        border: none !important;
        padding: 10px 0px !important; /* Adjusted padding */
        border-radius: 10px !important;
        transition: all 0.2s ease-in-out !important;
        flex: 1 !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        margin: 0 !important;
        min-width: 80px !important; /* Ensures the box doesn't squash the text */
    }

    /* Standardizing text inside Yes/No */
    div[role="radiogroup"] label p {
        font-size: 15px !important;
        margin: 0 !important;
        padding: 0 !important;
        white-space: nowrap !important; /* Prevents "Yes" from splitting into "Ye" and "s" */
        line-height: 1 !important;
    }

    /* Selected State (The White Slide) */
    div[role="radiogroup"] label:has(input:checked) {
        background-color: #FFFFFF !important;
        box-shadow: 0px 3px 8px rgba(0,0,0,0.12) !important;
    }

    /* Specific Colors for text when selected */
    div[role="radiogroup"] label:has(input[value="Yes"]):has(input:checked) p {
        color: #007AFF !important;
        font-weight: 600 !important;
    }
    div[role="radiogroup"] label:has(input[value="No"]):has(input:checked) p {
        color: #FF3B30 !important;
        font-weight: 600 !important;
    }
    div[role="radiogroup"] label:has(input[value="NA"]):has(input:checked) p {
        color: #8E8E93 !important;
        font-weight: 600 !important;
    }

    /* Main Submit Button (iOS Blue) */
    div.stButton > button {
        width: 100% !important;
        background-color: #007AFF !important;
        color: white !important;
        border: none !important;
        height: 50px !important;
        font-weight: 600 !important;
        border-radius: 14px !important;
        margin-top: 20px;
    }

    /* Input/Selectbox standardizing */
    .stSelectbox, .stTextInput {
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚌 Bus Stop Survey")

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
        st.markdown(f"### Authentication Required\n[Please click here to log in]({auth_url})"); st.stop()
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

allowed_stops = sorted([
    "AJ106 LRT AMPANG", "DAMANSARA INTAN", "ECOSKY RESIDENCE", "FAKULTI KEJURUTERAAN (UTARA)",
    "FAKULTI PERNIAGAAN DAN PERAKAUNAN", "FAKULTI UNDANG-UNDANG", "KILANG PLASTIK EKSPEDISI EMAS (OPP)",
    "KJ477 UTAR", "KJ560 SHELL SG LONG (OPP)", "KL107 LRT MASJID JAMEK", "KL1082 SK Methodist",
    "KL117 BSN LEBUH AMPANG", "KL1217 ILP KUALA LUMPUR", "KL2247 KOMERSIAL KIP", "KL377 WISMA SISTEM",
    "KOMERSIAL BURHANUDDIN (2)", "MASJID CYBERJAYA 10", "MRT SRI DELIMA PINTU C", "PERUMAHAN TTDI",
    "PJ312 Medan Selera Seksyen 19", "PJ476 MASJID SULTAN ABDUL AZIZ", "PJ721 ONE UTAMA NEW WING",
    "PPJ384 AURA RESIDENCE", "SA12 APARTMENT BAIDURI (OPP)", "SA26 PERUMAHAN SEKSYEN 11",
    "SCLAND EMPORIS", "SJ602 BANDAR BUKIT PUCHONG BP1", "SMK SERI HARTAMAS", "SMK SULTAN ABD SAMAD (TIMUR)"
])

staff_dict = {
"10005475": "MOHD RIZAL BIN RAMLI", "10020779": "NUR FAEZAH BINTI HARUN", "10014181": "NORAINSYIRAH BINTI ARIFFIN",
"10022768": "NORAZHA RAFFIZZI ZORKORNAINI", "10022769": "NUR HANIM HANIL", "10023845": "MUHAMMAD HAMKA BIN ROSLIM",
"10002059": "MUHAMAD NIZAM BIN IBRAHIM", "10005562": "AZFAR NASRI BIN BURHAN", "10010659": "MOHD SHAHFIEE BIN ABDULLAH",
"10008350": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "10003214": "NIK MOHD FADIR BIN NIK MAT RAWI", "10016370": "AHMAD AZIM BIN ISA",
"10022910": "NUR SHAHIDA BINTI MOHD TAMIJI ", "10023513": "MUHAMMAD SYAHMI BIN AZMEY", "10023273": "MOHD IDZHAM BIN ABU BAKAR",
"10023577": "MOHAMAD NAIM MOHAMAD SAPRI", "10023853": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "10008842": "MIRAN NURSYAWALNI AMIR",
"10015662": "MUHAMMAD HANIF BIN HASHIM", "10011944": "NUR HAZIRAH BINTI NAWI"
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

# --------- Form Layout ---------
staff_id = st.selectbox("👤 Staff ID", options=list(staff_dict.keys()), index=None, placeholder="Pilih ID...")
if staff_id:
    st.info(f"Staf: {staff_dict[staff_id]}")

stop = st.selectbox("📍 Bus Stop", allowed_stops, index=None, placeholder="Pilih hentian...")

if stop:
    matched_stop_data = stops_df[stops_df["Stop Name"] == stop]
    matched_route_nums = matched_stop_data["Route Number"].unique()
    current_route = " / ".join(map(str, matched_route_nums))
    matched_depot_names = routes_df[routes_df["Route Number"].isin(matched_route_nums)]["Depot"].unique()
    current_depot = " / ".join(map(str, matched_depot_names))
    st.markdown(f"**Laluan:** {current_route} | **Depot:** {current_depot}")

st.divider()

st.subheader("A. KELAKUAN KAPTEN BAS")
for i, q in enumerate(questions_a):
    st.markdown(f"**{q}**")
    options = ["Yes", "No", "NA"] if i >= 4 else ["Yes", "No"]
    st.session_state.responses[q] = st.radio(label=q, options=options, index=None, key=f"qa_{i}", horizontal=True, label_visibility="collapsed")

st.divider()

st.subheader("B. KEADAAN HENTIAN BAS")
for i, q in enumerate(questions_b):
    st.markdown(f"**{q}**")
    options = ["Yes", "No", "NA"] if "NA" in q else ["Yes", "No"]
    st.session_state.responses[q] = st.radio(label=q, options=options, index=None, key=f"qb_{i}", horizontal=True, label_visibility="collapsed")

st.divider()

# --------- Camera Section ---------
st.subheader("📸 Gambar (Exactly 3)")
if len(st.session_state.photos) < 3:
    col_cam, col_file = st.columns(2)
    with col_cam:
        cam_photo = st.camera_input(f"Photo #{len(st.session_state.photos) + 1}")
        if cam_photo:
            st.session_state.photos.append(cam_photo)
            st.rerun()
    with col_file:
        up_photo = st.file_uploader(f"Upload #{len(st.session_state.photos) + 1}", type=["png", "jpg", "jpeg"])
        if up_photo:
            st.session_state.photos.append(up_photo)
            st.rerun()
else:
    st.success("3 Gambar dirakam.")
    if st.button("Reset Gambar"):
        st.session_state.photos = []
        st.rerun()

# --------- Submit ---------
if st.button("Submit Survey"):
    if not staff_id or not stop or len(st.session_state.photos) != 3 or None in st.session_state.responses.values():
        st.error("Sila lengkapkan semua maklumat dan ambil 3 keping gambar.")
    else:
        with st.spinner("Submitting..."):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            photo_links = []
            for i, img in enumerate(st.session_state.photos):
                link = gdrive_upload_file(img.getvalue(), f"{timestamp}_{i}.jpg", "image/jpeg", FOLDER_ID)
                photo_links.append(link)

            answers = [st.session_state.responses[q] for q in all_questions]
            row = [timestamp, staff_id, staff_dict[staff_id], current_depot, current_route, stop] + answers + ["; ".join(photo_links)]
            header = ["Timestamp", "Staff ID", "Staff Name", "Depot", "Route", "Bus Stop"] + all_questions + ["Photos"]

            sheet_id = find_or_create_gsheet("survey_responses", FOLDER_ID)
            append_row(sheet_id, row, header)

            st.balloons()
            st.success("Berjaya dihantar!")
            st.session_state.photos = []
            st.session_state.responses = {q: None for q in all_questions}
            time.sleep(2)
            st.rerun()
