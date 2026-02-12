import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import json
import mimetypes
import time
import os
import pickle
from urllib.parse import urlencode

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Malaysia timezone
try:
    from zoneinfo import ZoneInfo
    MALAYSIA_ZONE = ZoneInfo("Asia/Kuala_Lumpur")
except ImportError:
    import pytz
    MALAYSIA_ZONE = pytz.timezone("Asia/Kuala_Lumpur")

# --------- Page Setup ---------
st.set_page_config(page_title="Bus Stop Survey", layout="wide")
st.title("Bus Stop Assessment Survey")

# --------- Google Drive Folder ID ---------
FOLDER_ID = "1U1E45NroftvHINPziURbJDaojsX6P-AP"

# --------- OAuth Setup ---------
SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/spreadsheets'
]

CLIENT_SECRETS_FILE = 'client_secrets.json'

def save_credentials(credentials):
    with open('token.pickle', 'wb') as token:
        pickle.dump(credentials, token)

def load_credentials():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    return creds

def get_authenticated_service():
    creds = load_credentials()
    if creds and creds.valid:
        drive_service = build('drive', 'v3', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)
        return drive_service, sheets_service

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)
        drive_service = build('drive', 'v3', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)
        return drive_service, sheets_service

    if "oauth_flow" not in st.session_state:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri='https://bus-stop-survey-dpl6qeby3stuvpiexjhovk.streamlit.app/'
        )
        st.session_state.oauth_flow = flow
    else:
        flow = st.session_state.oauth_flow

    query_params = st.query_params

    if "code" in query_params:
        try:
            base_url = st.runtime.scriptrunner.get_script_run_ctx().session_info.app_url
        except Exception:
            base_url = 'https://bus-stop-survey-dpl6qeby3stuvpiexjhovk.streamlit.app/'

        flat_params = {k: v[0] if isinstance(v, list) else v for k, v in query_params.items()}
        full_url = base_url
        if flat_params:
            full_url += "?" + urlencode(flat_params)

        try:
            flow.fetch_token(authorization_response=full_url)
            creds = flow.credentials
            save_credentials(creds)
            del st.session_state.oauth_flow
        except Exception as e:
            st.error(f"Authentication failed: {e}")
            st.stop()
    else:
        auth_url, _ = flow.authorization_url(prompt='consent')
        st.markdown(f"[Authenticate here]({auth_url})")
        st.stop()

    drive_service = build('drive', 'v3', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    return drive_service, sheets_service

# --------- Google API Setup ---------
drive_service, sheets_service = get_authenticated_service()

def gdrive_upload_file(file_bytes, filename, mimetype, folder_id=None):
    media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype)
    file_metadata = {"name": filename}
    if folder_id:
        file_metadata["parents"] = [folder_id]
    uploaded = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink",
        supportsAllDrives=True,
    ).execute()
    return uploaded.get("webViewLink"), uploaded.get("id")

def find_or_create_gsheet(sheet_name, folder_id=None):
    if folder_id:
        query = (f"'{folder_id}' in parents and name = '{sheet_name}' and "
                 "mimeType = 'application/vnd.google-apps.spreadsheet'")
    else:
        query = (f"name = '{sheet_name}' and "
                 "mimeType = 'application/vnd.google-apps.spreadsheet'")
    response = drive_service.files().list(
        q=query,
        fields="files(id, name)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()

    files = response.get("files", [])
    if files:
        return files[0]["id"]

    file_metadata = {
        "name": sheet_name,
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }
    if folder_id:
        file_metadata["parents"] = [folder_id]

    file = drive_service.files().create(
        body=file_metadata,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return file["id"]

def append_row_to_gsheet(sheet_id, values, header):
    sheet = sheets_service.spreadsheets()
    result = sheet.values().get(spreadsheetId=sheet_id, range="A1:A1").execute()
    if "values" not in result:
        sheet.values().update(
            spreadsheetId=sheet_id,
            range="A1",
            valueInputOption="RAW",
            body={"values": [header]},
        ).execute()
        row_num = 2
    else:
        row_values = sheet.values().get(spreadsheetId=sheet_id, range="A:A").execute().get("values", [])
        row_num = len(row_values) + 1

    sheet.values().append(
        spreadsheetId=sheet_id,
        range=f"A{row_num}",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [values]},
    ).execute()

# --------- Load Excel Data ---------
try:
    routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"❌ Failed to load bus_data.xlsx: {e}")
    st.stop()

# --------- Initialize Session State ---------
for key, default in {
    "staff_id": "",
    "selected_depot": "",
    "selected_route": "",
    "selected_stop": "",
    "condition": "1. Covered Bus Stop",
    "activity_category": "",
    "specific_conditions": set(),
    "other_text": "",
    "photos": [],
    "show_success": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# --------- Staff ID ---------
staff_id = st.text_input("👤 Staff ID (8 digits)", value=st.session_state.staff_id)
if staff_id and (not staff_id.isdigit() or len(staff_id) != 8):
    st.warning("⚠️ Staff ID must be exactly 8 digits.")
st.session_state.staff_id = staff_id

# --------- Depot ---------
depots = routes_df["Depot"].dropna().unique()
selected_depot = st.selectbox("1️⃣ Select Depot", depots, 
    index=list(depots).index(st.session_state.selected_depot) if st.session_state.selected_depot in depots else 0)
st.session_state.selected_depot = selected_depot

# --------- Route ---------
filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
selected_route = st.selectbox("2️⃣ Select Route Number", filtered_routes, 
    index=list(filtered_routes).index(st.session_state.selected_route) if st.session_state.selected_route in filtered_routes else 0)
st.session_state.selected_route = selected_route

# --------- Bus Stop ---------
filtered_stops_df = stops_df[
    (stops_df["Route Number"] == selected_route) & 
    stops_df["Stop Name"].notna() & 
    stops_df["Order"].notna() & 
    stops_df["dr"].notna()
].sort_values(by=["dr", "Order"])

filtered_stops = filtered_stops_df["Stop Name"].tolist()
if st.session_state.selected_stop not in filtered_stops:
    st.session_state.selected_stop = filtered_stops[0] if filtered_stops else ""

selected_stop = st.selectbox("3️⃣ Select Bus Stop", filtered_stops, 
    index=filtered_stops.index(st.session_state.selected_stop) if st.session_state.selected_stop in filtered_stops else 0)
st.session_state.selected_stop = selected_stop

# --------- Condition ---------
conditions = ["1. Covered Bus Stop", "2. Pole Only", "3. Layby", "4. Non-Infrastructure"]
condition = st.selectbox("4️⃣ Bus Stop Condition", conditions, 
    index=conditions.index(st.session_state.condition) if st.session_state.condition in conditions else 0)
st.session_state.condition = condition

# --------- Activity Category ---------
activity_options = ["", "1. On Board in the Bus", "2. On Ground Location"]
activity_category = st.selectbox("5️⃣ Categorizing Activities", activity_options, 
    index=activity_options.index(st.session_state.activity_category) if st.session_state.activity_category in activity_options else 0)
st.session_state.activity_category = activity_category

# --------- Situational Conditions ---------
onboard_options = [
    "1. Tiada penumpang menunggu",
    "2. Tiada isyarat (penumpang tidak menahan bas)",
    "3. Tidak berhenti/memperlahankan bas",
    "4. Salah tempat menunggu",
    "5. Bas penuh",
    "6. Mengejar masa waybill (punctuality)",
    "7. Kesesakan lalu lintas",
    "8. Kekeliruan laluan oleh pemandu baru",
    "9. Terdapat laluan tutup atas sebab tertentu (baiki jalan, pokok tumbang, lawatan delegasi)",
    "10. Hentian terlalu hampir simpang masuk",
    "11. Hentian berdekatan dengan traffic light",
    "12. Other (Please specify below)",
    "13. Remarks",
]

# UPDATED ON GROUND OPTIONS
onground_options = [
    "1. Tiada Masalah",
    "2. Infrastruktur sudah tiada/musnah",
    "3. Terlindung oleh pokok",
    "4. Terhalang oleh kenderaan parkir",
    "5. Hentian gelap dan tiada lampu jalan",
    "6. Perubahan Nama,Coordinate, Lokasi hentian",
    "7. Ada Infra, tiada bus bay ",
    "8. Ada Tiang, tiada bus bay ",
    "9. Hentian rosak & vandalism",
    "10. Keselamatan bas - lokasi hentian tidak sesuai ",
    "11. Keselamatan pax - Lokasi hentian tidak sesuai",
    "12. Other (Please specify below)",
    "13. Remarks",
]

options = onboard_options if activity_category == "1. On Board in the Bus" else (onground_options if activity_category == "2. On Ground Location" else [])

if options:
    st.markdown("6️⃣ Specific Situational Conditions (Select all that apply)")
    st.session_state.specific_conditions = {c for c in st.session_state.specific_conditions if c in options}
    for opt in options:
        checked = opt in st.session_state.specific_conditions
        if st.checkbox(opt, value=checked, key=opt):
            st.session_state.specific_conditions.add(opt)
        else:
            st.session_state.specific_conditions.discard(opt)
else:
    st.info("Please select an Activity Category above to see situational conditions.")

# --------- Descriptions ---------
other_label = next((opt for opt in options if "Other" in opt), None)
if other_label and other_label in st.session_state.specific_conditions:
    other_text = st.text_area("📝 Please describe the 'Other' condition (at least 2 words)", height=150, value=st.session_state.other_text)
    st.session_state.other_text = other_text
    if len(other_text.split()) < 2: st.warning("🚨 'Other' description must be at least 2 words.")
else:
    st.session_state.other_text = ""

remarks_label = next((opt for opt in options if "Remarks" in opt), None)
if remarks_label and remarks_label in st.session_state.specific_conditions:
    remarks_text = st.text_area("💬 Remarks (optional)", height=100, value=st.session_state.get("remarks_text", ""))
    st.session_state["remarks_text"] = remarks_text
else:
    st.session_state["remarks_text"] = ""

# --------- Photo Upload ---------
st.markdown("7️⃣ Add up to 5 Photos")
if len(st.session_state.photos) < 5:
    photo = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos) + 1}")
    if photo: st.session_state.photos.append(photo)

if len(st.session_state.photos) < 5:
    upload_photo = st.file_uploader(f"📁 Upload Photo #{len(st.session_state.photos) + 1}", type=["png", "jpg", "jpeg"])
    if upload_photo: st.session_state.photos.append(upload_photo)

if st.session_state.photos:
    st.subheader("📸 Saved Photos")
    to_delete = None
    for i, p in enumerate(st.session_state.photos):
        cols = st.columns([4, 1])
        cols[0].image(p, caption=f"Photo #{i + 1}", use_container_width=True)
        if cols[1].button(f"❌ Delete #{i + 1}", key=f"del_{i}"): to_delete = i
    if to_delete is not None: st.session_state.photos.pop(to_delete)

# --------- Submit ---------
with st.form(key="survey_form"):
    submit = st.form_submit_button("✅ Submit Survey")
    if submit:
        if not staff_id.strip() or len(staff_id) != 8 or not staff_id.isdigit():
            st.warning("❗ Please enter a valid 8-digit numeric Staff ID.")
        elif not st.session_state.photos:
            st.warning("❗ Please add at least one photo.")
        elif activity_category not in ["1. On Board in the Bus", "2. On Ground Location"]:
            st.warning("❗ Please select an Activity Category.")
        elif len(st.session_state.specific_conditions) == 0:
            st.warning("❗ Please select at least one Situational Condition.")
        elif other_label in st.session_state.specific_conditions and len(st.session_state.other_text.split()) < 2:
            st.warning("❗ 'Other' description must be at least 2 words.")
        else:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                photo_links = []
                for idx, img in enumerate(st.session_state.photos):
                    content = img.getvalue() if hasattr(img, "getvalue") else img.read()
                    filename = f"{timestamp}_photo{idx+1}.jpg"
                    mimetype = mimetypes.guess_type(filename)[0] or "image/jpeg"
                    link, _ = gdrive_upload_file(content, filename, mimetype, FOLDER_ID)
                    photo_links.append(link)

                cond_list = list(st.session_state.specific_conditions)
                if other_label in cond_list:
                    cond_list.remove(other_label)
                    cond_list.append(f"Other: {st.session_state.other_text.replace(';', ',')}")
                if remarks_label in cond_list:
                    cond_list.remove(remarks_label)
                    cond_list.append(f"Remarks: {st.session_state.get('remarks_text', '').replace(';', ',')}")

                row = [timestamp, staff_id, selected_depot, selected_route, selected_stop, condition, activity_category, "; ".join(cond_list), "; ".join(photo_links)]
                header = ["Timestamp", "Staff ID", "Depot", "Route", "Bus Stop", "Condition", "Activity", "Situational Conditions", "Photos"]

                gsheet_id = find_or_create_gsheet("survey_responses", FOLDER_ID)
                append_row_to_gsheet(gsheet_id, row, header)

                st.session_state.update({"condition": "1. Covered Bus Stop", "activity_category": "", "specific_conditions": set(), "other_text": "", "remarks_text": "", "photos": [], "show_success": True})
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to submit: {e}")

if st.session_state.get("show_success", False):
    st.success("✅ Submission complete! Thank you.")
    time.sleep(2)
    st.session_state["show_success"] = False

st.components.v1.html("""<script>setInterval(() => {fetch('/_stcore/health');}, 300000);</script>""", height=0)
