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
st.set_page_config(page_title="Bus Stop Survey", layout="wide")

# --------- APPLE UI LIGHT THEME CSS ---------
st.markdown("""
    <style>
    .stApp {
        background-color: #F5F5F7 !important;
        color: #1D1D1F !important;
        font-family: "SF Pro Text", -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    /* iOS Segmented Control Style */
    div[role="radiogroup"] {
        background-color: #E3E3E8 !important; 
        padding: 6px !important; 
        border-radius: 14px !important;
        gap: 8px !important;
        display: flex !important;
        flex-direction: row !important;
        max-width: 360px; 
    }

    [data-testid="stWidgetSelectionVisualizer"] {
        display: none !important;
    }

    div[role="radiogroup"] label {
        background-color: transparent !important;
        border: none !important;
        padding: 12px 0px !important; 
        border-radius: 10px !important;
        flex: 1 !important;
        display: flex !important;
        justify-content: center !important;
    }

    div[role="radiogroup"] label p {
        font-size: 16px !important; 
        color: #444444 !important; 
        font-weight: 700 !important; 
    }

    div[role="radiogroup"] label:has(input:checked) {
        background-color: #FFFFFF !important;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.1) !important;
    }

    /* Action Buttons */
    div.stButton > button:first-child {
        width: 100% !important;
        background-color: #007AFF !important;
        color: white !important;
        border-radius: 14px !important;
        height: 55px !important;
        font-weight: 600 !important;
    }

    button[key*="retake"] { background-color: #007AFF !important; color: white !important; }
    button[key*="remove"] { background-color: #FF3B30 !important; color: white !important; }

    .stAlert { border-radius: 12px !important; }
    </style>
    """, unsafe_allow_html=True)

# --------- Logic Functions ---------
FOLDER_ID = "1DjtLxgyQXwgjq_N6I_-rtYcBcnWhzMGp"
CLIENT_SECRETS_FILE = "client_secrets2.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]

# Ensure this is the RAW link from GitHub
BUS_LIST_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/bus_list.xlsx"

@st.cache_data
def load_bus_list(url):
    try:
        # Load specifically from sheet "Bus" and Column B
        df = pd.read_excel(url, sheet_name="Bus", usecols="B")
        df.columns = ["Bus_Number"]
        return df["Bus_Number"].dropna().unique().tolist()
    except Exception as e:
        st.error(f"Error loading GitHub file: {e}")
        return ["Error loading list"]

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
        st.markdown(f"### Authentication Required\n[Please log in with Google]({auth_url})"); st.stop()
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

# --------- Data Preparation ---------
routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")
bus_list_options = load_bus_list(BUS_LIST_URL)

allowed_stops = sorted(["AJ106 LRT AMPANG", "DAMANSARA INTAN", "ECOSKY RESIDENCE", "FAKULTI KEJURUTERAAN (UTARA)", "FAKULTI PERNIAGAAN DAN PERAKAUNAN", "FAKULTI UNDANG-UNDANG", "KILANG PLASTIK EKSPEDISI EMAS (OPP)", "KJ477 UTAR", "KJ560 SHELL SG LONG (OPP)", "KL107 LRT MASJID JAMEK", "KL1082 SK Methodist", "KL117 BSN LEBUH AMPANG", "KL1217 ILP KUALA LUMPUR", "KL2247 KOMERSIAL KIP", "KL377 WISMA SISTEM", "KOMERSIAL BURHANUDDIN (2)", "MASJID CYBERJAYA 10", "MRT SRI DELIMA PINTU C", "PERUMAHAN TTDI", "PJ312 Medan Selera Seksyen 19", "PJ476 MASJID SULTAN ABDUL AZIZ", "PJ721 ONE UTAMA NEW WING", "PPJ384 AURA RESIDENCE", "SA12 APARTMENT BAIDURI (OPP)", "SA26 PERUMAHAN SEKSYEN 11", "SCLAND EMPORIS", "SJ602 BANDAR BUKIT PUCHONG BP1", "SMK SERI HARTAMAS", "SMK SULTAN ABD SAMAD (TIMUR)"])
staff_dict = {"10005475": "MOHD RIZAL BIN RAMLI", "10020779": "NUR FAEZAH BINTI HARUN", "10014181": "NORAINSYIRAH BINTI ARIFFIN", "10022768": "NORAZHA RAFFIZZI ZORKORNAINI", "10022769": "NUR HANIM HANIL", "10023845": "MUHAMMAD HAMKA BIN ROSLIM", "10002059": "MUHAMAD NIZAM BIN IBRAHIM", "10005562": "AZFAR NASRI BIN BURHAN", "10010659": "MOHD SHAHFIEE BIN ABDULLAH", "10008350": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "10003214": "NIK MOHD FADIR BIN NIK MAT RAWI", "10016370": "AHMAD AZIM BIN ISA", "10022910": "NUR SHAHIDA BINTI MOHD TAMIJI ", "10023513": "MUHAMMAD SYAHMI BIN AZMEY", "10023273": "MOHD IDZHAM BIN ABU BAKAR", "10023577": "MOHAMAD NAIM MOHAMAD SAPRI", "10023853": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "10008842": "MIRAN NURSYAWALNI AMIR", "10015662": "MUHAMMAD HANIF BIN HASHIM", "10011944": "NUR HAZIRAH BINTI NAWI"}

if "photos" not in st.session_state: st.session_state.photos = []
questions_a = ["1. BC menggunakan telefon bimbit?", "2. BC memperlahankan/memberhentikan bas?", "3. BC memandu di lorong 1 (kiri)?", "4. Bas penuh dengan penumpang?", "5. BC tidak mengambil penumpang? (NA jika tiada)", "6. BC berlaku tidak sopan? (NA jika tiada)"]
questions_b = ["7. Hentian terlindung dari pandangan BC?", "8. Hentian terhalang oleh kenderaan parkir?", "9. Persekitaran bahaya untuk bas berhenti?", "10. Terdapat pembinaan berhampiran?", "11. Mempunyai bumbung?", "12. Mempunyai tiang?", "13. Mempunyai petak hentian?", "14. Mempunyai layby?", "15. Terlindung dari pandangan BC? (Gerai/Pokok)", "16. Pencahayaan baik?", "17. Penumpang beri isyarat menahan? (NA jika tiada)", "18. Penumpang leka/tidak peka? (NA jika tiada)", "19. Penumpang tiba lewat?", "20. Penumpang menunggu di luar kawasan hentian?"]
all_questions = questions_a + questions_b
if "responses" not in st.session_state: st.session_state.responses = {q: None for q in all_questions}

# --------- Main App UI ---------
st.title("🚌 Bus Stop Survey")

# Staff Selection
staff_id = st.selectbox("👤 Staff ID", options=list(staff_dict.keys()), index=None)
if staff_id: st.info(f"**Staff Name:** {staff_dict[staff_id]}")

# Bus Stop Selection
stop = st.selectbox("📍 Bus Stop", allowed_stops, index=None)
current_route, current_depot = "", ""
if stop:
    matched = stops_df[stops_df["Stop Name"] == stop]
    current_route = " / ".join(map(str, matched["Route Number"].unique()))
    current_depot = " / ".join(map(str, routes_df[routes_df["Route Number"].isin(matched["Route Number"].unique())]["Depot"].unique()))
    st.info(f"**Route:** {current_route} | **Depot:** {current_depot}")

st.divider()

# Vehicle Selection from GitHub Sheet "Bus"
st.subheader("🚌 Vehicle Information")
bus_number = st.selectbox("Select Bus Number", options=bus_list_options, index=None)

st.divider()

# Questions Grid
def render_questions(q_list):
    for i in range(0, len(q_list), 2):
        col1, col2 = st.columns(2)
        for idx, col in enumerate([col1, col2]):
            if i + idx < len(q_list):
                with col:
                    q = q_list[i+idx]
                    st.markdown(f"**{q}**")
                    opts = ["Yes", "No", "NA"] if "NA" in q else ["Yes", "No"]
                    st.session_state.responses[q] = st.radio(q, opts, index=None, horizontal=True, label_visibility="collapsed")

st.subheader("A. KELAKUAN KAPTEN BAS")
render_questions(questions_a)
st.divider()
st.subheader("B. KEADAAN HENTIAN BAS")
render_questions(questions_b)
st.divider()

# Single-Camera Capture Logic
st.subheader("📸 Evidence (3 Photos Required)")
if len(st.session_state.photos) < 3:
    st.write(f"Capturing Photo {len(st.session_state.photos) + 1} of 3")
    cam = st.camera_input("Take Photo", key=f"capture_{len(st.session_state.photos)}")
    if cam:
        st.session_state.photos.append(cam)
        st.rerun()
else:
    st.success("3 Photos captured.")

# Photo Grid with Actions
if st.session_state.photos:
    p_cols = st.columns(3)
    for i, p in enumerate(st.session_state.photos):
        with p_cols[i]:
            st.image(p, use_container_width=True)
            if st.button(f"🔄 Retake", key=f"retake_{i}"):
                st.session_state.photos.pop(i); st.rerun()
            if st.button(f"🗑️ Remove", key=f"remove_{i}"):
                st.session_state.photos.pop(i); st.rerun()

st.divider()

# Submit
if st.button("Submit Survey"):
    if not staff_id or not stop or not bus_number or len(st.session_state.photos) < 3 or None in st.session_state.responses.values():
        st.error("Please complete all fields and capture 3 photos.")
    else:
        with st.spinner("Submitting..."):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            urls = [gdrive_upload_file(p.getvalue(), f"{ts}_p{i+1}.jpg", "image/jpeg", FOLDER_ID) for i, p in enumerate(st.session_state.photos)]
            
            row = [ts, staff_id, staff_dict[staff_id], current_depot, current_route, stop, bus_number] + \
                  [st.session_state.responses[q] for q in all_questions] + ["; ".join(urls)]
            
            header = ["Timestamp", "Staff ID", "Name", "Depot", "Route", "Stop", "Bus No"] + all_questions + ["Photos"]
            
            sheet_id = find_or_create_gsheet("survey_responses", FOLDER_ID)
            append_row(sheet_id, row, header)
            
            st.success("Submitted successfully!")
            st.session_state.photos = []
            st.session_state.responses = {q: None for q in all_questions}
            time.sleep(2); st.rerun()
