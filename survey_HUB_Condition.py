import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import mimetypes
import time
import os
import pickle
import pytz 
from PIL import Image, ImageDraw, ImageFont

# --- Google API Imports ---
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

# --------- Timezone Setup ---------
KL_TZ = pytz.timezone('Asia/Kuala_Lumpur')

# --------- Page Setup ---------
st.set_page_config(page_title="Hub Profiling Survey", layout="wide")

# --------- Configuration ---------
FOLDER_ID = "1JKwlnKUVO3U74wTRu9U46ARF49dcglp7"
CLIENT_SECRETS_FILE = "client_secrets3.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]
REDIRECT_URI = "https://bus-stop-survey-fwaavwf7uxvxrfbjeqv9nq.streamlit.app/"

# --------- Staff Dictionary ---------
staff_dict = {"10005475": "MOHD RIZAL BIN RAMLI", "10020779": "NUR FAEZAH BINTI HARUN", "10014181": "NORAINSYIRAH BINTI ARIFFIN", "10022768": "NORAZHA RAFFIZZI ZORKORNAINI", "10022769": "NUR HANIM HANIL", "10023845": "MUHAMMAD HAMKA BIN ROSLIM", "10002059": "MUHAMAD NIZAM BIN IBRAHIM", "10005562": "AZFAR NASRI BIN BURHAN", "10010659": "MOHD SHAFIEE BIN ABDULLAH", "10008350": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "10003214": "NIK MOHD FADIR BIN NIK MAT RAWI", "10016370": "AHMAD AZIM BIN ISA", "10022910": "NUR SHAHIDA BINTI MOHD TAMIJI ", "10023513": "MUHAMMAD SYAHMI BIN AZMEY", "10023273": "MOHD IDZHAM BIN ABU BAKAR", "10023577": "MOHAMAD NAIM MOHAMAD SAPRI", "10023853": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "10008842": "MIRAN NURSYAWALNI AMIR", "10015662": "MUHAMMAD HANDIF BIN HASHIM", "10011944": "NUR HAZIRAH BINTI NAWI"}

# --------- Data Loading ---------
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

# --------- Auth Functions ---------
def save_credentials(creds):
    with open("token.pickle", "wb") as t:
        pickle.dump(creds, t)

def load_credentials():
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as t:
            return pickle.load(t)
    return None

def get_authenticated_service():
    if "creds" not in st.session_state:
        st.session_state.creds = load_credentials()
    
    creds = st.session_state.creds

    # Refresh token if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            st.session_state.creds = creds
        except:
            creds = None

    if creds and creds.valid:
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)

    # OAuth Flow
    if "flow" not in st.session_state:
        st.session_state.flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
        )

    if "code" in st.query_params:
        try:
            st.session_state.flow.fetch_token(code=st.query_params["code"])
            creds = st.session_state.flow.credentials
            save_credentials(creds)
            st.session_state.creds = creds
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Auth Error: {e}")
            del st.session_state.flow
            st.stop()
    else:
        auth_url, _ = st.session_state.flow.authorization_url(prompt="consent", access_type="offline")
        st.info("Sila log masuk untuk meneruskan.")
        st.link_button("Login with Google", auth_url)
        st.stop()

# Initialize API Services
drive_service, sheets_service = get_authenticated_service()

# --------- CSS ---------
st.markdown("""
    <style>
    .stApp { background-color: #F5F5F7 !important; color: #1D1D1F !important; }
    label[data-testid="stWidgetLabel"] p { font-size: 18px !important; font-weight: 600 !important; color: #3A3A3C !important; }
    .name-container { background-color: #E8F0FE; border-radius: 10px; padding: 12px 20px; margin-bottom: 20px; }
    .name-text { color: #1A73E8; font-weight: 600; font-size: 18px; }
    div.stButton > button { background-color: #007AFF !important; color: white !important; height: 60px !important; width: 100%; border-radius: 12px !important; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --------- Helper Functions ---------
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
        font_sub = ImageFont.load_default() # Replace with path to .ttf if needed
    except:
        font_sub = ImageFont.load_default()
    draw.text((20, h - 50), info_str, font=font_sub, fill="white")
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=90)
    return img_byte_arr.getvalue()

# --------- Session State ---------
if "photos" not in st.session_state: st.session_state.photos = []
if "videos" not in st.session_state: st.session_state.videos = []

# --------- Main App UI ---------
st.title("Hub Profiling & Facility Survey")

st.header("📋 Maklumat Asas")
col1, col2 = st.columns(2)

with col1:
    staff_options = sorted(list(staff_dict.keys()))
    staff_id_input = st.selectbox("1. Staff ID", options=staff_options, index=None, placeholder="Pilih atau Cari No. ID")
    nama_penilai = staff_dict.get(staff_id_input, "") if staff_id_input else ""
    st.markdown('Nama Penilai')
    if nama_penilai:
        st.markdown(f'<div class="name-container"><span class="name-text">Nama: {nama_penilai}</span></div>', unsafe_allow_html=True)
    
    if not hub_df.empty:
        hub_list = sorted(hub_df.iloc[:, 2].dropna().unique().tolist())
        selected_hub = st.selectbox("2. Nama Hab", options=hub_list, index=None, placeholder="Pilih Nama Hab")
    else:
        selected_hub = None

    depoh_val = hub_df[hub_df.iloc[:, 2] == selected_hub].iloc[0, 0] if selected_hub else ""
    st.text_input("3. Pilihan Depoh (Auto)", value=str(depoh_val), disabled=True)

with col2:
    tarikh = st.date_input("4. Tarikh Penilaian", value=datetime.now(KL_TZ))
    masa = datetime.now(KL_TZ).strftime("%I:%M %p")
    routes_val = hub_df[hub_df.iloc[:, 2] == selected_hub].iloc[0, 1] if selected_hub else ""
    st.text_area("6. Laluan Bas (Auto)", value=str(routes_val), disabled=True, height=100)

st.divider()

maklumat_asas = st.radio("7. Maklumat Asas Hub", ["Hub Utama", "Hub sokongan", "Hentian sahaja"], index=None, horizontal=True)
status_apo = st.radio("8. Status Enjin Hidup (APO SEMASA)", ["Dibenarkan", "Tidak Dibenarkan", "Bersyarat", "Lain - lain"], index=None, horizontal=True)
status_apo_catatan = st.text_input("Catatan APO", placeholder="Masukkan ulasan jika bersyarat/lain-lain") if status_apo in ["Bersyarat", "Lain - lain"] else ""

st.header("📋 PENILAIAN KEMUDAHAN HUB")
col3, col4 = st.columns(2)
with col3:
    fungsi_hub = st.multiselect("9. Fungsi Hub", ["Pertukaran shif Kapten Bas", "Rehat pemandu", "Menunggu trip seterusnya", "Parkir sementara dan rehat", "Transit penumpang", "Lain - lain"], default=None)
    catatan = st.text_area("10. Catatan", placeholder="Enter your answer")
    tandas = st.radio("11. TANDAS", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], index=None, horizontal=True)
    surau = st.radio("12. SURAU", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], index=None, horizontal=True)
    ruang_rehat = st.radio("13. Ruang Rehat Pemandu", ["Hab", "Ada Kiosk / Bilik Rehat (milik RapidKL)", "Tiada"], index=None, horizontal=True)

with col4:
    cahaya = st.radio("16. Cahaya Lampu", ["Mencukupi", "Kurang mencukupi", "Tidak mencukupi"], index=None, horizontal=True)
    parkir = st.radio("17. Susun Atur Parkir", ["Kawasan luas", "Kawasan terhad"], index=None, horizontal=True)
    kesesakan = st.radio("19. Risiko Kesesakan", ["Rendah", "Sederhana", "Tinggi"], index=None, horizontal=True)
    kategori_hub = st.radio("23. Kategori Hub (cadangan)", [
        "Kategori A : Ada hub dan ada kemudahan",
        "Kategori B : Ada hub and kemudahan tidak cukup",
        "Kategori D : Tiada hub, hentian sahaja and ada kemudahan",
        "Kategori C : Tiada hub, hentian sahaja and kemudahan tidak cukup"
    ], index=None)
    justifikasi = st.text_area("24. Justifikasi")

st.subheader("📸 Media Upload (Min 2, Max 5)")
total_media = len(st.session_state.photos) + len(st.session_state.videos)

if total_media < 5:
    cam_photo = st.camera_input("Take a photo")
    if cam_photo:
        st.session_state.photos.append(cam_photo)
        st.rerun()

    up_files = st.file_uploader("Upload Media", type=["jpg", "png", "jpeg", "mp4"], accept_multiple_files=True)
    if up_files:
        for f in up_files:
            if "video" in f.type:
                st.session_state.videos.append(f)
            else:
                st.session_state.photos.append(f)

if st.button("Submit Profiling Report"):
    if not selected_hub or not nama_penilai or total_media < 2:
        st.error("Sila lengkapkan maklumat dan muat naik sekurang-kurangnya 2 media.")
    else:
        with st.spinner("Submitting to Google..."):
            try:
                media_urls = []
                for idx, p in enumerate(st.session_state.photos):
                    url = gdrive_upload_file(add_watermark(p.getvalue(), selected_hub), f"HUB_{selected_hub}_{idx}.jpg", "image/jpeg", FOLDER_ID)
                    media_urls.append(url)
                for idx, v in enumerate(st.session_state.videos):
                    url = gdrive_upload_file(v.getvalue(), f"HUB_VIDEO_{selected_hub}_{idx}.mp4", "video/mp4", FOLDER_ID)
                    media_urls.append(url)

                row = [datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M:%S"), nama_penilai, depoh_val, str(tarikh), str(masa), selected_hub, routes_val, maklumat_asas, status_apo, ", ".join(fungsi_hub), catatan, tandas, surau, ruang_rehat, cahaya, parkir, kesesakan, kategori_hub, justifikasi, "; ".join(media_urls)]
                header = ["Timestamp", "Penilai", "Depot", "Tarikh", "Masa", "Hab", "Laluan", "Asas", "Status APO", "Fungsi", "Catatan", "Tandas", "Surau", "Rehat", "Cahaya", "Parkir", "Ksesakan", "Kategori Hub", "Justifikasi", "Links"]
                
                sheet_id = find_or_create_gsheet("hub_profiling_responses", FOLDER_ID)
                append_row(sheet_id, row, header)
                
                st.success("Report Submitted Successfully!")
                st.session_state.photos = []; st.session_state.videos = []
                time.sleep(2); st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
