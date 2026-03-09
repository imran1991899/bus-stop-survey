import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import mimetypes
import time
import os
import pickle
from urllib.parse import urlencode
from PIL import Image, ImageDraw, ImageFont
import pytz 
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

# --------- Timezone & Page Setup ---------
KL_TZ = pytz.timezone('Asia/Kuala_Lumpur')
st.set_page_config(page_title="Hub Profiling Survey", layout="wide")

# --------- Staff Dictionary ---------
staff_dict = {"10005475": "MOHD RIZAL BIN RAMLI", "10020779": "NUR FAEZAH BINTI HARUN", "10014181": "NORAINSYIRAH BINTI ARIFFIN", "10022768": "NORAZHA RAFFIZZI ZORKORNAINI", "10022769": "NUR HANIM HANIL", "10023845": "MUHAMMAD HAMKA BIN ROSLIM", "10002059": "MUHAMAD NIZAM BIN IBRAHIM", "10005562": "AZFAR NASRI BIN BURHAN", "10010659": "MOHD SHAFIEE BIN ABDULLAH", "10008350": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "10003214": "NIK MOHD FADIR BIN NIK MAT RAWI", "10016370": "AHMAD AZIM BIN ISA", "10022910": "NUR SHAHIDA BINTI MOHD TAMIJI ", "10023513": "MUHAMMAD SYAHMI BIN AZMEY", "10023273": "MOHD IDZHAM BIN ABU BAKAR", "10023577": "MOHAMAD NAIM MOHAMAD SAPRI", "10023853": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "10008842": "MIRAN NURSYAWALNI AMIR", "10015662": "MUHAMMAD HANDIF BIN HASHIM", "10011944": "NUR HAZIRAH BINTI NAWI"}

# --------- Data Loading ---------
@st.cache_data
def load_hub_data():
    try:
        df = pd.read_excel("hub name.xlsx")
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except:
        return pd.DataFrame()

hub_df = load_hub_data()

# --- Google API Setup ---
FOLDER_ID = "1JKwlnKUVO3U74wTRu9U46ARF49dcglp7"
CLIENT_SECRETS_FILE = "client_secrets3.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]
REDIRECT_URI = "https://bus-stop-survey-fwaavwf7uxvxrfbjeqv9nq.streamlit.app/"

def save_creds(creds):
    with open("token.pickle", "wb") as t: pickle.dump(creds, t)

def load_creds():
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as t: return pickle.load(t)
    return None

def get_authenticated_service():
    creds = load_creds()
    if creds and creds.valid:
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_creds(creds)
            return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
        except: pass

    # Handshake Fix: Use a persistent file for the verifier
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    
    if "code" in st.query_params:
        # Load the verifier from the temporary file instead of memory
        if os.path.exists("verifier.tmp"):
            with open("verifier.tmp", "r") as f:
                flow.code_verifier = f.read()
            
            try:
                full_url = REDIRECT_URI + "?" + urlencode(st.query_params)
                flow.fetch_token(authorization_response=full_url)
                save_creds(flow.credentials)
                if os.path.exists("verifier.tmp"): os.remove("verifier.tmp")
                st.query_params.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Handshake failed: {e}")
                st.stop()
        else:
            st.warning("Session lost. Retrying login...")
            time.sleep(1)
            st.query_params.clear()
            st.rerun()
    else:
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
        # Save verifier to a physical file so it's there when you come back
        with open("verifier.tmp", "w") as f:
            f.write(flow.code_verifier)
        st.markdown(f"### [🔴 Click Here to Login with Google]({auth_url})")
        st.stop()

drive_service, sheets_service = get_authenticated_service()

# --------- Upload Functions ---------
def gdrive_upload(file_bytes, filename, mimetype):
    media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype)
    meta = {"name": filename, "parents": [FOLDER_ID]}
    up = drive_service.files().create(body=meta, media_body=media, fields="webViewLink").execute()
    return up["webViewLink"]

def append_sheet(row, header):
    query = f"'{FOLDER_ID}' in parents and name='hub_profiling_responses' and mimeType='application/vnd.google-apps.spreadsheet'"
    res = drive_service.files().list(q=query).execute().get("files", [])
    if not res:
        file = drive_service.files().create(body={"name": "hub_profiling_responses", "mimeType": "application/vnd.google-apps.spreadsheet", "parents": [FOLDER_ID]}, fields="id").execute()
        sid = file["id"]
        sheets_service.spreadsheets().values().update(spreadsheetId=sid, range="A1", valueInputOption="RAW", body={"values": [header]}).execute()
    else:
        sid = res[0]["id"]
    sheets_service.spreadsheets().values().append(spreadsheetId=sid, range="A1", valueInputOption="RAW", body={"values": [row]}).execute()

def add_watermark(image_bytes, label):
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    txt = f"{datetime.now(KL_TZ).strftime('%d/%m/%y %H:%M')} | {label}"
    draw.text((20, img.size[1]-40), txt, fill="white")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

# --------- UI Layout ---------
st.title("Hub Profiling Survey")

if "photos" not in st.session_state: st.session_state.photos = []

col1, col2 = st.columns(2)
with col1:
    staff_id = st.selectbox("Staff ID", options=sorted(list(staff_dict.keys())), index=None)
    nama = staff_dict.get(staff_id, "")
    st.info(f"Nama: {nama}" if nama else "Sila pilih Staff ID")
    
    hubs = sorted(hub_df.iloc[:, 2].dropna().unique().tolist()) if not hub_df.empty else []
    sel_hub = st.selectbox("Nama Hab", options=hubs, index=None)

with col2:
    tarikh = st.date_input("Tarikh", value=datetime.now(KL_TZ))
    cam = st.camera_input("Ambil Gambar Hab")
    if cam and cam not in st.session_state.photos:
        st.session_state.photos.append(cam)

if st.button("Hantar Laporan"):
    if not sel_hub or len(st.session_state.photos) < 1:
        st.error("Sila pilih Hab dan ambil gambar.")
    else:
        with st.spinner("Menghantar..."):
            urls = []
            for i, p in enumerate(st.session_state.photos):
                w_img = add_watermark(p.getvalue(), sel_hub)
                urls.append(gdrive_upload(w_img, f"{sel_hub}_{i}.jpg", "image/jpeg"))
            
            row = [datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M:%S"), nama, sel_hub, "; ".join(urls)]
            append_sheet(row, ["Timestamp", "Penilai", "Hab", "Links"])
            st.success("Berjaya!")
            st.session_state.photos = []
            time.sleep(2)
            st.rerun()
