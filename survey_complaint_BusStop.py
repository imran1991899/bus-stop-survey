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
    .stApp {
        background-color: #F5F5F7 !important;
        color: #1D1D1F !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }

    /* Target specific selectbox labels to be bigger and dark gray */
    label[data-testid="stWidgetLabel"] p {
        font-size: 18px !important;
        font-weight: 600 !important;
        color: #3A3A3C !important;
    }

    /* Centering the Submit Button and Remove Buttons */
    .stButton {
        display: flex;
        justify-content: center;
    }

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

    [data-testid="stWidgetSelectionVisualizer"] {
        display: none !important;
    }

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

    div[role="radiogroup"] label p {
        font-size: 16px !important; 
        margin: 0 !important;
        padding: 0 20px !important;
        white-space: nowrap !important; 
        overflow: visible !important;
        line-height: 1.2 !important;
        text-align: center !important;
        color: #444444 !important; 
        font-weight: 700 !important; 
    }

    div[role="radiogroup"] label:has(input:checked) {
        background-color: #FFFFFF !important;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.15) !important;
    }

    div[role="radiogroup"] label:has(input:checked) p {
        color: #000000 !important; 
    }

    /* Standard Button Styling */
    div.stButton > button {
        background-color: #007AFF !important;
        color: white !important;
        border: none !important;
        height: 60px !important;
        font-weight: 600 !important;
        border-radius: 16px !important;
        font-size: 18px !important;
        padding: 0 40px !important;
    }
    
    /* Styling for the centered Take Photo text inside camera component */
    [data-testid="stCameraInput"] label div {
        color: #FFD700 !important; /* Yellow */
        font-weight: bold !important;
    }

    .stAlert {
        border-radius: 12px !important;
        border: none !important;
        margin-top: 10px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --------- Google API Configuration ---------
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
        creds.refresh(Request())
        save_credentials(creds)
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, 
                                       redirect_uri="https://bus-stop-survey-99f8wusughejfcfvrvxmyl.streamlit.app/")
    query_params = st.query_params
    if "code" in query_params:
        full_url = "https://bus-stop-survey-99f8wusughejfcfvrvxmyl.streamlit.app/?" + urlencode(query_params)
        flow.fetch_token(authorization_response=full_url)
        creds = flow.credentials
        save_credentials(creds)
    else:
        auth_url, _ = flow.authorization_url(prompt="consent")
        st.markdown(f"### Authentication Required\n[Please log in with Google]({auth_url})")
        st.stop()
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

try:
    bus_df = pd.read_excel("bus_list.xlsx", sheet_name="bus list", usecols=[1])
    bus_list = sorted(bus_df.iloc[:, 0].dropna().astype(str).unique().tolist())
except Exception as e:
    st.error(f"Error loading bus_list.xlsx: {e}")
    bus_list = []

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

staff_dict = {"10005475": "MOHD RIZAL BIN RAMLI", "10020779": "NUR FAEZAH BINTI HARUN", "10014181": "NORAINSYIRAH BINTI ARIFFIN", "10022768": "NORAZHA RAFFIZZI ZORKORNAINI", "10022769": "NUR HANIM HANIL", "10023845": "MUHAMMAD HAMKA BIN ROSLIM", "10002059": "MUHAMAD NIZAM BIN IBRAHIM", "10005562": "AZFAR NASRI BIN BURHAN", "10010659": "MOHD SHAHFIEE BIN ABDULLAH", "10008350": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "10003214": "NIK MOHD FADIR BIN NIK MAT RAWI", "10016370": "AHMAD AZIM BIN ISA", "10022910": "NUR SHAHIDA BINTI MOHD TAMIJI ", "10023513": "MUHAMMAD SYAHMI BIN AZMEY", "10023273": "MOHD IDZHAM BIN ABU BAKAR", "10023577": "MOHAMAD NAIM MOHAMAD SAPRI", "10023853": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "10008842": "MIRAN NURSYAWALNI AMIR", "10015662": "MUHAMMAD HANDIF BIN HASHIM", "10011944": "NUR HAZIRAH BINTI NAWI"}

if "photos" not in st.session_state: st.session_state.photos = []

# Question Lists
questions_a = ["1. BC menggunakan telefon bimbit?", "2. BC memperlahankan/memberhentikan bas?", "3. BC memandu di lorong 1 (kiri)?", "4. Bas penuh dengan penumpang?", "5. BC tidak mengambil penumpang? (NA jika tiada)", "6. BC berlaku tidak sopan? (NA jika tiada)"]
questions_c = ["7. Penumpang beri isyarat menahan? (NA jika tiada)", "8. Penumpang leka/tidak peka? (NA jika tiada)", "9. Penumpang tiba lewat?", "10. Penumpang menunggu di luar kawasan hentian?"]
questions_b = ["11. Hentian terlindung dari pandangan BC? (semak, pokok, Gerai, lain2)", "12. Hentian terhalang oleh kenderaan parkir?", "13. Persekitaran bahaya untuk bas behenate?", "14. Terdapat pembinaan berhampiran?", "15. Mempunyai bumbung?", "16. Mempunyai tiang?", "17. Mempunyai petak hentian?", "18. Mempunyai layby?"]

all_questions = questions_a + ["Ada Penumpang?"] + questions_c + questions_b
if "responses" not in st.session_state: st.session_state.responses = {q: None for q in all_questions}

# --------- Main App UI ---------
st.title("BC and Bus Stop Survey")

col_staff, col_stop = st.columns(2)
with col_staff:
    staff_id = st.selectbox("👤 Staff ID", options=list(staff_dict.keys()), index=None, placeholder="Pilih ID Staf...")
    if staff_id:
        st.info(f"**Nama:** {staff_dict[staff_id]}")

with col_stop:
    stop = st.selectbox("📍 Bus Stop", allowed_stops, index=None, placeholder="Pilih Hentian Bas...")
    current_route, current_depot = "", ""
    if stop:
        matched_stop_data = stops_df[stops_df["Stop Name"] == stop]
        current_route = " / ".join(map(str, matched_stop_data["Route Number"].unique()))
        current_depot = " / ".join(map(str, routes_df[routes_df["Route Number"].isin(matched_stop_data["Route Number"].unique())]["Depot"].unique()))

st.divider()

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

# SECTION A
st.subheader("A. KELAKUAN KAPTEN BAS")
selected_bus = st.selectbox("🚌 Pilih No. Bas", options=bus_list, index=None, placeholder="Pilih no pendaftaran bas...")
render_grid_questions(questions_a)

st.divider()

# SECTION C (Conditional)
st.subheader("C. PENUMPANG")
st.markdown("**ada penumpang?**")
has_passengers = st.radio("ada penumpang?", options=["Yes", "No"], index=None, key="has_pax", horizontal=True, label_visibility="collapsed")
st.session_state.responses["Ada Penumpang?"] = has_passengers

if has_passengers == "Yes":
    render_grid_questions(questions_c)
else:
    for q in questions_c:
        st.session_state.responses[q] = "No Passenger"

st.divider()

# SECTION B
st.subheader("B. KEADAAN HENTIAN BAS")
render_grid_questions(questions_b)

st.divider()

# --------- Photo Section ---------
st.subheader("📸 Take Photo (3 Photos Required)")
if len(st.session_state.photos) < 3:
    col_cam, col_up = st.columns(2)
    with col_cam:
        cam_in = st.camera_input(f"Take Photo (Ambil Gambar #{len(st.session_state.photos)+1})")
        if cam_in: 
            st.session_state.photos.append(cam_in)
            st.rerun()
    with col_up:
        file_in = st.file_uploader(f"Upload Gambar #{len(st.session_state.photos)+1}", type=["jpg", "png", "jpeg"])
        if file_in: 
            st.session_state.photos.append(file_in)
            st.rerun()

if st.session_state.photos:
    img_cols = st.columns(3)
    for idx, pic in enumerate(st.session_state.photos):
        with img_cols[idx]:
            st.image(pic, use_container_width=True)
            if st.button(f"Remove", key=f"remove_{idx}"):
                st.session_state.photos.pop(idx)
                st.rerun()

st.divider()

# --------- Submit ---------
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    if st.button("Submit Survey"):
        check_responses = [st.session_state.responses[q] for q in questions_a + ["Ada Penumpang?"] + questions_b]
        if has_passengers == "Yes":
            check_responses += [st.session_state.responses[q] for q in questions_c]
            
        if not staff_id or not stop or not selected_bus or len(st.session_state.photos) != 3 or None in check_responses:
            st.error("Sila pastikan semua soalan dijawab, No. Bas dipilih, dan 3 keping gambar disediakan.")
        else:
            with st.spinner("Menghantar data ke Google Drive..."):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                photo_urls = [gdrive_upload_file(p.getvalue(), f"{timestamp}_{idx}.jpg", "image/jpeg", FOLDER_ID) for idx, p in enumerate(st.session_state.photos)]
                row_data = [timestamp, staff_id, staff_dict[staff_id], current_depot, current_route, stop, selected_bus] + \
                           [st.session_state.responses[q] for q in all_questions] + ["; ".join(photo_urls)]
                header_data = ["Timestamp", "Staff ID", "Staff Name", "Depot", "Route", "Bus Stop", "Bus Register No"] + all_questions + ["Photos"]
                gsheet_id = find_or_create_gsheet("survey_responses", FOLDER_ID)
                append_row(gsheet_id, row_data, header_data)
                st.success("Tinjauan berjaya dihantar!")
                st.session_state.photos = []
                st.session_state.responses = {q: None for q in all_questions}
                time.sleep(2)
                st.rerun()
