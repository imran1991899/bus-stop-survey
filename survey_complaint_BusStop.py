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

# --------- THEME LOADER ---------
def load_external_theme(file_path="theme.txt"):
    """Reads CSS from theme.txt in your repository if it exists."""
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return f.read()
    return ""

external_css = load_external_theme("theme.txt")

# --------- APPLE UI GRID THEME CSS ---------
st.markdown(f"""
    <style>
    .stApp {{
        background-color: #F5F5F7 !important;
        color: #1D1D1F !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }}

    div[role="radiogroup"] {{
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
    }}

    [data-testid="stWidgetSelectionVisualizer"] {{
        display: none !important;
    }}

    div[role="radiogroup"] label {{
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
    }}

    div[role="radiogroup"] label p {{
        font-size: 16px !important; 
        margin: 0 !important;
        padding: 0 20px !important;
        white-space: nowrap !important; 
        line-height: 1.2 !important;
        text-align: center !important;
        color: #444444 !important; 
        font-weight: 700 !important; 
    }}

    div[role="radiogroup"] label:has(input:checked) {{
        background-color: #FFFFFF !important;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.15) !important;
    }}

    div[role="radiogroup"] label:has(input:checked) p {{
        color: #000000 !important; 
    }}

    div.stButton > button {{
        width: 100% !important;
        background-color: #007AFF !important;
        color: white !important;
        border: none !important;
        height: 60px !important;
        font-weight: 600 !important;
        border-radius: 16px !important;
        font-size: 18px !important;
        margin-top: 30px;
    }}

    .stAlert {{
        border-radius: 12px !important;
    }}

    /* Inject external theme from your text file */
    {external_css}
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
    bus_list = []

staff_dict = {"10005475": "MOHD RIZAL BIN RAMLI", "10020779": "NUR FAEZAH BINTI HARUN", "10014181": "NORAINSYIRAH BINTI ARIFFIN", "10022768": "NORAZHA RAFFIZZI ZORKORNAINI", "10022769": "NUR HANIM HANIL", "10023845": "MUHAMMAD HAMKA BIN ROSLIM", "10002059": "MUHAMAD NIZAM BIN IBRAHIM", "10005562": "AZFAR NASRI BIN BURHAN", "10010659": "MOHD SHAHFIEE BIN ABDULLAH", "10008350": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "10003214": "NIK MOHD FADIR BIN NIK MAT RAWI", "10016370": "AHMAD AZIM BIN ISA", "10022910": "NUR SHAHIDA BINTI MOHD TAMIJI ", "10023513": "MUHAMMAD SYAHMI BIN AZMEY", "10023273": "MOHD IDZHAM BIN ABU BAKAR", "10023577": "MOHAMAD NAIM MOHAMAD SAPRI", "10023853": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "10008842": "MIRAN NURSYAWALNI AMIR", "10015662": "MUHAMMAD HANIF BIN HASHIM", "10011944": "NUR HAZIRAH BINTI NAWI"}

# --------- Session State Initialization ---------
if "photos" not in st.session_state: st.session_state.photos = []
if "responses" not in st.session_state: st.session_state.responses = {}
if "persistent_staff_id" not in st.session_state: st.session_state.persistent_staff_id = None
if "reset_key" not in st.session_state: st.session_state.reset_key = 0

questions_a = ["1. BC menggunakan telefon bimbit?", "2. BC memperlahankan/memberhentikan bas?", "3. BC memandu di lorong 1 (kiri)?", "4. Bas penuh dengan penumpang?", "5. BC tidak mengambil penumpang? (NA jika tiada)", "6. BC berlaku tidak sopan? (NA jika tiada)"]
questions_b = ["7. Hentian terlindung dari pandangan BC?", "8. Hentian terhalang oleh kenderaan parkir?", "9. Persekitaran bahaya untuk bas berhenti?", "10. Terdapat pembinaan berhampiran?", "11. Mempunyai bumbung?", "12. Mempunyai tiang?", "13. Mempunyai petak hentian?", "14. Mempunyai layby?", "15. Terlindung dari pandangan BC? (Gerai/Pokok)", "16. Pencahayaan baik?", "17. Penumpang beri isyarat menahan? (NA jika tiada)", "18. Penumpang leka/tidak peka? (NA jika tiada)", "19. Penumpang tiba lewat?", "20. Penumpang menunggu di luar kawasan hentian?"]
all_questions = questions_a + questions_b

# --------- Main App UI ---------
st.title("BC and Bus Stop Survey")

# PERSISTENT SECTION (Does not reset)
staff_options = list(staff_dict.keys())
def_idx = staff_options.index(st.session_state.persistent_staff_id) if st.session_state.persistent_staff_id in staff_options else None

staff_id = st.selectbox("👤 Staff ID", options=staff_options, index=def_idx, placeholder="Pilih ID Staf...")
st.session_state.persistent_staff_id = staff_id

if staff_id:
    st.info(f"**Nama:** {staff_dict[staff_id]}")

st.divider()

# RESETTABLE SECTION (Wrapped in key-based container)
# Changing reset_key forces all widgets inside to reload as 'new'
form_key = st.session_state.reset_key

col_stop, col_bus_sel = st.columns(2)
with col_stop:
    stop = st.selectbox("📍 Bus Stop", sorted(stops_df["Stop Name"].unique()), index=None, placeholder="Pilih Hentian Bas...", key=f"stop_sel_{form_key}")
    current_route, current_depot = "", ""
    if stop:
        matched_stop_data = stops_df[stops_df["Stop Name"] == stop]
        current_route = " / ".join(map(str, matched_stop_data["Route Number"].unique()))
        current_depot = " / ".join(map(str, routes_df[routes_df["Route Number"].isin(matched_stop_data["Route Number"].unique())]["Depot"].unique()))
        st.info(f"**Route:** {current_route} | **Depot:** {current_depot}")

with col_bus_sel:
    selected_bus = st.selectbox("🚌 Pilih No. Pendaftaran Bas", options=bus_list, index=None, placeholder="Pilih no pendaftaran bas...", key=f"bus_sel_{form_key}")

st.subheader("A. KELAKUAN KAPTEN BAS")
for q in questions_a:
    st.markdown(f"**{q}**")
    opts = ["Yes", "No", "NA"] if "NA" in q else ["Yes", "No"]
    st.session_state.responses[q] = st.radio(q, opts, index=None, key=f"q_{q}_{form_key}", horizontal=True, label_visibility="collapsed")

st.divider()

st.subheader("B. KEADAAN HENTIAN BAS")
for q in questions_b:
    st.markdown(f"**{q}**")
    opts = ["Yes", "No", "NA"] if "NA" in q else ["Yes", "No"]
    st.session_state.responses[q] = st.radio(q, opts, index=None, key=f"q_{q}_{form_key}", horizontal=True, label_visibility="collapsed")

st.divider()

# Photo Capture
st.subheader("📸 Take Photo (3 Photos Required)")
if len(st.session_state.photos) < 3:
    col_cam, col_up = st.columns(2)
    with col_cam:
        cam_in = st.camera_input(f"Ambil Gambar #{len(st.session_state.photos)+1}")
        if cam_in: 
            st.session_state.photos.append(cam_in)
            st.rerun()
    with col_up:
        file_in = st.file_uploader(f"Upload Gambar #{len(st.session_state.photos)+1}", type=["jpg", "png", "jpeg"])
        if file_in: 
            st.session_state.photos.append(file_in)
            st.rerun()
else:
    st.success("3 Gambar berjaya dirakam.")
    if st.button("Reset Gambar"):
        st.session_state.photos = []
        st.rerun()

if st.session_state.photos:
    img_cols = st.columns(3)
    for idx, pic in enumerate(st.session_state.photos):
        img_cols[idx].image(pic, use_container_width=True)

# Submit Logic
if st.button("Submit Survey"):
    if not staff_id or not stop or not selected_bus or len(st.session_state.photos) != 3 or None in st.session_state.responses.values():
        st.error("Sila pastikan semua soalan dijawab, No. Bas dipilih, dan 3 keping gambar disediakan.")
    else:
        with st.spinner("Menghantar data..."):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            photo_urls = [gdrive_upload_file(p.getvalue(), f"{timestamp}_{idx}.jpg", "image/jpeg", FOLDER_ID) for idx, p in enumerate(st.session_state.photos)]
            
            row_data = [timestamp, staff_id, staff_dict[staff_id], current_depot, current_route, stop, selected_bus] + \
                       [st.session_state.responses[q] for q in all_questions] + ["; ".join(photo_urls)]
            
            header_data = ["Timestamp", "Staff ID", "Staff Name", "Depot", "Route", "Bus Stop", "Bus Register No"] + all_questions + ["Photos"]
            
            gsheet_id = find_or_create_gsheet("survey_responses", FOLDER_ID)
            append_row(gsheet_id, row_data, header_data)
            
            st.success("Tinjauan berjaya dihantar!")
            
            # --- THE RESET LOGIC ---
            st.session_state.photos = []
            st.session_state.responses = {}
            st.session_state.reset_key += 1  # Incrementing this clears all input widgets inside the resettlement section
            
            time.sleep(2)
            st.rerun()
