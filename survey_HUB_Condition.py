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
}

# --------- Load External Data ---------
@st.cache_data
def load_hub_data():
    try:
        # Load the file 'hub name.xlsx'
        df = pd.read_excel("hub name.xlsx")
        # Clean headers: Column A should be 'Depot', Column B should be 'Routes'
        # We rename them manually here just in case they are different in Excel
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error loading 'hub name.xlsx': {e}")
        return pd.DataFrame(columns=["Depot", "Routes"])

hub_df = load_hub_data()

# --------- APPLE UI GRID THEME CSS ---------
st.markdown("""
    <style>
    .stApp { background-color: #F5F5F7 !important; color: #1D1D1F !important; font-family: -apple-system, sans-serif !important; }
    label[data-testid="stWidgetLabel"] p { font-size: 16px !important; font-weight: 600 !important; color: #1D1D1F !important; margin-bottom: 8px !important; }
    div[role="radiogroup"] { background-color: #E3E3E8 !important; padding: 4px !important; border-radius: 10px !important; display: flex !important; flex-direction: row !important; }
    div[role="radiogroup"] label:has(input:checked) { background-color: #FFFFFF !important; border-radius: 8px !important; box-shadow: 0px 2px 5px rgba(0,0,0,0.1) !important; }
    div.stButton > button { background-color: #007AFF !important; color: white !important; height: 55px !important; border-radius: 12px !important; font-weight: 700 !important; }
    </style>
    """, unsafe_allow_html=True)

# Google API logic
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

FOLDER_ID = "1JKwlnKUVO3U74wTRu9U46ARF49dcglp7"
CLIENT_SECRETS_FILE = "client_secrets3.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]

def save_credentials(creds):
    with open("token.pickle", "wb") as t: pickle.dump(creds, t)
def load_credentials():
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as t: return pickle.load(t)
    return None

def get_authenticated_service():
    creds = load_credentials()
    if creds and creds.valid:
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request()); save_credentials(creds)
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri="https://bus-stop-survey-fwaavwf7uxvxrfbjeqv9nq.streamlit.app/")
    if "code" in st.query_params:
        full_url = "https://bus-stop-survey-fwaavwf7uxvxrfbjeqv9nq.streamlit.app/?" + urlencode(st.query_params)
        flow.fetch_token(authorization_response=full_url)
        creds = flow.credentials; save_credentials(creds)
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    else:
        auth_url, _ = flow.authorization_url(prompt="consent")
        st.markdown(f"### Authentication Required\n[Please log in with Google]({auth_url})")
        st.stop()

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

def add_watermark(image_bytes, hub_label):
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    now = datetime.now(KL_TZ)
    info_str = f"{now.strftime('%d/%m/%y %I:%M %p')} | {hub_label.upper()}"
    draw.text((20, h - 50), info_str, fill="white")
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=90)
    return img_byte_arr.getvalue()

if "photos" not in st.session_state: st.session_state.photos = []
if "videos" not in st.session_state: st.session_state.videos = []

# --------- Main App UI ---------
st.title("Hub Profiling & Facility Survey")

st.header("📋 Maklumat Asas")
col1, col2 = st.columns(2)

with col1:
    staff_id = st.text_input("1. Nama (Masukkan Staff ID)", placeholder="Enter Staff ID")
    nama_penilai = staff_dict.get(staff_id, "Staff Not Found")
    if staff_id: st.info(f"Nama Penilai: {nama_penilai}")

    # User enters Hub Name manually since it's not in the Excel
    nama_hab = st.text_input("2. Nama Hab", placeholder="Masukkan nama hab")

    # Dropdown to select Depot from Column A of Excel
    if not hub_df.empty:
        depot_list = sorted(hub_df.iloc[:, 0].dropna().unique().tolist())
        selected_depot = st.selectbox("3. Pilihan Depoh (Dari Excel)", options=depot_list, index=None)
    else:
        selected_depot = None
        st.warning("Excel file 'hub name.xlsx' is empty or missing.")

with col2:
    tarikh = st.date_input("4. Tarikh Penilaian", value=datetime.now(KL_TZ))
    masa = st.time_input("5. Masa Penilaian", value=datetime.now(KL_TZ).time())
    
    # Auto-fetch Routes from Column B based on Selected Depot
    routes_auto = ""
    if selected_depot:
        # Get value from second column (index 1) where first column matches
        routes_auto = hub_df[hub_df.iloc[:, 0] == selected_depot].iloc[0, 1]
    
    st.text_area("6. Laluan Bas (Auto dari Excel)", value=str(routes_auto), disabled=True, height=100)

st.divider()

# --- Question Flow ---
maklumat_asas = st.radio("7. Maklumat Asas Hub", ["Hub Utama", "Hub sokongan", "Hentian sahaja"], horizontal=True)
status_apo = st.radio("8. Status Enjin Hidup (APO SEMASA)", ["Dibenarkan", "Tidak Dibenarkan", "Bersyarat", "Lain - lain"], horizontal=True)

st.header("🏗️ PENILAIAN KEMUDAHAN HUB")
col3, col4 = st.columns(2)
with col3:
    fungsi_hub = st.multiselect("9. Fungsi Hub", ["Pertukaran shif Kapten Bas", "Rehat pemandu", "Menunggu trip seterusnya", "Parkir sementara dan rehat", "Transit penumpang", "Lain - lain"])
    catatan = st.text_area("10. Catatan", placeholder="Enter your answer")
    tandas = st.radio("11. TANDAS - Kemudahan Hab", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], horizontal=True)
    surau = st.radio("12. SURAU - Kemudahan Hab", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], horizontal=True)
    ruang_rehat = st.radio("13. Ruang Rehat Pemandu - Kemudahan Hub", ["Hab", "Ada Kiosk / Bilik Rehat (milik RapidKL)", "Tiada"], horizontal=True)
    kiosk = st.radio("14. Kiosk - Kemudahan Hub", ["Masih ada dan selesa digunakan", "Ada tetapi kurang selesa digunakan", "Tiada"], horizontal=True)
    bumbung = st.radio("15. Kawasan Berbumbung - Kemudahan Hub", ["Ada", "Tiada", "Khemah"], horizontal=True)

with col4:
    cahaya = st.radio("16. Cahaya Lampu - Kemudahan Hub", ["Mencukupi", "Kurang mencukupi", "Tidak mencukupi"], horizontal=True)
    parkir = st.radio("17. Susun Atur / Kawasan Parkir - Kemudahan Hub", ["Kawasan luas", "Kawasan terhad"], horizontal=True)
    akses = st.radio("18. Akses Keluar & Masuk - Kemudahan Hub", ["Baik", "Kurang baik", "Tidak baik"], horizontal=True)
    kesesakan = st.radio("19. Risiko Kesesakan - Kemudahan Hub", ["Rendah", "Sederhana", "Tinggi"], horizontal=True)
    trafik = st.radio("20. Keselamatan Trafik - Kemudahan Hub", ["Selamat", "Kurang Selamat", "Tidak Selamat"], horizontal=True)
    lain_lain = st.text_input("21. Lain - lain - Kemudahan Hub")
    cadangan = st.radio("22. Cadangan Tindakan dari pihak pemerhati", ["Masukkan dalam APO", "Tidak masukkan dalam APO"], horizontal=True)

st.subheader("📸 Media Upload")
up_file = st.file_uploader("Upload Media", type=["jpg", "png", "jpeg", "mp4"])
if up_file:
    if "video" in (mimetypes.guess_type(up_file.name)[0] or ""): st.session_state.videos.append(up_file)
    else: st.session_state.photos.append(up_file)

if st.button("Submit Profiling Report"):
    if not nama_hab or nama_penilai == "Staff Not Found" or not selected_depot:
        st.error("Sila lengkapkan ID Staf, Nama Hab, dan Pilihan Depoh.")
    else:
        with st.spinner("Submitting..."):
            try:
                media_urls = []
                for idx, p in enumerate(st.session_state.photos):
                    url = gdrive_upload_file(add_watermark(p.getvalue(), nama_hab), f"HUB_{nama_hab}_{idx}.jpg", "image/jpeg", FOLDER_ID)
                    media_urls.append(url)
                
                row = [datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M:%S"), nama_penilai, selected_depot, str(tarikh), str(masa), nama_hab, routes_auto, maklumat_asas, status_apo, ", ".join(fungsi_hub), catatan, tandas, surau, ruang_rehat, kiosk, bumbung, cahaya, parkir, akses, kesesakan, trafik, lain_lain, cadangan, "; ".join(media_urls)]
                header = ["Timestamp", "Penilai", "Depot", "Tarikh", "Masa", "Nama Hab", "Laluan", "Asas", "Status APO", "Fungsi", "Catatan", "Tandas", "Surau", "Rehat", "Kiosk", "Bumbung", "Cahaya", "Parkir", "Akses", "Kesesakan", "Trafik", "Lain-lain", "Cadangan", "Media"]
                
                append_row(find_or_create_gsheet("hub_profiling_responses", FOLDER_ID), row, header)
                st.success("Report Submitted!")
                st.session_state.photos = []; st.session_state.videos = []
                time.sleep(2); st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
