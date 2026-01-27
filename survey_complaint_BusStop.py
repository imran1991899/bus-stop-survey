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
st.set_page_config(page_title="Bus Stop Survey", layout="wide")

# --------- THEME CSS: CYBER-DARK GLOW EFFECT ---------
st.markdown("""
    <style>
    /* 1. Main Background - Deep Obsidian */
    .stApp {
        background-color: #050a05 !important;
        color: #39FF14 !important;
    }

    /* 2. Neon Green Text & Headers */
    h1, h2, h3, p, span, label {
        color: #39FF14 !important;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* 3. Dropdown/Selectbox Styling */
    div[data-baseweb="select"] > div {
        background-color: #0d110d !important;
        border: 1px solid #1c331c !important;
        color: #39FF14 !important;
    }

    /* 4. YES / NO / NA BUTTONS - FULL GLOW ON SELECTION */
    div[role="radiogroup"] {
        display: flex;
        flex-direction: row;
        gap: 20px;
        padding: 15px 0;
    }

    /* Base Button Design */
    div[role="radiogroup"] label {
        background-color: #0d110d !important;
        border: 2px solid #1c331c !important;
        border-radius: 8px !important;
        padding: 15px 45px !important;
        transition: all 0.3s ease-in-out !important;
        cursor: pointer !important;
        min-width: 120px;
        text-align: center;
    }

    /* YES - Selected Glow Green */
    div[role="radiogroup"] label:has(input[value="Yes"]):has(input:checked) {
        background-color: #39FF14 !important;
        border-color: #39FF14 !important;
        box-shadow: 0 0 25px #39FF14, inset 0 0 10px rgba(0,0,0,0.5) !important;
    }
    div[role="radiogroup"] label:has(input[value="Yes"]):has(input:checked) p {
        color: #000000 !important;
        font-weight: 900 !important;
    }

    /* NO - Selected Glow Red */
    div[role="radiogroup"] label:has(input[value="No"]):has(input:checked) {
        background-color: #FF3131 !important;
        border-color: #FF3131 !important;
        box-shadow: 0 0 25px #FF3131, inset 0 0 10px rgba(0,0,0,0.5) !important;
    }
    div[role="radiogroup"] label:has(input[value="No"]):has(input:checked) p {
        color: #ffffff !important;
        font-weight: 900 !important;
    }

    /* NA - Selected Glow Gray */
    div[role="radiogroup"] label:has(input[value="NA"]):has(input:checked) {
        background-color: #444444 !important;
        border-color: #888888 !important;
        box-shadow: 0 0 15px #888888 !important;
    }

    /* Hide standard radio dot circles */
    div[role="radiogroup"] [data-testid="stWidgetSelectionVisualizer"] {
        display: none !important;
    }

    /* 5. BIG SUBMIT BUTTON - DASHBOARD STYLE */
    div.stButton > button {
        width: 100% !important;
        background-color: #0d110d !important;
        color: #39FF14 !important;
        border: 2px solid #39FF14 !important;
        border-radius: 12px !important;
        height: 80px !important;
        font-size: 24px !important;
        font-weight: bold !important;
        text-transform: uppercase;
        margin-top: 30px;
        transition: 0.3s;
    }
    div.stButton > button:hover {
        background-color: #39FF14 !important;
        color: #000000 !important;
        box-shadow: 0 0 30px #39FF14 !important;
    }

    /* Info Boxes and Alerts */
    .stAlert {
        background-color: #0d110d !important;
        border: 1px solid #1c331c !important;
        color: #39FF14 !important;
    }
    
    hr {
        border-color: #1c331c !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📟 BUS STOP SURVEY ENTRY")

# --------- Google Integration Constants ---------
FOLDER_ID = "1DjtLxgyQXwgjq_N6I_-rtYcBcnWhzMGp"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]
CLIENT_SECRETS_FILE = "client_secrets2.json"

# --------- Authentication Logic ---------
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
        st.markdown(f"[Authorize here]({auth_url})"); st.stop()
    return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)

drive_service, sheets_service = get_authenticated_service()

# --------- Upload Helper Functions ---------
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

# --------- Data Preparation ---------
routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")

allowed_stops = sorted(stops_df["Stop Name"].unique().tolist())

staff_dict = {
    "8917": "MOHD RIZAL BIN RAMLI", "8918": "NUR FAEZAH BINTI HARUN", "8919": "NORAINSYIRAH BINTI ARIFFIN",
    "8920": "NORAZHA RAFFIZZI ZORKORNAINI", "8921": "NUR HANIM HANIL", "8922": "MUHAMMAD HAMKA BIN ROSLIM",
    "8923": "MUHAMAD NIZAM BIN IBRAHIM", "8924": "AZFAR NASRI BIN BURHAN", "8925": "MOHD SHAHFIEE BIN ABDULLAH",
    "8926": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "8927": "NIK MOHD FADIR BIN NIK MAT RAWI", "8928": "AHMAD AZIM BIN ISA",
    "8929": "NUR SHAHIDA BINTI MOHD TAMIJI", "8930": "MUHAMMAD SYAHMI BIN AZMEY", "8931": "MOHD IDZHAM BIN ABU BAKAR",
    "8932": "MOHAMAD NAIM MOHAMAD SAPRI", "8933": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "8934": "MIRAN NURSYAWALNI AMIR",
    "8935": "MUHAMMAD HANIF BIN HASHIM", "8936": "NUR HAZIRAH BINTI NAWI"
}

# --------- State Management ---------
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

# --------- Form Construction ---------
staff_id = st.selectbox("👤 STAFF IDENTIFICATION", options=list(staff_dict.keys()), index=None, placeholder="Select ID...")
if staff_id: st.success(f"NAME: {staff_dict[staff_id]}")

stop = st.selectbox("📍 BUS STOP LOCATION", allowed_stops, index=None, placeholder="Search stop...")
current_route = ""
current_depot = ""
if stop:
    matched_stop_data = stops_df[stops_df["Stop Name"] == stop]
    matched_route_nums = matched_stop_data["Route Number"].unique()
    current_route = " / ".join(map(str, matched_route_nums))
    matched_depot_names = routes_df[routes_df["Route Number"].isin(matched_route_nums)]["Depot"].unique()
    current_depot = " / ".join(map(str, matched_depot_names))
    st.info(f"ROUTE: {current_route}  |  DEPOT: {current_depot}")

st.markdown("---")
st.markdown("### 01. DRIVER CONDUCT")
for i, q in enumerate(questions_a):
    st.write(f"**{q}**")
    opts = ["Yes", "No", "NA"] if i >= 4 else ["Yes", "No"]
    st.session_state.responses[q] = st.radio(q, options=opts, index=None, key=f"qa_{i}", horizontal=True, label_visibility="collapsed")
    st.markdown("<br>", unsafe_allow_html=True)

st.markdown("---")
st.markdown("### 02. INFRASTRUCTURE & ENVIRONMENT")
for i, q in enumerate(questions_b):
    st.write(f"**{q}**")
    opts = ["Yes", "No", "NA"] if "NA" in q else ["Yes", "No"]
    st.session_state.responses[q] = st.radio(q, options=opts, index=None, key=f"qb_{i}", horizontal=True, label_visibility="collapsed")
    st.markdown("<br>", unsafe_allow_html=True)

st.markdown("---")
st.markdown("### 03. SCAN EVIDENCE (3 IMAGES)")
if len(st.session_state.photos) < 3:
    cam_in = st.camera_input(f"SCANNING IMAGE #{len(st.session_state.photos) + 1}")
    if cam_in:
        st.session_state.photos.append(cam_in)
        st.rerun()
else:
    st.success("ALL IMAGES CAPTURED")
    if st.button("RESET IMAGES"):
        st.session_state.photos = []
        st.rerun()

# --------- Submission ---------
if st.button("✅ SEND SURVEY DATA TO DATABASE"):
    if not staff_id or not stop or len(st.session_state.photos) != 3 or None in st.session_state.responses.values():
        st.error("🚨 TRANSMISSION FAILED: INCOMPLETE FORM DATA")
    else:
        with st.spinner("UPLOADING..."):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            links = []
            for i, img in enumerate(st.session_state.photos):
                url = gdrive_upload_file(img.getvalue(), f"{timestamp}_{i}.jpg", "image/jpeg", FOLDER_ID)
                links.append(url)

            ans = [st.session_state.responses[q] for q in all_questions]
            row_data = [timestamp, staff_id, staff_dict[staff_id], current_depot, current_route, stop] + ans + ["; ".join(links)]
            headers = ["Timestamp", "Staff ID", "Name", "Depot", "Route", "Stop"] + all_questions + ["Photos"]

            sheet_id = find_or_create_gsheet("Survey_Responses_Log", FOLDER_ID)
            append_row(sheet_id, row_data, headers)

            st.success("📡 SURVEY SUBMITTED SUCCESSFULLY")
            st.session_state.photos = []
            st.session_state.responses = {q: None for q in all_questions}
            time.sleep(2)
            st.rerun()
