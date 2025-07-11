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
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
st.title("🚌 Bus Stop Assessment Survey")

# --------- Google Drive Folder ID ---------
# Replace this with your actual Google Drive folder ID
FOLDER_ID = "your_google_drive_folder_id_here"

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
            redirect_uri='https://bus-stop-survey-cdpdt8wk87srejtieqiesh.streamlit.app/'  # Your actual redirect URI here
        )
        st.session_state.oauth_flow = flow
    else:
        flow = st.session_state.oauth_flow

    query_params = st.query_params

    if "code" in query_params:
        # Get base URL of app
        try:
            base_url = st.runtime.scriptrunner.get_script_run_ctx().session_info.app_url
        except Exception:
            # fallback if runtime API unavailable (e.g., local)
            base_url = 'https://bus-stop-survey-cdpdt8wk87srejtieqiesh.streamlit.app/'

        # Flatten query params (dict of lists) for urlencode
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

# --------- Upload file to Drive (uses OAuth creds) ---------
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

# --------- Find or Create GSheet (uses OAuth creds) ---------
def find_or_create_gsheet(sheet_name, folder_id=None):
    if folder_id:
        query = (
            f"'{folder_id}' in parents and name = '{sheet_name}' and "
            "mimeType = 'application/vnd.google-apps.spreadsheet'"
        )
    else:
        query = (
            f"name = '{sheet_name}' and "
            "mimeType = 'application/vnd.google-apps.spreadsheet'"
        )
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

# --------- Append row to GSheet (uses OAuth creds) ---------
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
        row_values = (
            sheet.values().get(spreadsheetId=sheet_id, range="A:A").execute().get("values", [])
        )
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
selected_depot = st.selectbox(
    "1️⃣ Select Depot",
    depots,
    index=list(depots).index(st.session_state.selected_depot)
    if st.session_state.selected_depot in depots
    else 0,
)
st.session_state.selected_depot = selected_depot

# --------- Route ---------
filtered_routes = (
    routes_df[routes_df["Depot"] == selected_depot]["Route Number"]
    .dropna()
    .unique()
)
selected_route = st.selectbox(
    "2️⃣ Select Route Number",
    filtered_routes,
    index=list(filtered_routes).index(st.session_state.selected_route)
    if st.session_state.selected_route in filtered_routes
    else 0,
)
st.session_state.selected_route = selected_route

# --------- Bus Stop ---------
filtered_stops_df = stops_df[
    (stops_df["Route Number"] == selected_route)
    & stops_df["Stop Name"].notna()
    & stops_df["Order"].notna()
    & stops_df["dr"].notna()
].sort_values(by=["dr", "Order"])

filtered_stops = filtered_stops_df["Stop Name"].tolist()
if st.session_state.selected_stop not in filtered_stops:
    st.session_state.selected_stop = filtered_stops[0] if filtered_stops else ""

selected_stop = st.selectbox(
    "3️⃣ Select Bus Stop",
    filtered_stops,
    index=filtered_stops.index(st.session_state.selected_stop)
    if st.session_state.selected_stop in filtered_stops
    else 0,
)
st.session_state.selected_stop = selected_stop

# --------- Condition ---------
conditions = [
    "1. Covered Bus Stop",
    "2. Pole Only",
    "3. Bus Bay",
    "4. Bus Stop without Shelter",
]
condition = st.radio("4️⃣ Condition", conditions, index=conditions.index(st.session_state.condition))
st.session_state.condition = condition

# --------- Activity Category ---------
activity_category = st.text_input("5️⃣ Activity Category", st.session_state.activity_category)
st.session_state.activity_category = activity_category

# --------- Specific Conditions ---------
specific_options = [
    "Poor Visibility",
    "No Ramp",
    "Ramp in Bad Condition",
    "Damaged Shelter",
    "No Seating",
]
specific_conditions = st.multiselect("6️⃣ Specific Conditions", specific_options, list(st.session_state.specific_conditions))
st.session_state.specific_conditions = set(specific_conditions)

# --------- Other Text ---------
other_text = st.text_area("7️⃣ Other Comments", st.session_state.other_text)
st.session_state.other_text = other_text

# --------- Upload Photos ---------
uploaded_photos = st.file_uploader(
    "8️⃣ Upload Photos (you can upload multiple)",
    accept_multiple_files=True,
    type=["jpg", "jpeg", "png"],
)

if uploaded_photos:
    # Add uploaded files to session state list
    for photo in uploaded_photos:
        if photo not in st.session_state.photos:
            st.session_state.photos.append(photo)

# Show thumbnails and remove buttons for uploaded photos
if st.session_state.photos:
    st.write("### Uploaded Photos")
    cols = st.columns(len(st.session_state.photos))
    remove_indices = []
    for i, photo in enumerate(st.session_state.photos):
        with cols[i]:
            st.image(photo, width=150)
            if st.button(f"Remove {photo.name}", key=f"remove_{i}"):
                remove_indices.append(i)
    # Remove photos if requested
    for i in sorted(remove_indices, reverse=True):
        del st.session_state.photos[i]

# --------- Submit ---------
if st.button("Submit Survey"):
    if not staff_id or len(staff_id) != 8 or not staff_id.isdigit():
        st.error("Please enter a valid 8-digit Staff ID.")
    else:
        with st.spinner("Uploading photos and submitting data..."):
            now = datetime.now(MALAYSIA_ZONE)
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
            photo_links = []

            # Upload photos to Drive folder
            for photo in st.session_state.photos:
                photo_bytes = photo.read()
                mimetype = mimetypes.guess_type(photo.name)[0] or "image/jpeg"
                link, _ = gdrive_upload_file(photo_bytes, photo.name, mimetype, FOLDER_ID)
                photo_links.append(link)

            # Prepare data row
            row = [
                timestamp,
                staff_id,
                selected_depot,
                selected_route,
                selected_stop,
                condition,
                activity_category,
                ", ".join(specific_conditions),
                other_text,
                ", ".join(photo_links),
            ]

            # Sheet header
            header = [
                "Timestamp",
                "Staff ID",
                "Depot",
                "Route Number",
                "Bus Stop",
                "Condition",
                "Activity Category",
                "Specific Conditions",
                "Other Comments",
                "Photo Links",
            ]

            # Find or create sheet in folder
            sheet_name = "Bus Stop Assessment Survey"
            sheet_id = find_or_create_gsheet(sheet_name, FOLDER_ID)

            # Append data row
            append_row_to_gsheet(sheet_id, row, header)

            # Clear photos and success message
            st.session_state.photos.clear()
            st.success("✅ Survey submitted successfully!")

