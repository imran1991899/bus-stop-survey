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

# --------- APPLE UI GRID THEME CSS ---------
st.markdown("""
    <style>
    /* Global App Background */
    .stApp {
        background-color: #F5F5F7 !important;
        color: #1D1D1F !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }

    /* iOS Segmented Control Style - ENLARGED & MOVED HIGHER */
    div[role="radiogroup"] {
        background-color: #E3E3E8 !important; 
        padding: 6px !important; 
        border-radius: 14px !important;
        gap: 8px !important;
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        margin-top: 2px !important; 
        margin-bottom: 28px !important; 
        max-width: 360px; 
        min-height: 58px !important; 
    }

    /* Hide standard radio circles */
    [data-testid="stWidgetSelectionVisualizer"] {
        display: none !important;
    }

    /* Individual Radio Item Label - THE BIGGER WHITE BOX */
    div[role="radiogroup"] label {
        background-color: transparent !important;
        border: none !important;
        padding: 14px 0px !important; 
        border-radius: 11px !important;
        transition: all 0.2s ease-in-out !important;
        flex: 1 !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        margin: 0 !important;
    }

    /* UPDATED: Text Formatting for Yes/No - BOLD DARK GRAY */
    div[role="radiogroup"] label p {
        font-size: 16px !important; 
        margin: 0 !important;
        padding: 0 20px !important;
        white-space: nowrap !important; 
        overflow: visible !important;
        line-height: 1.2 !important;
        text-align: center !important;
        color: #444444 !important; /* Bold Dark Gray */
        font-weight: 700 !important; 
    }

    /* Selected State (The White Slide) */
    div[role="radiogroup"] label:has(input:checked) {
        background-color: #FFFFFF !important;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.15) !important;
    }

    /* Selected State Text */
    div[role="radiogroup"] label:has(input:checked) p {
        color: #000000 !important; 
    }

    /* Main Submit Button Styling */
    div.stButton > button {
        width: 100% !important;
        background-color: #007AFF !important;
        color: white !important;
        border: none !important;
        height: 60px !important;
        font-weight: 600 !important;
        border-radius: 16px !important;
        font-size: 18px !important;
        margin-top: 30px;
    }

    /* Consistency for Info Boxes */
    .stAlert {
        border-radius: 12px !important;
        border: none !important;
        margin-top: 10px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --------- Logic Functions ---------
FOLDER_ID = "1DjtLxgyQXwgjq_N6I_-rtYcBcnWhzMGp"
CLIENT_SECRETS_FILE = "client_secrets2.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]

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

staff_dict = {"10005475": "MOHD RIZAL BIN RAMLI", "10020779": "NUR FAEZAH BINTI HARUN", "10014181": "NORAINSYIRAH BINTI ARIFFIN", "10022768": "NORAZHA RAFFIZZI ZORKORNAINI", "10022769": "NUR HANIM HANIL", "10023845": "MUHAMMAD HAMKA BIN ROSLIM", "10002059": "MUHAMAD NIZAM BIN IBRAHIM", "10005562": "AZFAR NASRI BIN BURHAN", "10010659": "MOHD SHAHFIEE BIN ABDULLAH", "10008350": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "10003214": "NIK MOHD FADIR BIN NIK MAT RAWI", "10016370": "AHMAD AZIM BIN ISA", "10022910": "NUR SHAHIDA BINTI MOHD TAMIJI ", "10023513": "MUHAMMAD SYAHMI BIN AZMEY", "10023273": "MOHD IDZHAM BIN ABU BAKAR", "10023577": "MOHAMAD NAIM MOHAMAD SAPRI", "10023853": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "10008842": "MIRAN NURSYAWALNI AMIR", "10015662": "MUHAMMAD HANIF BIN HASHIM", "10011944": "NUR HAZIRAH BINTI NAWI"}

if "photos" not in st.session_state: st.session_state.photos = []
questions_a = ["1. BC menggunakan telefon bimbit?", "2. BC memperlahankan/memberhentikan bas?", "3. BC memandu di lorong 1 (kiri)?", "4. Bas penuh dengan penumpang?", "5. BC tidak mengambil penumpang? (NA jika tiada)", "6. BC berlaku tidak sopan? (NA jika tiada)"]
questions_b = ["7. Hentian terlindung dari pandangan BC?", "8. Hentian terhalang oleh kenderaan parkir?", "9. Persekitaran bahaya untuk bas berhenti?", "10. Terdapat pembinaan berhampiran?", "11. Mempunyai bumbung?", "12. Mempunyai tiang?", "13. Mempunyai petak hentian?", "14. Mempunyai layby?", "15. Terlindung dari pandangan BC? (Gerai/Pokok)", "16. Pencahayaan baik?", "17. Penumpang beri isyarat menahan? (NA jika tiada)", "18. Penumpang leka/tidak peka? (NA jika tiada)", "19. Penumpang tiba lewat?", "20. Penumpang menunggu di luar kawasan hentian?"]
all_questions = questions_a + questions_b
if "responses" not in st.session_state: st.session_state.responses = {q: None for q in all_questions}

# --------- Main App UI ---------
st.title("BC and Bus Stop Stop Survey")

# Staff Section
staff_id = st.selectbox("👤 Staff ID", options=list(staff_dict.keys()), index=None, placeholder="Pilih ID Staf...")
if staff_id:
    # UPDATED: Only show name in bold
    st.info(f"**{staff_dict[staff_id]}**")

# Bus Stop Section
stop = st.selectbox("📍 Bus Stop", allowed_stops, index=None, placeholder="Pilih Hentian Bas...")

current_route, current_depot = "", ""
if stop:
    matched_stop_data = stops_df[stops_df["Stop Name"] == stop]
    current_route = " / ".join(map(str, matched_stop_data["Route Number"].unique()))
    current_depot = " / ".join(map(str, routes_df[routes_df["Route Number"].isin(matched_stop_data["Route Number"].unique())]["Depot"].unique()))
    st.info(f"**Route:** {current_route} | **Depot:** {current_depot}")

st.divider()

# Question Rendering Logic
def render_grid_questions(q_list):
    for i in range(0, len(q_list), 2):
        col1, col2 = st.columns(2)
        with col1:
            q = q_list[i]
            st.markdown(f"**{q}**")
            opts = ["Yes", "No", "NA"] if "NA" in q else ["Yes", "No"]
            st.session_state.responses[q] = st.radio(label=q, options=opts, index=None, key=f"r_{q}", horizontal=True, label_visibility="collapsed")
        
        if i + 1 < len(q_list):
            with col2:
                q = q_list[i+1]
                st.markdown(f"**{q}**")
                opts = ["Yes", "No", "NA"] if "NA" in q else ["Yes", "No"]
                st.session_state.responses[q] = st.radio(label=q, options=opts, index=None, key=f"r_{q}", horizontal=True, label_visibility="collapsed")

st.subheader("A. KELAKUAN KAPTEN BAS")
render_grid_questions(questions_a)

st.divider()

st.subheader("B. KEADAAN HENTIAN BAS")
render_grid_questions(questions_b)

st.divider()

# Photo Evidence
st.subheader("📸 Take Photo (3 Photos Required)")
if len(st.session_state.photos) < 3:
    col_cam, col_up = st.columns(2)
    with col_cam:
        cam_in = st.camera_input(f"Ambil Gambar #{len(st.session_state.photos)+1}")
        if cam_in: 
            st.session_state.photos.append(cam_in); st.rerun()
    with col_up:
        file_in = st.file_uploader(f"Upload Gambar #{len(st.session_state.photos)+1}", type=["jpg", "png", "jpeg"])
        if file_in: 
            st.session_state.photos.append(file_in); st.rerun()
else:
    st.success("3 Gambar berjaya dirakam.")
    if st.button("Reset Gambar"):
        st.session_state.photos = []; st.rerun()

if st.session_state.photos:
    img_cols = st.columns(3)
    for idx, pic in enumerate(st.session_state.photos):
        img_cols[idx].image(pic, use_container_width=True)

# Submit Logic
if st.button("Submit Survey"):
    if not staff_id or not stop or len(st.session_state.photos) != 3 or None in st.session_state.responses.values():
        st.error("Sila pastikan semua soalan dijawab dan 3 keping gambar disediakan.")
    else:
        with st.spinner("Menghantar..."):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            photo_urls = [gdrive_upload_file(p.getvalue(), f"{timestamp}_{idx}.jpg", "image/jpeg", FOLDER_ID) for idx, p in enumerate(st.session_state.photos)]
            
            row_data = [timestamp, staff_id, staff_dict[staff_id], current_depot, current_route, stop] + \
                       [st.session_state.responses[q] for q in all_questions] + ["; ".join(photo_urls)]
            
            header_data = ["Timestamp", "Staff ID", "Staff Name", "Depot", "Route", "Bus Stop"] + all_questions + ["Photos"]
            
            gsheet_id = find_or_create_gsheet("survey_responses", FOLDER_ID)
            append_row(gsheet_id, row_data, header_data)
            
            st.success("Tinjauan berjaya dihantar!")
            # Reset state
            st.session_state.photos = []
            st.session_state.responses = {q: None for q in all_questions}
            time.sleep(2)
            st.rerun()


