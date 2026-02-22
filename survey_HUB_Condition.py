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

# --------- Timezone Setup ---------
KL_TZ = pytz.timezone('Asia/Kuala_Lumpur')

# --------- Page Setup ---------
st.set_page_config(page_title="Hub Profiling Survey", layout="wide")

# --------- APPLE UI GRID THEME CSS ---------
st.markdown("""
    <style>
    .stApp {
        background-color: #F5F5F7 !important;
        color: #1D1D1F !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }
    label[data-testid="stWidgetLabel"] p {
        font-size: 16px !important;
        font-weight: 600 !important;
        color: #1D1D1F !important;
        margin-bottom: 8px !important;
    }
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
    div[role="radiogroup"] {
        background-color: #E3E3E8 !important; 
        padding: 4px !important; 
        border-radius: 10px !important;
        display: flex !important;
        flex-direction: row !important;
        margin-bottom: 20px !important;
    }
    div[role="radiogroup"] label {
        flex: 1 !important;
        background-color: transparent !important;
        justify-content: center !important;
        padding: 8px !important;
    }
    div[role="radiogroup"] label:has(input:checked) {
        background-color: #FFFFFF !important;
        border-radius: 8px !important;
        box-shadow: 0px 2px 5px rgba(0,0,0,0.1) !important;
    }
    div.stButton > button {
        background-color: #007AFF !important;
        color: white !important;
        height: 55px !important;
        border-radius: 12px !important;
        width: 100%;
        font-weight: 700 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Essential Google API Imports
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

# --------- Google API Logic (Keeping existing functions) ---------
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

# --------- Helper: Watermark ---------
def add_watermark(image_bytes, stop_name):
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    font_scale = int(w * 0.10) 
    now = datetime.now(KL_TZ)
    time_str = now.strftime("%I:%M %p")
    info_str = f"{now.strftime('%d/%m/%y')} | {stop_name.upper()}"
    try:
        font_main = ImageFont.truetype("arialbd.ttf", font_scale)
        font_sub = ImageFont.truetype("arialbd.ttf", int(font_scale * 0.4))
    except:
        font_main = ImageFont.load_default()
        font_sub = ImageFont.load_default()
    draw.text((20, h - font_scale - 60), time_str, font=font_main, fill="orange")
    draw.text((20, h - 50), info_str, font=font_sub, fill="white")
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=90)
    return img_byte_arr.getvalue()

# --------- State Initialization ---------
if "photos" not in st.session_state: st.session_state.photos = []
if "videos" not in st.session_state: st.session_state.videos = []

# --------- Main App UI ---------
st.title("Hub Profiling & Facility Survey")

# 1. Basic Information
st.header("📋 Maklumat Asas")
col1, col2 = st.columns(2)
with col1:
    nama_penilai = st.text_input("1. Nama", placeholder="Enter your name")
    depoh = st.selectbox("2. Pilihan Depoh (Hub Profiling)", 
                        ["Cheras Selatan", "Batu Caves", "Shah Alam", "Maluri", "BRT Sunway", 
                         "MRTFB Kajang", "MRTFB Serdang", "MRTFB Jinjang", "MRTFB Sungai Buloh"], index=None)
    tarikh = st.date_input("3. Tarikh Penilaian", value=datetime.now(KL_TZ))

with col2:
    masa = st.time_input("4. Masa Penilaian", value=datetime.now(KL_TZ).time())
    nama_hab = st.text_input("5. Nama Hab", placeholder="Enter Hub name")
    laluan = st.text_area("6. Laluan Bas yang menggunakan hab ini", placeholder="Contoh: T801, 802...")

status_apo = st.radio("8. Status Enjin Hidup (APO SEMASA)", ["Dibenarkan", "Tidak Dibenarkan", "Bersyarat", "Lain - lain"], horizontal=True)

st.divider()

# 2. Hub Assessment
st.header("🏗️ Penilaian Kemudahan Hub")
col3, col4 = st.columns(2)

with col3:
    maklumat_asas = st.radio("7. Maklumat Asas Hub", ["Hub Utama", "Hub sokongan", "Hentian sahaja"], horizontal=True)
    fungsi_hub = st.multiselect("10. Fungsi Hub (boleh pilih lebih dari satu)", 
                               ["Pertukaran shif Kapten Bas", "Rehat pemandu", "Menunggu trip seterusnya", 
                                "Parkir sementara dan rehat (bermula di hentian lain)", "Transit penumpang", "Lain - lain"])
    tandas = st.radio("12. TANDAS - Kemudahan Hab", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], horizontal=True)
    surau = st.radio("13. SURAU - Kemudahan Hab", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], horizontal=True)
    ruang_rehat = st.radio("14. Ruang Rehat Pemandu", ["Hab", "Ada Kiosk / Bilik Rehat (milik RapidKL)", "Tiada (BC rehat dalam bas / rehat di luar bas)"], horizontal=True)
    kiosk = st.radio("15. Kiosk", ["Masih ada dan selesa digunakan", "Ada tetapi kurang selesa digunakan", "Tiada"], horizontal=True)

with col4:
    bumbung = st.radio("16. Kawasan Berbumbung", ["Ada", "Tiada", "Khemah"], horizontal=True)
    cahaya = st.radio("17. Cahaya Lampu", ["Mencukupi", "Kurang mencukupi", "Tidak mencukupi"], horizontal=True)
    parkir = st.radio("18. Susun Atur / Kawasan Parkir", ["Kawasan luas", "Kawasan terhad"], horizontal=True)
    akses = st.radio("19. Akses Keluar & Masuk", ["Baik", "Kurang baik", "Tidak baik"], horizontal=True)
    kesesakan = st.radio("20. Risiko Kesesakan", ["Rendah", "Sederhana", "Tinggi"], horizontal=True)
    trafik = st.radio("21. Keselamatan Trafik", ["Selamat", "Kurang Selamat", "Tidak Selamat"], horizontal=True)

catatan = st.text_area("11. Catatan", placeholder="Tambahkan maklumat tambahan jika ada...")
lain_lain = st.text_input("22. Lain - lain - Kemudahan Hab")
cadangan = st.radio("23. Cadangan Tindakan dari pihak pemerhati", 
                    ["Masukkan dalam APO dan dibenarkan enjin hidup", "Tidak masukkan dalam APO dan tidak dibenarkan enjin hidup"], horizontal=True)

st.divider()

# 3. Media Section
st.subheader("📸 Media Upload (Min 1 Item Required)")
current_media_count = len(st.session_state.photos) + len(st.session_state.videos)

col_cam, col_up = st.columns(2)
with col_cam:
    cam_in = st.camera_input("Capture Hub Photo")
    if cam_in: 
        st.session_state.photos.append(cam_in)
        st.rerun()
with col_up:
    file_in = st.file_uploader("Upload Hub Media", type=["jpg", "png", "jpeg", "mp4"])
    if file_in: 
        mime_type, _ = mimetypes.guess_type(file_in.name)
        if mime_type and mime_type.startswith("video"): st.session_state.videos.append(file_in)
        else: st.session_state.photos.append(file_in)
        st.rerun()

# Display uploaded
if st.session_state.photos or st.session_state.videos:
    m_cols = st.columns(4)
    for i, p in enumerate(st.session_state.photos):
        m_cols[i % 4].image(p, use_container_width=True)
    for i, v in enumerate(st.session_state.videos):
        m_cols[(len(st.session_state.photos) + i) % 4].video(v)

# --------- Submit Logic ---------
if st.button("Submit Profiling Report"):
    if not nama_penilai or not nama_hab or not depoh:
        st.error("Sila isi maklumat asas (Nama, Depoh, dan Nama Hab).")
    else:
        saving_placeholder = st.empty()
        saving_placeholder.info("⏳ Uploading to Google Drive & Sheets... Please wait.")
        
        try:
            # 1. Media Upload
            media_urls = []
            for idx, p in enumerate(st.session_state.photos):
                processed = add_watermark(p.getvalue(), nama_hab)
                url = gdrive_upload_file(processed, f"HUB_{nama_hab}_{idx}.jpg", "image/jpeg", FOLDER_ID)
                media_urls.append(url)
            
            for idx, v in enumerate(st.session_state.videos):
                v_url = gdrive_upload_file(v.getvalue(), f"HUB_{nama_hab}_{idx}.mp4", "video/mp4", FOLDER_ID)
                media_urls.append(v_url)

            # 2. Row Data Preparation
            final_ts = datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M:%S")
            row_data = [
                final_ts, nama_penilai, depoh, str(tarikh), str(masa), nama_hab, laluan, 
                maklumat_asas, status_apo, ", ".join(fungsi_hub), catatan, tandas, 
                surau, ruang_rehat, kiosk, bumbung, cahaya, parkir, akses, 
                kesesakan, trafik, lain_lain, cadangan, "; ".join(media_urls)
            ]
            
            header_data = [
                "Timestamp", "Nama Penilai", "Depoh", "Tarikh", "Masa", "Nama Hab", "Laluan",
                "Maklumat Asas", "Status APO", "Fungsi Hub", "Catatan", "Tandas", 
                "Surau", "Ruang Rehat", "Kiosk", "Bumbung", "Cahaya", "Parkir", "Akses",
                "Kesesakan", "Trafik", "Lain-lain", "Cadangan", "Media Links"
            ]

            append_row(find_or_create_gsheet("hub_profiling_responses", FOLDER_ID), row_data, header_data)
            
            st.success("Report Submitted Successfully!")
            st.session_state.photos = []
            st.session_state.videos = []
            time.sleep(2)
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")
