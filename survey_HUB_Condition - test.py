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
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --------- Configuration ---------
KL_TZ = pytz.timezone('Asia/Kuala_Lumpur')
FOLDER_ID = "1ejwc-x6Piu4jxKh03s4U52nk-YfDZZmu"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]

# --------- Page Setup ---------
st.set_page_config(page_title="Hub Profiling Survey", layout="wide")

# --------- Staff Dictionary ---------
staff_dict = {"10005475": "MOHD RIZAL BIN RAMLI", "10020779": "NUR FAEZAH BINTI HARUN", "10014181": "NORAINSYIRAH BINTI ARIFFIN", "10022768": "NORAZHA RAFFIZZI ZORKORNAINI", "10022769": "NUR HANIM HANIL", "10023845": "MUHAMMAD HAMKA BIN ROSLIM", "10002059": "MUHAMAD NIZAM BIN IBRAHIM", "10005562": "AZFAR NASRI BIN BURHAN", "10010659": "MOHD SHAFIEE BIN ABDULLAH", "10008350": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "10003214": "NIK MOHD FADIR BIN NIK MAT RAWI", "10016370": "AHMAD AZIM BIN ISA", "10022910": "NUR SHAHIDA BINTI MOHD TAMIJI ", "10023513": "MUHAMMAD SYAHMI BIN AZMEY", "10023273": "MOHD IDZHAM BIN ABU BAKAR", "10023577": "MOHAMAMAD NAIM MOHAMAD SAPRI", "10023853": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "10008842": "MIRAN NURSYAWALNI AMIR", "10015662": "MUHAMMAD HANDIF BIN HASHIM", "10011944": "NUR HAZIRAH BINTI NAWI"}

# --------- Google API Auth (Adjusted for TOML Secrets) ---------
@st.cache_resource
def get_authenticated_service():
    # Attempt to load from Streamlit Secrets
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets 'gcp_service_account' not found in Streamlit settings.")
            st.stop()
            
        # Get dictionary from st.secrets
        info = dict(st.secrets["gcp_service_account"])
        
        # Service Account authentication using dictionary info
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=SCOPES)
        
        drive_service = build("drive", "v3", credentials=creds)
        sheets_service = build("sheets", "v4", credentials=creds)
        return drive_service, sheets_service
    except Exception as e:
        st.error(f"Authentication Failed: {e}")
        st.stop()

drive_service, sheets_service = get_authenticated_service()

# --------- CSS FOR STANDARDIZED DARK GRAY TEXT ---------
st.markdown("""
    <style>
    .stApp { background-color: #F5F5F7 !important; color: #1D1D1F !important; }
    label[data-testid="stWidgetLabel"] p, div[data-testid="stMarkdownContainer"] p {
        font-size: 18px !important; font-weight: 600 !important; color: #3A3A3C !important;
    }
    div[role="radiogroup"] {
        background-color: #E3E3E8 !important; padding: 6px !important; border-radius: 14px !important;
        display: flex !important; flex-direction: row !important; margin-bottom: 28px !important; max-width: 450px; 
    }
    div[role="radiogroup"] label p { font-size: 14px !important; color: #444444 !important; font-weight: 700 !important; }
    div[role="radiogroup"] label:has(input:checked) { background-color: #FFFFFF !important; border-radius: 11px !important; }
    div.stButton > button { background-color: #007AFF !important; color: white !important; height: 60px !important; width: 100%; border-radius: 16px !important; }
    .name-container { background-color: #E8F0FE; border-radius: 10px; padding: 12px 20px; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --------- Helper Functions ---------
@st.cache_data
def load_hub_data():
    try:
        df = pd.read_excel("hub name.xlsx")
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error loading 'hub name.xlsx': {e}")
        return pd.DataFrame()

def gdrive_upload_file(file_bytes, filename, mimetype, folder_id=None):
    media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype, resumable=True)
    metadata = {"name": filename}
    if folder_id: metadata["parents"] = [folder_id]
    uploaded = drive_service.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()
    return uploaded["webViewLink"]

def find_or_create_gsheet(name, folder_id):
    query = f"'{folder_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
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
    try: font_sub = ImageFont.truetype("arialbd.ttf", int(w * 0.04))
    except: font_sub = ImageFont.load_default()
    draw.text((20, h - (h*0.08)), info_str, font=font_sub, fill="white")
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=85)
    return img_byte_arr.getvalue()

# --------- App Main Logic ---------
hub_df = load_hub_data()
if "photos" not in st.session_state: st.session_state.photos = []
if "videos" not in st.session_state: st.session_state.videos = []

st.title("Hub Profiling & Facility Survey")

# 1. Maklumat Asas
st.header("📋 Maklumat Asas")
col1, col2 = st.columns(2)

with col1:
    staff_options = sorted(list(staff_dict.keys()))
    staff_id_input = st.selectbox("1. Staff ID", options=staff_options, index=None, placeholder="Pilih No. ID")
    nama_penilai = staff_dict.get(staff_id_input, "")
    st.markdown(f'<div class="name-container"><b>Nama Penilai:</b><br>{nama_penilai if nama_penilai else "---"}</div>', unsafe_allow_html=True)

    if not hub_df.empty:
        hub_list = sorted(hub_df.iloc[:, 2].dropna().unique().tolist())
        selected_hub = st.selectbox("2. Nama Hab", options=hub_list, index=None)
    else: selected_hub = None

    depoh_val = hub_df[hub_df.iloc[:, 2] == selected_hub].iloc[0, 0] if selected_hub else ""
    st.text_input("3. Pilihan Depoh (Auto)", value=str(depoh_val), disabled=True)

with col2:
    tarikh = st.date_input("4. Tarikh Penilaian", value=datetime.now(KL_TZ))
    masa = datetime.now(KL_TZ).strftime("%I:%M %p")
    routes_val = hub_df[hub_df.iloc[:, 2] == selected_hub].iloc[0, 1] if selected_hub else ""
    st.text_area("6. Laluan Bas (Auto)", value=str(routes_val), disabled=True, height=68)

st.divider()

# --- Survey Questions ---
maklumat_asas = st.radio("7. Maklumat Asas Hub", ["Hub Utama", "Hub sokongan", "Hentian sahaja"], index=None, horizontal=True)
status_apo = st.radio("8. Status Enjin Hidup (APO SEMASA)", ["Dibenarkan", "Tidak Dibenarkan", "Bersyarat", "Lain - lain"], index=None, horizontal=True)
status_apo_catatan = st.text_input("Catatan (Jika Bersyarat/Lain)") if status_apo in ["Bersyarat", "Lain - lain"] else ""

st.header("📋 PENILAIAN KEMUDAHAN HUB")
c3, c4 = st.columns(2)
with c3:
    fungsi_hub = st.multiselect("9. Fungsi Hub", ["Pertukaran shif Kapten Bas", "Rehat pemandu", "Menunggu trip seterusnya", "Parkir sementara dan rehat", "Transit penumpang", "Lain - lain"])
    catatan = st.text_area("10. Catatan Am")
    tandas = st.radio("11. TANDAS", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], index=None, horizontal=True)
    surau = st.radio("12. SURAU", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], index=None, horizontal=True)
    ruang_rehat = st.radio("13. Ruang Rehat Pemandu", ["Ada (Hab)", "Ada (Kiosk/Bilik Rehat)", "Tiada"], index=None, horizontal=True)
    kiosk = st.radio("14. Kiosk", ["Ada (Selesa)", "Ada (Kurang Selesa)", "Tiada"], index=None, horizontal=True)

with c4:
    bumbung = st.radio("15. Bumbung", ["Ada", "Tiada", "Khemah"], index=None, horizontal=True)
    cahaya = st.radio("16. Cahaya Lampu", ["Mencukupi", "Kurang mencukupi", "Tidak mencukupi"], index=None, horizontal=True)
    parkir = st.radio("17. Parkir", ["Kawasan luas", "Kawasan terhad"], index=None, horizontal=True)
    kesesakan = st.radio("19. Risiko Kesesakan", ["Rendah", "Sederhana", "Tinggi"], index=None, horizontal=True)
    kategori_hub = st.radio("23. Kategori Hub (Cadangan)", ["Kategori A", "Kategori B", "Kategori C", "Kategori D"], index=None)
    justifikasi = st.text_area("24. Justifikasi")

# --- Media ---
st.subheader("📸 Media Upload (Min 2, Max 5)")
cam_photo = st.camera_input("Ambil Gambar")
if cam_photo and cam_photo not in st.session_state.photos:
    st.session_state.photos.append(cam_photo)
    st.rerun()

up_files = st.file_uploader("Upload Gambar/Video", type=["jpg", "png", "jpeg", "mp4"], accept_multiple_files=True)
if up_files:
    for f in up_files:
        if (len(st.session_state.photos) + len(st.session_state.videos)) < 5:
            if "video" in (mimetypes.guess_type(f.name)[0] or ""):
                if f not in st.session_state.videos: st.session_state.videos.append(f)
            else:
                if f not in st.session_state.photos: st.session_state.photos.append(f)

if st.button("Clear Media"):
    st.session_state.photos = []; st.session_state.videos = []; st.rerun()

# --- Submit ---
if st.button("Submit Profiling Report"):
    total_m = len(st.session_state.photos) + len(st.session_state.videos)
    if not selected_hub or not staff_id_input:
        st.error("Lengkapkan Staff ID dan Nama Hab!")
    elif total_m < 2:
        st.error("Upload sekurang-kurangnya 2 media!")
    else:
        with st.spinner("Uploading to Google Drive..."):
            try:
                urls = []
                for idx, p in enumerate(st.session_state.photos):
                    urls.append(gdrive_upload_file(add_watermark(p.getvalue(), selected_hub), f"IMG_{selected_hub}_{idx}.jpg", "image/jpeg", FOLDER_ID))
                for idx, v in enumerate(st.session_state.videos):
                    urls.append(gdrive_upload_file(v.getvalue(), f"VID_{selected_hub}_{idx}.mp4", "video/mp4", FOLDER_ID))

                row = [datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M:%S"), nama_penilai, depoh_val, str(tarikh), masa, selected_hub, routes_val, maklumat_asas, status_apo, ", ".join(fungsi_hub), catatan, tandas, surau, ruang_rehat, kiosk, bumbung, cahaya, parkir, kesesakan, kategori_hub, justifikasi, "; ".join(urls)]
                header = ["Timestamp", "Penilai", "Depot", "Tarikh", "Masa", "Hab", "Laluan", "Asas", "Status APO", "Fungsi", "Catatan", "Tandas", "Surau", "Rehat", "Kiosk", "Bumbung", "Cahaya", "Parkir", "Ksesakan", "Kategori", "Justifikasi", "Links"]
                
                append_row(find_or_create_gsheet("hub_profiling_responses", FOLDER_ID), row, header)
                st.success("Berjaya Dihantar!")
                st.session_state.photos = []; st.session_state.videos = []
                time.sleep(2); st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
