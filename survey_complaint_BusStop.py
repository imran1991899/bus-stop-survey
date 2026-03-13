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

# Essential Google API Imports
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

# --------- Timezone & Page Setup ---------
KL_TZ = pytz.timezone('Asia/Kuala_Lumpur')
st.set_page_config(page_title="Bus Stop Survey", layout="wide")

# --------- 2. HEARTBEAT & KEEP ALIVE ---------
def keep_alive():
    """Keeps the session state active and logs activity"""
    if "heartbeat" not in st.session_state:
        st.session_state.heartbeat = time.time()
    
    # Check if 10 minutes (600 seconds) have passed
    if time.time() - st.session_state.heartbeat > 600:
        st.session_state.heartbeat = time.time()
        # This print goes to the 'Logs' in Streamlit Cloud
        print(f"Heartbeat: App still active for user at {datetime.now(KL_TZ)}")

# Run the heartbeat immediately on every script rerun
keep_alive()

# --------- APPLE UI GRID THEME CSS ---------
st.markdown("""
    <style>
    .stApp { background-color: #F5F5F7 !important; color: #1D1D1F !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important; }
    label[data-testid="stWidgetLabel"] p { font-size: 18px !important; font-weight: 600 !important; color: #3A3A3C !important; }
    .custom-spinner { padding: 20px; background-color: #FFF9F0; border: 2px solid #FFCC80; border-radius: 14px; color: #E67E22; text-align: center; font-weight: bold; margin-bottom: 20px; }
    div[role="radiogroup"] { background-color: #E3E3E8 !important; padding: 6px !important; border-radius: 14px !important; gap: 8px !important; display: flex !important; flex-direction: row !important; align-items: center !important; margin-bottom: 28px !important; max-width: 360px; min-height: 58px !important; }
    [data-testid="stWidgetSelectionVisualizer"] { display: none !important; }
    div[role="radiogroup"] label { background-color: transparent !important; border: none !important; padding: 14px 0px !important; border-radius: 11px !important; transition: all 0.2s ease-in-out !important; flex: 1 !important; display: flex !important; justify-content: center !important; align-items: center !important; }
    div[role="radiogroup"] label p { font-size: 16px !important; margin: 0 !important; padding: 0 20px !important; white-space: nowrap !important; color: #444444 !important; font-weight: 700 !important; }
    div[role="radiogroup"] label:has(input:checked) { background-color: #FFFFFF !important; box-shadow: 0px 4px 12px rgba(0,0,0,0.15) !important; }
    div.stButton > button { background-color: #007AFF !important; color: white !important; border: none !important; height: 60px !important; font-weight: 600 !important; border-radius: 16px !important; font-size: 18px !important; width: 100%; }
    [data-testid="stCameraInput"] { border: 2px dashed #007AFF; border-radius: 20px; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --------- Helper: MASSIVE ORANGE WATERMARK ---------
def add_watermark(image_bytes, stop_name):
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    font_scale = int(w * 0.16) 
    now = datetime.now(KL_TZ)
    time_str = now.strftime("%I:%M %p")
    info_str = f"{now.strftime('%d/%m/%y')} | {stop_name.upper()}"
    try:
        font_main = ImageFont.truetype("arialbd.ttf", font_scale)
        font_sub = ImageFont.truetype("arialbd.ttf", int(font_scale * 0.4))
    except:
        font_main = ImageFont.load_default()
        font_sub = ImageFont.load_default()
    margin_left, margin_bottom = int(w * 0.02), int(h * 0.02)
    sub_bbox = font_sub.getbbox(info_str)
    y_pos_sub = h - margin_bottom - (sub_bbox[3] - sub_bbox[1])
    y_pos_main = y_pos_sub - (font_main.getbbox(time_str)[3] - font_main.getbbox(time_str)[1]) - 10 
    draw.text((margin_left, y_pos_main), time_str, font=font_main, fill="orange")
    draw.text((margin_left, y_pos_sub), info_str, font=font_sub, fill="white")
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=95)
    return buf.getvalue()

# --------- Google API Configuration ---------
FOLDER_ID = "1DjtLxgyQXwgjq_N6I_-rtYcBcnWhzMGp"
CLIENT_SECRETS_FILE = "client_secrets2.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]
REDIRECT_URI = "https://bus-stop-survey-99f8wusughejfcfvrvxmyl.streamlit.app/"

def save_credentials(credentials):
    with open("token.pickle", "wb") as token: pickle.dump(credentials, token)

def load_credentials():
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token: return pickle.load(token)
    return None

def get_authenticated_service():
    creds = load_credentials()
    if creds and creds.valid:
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
        except: pass

    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    
    # Handshake Fix logic
    if "code" in st.query_params:
        if os.path.exists("verifier.tmp"):
            with open("verifier.tmp", "r") as f:
                flow.code_verifier = f.read()
            try:
                # Build full response URL to satisfy library
                full_url = REDIRECT_URI + "?" + urlencode(st.query_params)
                flow.fetch_token(authorization_response=full_url)
                save_credentials(flow.credentials)
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
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline", include_granted_scopes="true")
        # Save verifier to physical file before leaving the app
        with open("verifier.tmp", "w") as f:
            f.write(flow.code_verifier)
        st.markdown(f"### Authentication Required\n[🔴 Click Here to Login with Google]({auth_url})")
        st.stop()

drive_service, sheets_service = get_authenticated_service()

def gdrive_upload_file(file_bytes, filename, mimetype, folder_id=None):
    media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype)
    metadata = {"name": filename}
    if folder_id: metadata["parents"] = [folder_id]
    uploaded = drive_service.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()
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
all_available_stops = sorted(stops_df["Stop Name"].dropna().unique().tolist())

try:
    bus_df = pd.read_excel("bus_list.xlsx", sheet_name="bus list", usecols=[1])
    bus_list = sorted(bus_df.iloc[:, 0].dropna().astype(str).unique().tolist())
except: bus_list = []

staff_dict = {"10005475": "MOHD RIZAL BIN RAMLI", "10020779": "NUR FAEZAH BINTI HARUN", "10014181": "NORAINSYIRAH BINTI ARIFFIN", "10022768": "NORAZHA RAFFIZZI ZORKORNAINI", "10022769": "NUR HANIM HANIL", "10023845": "MUHAMMAD HAMKA BIN ROSLIM", "10002059": "MUHAMAD NIZAM BIN IBRAHIM", "10005562": "AZFAR NASRI BIN BURHAN", "10010659": "MOHD SHAFIEE BIN ABDULLAH", "10008350": "MUHAMMAD MUSTAQIM BIN FAZIT OSMAN", "10003214": "NIK MOHD FADIR BIN NIK MAT RAWI", "10016370": "AHMAD AZIM BIN ISA", "10022910": "NUR SHAHIDA BINTI MOHD TAMIJI ", "10023513": "MUHAMMAD SYAHMI BIN AZMEY", "10023273": "MOHD IDZHAM BIN ABU BAKAR", "10023577": "MOHAMAD NAIM MOHAMAD SAPRI", "10023853": "MUHAMAD IMRAN BIN MOHD NASRUDDIN", "10008842": "MIRAN NURSYAWALNI AMIR", "10015662": "MUHAMMAD HANDIF BIN HASHIM", "10011944": "NUR HAZIRAH BINTI NAWI"}

if "photos" not in st.session_state: st.session_state.photos = []
if "videos" not in st.session_state: st.session_state.videos = []

questions_a = ["1. BC menggunakan telefon bimbit?", "2. BC memperlahankan/memberhentikan bas?", "3. BC memandu di lorong 1 (kiri)?", "4. Bas penuh dengan penumpang?", "5. BC tidak mengambil penumpang?", "6. BC berlaku tidak sopan?"]
questions_c = ["7. Penumpang beri isyarat menahan? (NA jika tiada)", "8. Penumpang leka/tidak peka? (NA jika tiada)", "9. Penumpang tiba lewat?", "10. Penumpang menunggu di luar kawasan hentian?"]
questions_b = ["11. Hentian terlindung dari pandangan BC? (semak, pokok, Gerai, lain2)", "12. Hentian terhalang oleh kenderaan parkir?", "13. Persekitaran bahaya untuk bas berhenti?", "14. Terdapat pembinaan berhampiran?", "15. Mempunyai bumbung?", "16. Mempunyai tiang?", "17. Mempunyai petak hentian?", "18. Mempunyai layby?"]
all_questions = questions_a + ["Ada Penumpang?"] + questions_c + questions_b

if "responses" not in st.session_state: st.session_state.responses = {q: None for q in all_questions}

# --------- Main App UI ---------
st.title("BC and Bus Stop Survey")

col_staff, col_stop = st.columns(2)
with col_staff:
    staff_id = st.selectbox("👤 OE Staff ID", options=list(staff_dict.keys()), index=None, placeholder="Pilih ID Staf...", key="staff_id_select")
    if staff_id: st.info(f"**Nama:** {staff_dict[staff_id]}")

with col_stop:
    stop = st.selectbox("📍 Bus Stop", all_available_stops, index=None, placeholder="Pilih Hentian Bas...", key="stop_select")
    current_route, current_depot = "", ""
    if stop:
        matched_stop_data = stops_df[stops_df["Stop Name"] == stop]
        current_route = " / ".join(map(str, matched_stop_data["Route Number"].unique()))
        current_depot = " / ".join(map(str, routes_df[routes_df["Route Number"].isin(matched_stop_data["Route Number"].unique())]["Depot"].unique()))

st.divider()

def render_grid_questions(q_list):
    for i in range(0, len(q_list), 2):
        col1, col2 = st.columns(2)
        for idx, q in enumerate([q_list[i], q_list[i+1] if i+1 < len(q_list) else None]):
            if q:
                with (col1 if idx==0 else col2):
                    st.markdown(f"**{q}**")
                    opts = ["Yes", "No", "NA"] if "NA" in q else ["Yes", "No"]
                    st.session_state.responses[q] = st.radio(label=q, options=opts, index=None, key=f"r_{q}", horizontal=True, label_visibility="collapsed")

st.subheader("A. KELAKUAN KAPTEN BAS")
c1, c2, c3 = st.columns(3)
bc_id = c1.number_input("BC id:", value=None, step=1, key="bc_id_input")
bus_reg = c2.selectbox("🚌 Pilih No. Bas:", options=bus_list, index=None, key="bus_select")
speed = c3.number_input("Kelajuan Bas (km/h):", min_value=0, max_value=120, value=None, key="bus_speed_input")
render_grid_questions(questions_a)

st.divider()
st.subheader("C. PENUMPANG")
has_pax = st.radio("Ada penumpang?", options=["Yes", "No"], index=None, key="has_pax", horizontal=True)
st.session_state.responses["Ada Penumpang?"] = has_pax
if has_pax == "No":
    for q in questions_c: st.session_state.responses[q] = "No Passenger"
else:
    render_grid_questions(questions_c)

st.divider()
st.subheader("B. KEADAAN HENTIAN BAS")
render_grid_questions(questions_b)

st.divider()
st.subheader("📸 Media Upload (3 Items Required)")
cur_count = len(st.session_state.photos) + len(st.session_state.videos)
if cur_count < 3:
    c_cam, c_file = st.columns(2)
    cam = c_cam.camera_input(f"Capture #{cur_count + 1}", key=f"c_{cur_count}")
    if cam: st.session_state.photos.append(cam); st.rerun()
    f_up = c_file.file_uploader(f"Upload #{cur_count + 1}", type=["jpg","png","jpeg","mp4","mov"], key=f"f_{cur_count}")
    if f_up:
        m, _ = mimetypes.guess_type(f_up.name)
        if m and m.startswith("video"): st.session_state.videos.append(f_up)
        else: st.session_state.photos.append(f_up)
        st.rerun()

# Display/Remove media
if st.session_state.photos or st.session_state.videos:
    m_cols = st.columns(3)
    all_m = [('p', p) for p in st.session_state.photos] + [('v', v) for v in st.session_state.videos]
    for i, (t, data) in enumerate(all_m):
        with m_cols[i % 3]:
            if t == 'p': st.image(data)
            else: st.video(data)
            if st.button(f"Remove {i}", key=f"rm_{i}"):
                if t == 'p': st.session_state.photos.remove(data)
                else: st.session_state.videos.remove(data)
                st.rerun()

if st.button("Submit Survey"):
    if not staff_id or not stop or not bus_reg or (len(st.session_state.photos) + len(st.session_state.videos)) != 3:
        st.error("Missing fields or media.")
    else:
        with st.spinner("Uploading..."):
            try:
                t_str = datetime.now(KL_TZ).strftime("%Y%m%d_%H%M%S")
                urls = []
                for idx, p in enumerate(st.session_state.photos):
                    urls.append(gdrive_upload_file(add_watermark(p.getvalue(), stop), f"{stop}_{t_str}_{idx}.jpg", "image/jpeg", FOLDER_ID))
                for idx, v in enumerate(st.session_state.videos):
                    urls.append(gdrive_upload_file(v.getvalue(), f"{stop}_{t_str}_{idx}.mp4", "video/mp4", FOLDER_ID))
                
                row = [datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M:%S"), staff_id, staff_dict[staff_id], current_depot, current_route, stop, bus_reg] + \
                      [st.session_state.responses[q] for q in all_questions] + ["; ".join(urls)]
                
                # Align columns for spreadsheet
                while len(row) < 30: row.append("")
                row.insert(30, speed or ""); row.insert(31, bc_id or "")
                
                header = ["Timestamp", "Staff ID", "Name", "Depot", "Route", "Stop", "Bus"] + all_questions + ["Links"]
                while len(header) < 30: header.append("")
                header.insert(30, "Speed"); header.insert(31, "BC ID")

                append_row(find_or_create_gsheet("survey_responses", FOLDER_ID), row, header)
                st.success("Submitted!")
                st.session_state.photos, st.session_state.videos = [], []
                st.session_state.responses = {q: None for q in all_questions}
                time.sleep(2); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

