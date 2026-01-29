import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import mimetypes
import time
import os
import pickle
import re
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

    /* Standard Widget Labels */
    label[data-testid="stWidgetLabel"] p {
        font-size: 18px !important;
        font-weight: 600 !important;
        color: #3A3A3C !important;
    }

    /* Custom Spinner */
    .custom-spinner {
        padding: 20px;
        background-color: #FFF9F0;
        border: 2px solid #FFCC80;
        border-radius: 14px;
        color: #E67E22;
        text-align: center;
        font-weight: bold;
        margin-bottom: 20px;
    }

    /* Radio Group Styling */
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
        color: #444444 !important; 
        font-weight: 700 !important; 
    }

    div[role="radiogroup"] label:has(input:checked) {
        background-color: #FFFFFF !important;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.15) !important;
    }

    /* Submit Button */
    div.stButton > button {
        background-color: #007AFF !important;
        color: white !important;
        border: none !important;
        height: 60px !important;
        font-weight: 600 !important;
        border-radius: 16px !important;
        font-size: 18px !important;
        padding: 0 40px !important;
        width: 100%;
    }

    /* Camera Enhancement */
    [data-testid="stCameraInput"] {
        border: 2px dashed #007AFF;
        border-radius: 16px;
        padding: 10px;
    }
    
    [data-testid="stCameraInput"] video {
        border-radius: 12px;
        object-fit: cover;
    }

    [data-testid="stCameraInput"] label div {
        color: #007AFF !important;
        font-weight: bold !important;
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
                                       redirect_uri="https://bus-stop-survey-kwaazvrcnnrtfyniqjwzlc.streamlit.app/")
    query_params = st.query_params
    if "code" in query_params:
        full_url = "https://bus-stop-survey-kwaazvrcnnrtfyniqjwzlc.streamlit.app/?" + urlencode(query_params)
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

allowed_stops = sorted(["AJ106 LRT AMPANG", "DAMANSARA INTAN", "ECOSKY RESIDENCE", "FAKULTI KEJURUTERAAN (UTARA)", "FAKULTI PERNIAGAAN DAN PERAKAUNAN", "FAKULTI UNDANG-UNDANG", "KILANG PLASTIK EKSPEDISI EMAS (OPP)", "KJ477 UTAR", "KJ560 SHELL SG LONG (OPP)", "KL107 LRT MASJID JAMEK", "KL1082 SK Methodist", "KL117 BSN LEBUH AMPANG", "KL1217 ILP KUALA LUMPUR", "KL2247 KOMERSIAL KIP", "KL377 WISMA SISTEM", "KOMERSIAL BURHANUDDIN (2)", "MASJID CYBERJAYA 10", "MRT SRI DELIMA PINTU C", "PERUMAHAN TTDI", "PJ312 Medan Selera Seksyen 19", "PJ476 MASJID SULTAN ABDUL AZIZ", "PJ721 ONE UTAMA NEW WING", "PPJ384 AURA RESIDENCE", "SA12 APARTMENT BAIDURI (OPP)", "SA26 PERUMAHAN SEKSYEN 11", "SCLAND EMPORIS", "SJ602 BANDAR BUKIT PUCHONG BP1", "SMK SERI HARTAMAS", "SMK SULTAN ABD SAMAD (TIMUR)"])

staff_dict = {"10005475": "MOHD RIZAL BIN RAMLI", "10020779": "NUR FAEZAH BINTI HARUN", "10014181": "NORAINSYIRAH BINTI ARIFFIN", "10022768": "NORAZHA RAFFIZZI ZORKORNAINI", "10022769": "NUR HANIM HANIL", "10023845": "MUHAMMAD HAMKA BIN ROSLIM", "10002059": "MUHAMAD NIZAM BIN IBRAHIM", "10005562": "AZFAR NASRI BIN BURHAN", "10010659": "MOHD SHAFIEE BIN ABDULLAH", "10008350": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "10003214": "NIK MOHD FADIR BIN NIK MAT RAWI", "10016370": "AHMAD AZIM BIN ISA", "10022910": "NUR SHAHIDA BINTI MOHD TAMIJI ", "10023513": "MUHAMMAD SYAHMI BIN AZMEY", "10023273": "MOHD IDZHAM BIN ABU BAKAR", "10023577": "MOHAMAD NAIM MOHAMAD SAPRI", "10023853": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "10008842": "MIRAN NURSYAWALNI AMIR", "10015662": "MUHAMMAD HANIF BIN HASHIM", "10011944": "NUR HAZIRAH BINTI NAWI"}

if "saved_staff_id" not in st.session_state: st.session_state.saved_staff_id = None
if "saved_stop" not in st.session_state: st.session_state.saved_stop = None
if "photos" not in st.session_state: st.session_state.photos = []
if "videos" not in st.session_state: st.session_state.videos = []

questions_a = ["1. BC menggunakan telefon bimbit?", "2. BC memperlahankan/memberhentikan bas?", "3. BC memandu di lorong 1 (kiri)?", "4. Bas penuh dengan penumpang?", "5. BC tidak mengambil penumpang? (NA jika tiada)", "6. BC berlaku tidak sopan? (NA jika tiada)"]
questions_c = ["7. Penumpang beri isyarat menahan? (NA jika tiada)", "8. Penumpang leka/tidak peka? (NA jika tiada)", "9. Penumpang tiba lewat?", "10. Penumpang menunggu di luar kawasan hentian?"]
questions_b = ["11. Hentian terlindung dari pandangan BC? (semak, pokok, Gerai, lain2)", "12. Hentian terhalang oleh kenderaan parkir?", "13. Persekitaran bahaya untuk bas berhenti?", "14. Terdapat pembinaan berhampiran?", "15. Mempunyai bumbung?", "16. Mempunyai tiang?", "17. Mempunyai petak hentian?", "18. Mempunyai layby?"]

all_questions = questions_a + ["Ada Penumpang?"] + questions_c + questions_b
if "responses" not in st.session_state: st.session_state.responses = {q: None for q in all_questions}

# --------- Main App UI ---------
st.title("BC and Bus Stop Survey")

col_staff, col_stop = st.columns(2)
with col_staff:
    staff_id = st.selectbox("👤 Staff ID", options=list(staff_dict.keys()), 
                            index=list(staff_dict.keys()).index(st.session_state.saved_staff_id) if st.session_state.saved_staff_id in staff_dict else None, 
                            placeholder="Pilih ID Staf...", key="staff_id_select")
    if staff_id:
        st.info(f"**Nama:** {staff_dict[staff_id]}")
        st.session_state.saved_staff_id = staff_id

with col_stop:
    stop = st.selectbox("📍 Bus Stop", allowed_stops, 
                        index=allowed_stops.index(st.session_state.saved_stop) if st.session_state.saved_stop in allowed_stops else None, 
                        placeholder="Pilih Hentian Bas...", key="stop_select")
    current_route, current_depot = "", ""
    if stop:
        st.session_state.saved_stop = stop
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

st.subheader("A. KELAKUAN KAPTEN BAS")
selected_bus = st.selectbox("🚌 Pilih No. Bas", options=bus_list, index=None, placeholder="Pilih no pendaftaran bas...", key="bus_select")
render_grid_questions(questions_a)
st.divider()

st.subheader("C. PENUMPANG")
st.markdown("**ada penumpang?**")
has_passengers = st.radio("ada penumpang?", options=["Yes", "No"], index=None, key="has_pax", horizontal=True, label_visibility="collapsed")
st.session_state.responses["Ada Penumpang?"] = has_passengers
if has_passengers == "Yes": render_grid_questions(questions_c)
else:
    for q in questions_c: st.session_state.responses[q] = "No Passenger"
st.divider()

st.subheader("B. KEADAAN HENTIAN BAS")
render_grid_questions(questions_b)
st.divider()

# --------- High Resolution Media Section ---------
st.subheader("📸 Media Upload (3 Items Required)")
st.info("💡 **TIP:** For high-resolution photos or video recording, use the **Upload** button and select 'Camera'.")

current_media_count = len(st.session_state.photos) + len(st.session_state.videos)

if current_media_count < 3:
    col_cam, col_up = st.columns(2)
    with col_cam:
        # Changed key to be dynamic based on count to prevent double-firing
        cam_in = st.camera_input(f"Quick Capture #{current_media_count + 1}", key=f"cam_trigger_{current_media_count}")
        if cam_in: 
            st.session_state.photos.append(cam_in)
            st.rerun()
    with col_up:
        # Changed key to be dynamic based on count
        file_in = st.file_uploader(f"Upload Media #{current_media_count + 1}", 
                                   type=["jpg", "png", "jpeg", "mp4", "mov", "avi"],
                                   key=f"file_trigger_{current_media_count}")
        if file_in: 
            mime_type, _ = mimetypes.guess_type(file_in.name)
            if mime_type and mime_type.startswith("video"):
                st.session_state.videos.append(file_in)
            else:
                st.session_state.photos.append(file_in)
            st.rerun()

# Display uploaded items
if st.session_state.photos or st.session_state.videos:
    media_cols = st.columns(3)
    current_idx = 0
    for idx, pic in enumerate(st.session_state.photos):
        with media_cols[current_idx % 3]:
            st.image(pic, use_container_width=True)
            if st.button(f"Remove Photo {idx}", key=f"rm_p_{idx}"):
                st.session_state.photos.pop(idx); st.rerun()
        current_idx += 1
    for idx, vid in enumerate(st.session_state.videos):
        with media_cols[current_idx % 3]:
            st.video(vid)
            if st.button(f"Remove Video {idx}", key=f"rm_v_{idx}"):
                st.session_state.videos.pop(idx); st.rerun()
        current_idx += 1

st.divider()

# --------- Submit Logic ---------
if st.button("Submit Survey"):
    total_media = len(st.session_state.photos) + len(st.session_state.videos)
    check_responses = [st.session_state.responses[q] for q in questions_a + ["Ada Penumpang?"] + questions_b]
    if has_passengers == "Yes": check_responses += [st.session_state.responses[q] for q in questions_c]
            
    if not staff_id or not stop or not selected_bus or total_media != 3 or None in check_responses:
        st.error("Sila pastikan semua soalan dijawab, No. Bas dipilih, dan 3 keping media disediakan.")
    else:
        saving_placeholder = st.empty()
        saving_placeholder.markdown('<div class="custom-spinner">⏳ Saving data... Please wait.</div>', unsafe_allow_html=True)
        
        try:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_stop_name = re.sub(r'[^a-zA-Z0-9]', '_', stop)
            
            media_urls = []
            for idx, p in enumerate(st.session_state.photos):
                url = gdrive_upload_file(p.getvalue(), f"{safe_stop_name}_{timestamp_str}_IMG_{idx+1}.jpg", "image/jpeg", FOLDER_ID)
                media_urls.append(url)
            
            for idx, v in enumerate(st.session_state.videos):
                m_type, _ = mimetypes.guess_type(v.name)
                ext = v.name.split('.')[-1] if '.' in v.name else 'mp4'
                v_url = gdrive_upload_file(v.getvalue(), f"{safe_stop_name}_{timestamp_str}_VID_{idx+1}.{ext}", m_type or "video/mp4", FOLDER_ID)
                media_urls.append(v_url)

            final_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row_data = [final_ts, staff_id, staff_dict[staff_id], current_depot, current_route, stop, selected_bus] + \
                       [st.session_state.responses[q] for q in all_questions] + ["; ".join(media_urls)]
            
            header_data = ["Timestamp", "Staff ID", "Staff Name", "Depot", "Route", "Bus Stop", "Bus Register No"] + all_questions + ["Media Links"]
            append_row(find_or_create_gsheet("survey_responses", FOLDER_ID), row_data, header_data)
            
            saving_placeholder.empty() 
            st.success("Submitted Successfully!")
            
            # --- RESET LOGIC ---
            # 1. Clear Photos and Videos
            st.session_state.photos, st.session_state.videos = [], []
            # 2. Reset All Responses to None
            st.session_state.responses = {q: None for q in all_questions}
            # 3. Clear the Bus Select widget (not Staff/Stop)
            if "bus_select" in st.session_state:
                del st.session_state["bus_select"]
            # 4. Clear all radio widget keys
            for key in list(st.session_state.keys()):
                if key.startswith("r_") or key == "has_pax":
                    del st.session_state[key]
            
            time.sleep(2); st.rerun()
        except Exception as e:
            saving_placeholder.empty(); st.error(f"Error: {e}")
