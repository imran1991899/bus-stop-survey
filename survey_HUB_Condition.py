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
from PIL import Image, ImageDraw, ImageFont
import pytz 
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

# --------- Timezone Setup ---------
KL_TZ = pytz.timezone('Asia/Kuala_Lumpur')

# --------- Page Setup ---------
st.set_page_config(page_title="Hub Profiling Survey", layout="wide")

# --------- Staff Dictionary ---------
staff_dict = {"10005475": "MOHD RIZAL BIN RAMLI", "10020779": "NUR FAEZAH BINTI HARUN", "10014181": "NORAINSYIRAH BINTI ARIFFIN", "10022768": "NORAZHA RAFFIZZI ZORKORNAINI", "10022769": "NUR HANIM HANIL", "10023845": "MUHAMMAD HAMKA BIN ROSLIM", "10002059": "MUHAMAD NIZAM BIN IBRAHIM", "10005562": "AZFAR NASRI BIN BURHAN", "10010659": "MOHD SHAFIEE BIN ABDULLAH", "10008350": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "10003214": "NIK MOHD FADIR BIN NIK MAT RAWI", "10016370": "AHMAD AZIM BIN ISA", "10022910": "NUR SHAHIDA BINTI MOHD TAMIJI ", "10023513": "MUHAMMAD SYAHMI BIN AZMEY", "10023273": "MOHD IDZHAM BIN ABU BAKAR", "10023577": "MOHAMAD NAIM MOHAMAD SAPRI", "10023853": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "10008842": "MIRAN NURSYAWALNI AMIR", "10015662": "MUHAMMAD HANDIF BIN HASHIM", "10011944": "NUR HAZIRAH BINTI NAWI"}

# --------- Load External Data ---------
@st.cache_data
def load_hub_data():
    try:
        df = pd.read_excel("hub name.xlsx")
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error loading 'hub name.xlsx': {e}")
        return pd.DataFrame()

hub_df = load_hub_data()

# --------- CSS STYLING ---------
st.markdown("""
    <style>
    .stApp { background-color: #F5F5F7 !important; color: #1D1D1F !important; }
    label[data-testid="stWidgetLabel"] p { font-size: 18px !important; font-weight: 600 !important; color: #3A3A3C !important; }
    .name-container { background-color: #E8F0FE; border-radius: 10px; padding: 12px 20px; margin-bottom: 20px; }
    .name-text { color: #1A73E8; font-weight: 600; font-size: 18px; }
    div.stButton > button { background-color: #007AFF !important; color: white !important; height: 60px !important; border-radius: 12px !important; width: 100%; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- Google OAuth Logic ---
FOLDER_ID = "1JKwlnKUVO3U74wTRu9U46ARF49dcglp7"
CLIENT_SECRETS_FILE = "client_secrets3.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]
REDIRECT_URI = "https://bus-stop-survey-fwaavwf7uxvxrfbjeqv9nq.streamlit.app/"

def save_credentials(creds):
    with open("token.pickle", "wb") as t: pickle.dump(creds, t)

def load_credentials():
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as t: return pickle.load(t)
    return None

def get_authenticated_service():
    creds = load_credentials()
    
    # Check if existing token is still valid
    if creds and creds.valid:
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    
    # Try to refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
        except:
            pass

    # Start new Flow
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)

    # If returning from Google with a 'code'
    if "code" in st.query_params:
        if "cv" in st.session_state:
            # Re-inject the stored verifier into the flow
            flow.code_verifier = st.session_state["cv"]
            try:
                full_url = REDIRECT_URI + "?" + urlencode(st.query_params)
                flow.fetch_token(authorization_response=full_url)
                creds = flow.credentials
                save_credentials(creds)
                st.query_params.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Handshake error: {e}")
                if st.button("Try Login Again"):
                    st.query_params.clear()
                    st.rerun()
                st.stop()
        else:
            st.warning("Session lost. Please restart login.")
            st.query_params.clear()
            st.stop()
    else:
        # Request login URL
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
        # Save verifier string to session state
        st.session_state["cv"] = flow.code_verifier
        st.markdown(f"### Authorization Required\n[Please log in with Google]({auth_url})")
        st.stop()

drive_service, sheets_service = get_authenticated_service()

# --------- Google Drive/Sheets Functions ---------
def gdrive_upload_file(file_bytes, filename, mimetype, folder_id=None):
    media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype)
    metadata = {"name": filename}
    if folder_id: metadata["parents"] = [folder_id]
    uploaded = drive_service.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()
    return uploaded["webViewLink"]

def append_row(sheet_id, row, header):
    sheet = sheets_service.spreadsheets()
    existing = sheet.values().get(spreadsheetId=sheet_id, range="A1:A1").execute()
    if "values" not in existing:
        sheet.values().update(spreadsheetId=sheet_id, range="A1", valueInputOption="RAW", body={"values": [header]}).execute()
    sheet.values().append(spreadsheetId=sheet_id, range="A1", valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": [row]}).execute()

def find_or_create_gsheet(name, folder_id):
    query = f"'{folder_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.spreadsheet'"
    res = drive_service.files().list(q=query, fields="files(id)").execute()
    if res.get("files"): return res["files"][0]["id"]
    file = drive_service.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.spreadsheet", "parents": [folder_id]}, fields="id").execute()
    return file["id"]

def add_watermark(image_bytes, hub_label):
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    now = datetime.now(KL_TZ)
    info_str = f"{now.strftime('%d/%m/%y %I:%M %p')} | {hub_label.upper()}"
    try: font_sub = ImageFont.truetype("arialbd.ttf", int(w * 0.04))
    except: font_sub = ImageFont.load_default()
    draw.text((20, h - 50), info_str, font=font_sub, fill="white")
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=90)
    return buf.getvalue()

# --------- Main UI ---------
if "photos" not in st.session_state: st.session_state.photos = []
if "videos" not in st.session_state: st.session_state.videos = []

st.title("Hub Profiling & Facility Survey")

st.header("📋 Maklumat Asas")
col1, col2 = st.columns(2)

with col1:
    staff_id = st.selectbox("1. Staff ID", options=sorted(list(staff_dict.keys())), index=None)
    nama = staff_dict.get(staff_id, "")
    if nama:
        st.markdown(f'<div class="name-container"><span class="name-text">Nama: {nama}</span></div>', unsafe_allow_html=True)
    
    hub_list = sorted(hub_df.iloc[:, 2].dropna().unique().tolist()) if not hub_df.empty else []
    sel_hub = st.selectbox("2. Nama Hab", options=hub_list, index=None)
    
    depoh = hub_df[hub_df.iloc[:, 2] == sel_hub].iloc[0, 0] if sel_hub else ""
    st.text_input("3. Pilihan Depoh (Auto)", value=str(depoh), disabled=True)

with col2:
    tarikh = st.date_input("4. Tarikh Penilaian", value=datetime.now(KL_TZ))
    laluan = hub_df[hub_df.iloc[:, 2] == sel_hub].iloc[0, 1] if sel_hub else ""
    st.text_area("6. Laluan Bas (Auto)", value=str(laluan), disabled=True, height=100)

st.divider()

# Question Sections
maklumat = st.radio("7. Maklumat Asas Hub", ["Hub Utama", "Hub sokongan", "Hentian sahaja"], index=None, horizontal=True)
apo = st.radio("8. Status Enjin Hidup", ["Dibenarkan", "Tidak Dibenarkan", "Bersyarat", "Lain - lain"], index=None, horizontal=True)
apo_catatan = st.text_input("Ulasan APO") if apo in ["Bersyarat", "Lain - lain"] else ""

st.subheader("📸 Media Upload (Min 2)")
total = len(st.session_state.photos) + len(st.session_state.videos)

cam = st.camera_input("Take photo")
if cam and cam not in st.session_state.photos:
    st.session_state.photos.append(cam)
    st.rerun()

up = st.file_uploader("Upload Photos/Videos", type=["jpg", "png", "jpeg", "mp4"], accept_multiple_files=True)
if up:
    for f in up:
        if f not in st.session_state.photos and f not in st.session_state.videos:
            if "video" in (mimetypes.guess_type(f.name)[0] or ""): st.session_state.videos.append(f)
            else: st.session_state.photos.append(f)

if st.button("Submit Profiling Report"):
    if not sel_hub or not staff_id or total < 2:
        st.error("Lengkapkan maklumat dan muat naik sekurang-kurangnya 2 media.")
    else:
        with st.spinner("Submitting..."):
            try:
                urls = []
                for idx, p in enumerate(st.session_state.photos):
                    urls.append(gdrive_upload_file(add_watermark(p.getvalue(), sel_hub), f"IMG_{sel_hub}_{idx}.jpg", "image/jpeg", FOLDER_ID))
                for idx, v in enumerate(st.session_state.videos):
                    urls.append(gdrive_upload_file(v.getvalue(), f"VID_{sel_hub}_{idx}.mp4", "video/mp4", FOLDER_ID))

                row = [datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M:%S"), nama, depoh, str(tarikh), sel_hub, "; ".join(urls)]
                append_row(find_or_create_gsheet("hub_profiling_responses", FOLDER_ID), row, ["Timestamp", "Penilai", "Depot", "Tarikh", "Hab", "Links"])
                
                st.success("Report Submitted!")
                st.session_state.photos = []; st.session_state.videos = []
                time.sleep(2); st.rerun()
            except Exception as e:
                st.error(f"Submission error: {e}")
