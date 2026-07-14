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
    "10005475": "MOHD RIZAL BIN RAMLI", 
    "10020779": "NUR FAEZAH BINTI HARUN", 
    "10014181": "NORAINSYIRAH BINTI ARIFFIN", 
    "10022768": "NORAZHA RAFFIZZI ZORKORNAINI", 
    "10022769": "NUR HANIM HANIL", 
    "10023845": "MUHAMMAD HAMKA BIN ROSLIM", 
    "10002059": "MUHAMAD NIZAM BIN IBRAHIM", 
    "10005562": "AZFAR NASRI BIN BURHAN", 
    "10010659": "MOHD SHAFIEE BIN ABDULLAH", 
    "10008350": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", 
    "10003214": "NIK MOHD FADIR BIN NIK MAT RAWI", 
    "10016370": "AHMAD AZIM BIN ISA", 
    "10022910": "NUR SHAHIDA BINTI MOHD TAMIJI ", 
    "10023513": "MUHAMMAD SYAHMI BIN AZMEY", 
    "10023273": "MOHD IDZHAM BIN ABU BAKAR", 
    "10023577": "MOHAMAD NAIM MOHAMAD SAPRI", 
    "10023853": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", 
    "10008842": "MIRAN NURSYAWALNI AMIR", 
    "10015662": "MUHAMMAD HANDIF BIN HASHIM", 
    "10011944": "NUR HAZIRAH BINTI NAWI"
}

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

# --------- CSS FOR STANDARDIZED DARK GRAY TEXT ---------
st.markdown("""
    <style>
    .stApp {
        background-color: #F5F5F7 !important;
        color: #1D1D1F !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }

    /* Target ALL labels, p-tags inside widgets, and markdown headers to ensure dark gray uniformity */
    label[data-testid="stWidgetLabel"] p, 
    .st-emotion-cache-16296vi p, 
    .st-emotion-cache-ue6h4q p,
    div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stWidgetLabel"],
    .st-emotion-cache-18357p9 p,
    .st-emotion-cache-1p05t8e p {
        font-size: 18px !important;
        font-weight: 600 !important;
        color: #3A3A3C !important;
        opacity: 1 !important;
        -webkit-text-fill-color: #3A3A3C !important;
    }

    /* Specifically target radio button headers which often default to white/light gray */
    div[role="radiogroup"] > label > div > p {
        color: #3A3A3C !important;
    }

    /* Force specific widget label containers to obey the color */
    .stSelectbox label, .stTextInput label, .stTextArea label, 
    .stDateInput label, .stTimeInput label, .stMultiSelect label, .stRadio label {
        color: #3A3A3C !important;
    }

    /* Styled Container for Nama Penilai */
    .name-container {
        background-color: #E8F0FE;
        border-radius: 10px;
        padding: 12px 20px;
        margin-top: 5px;
        margin-bottom: 20px;
    }
    .name-text {
        color: #1A73E8;
        font-weight: 600;
        font-size: 18px;
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
        max-width: 450px; 
        min-height: 58px !important; 
    }

    [data-testid="stWidgetSelectionVisualizer"] {
        display: none !important;
    }

    div[role="radiogroup"] label {
        background-color: transparent !important;
        border: none !important;
        padding: 10px 0px !important; 
        border-radius: 11px !important;
        transition: all 0.2s ease-in-out !important;
        flex: 1 !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        margin: 0 !important;
    }

    /* Text INSIDE the radio buttons (Options) */
    div[role="radiogroup"] label p {
        font-size: 14px !important; 
        margin: 0 !important;
        padding: 0 10px !important;
        white-space: normal !important; 
        color: #444444 !important; 
        font-weight: 700 !important; 
        text-align: center;
    }

    div[role="radiogroup"] label:has(input:checked) {
        background-color: #FFFFFF !important;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.15) !important;
    }

    /* Button Styling */
    div.stButton > button {
        background-color: #007AFF !important;
        color: white !important;
        border: none !important;
        height: 80px !important;
        font-weight: 600 !important;
        border-radius: 16px !important;
        font-size: 18px !important;
        padding: 0 40px !important;
        width: 100%;
    }

    /* Camera Input Styling */
    [data-testid="stCameraInput"] {
        border: 2px dashed #007AFF;
        border-radius: 20px; 
        padding: 10px;
    }
    
    [data-testid="stCameraInput"] video {
        border-radius: 12px;
        object-fit: cover;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Google API Setup ---
FOLDER_ID = "1JKwlnKUVO3U74wTRu9U46ARF49dcglp7"
CLIENT_SECRETS_FILE = "client_secrets3.json"
REDIRECT_URI = "https://bus-stop-survey-fwaavwf7uxvxrfbjeqv9nq.streamlit.app/"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]

def save_credentials(creds):
    with open("token.pickle", "wb") as t: 
        pickle.dump(creds, t)

def load_credentials():
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as t: 
            return pickle.load(t)
    return None

def get_authenticated_service():
    creds = load_credentials()
    
    # 1. Valid credentials exist
    if creds and creds.valid:
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    
    # 2. Expired but refreshable
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
        except Exception:
            pass
            
    # 3. Handle OAuth Handshake
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    query_params = st.query_params

    if "code" in query_params:
        # Check for the verifier file saved before redirect
        if os.path.exists("verifier.tmp"):
            with open("verifier.tmp", "r") as f:
                flow.code_verifier = f.read()
            try:
                # Reconstruct response URL safely
                full_url = REDIRECT_URI + "?" + urlencode(query_params)
                flow.fetch_token(authorization_response=full_url)
                save_credentials(flow.credentials)
                
                # Cleanup verifier temp file
                if os.path.exists("verifier.tmp"):
                    os.remove("verifier.tmp")
                
                st.query_params.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Handshake failed: {e}")
                st.stop()
        else:
            st.warning("Session verifier lost. Restarting login...")
            time.sleep(2)
            st.query_params.clear()
            st.rerun()
    else:
        # Save verifier to disk first, then build the Auth URL
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline", include_granted_scopes="true")
        with open("verifier.tmp", "w") as f:
            f.write(flow.code_verifier)
            
        st.markdown(f"### Authentication Required\n[🔴 Click Here to Login with Google]({auth_url})")
        st.stop()

# Initialize Google Authenticated APIs
drive_service, sheets_service = get_authenticated_service()

def gdrive_upload_file(file_bytes, filename, mimetype, folder_id=None):
    media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype)
    metadata = {"name": filename}
    if folder_id: 
        metadata["parents"] = [folder_id]
    uploaded = drive_service.files().create(
        body=metadata, 
        media_body=media, 
        fields="id, webViewLink", 
        supportsAllDrives=True
    ).execute()
    return uploaded["webViewLink"]

def find_or_create_gsheet(name, folder_id):
    query = f"'{folder_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.spreadsheet'"
    res = drive_service.files().list(q=query, fields="files(id)").execute()
    if res.get("files"): 
        return res["files"][0]["id"]
    file = drive_service.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.spreadsheet", "parents": [folder_id]}, 
        fields="id"
    ).execute()
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

if "photos" not in st.session_state: 
    st.session_state.photos = []
if "videos" not in st.session_state: 
    st.session_state.videos = []

# --------- Main App UI ---------
st.title("Hub Profiling & Facility Survey")

# 1. Maklumat Asas
st.header("📋 Maklumat Asas")
col1, col2 = st.columns(2)

with col1:
    staff_options = sorted(list(staff_dict.keys()))
    staff_id_input = st.selectbox("1. Staff ID", options=staff_options, index=None, placeholder="Pilih atau Cari No. ID")
    
    nama_penilai = staff_dict.get(staff_id_input, "") if staff_id_input else ""
    st.markdown('<p style="font-size: 18px; font-weight: 600; color: #3A3A3C; margin-bottom: 5px;">Nama Penilai</p>', unsafe_allow_html=True)
    if nama_penilai:
        st.markdown(f'<div class="name-container"><span class="name-text">Nama: {nama_penilai}</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="name-container"><span class="name-text" style="color: #999;">Nama akan dipaparkan secara automatik</span></div>', unsafe_allow_html=True)

    if not hub_df.empty and hub_df.shape[1] >= 3:
        hub_list = sorted(hub_df.iloc[:, 2].dropna().unique().tolist())
        selected_hub = st.selectbox("2. Nama Hab", options=hub_list, index=None, placeholder="Pilih Nama Hab")
    else:
        selected_hub = None
        st.error("Excel format error.")

    depoh_val = ""
    if selected_hub:
        depoh_val = hub_df[hub_df.iloc[:, 2] == selected_hub].iloc[0, 0]
    st.text_input("3. Pilihan Depoh (Auto)", value=str(depoh_val), disabled=True)

with col2:
    tarikh = st.date_input("4. Tarikh Penilaian", value=datetime.now(KL_TZ))
    
    # Hide masa from UI but define in background
    masa = datetime.now(KL_TZ).strftime("%I:%M %p")
    
    routes_val = ""
    if selected_hub:
        routes_val = hub_df[hub_df.iloc[:, 2] == selected_hub].iloc[0, 1]
    st.text_area("6. Laluan Bas (Auto)", value=str(routes_val), disabled=True, height=100)

st.divider()

# --- Survey Logic ---
maklumat_asas = st.radio("7. Maklumat Asas Hub", ["Hub Utama", "Hub sokongan", "Hentian sahaja"], index=None, horizontal=True)

# Question 8 with conditional free-text logic
status_apo = st.radio("8. Status Enjin Hidup (APO SEMASA)", ["Dibenarkan", "Tidak Dibenarkan", "Bersyarat", "Lain - lain"], index=None, horizontal=True)
status_apo_catatan = ""
if status_apo in ["Bersyarat", "Lain - lain"]:
    status_apo_catatan = st.text_input("Catatan", placeholder="Masukkan ulasan anda di sini")

st.header("📋 PENILAIAN KEMUDAHAN HUB")
col3, col4 = st.columns(2)
with col3:
    fungsi_hub = st.multiselect("9. Fungsi Hub", ["Pertukaran shif Kapten Bas", "Rehat pemandu", "Menunggu trip seterusnya", "Parkir sementara dan rehat", "Transit penumpang", "Lain - lain"], default=None)
    catatan = st.text_area("10. Catatan", placeholder="Enter your answer")
    tandas = st.radio("11. TANDAS - Kemudahan Hab", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], index=None, horizontal=True)
    surau = st.radio("12. SURAU - Kemudahan Hab", ["Ada dan milik RapidKL", "Ada tetapi bukan milik RapidKL", "Tiada"], index=None, horizontal=True)
    ruang_rehat = st.radio("13. Ruang Rehat Pemandu - Kemudahan Hub", ["Hab", "Ada Kiosk / Bilik Rehat (milik RapidKL)", "Tiada (BC rehat dalam bas / rehat di luar bas)"], index=None, horizontal=True)
    kiosk = st.radio("14. Kiosk - Kemudahan Hub", ["Masih ada dan selesa digunakan", "Ada tetapi kurang selesa digunakan", "Tiada"], index=None, horizontal=True)
    bumbung = st.radio("15. Kawasan Berbumbung - Kemudahan Hub", ["Ada", "Tiada", "Khemah"], index=None, horizontal=True)

with col4:
    cahaya = st.radio("16. Cahaya Lampu - Kemudahan Hub", ["Mencukupi", "Kurang mencukupi", "Tidak mencukupi"], index=None, horizontal=True)
    parkir = st.radio("17. Susun Atur / Kawasan Parkir - Kemudahan Hub", ["Kawasan luas", "Kawasan terhad"], index=None, horizontal=True)
    akses = st.radio("18. Akses Keluar & Masuk - Kemudahan Hub", ["Baik", "Kurang baik", "Tidak baik"], index=None, horizontal=True)
    kesesakan = st.radio("19. Risiko Kesesakan - Kemudahan Hub", ["Rendah", "Sederhana", "Tinggi"], index=None, horizontal=True)
    trafik = st.radio("20. Keselamatan Trafik - Kemudahan Hub", ["Selamat", "Kurang Selamat", "Tidak Selamat"], index=None, horizontal=True)
    lain_lain = st.text_input("21. Lain - lain - Kemudahan Hub")
    cadangan = st.radio("22. Cadangan Tindakan dari pihak pemerhati", ["Masukkan dalam APO dan dibenarkan enjin hidup", "Tidak masukkan dalam APO dan tidak dibenarkan enjin hidup"], index=None, horizontal=True)
    kategori_hub = st.radio("23. Kategori Hub (cadangan)", [
        "Kategori A : Ada hub dan ada kemudahan",
        "Kategori B : Ada hub and kemudahan tidak cukup",
        "Kategori D : Tiada hub, hentian sahaja and ada kemudahan",
        "Kategori C : Tiada hub, hentian sahaja and kemudahan tidak cukup"
    ], index=None, horizontal=False)
    
    justifikasi = st.text_area("24. Justifikasi", placeholder="Masukkan justifikasi anda di sini")

# --------- Media Upload Logic ---------
st.subheader("📸 Media Upload (Min 2, Max 5)")

# Input components for Media
cam_photo = st.camera_input("Take a photo of the Hub")
if cam_photo:
    # Append camera input photo securely if not already present
    if cam_photo not in st.session_state.photos:
        st.session_state.photos.append(cam_photo)
        st.rerun()

up_files = st.file_uploader("Upload Hub Media", type=["jpg", "png", "jpeg", "mp4"], accept_multiple_files=True)
if up_files:
    for f in up_files:
        total_media = len(st.session_state.photos) + len(st.session_state.videos)
        if total_media < 5:
            # Check mime-type to differentiate photos and videos
            mime = mimetypes.guess_type(f.name)[0]
            if mime and "video" in mime:
                if f not in st.session_state.videos:
                    st.session_state.videos.append(f)
            else:
                if f not in st.session_state.photos:
                    st.session_state.photos.append(f)
                    
# Display saved media with deletion action
if st.session_state.photos or st.session_state.videos:
    st.write("---")
    st.subheader("🖼️ Managed Uploaded Assets")
    
    # Manage Photo deletions
    for idx, p in enumerate(st.session_state.photos):
        col_img, col_act = st.columns([6, 1])
        col_img.image(p, caption=f"Photo #{idx + 1}", width=350)
        if col_act.button(f"🗑️ Delete Photo {idx + 1}", key=f"del_photo_{idx}"):
            st.session_state.photos.pop(idx)
            st.rerun()
            
    # Manage Video deletions
    for idx, v in enumerate(st.session_state.videos):
        col_vid, col_act = st.columns([6, 1])
        col_vid.video(v, format="video/mp4")
        if col_act.button(f"🗑️ Delete Video {idx + 1}", key=f"del_video_{idx}"):
            st.session_state.videos.pop(idx)
            st.rerun()

# --------- Submission Form Block ---------
st.write("---")
with st.form(key="final_submission_form"):
    submit_button = st.form_submit_button("✅ Submit Hub Survey")
    if submit_button:
        total_media_count = len(st.session_state.photos) + len(st.session_state.videos)
        
        # Form Validation Guardrails
        if not staff_id_input:
            st.warning("❗ Sila pilih Staff ID anda.")
        elif not selected_hub:
            st.warning("❗ Sila pilih Nama Hab.")
        elif not maklumat_asas:
            st.warning("❗ Sila jawab soalan 7 (Maklumat Asas Hub).")
        elif not status_apo:
            st.warning("❗ Sila jawab soalan 8 (Status Enjin Hidup).")
        elif total_media_count < 2:
            st.warning(f"❗ Sila upload sekurang-kurangnya 2 media assets (Anda sekarang mempunyai: {total_media_count}).")
        elif total_media_count > 5:
            st.warning(f"❗ Had maksimum media ialah 5 assets (Anda sekarang mempunyai: {total_media_count}).")
        else:
            try:
                # Setup custom progress indicator
                st.markdown('<div class="custom-spinner">Processing and uploading data... Please do not close the window.</div>', unsafe_allow_html=True)
                
                timestamp = datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M:%S")
                clean_hub_name = re.sub(r'[^a-zA-Z0-9_\s-]', '', selected_hub).strip().replace(" ", "_")
                
                media_links = []
                
                # Process and Watermark Photos
                for idx, img in enumerate(st.session_state.photos):
                    raw_bytes = img.getvalue() if hasattr(img, "getvalue") else img.read()
                    processed_bytes = add_watermark(raw_bytes, selected_hub)
                    filename = f"{timestamp.replace(':', '-')}_{clean_hub_name}_photo{idx+1}.jpg"
                    link = gdrive_upload_file(processed_bytes, filename, "image/jpeg", FOLDER_ID)
                    media_links.append(link)
                
                # Process Videos (no watermark is applied to raw video files)
                for idx, vid in enumerate(st.session_state.videos):
                    raw_bytes = vid.getvalue() if hasattr(vid, "getvalue") else vid.read()
                    filename = f"{timestamp.replace(':', '-')}_{clean_hub_name}_video{idx+1}.mp4"
                    link = gdrive_upload_file(raw_bytes, filename, "video/mp4", FOLDER_ID)
                    media_links.append(link)

                # Prepare payload
                fungsi_hub_str = "; ".join(fungsi_hub) if fungsi_hub else ""
                survey_row = [
                    timestamp,
                    staff_id_input,
                    nama_penilai,
                    selected_hub,
                    str(depoh_val),
                    tarikh.strftime("%Y-%m-%d"),
                    masa,
                    str(routes_val),
                    maklumat_asas,
                    status_apo,
                    status_apo_catatan,
                    fungsi_hub_str,
                    catatan,
                    tandas,
                    surau,
                    ruang_rehat,
                    kiosk,
                    bumbung,
                    cahaya,
                    parkir,
                    akses,
                    kesesakan,
                    trafik,
                    lain_lain,
                    cadangan,
                    kategori_hub,
                    justifikasi,
                    "; ".join(media_links)
                ]
                
                survey_headers = [
                    "Timestamp", "Staff ID", "Nama Penilai", "Nama Hub", "Depoh", 
                    "Tarikh Penilaian", "Masa", "Laluan Bas", "Maklumat Asas Hub", 
                    "Status APO", "Catatan Status APO", "Fungsi Hub", "Catatan", 
                    "Tandas", "Surau", "Ruang Rehat", "Kiosk", "Kawasan Berbumbung", 
                    "Cahaya Lampu", "Kawasan Parkir", "Akses Keluar Masuk", 
                    "Risiko Kesesakan", "Keselamatan Trafik", "Lain-lain", 
                    "Cadangan Tindakan", "Kategori Hub", "Justifikasi", "Media Uploads"
                ]

                # Find or Create target Spreadsheet & write data
                gsheet_id = find_or_create_gsheet("survey_responses", FOLDER_ID)
                append_row(gsheet_id, survey_row, survey_headers)
                
                # Complete the flow successfully
                st.success("🎉 Borang Hub Profiling berjaya dihantar!")
                st.session_state.photos = []
                st.session_state.videos = []
                time.sleep(2.5)
                st.rerun()
                
            except Exception as e:
                st.error(f"Error semasa menghantar borang: {e}")
