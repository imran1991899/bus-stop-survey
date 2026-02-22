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

# --------- CSS FOR DARK GRAY TEXT & UNIFORM SHAPE ---------
st.markdown("""
    <style>
    .stApp { background-color: #F5F5F7 !important; color: #1D1D1F !important; font-family: -apple-system, sans-serif !important; }
    
    /* Label Styling */
    label[data-testid="stWidgetLabel"] p { font-size: 16px !important; font-weight: 600 !important; color: #1D1D1F !important; margin-bottom: 8px !important; }
    
    /* Radio Group Container */
    div[role="radiogroup"] { 
        background-color: #E3E3E8 !important; 
        padding: 6px !important; 
        border-radius: 12px !important; 
        display: flex !important; 
        flex-direction: row !important; 
        gap: 10px !important;
        width: fit-content !important;
    }
    
    /* Individual Radio Option - Uniform & Standard */
    div[role="radiogroup"] label {
        background-color: transparent !important;
        border-radius: 8px !important;
        padding: 8px 25px !important; 
        min-width: 120px !important;   
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        border: none !important;
    }

    /* Text inside the options - DARK GRAY */
    div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
        color: #333333 !important; 
        font-weight: 500 !important;
    }
    
    /* Selected State Button Shape */
    div[role="radiogroup"] label:has(input:checked) { 
        background-color: #FFFFFF !important; 
        box-shadow: 0px 2px 5px rgba(0,0,0,0.1) !important; 
    }

    div.stButton > button { background-color: #007AFF !important; color: white !important; height: 55px !important; border-radius: 12px !important; font-weight: 700 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- Google API Setup ---
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
    try:
        font_sub = ImageFont.truetype("arialbd.ttf", int(w * 0.04))
    except:
        font_sub = ImageFont.load_default()
    draw.text((20, h - 50), info_str, font=font_sub, fill="white")
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=90)
    return img_byte_arr.getvalue()

if "photos" not in st.session_state: st.session_state.photos = []
if "videos" not in st.session_state: st.session_state.videos = []

# --------- Main App UI ---------
st.title("Hub Profiling & Facility Survey")

# 1. Maklumat Asas
st.header("📋 Maklumat Asas")
col1, col2 = st.columns(2)

with col1:
    # Function of ID: Search name when number is put in
    staff_id_input = st.text_input("1. Staff ID", placeholder="Masukkan No. ID")
    nama_penilai = staff_dict.get(staff_id_input, "")
    
    st.text_input("Nama Penilai", value=nama_penilai, disabled=True, placeholder="Nama akan dipaparkan secara automatik")

    if not hub_df.empty and hub_df.shape[1] >= 3:
        hub_list = sorted(hub_df.iloc[:, 2].dropna().unique().tolist())
        selected_hub = st.selectbox("2. Nama Hab", options=hub_list, index=None, placeholder="Pilih Nama Hab")
    else:
        selected_hub = None
        st.error("Excel format error. Ensure 3 columns (Depot, Routes, Hub Name).")

    depoh_val = ""
    if selected_hub:
        depoh_val = hub_df[hub_df.iloc[:, 2] == selected_hub].iloc[0, 0]
    st.text_input("3. Pilihan Depoh (Auto)", value=str(depoh_val), disabled=True)

with col2:
    tarikh = st.date_input("4. Tarikh Penilaian", value=datetime.now(KL_TZ))
    masa = st.time_input("5. Masa Penilaian", value=datetime.now(KL_TZ).time())
    
    routes_val = ""
    if selected_hub:
        routes_val = hub_df[hub_df.iloc[:, 2] == selected_hub].iloc[0, 1]
    st.text_area("6. Laluan Bas (Auto)", value=str(routes_val), disabled=True, height=100)

st.divider()

# --- Survey Logic ---
maklumat_asas = st.radio("7. Maklumat Asas Hub", ["Hub Utama", "Hub sokongan", "Hentian sahaja"], horizontal=True)
status_apo = st.radio("8. Status Enjin Hidup (APO SEMASA)", ["Dibenarkan", "Tidak Dibenarkan", "Bersyarat", "Lain - lain"], horizontal=True)

st.header("🏗️ PENILAIAN KEMUDAHAN HUB")
col3, col4 = st.columns(2)
with col3:
    fungsi_hub = st.multiselect("9. Fungsi Hub", ["Pertukaran shif Kapten Bas", "Rehat pemandu", "Menunggu trip seterusnya", "Parkir sementara dan rehat", "Transit penumpang", "Lain - lain"])
    catatan = st.text_area("10. Catatan", placeholder="Enter your answer")
    tandas = st.radio("11. TANDAS - Kemudahan Hab", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], horizontal=True)
    surau = st.radio("12. SURAU - Kemudahan Hab", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], horizontal=True)
    ruang_rehat = st.radio("13. Ruang Rehat Pemandu - Kemudahan Hub", ["Hab", "Ada Kiosk / Bilik Rehat (milik RapidKL)", "Tiada (BC rehat dalam bas / rehat di luar bas)"], horizontal=True)
    kiosk = st.radio("14. Kiosk - Kemudahan Hub", ["Masih ada dan selesa digunakan", "Ada tetapi kurang selesa digunakan", "Tiada"], horizontal=True)
    bumbung = st.radio("15. Kawasan Berbumbung - Kemudahan Hub", ["Ada", "Tiada", "Khemah"], horizontal=True)

with col4:
    cahaya = st.radio("16. Cahaya Lampu - Kemudahan Hub", ["Mencukupi", "Kurang mencukupi", "Tidak mencukupi"], horizontal=True)
    parkir = st.radio("17. Susun Atur / Kawasan Parkir - Kemudahan Hub", ["Kawasan luas", "Kawasan terhad"], horizontal=True)
    akses = st.radio("18. Akses Keluar & Masuk - Kemudahan Hub", ["Baik", "Kurang baik", "Tidak baik"], horizontal=True)
    kesesakan = st.radio("19. Risiko Kesesakan - Kemudahan Hub", ["Rendah", "Sederhana", "Tinggi"], horizontal=True)
    trafik = st.radio("20. Keselamatan Trafik - Kemudahan Hub", ["Selamat", "Kurang Selamat", "Tidak Selamat"], horizontal=True)
    lain_lain = st.text_input("21. Lain - lain - Kemudahan Hub")
    cadangan = st.radio("22. Cadangan Tindakan dari pihak pemerhati", ["Masukkan dalam APO dan dibenarkan enjin hidup", "Tidak masukkan dalam APO dan tidak dibenarkan enjin hidup"], horizontal=True)

st.subheader("📸 Media Upload")
up_file = st.file_uploader("Capture or Upload Hub Media", type=["jpg", "png", "jpeg", "mp4"])
if up_file:
    mime = mimetypes.guess_type(up_file.name)[0] or ""
    if "video" in mime: st.session_state.videos.append(up_file)
    else: st.session_state.photos.append(up_file)

if st.button("Submit Profiling Report"):
    if not selected_hub or not nama_penilai:
        st.error("Sila masukkan Staff ID yang sah dan pilih Nama Hab.")
    else:
        with st.spinner("Submitting Report..."):
            try:
                media_urls = []
                for idx, p in enumerate(st.session_state.photos):
                    url = gdrive_upload_file(add_watermark(p.getvalue(), selected_hub), f"HUB_{selected_hub}_{idx}.jpg", "image/jpeg", FOLDER_ID)
                    media_urls.append(url)
                
                row = [datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M:%S"), nama_penilai, depoh_val, str(tarikh), str(masa), selected_hub, routes_val, maklumat_asas, status_apo, ", ".join(fungsi_hub), catatan, tandas, surau, ruang_rehat, kiosk, bumbung, cahaya, parkir, akses, kesesakan, trafik, lain_lain, cadangan, "; ".join(media_urls)]
                header = ["Timestamp", "Penilai", "Depot", "Tarikh", "Masa", "Hab", "Laluan", "Asas", "Status APO", "Fungsi", "Catatan", "Tandas", "Surau", "Rehat", "Kiosk", "Bumbung", "Cahaya", "Parkir", "Akses", "Kesesakan", "Trafik", "Lain-lain", "Cadangan", "Links"]
                
                append_row(find_or_create_gsheet("hub_profiling_responses", FOLDER_ID), row, header)
                st.success("Report Submitted Successfully!")
                st.session_state.photos = []; st.session_state.videos = []
                time.sleep(2); st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
