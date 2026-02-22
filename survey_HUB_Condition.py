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

# --------- Staff Dictionary ---------
staff_dict = {
    "12345": "Ahmad Bin Ali",
    "67890": "Siti Nurhaliza",
    "11223": "Mohd Razak",
    "44556": "Nurul Izzah",
    # Add more staff ID: Name pairs here
}

# --------- Load External Data (Hubs & Routes) ---------
@st.cache_data
def load_hub_data():
    try:
        # Load the file and strip any accidental spaces from column headers
        df = pd.read_excel("hub name.xlsx")
        df.columns = df.columns.astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Error loading hub name.xlsx: {e}")
        return pd.DataFrame(columns=["Depot", "Routes"])

hub_df = load_hub_data()

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

# --------- Google API Logic ---------
FOLDER_ID = "1JKwlnKUVO3U74wTRu9U46ARF49dcglp7"
CLIENT_SECRETS_FILE = "client_secrets3.json"
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
                                       redirect_uri="https://bus-stop-survey-fwaavwf7uxvxrfbjeqv9nq.streamlit.app/")
    query_params = st.query_params
    if "code" in query_params:
        full_url = "https://bus-stop-survey-fwaavwf7uxvxrfbjeqv9nq.streamlit.app/?" + urlencode(query_params)
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

# 1. Maklumat Asas
st.header("📋 Maklumat Asas")
col1, col2 = st.columns(2)

with col1:
    staff_id_input = st.text_input("1. Nama (Masukkan Staff ID)", placeholder="Enter your staff ID")
    nama_penilai = staff_dict.get(staff_id_input, "Staff Not Found")
    if staff_id_input:
        st.info(f"Penilai: {nama_penilai}")

    # Safety check for Hub Name column
    if not hub_df.empty and 'Hub Name' in hub_df.columns:
        hub_options = sorted(hub_df['Hub Name'].dropna().unique().tolist())
        nama_hab = st.selectbox("2. Nama Hab", options=hub_options, index=None, placeholder="Pilih Nama Hab")
    else:
        st.error("Missing 'Hub Name' column in Excel.")
        nama_hab = None

    # Logic to auto-show Depot and Routes
    depoh_val = ""
    routes_val = ""
    if nama_hab:
        hub_data = hub_df[hub_df['Hub Name'] == nama_hab].iloc[0]
        depoh_val = hub_data.get('Depot', 'N/A')
        routes_val = hub_data.get('Routes', 'N/A')

    st.text_input("3. Pilihan Depoh (Hub Profiling)", value=str(depoh_val), disabled=True)

with col2:
    tarikh = st.date_input("4. Tarikh Penilaian", value=datetime.now(KL_TZ))
    masa = st.time_input("5. Masa Penilaian", value=datetime.now(KL_TZ).time())
    st.text_area("6. Laluan Bas yang menggunakan hab ini", value=str(routes_val), disabled=True, height=100)

st.divider()

# 2. Status Section
maklumat_asas = st.radio("7. Maklumat Asas Hub", ["Hub Utama", "Hub sokongan", "Hentian sahaja"], horizontal=True)
status_apo = st.radio("8. Status Enjin Hidup (APO SEMASA)", ["Dibenarkan", "Tidak Dibenarkan", "Bersyarat", "Lain - lain"], horizontal=True)

st.divider()

# 3. Hub Assessment
st.header("🏗️ PENILAIAN KEMUDAHAN HUB")
col3, col4 = st.columns(2)

with col3:
    fungsi_hub = st.multiselect("9. Fungsi Hub (boleh pilih lebih dari satu)", 
                               ["Pertukaran shif Kapten Bas", "Rehat pemandu", "Menunggu trip seterusnya", 
                                "Parkir sementara dan rehat (bermula di hentian lain)", "Transit penumpang", "Lain - lain"])
    catatan = st.text_area("10. Catatan", placeholder="Enter your answer")
    tandas = st.radio("11. TANDAS - Kemudahan Hub", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], horizontal=True)
    surau = st.radio("12. SURAU - Kemudahan Hub", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], horizontal=True)
    ruang_rehat = st.radio("13. Ruang Rehat Pemandu - Kemudahan Hub", ["Hab", "Ada Kiosk / Bilik Rehat (milik RapidKL)", "Tiada (BC rehat dalam bas / rehat di luar bas)"], horizontal=True)
    kiosk = st.radio("14. Kiosk - Kemudahan Hub", ["Masih ada dan selesa digunakan", "Ada tetapi kurang selesa digunakan", "Tiada"], horizontal=True)
    bumbung = st.radio("15. Kawasan Berbumbung - Kemudahan Hub", ["Ada", "Tiada", "Khemah"], horizontal=True)

with col4:
    cahaya = st.radio("16. Cahaya Lampu - Kemudahan Hub", ["Mencukupi", "Kurang mencukupi", "Tidak mencukupi"], horizontal=True)
    parkir = st.radio("17. Susun Atur / Kawasan Parkir - Kemudahan Hub", ["Kawasan luas", "Kawasan terhad"], horizontal=True)
    akses = st.radio("18. Akses Keluar & Masuk - Kemudahan Hub", ["Baik", "Kurang baik", "Tidak baik"], horizontal=True)
    kesesakan = st.radio("19. Risiko Kesesakan - Kemudahan Hub", ["Rendah", "Sederhana", "Tinggi"], horizontal=True)
    trafik = st.radio("20. Keselamatan Trafik - Kemudahan Hub", ["Selamat", "Kurang Selamat", "Tidak Selamat"], horizontal=True)
    lain_lain = st.text_input("21. Lain - lain - Kemudahan Hub", placeholder="Enter your answer")

cadangan = st.radio("22. Cadangan Tindakan dari pihak pemerhati", 
                    ["Masukkan dalam APO dan dibenarkan enjin hidup", "Tidak masukkan dalam APO dan tidak dibenarkan enjin hidup"], horizontal=True)

st.divider()

# 4. Media Section
st.subheader("📸 Media Upload (Min 1 Item Required)")
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

# Display uploaded media
if st.session_state.photos or st.session_state.videos:
    m_cols = st.columns(4)
    for i, p in enumerate(st.session_state.photos):
        m_cols[i % 4].image(p, use_container_width=True)
    for i, v in enumerate(st.session_state.videos):
        m_cols[(len(st.session_state.photos) + i) % 4].video(v)

# --------- Submit Logic ---------
if st.button("Submit Profiling Report"):
    if nama_penilai == "Staff Not Found" or not nama_hab:
        st.error("Sila pastikan Staff ID betul dan Nama Hab dipilih.")
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
                final_ts, nama_penilai, depoh_val, str(tarikh), str(masa), nama_hab, routes_val, 
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
            st.error(f"Error during submission: {e}")
