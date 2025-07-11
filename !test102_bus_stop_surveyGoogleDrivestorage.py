import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import json
import mimetypes
import time
import os
import pickle

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

    # --- OAuth Flow handling ---
    # Only create flow if not in session_state
    if "oauth_flow" not in st.session_state:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri='https://bus-stop-survey-cdpdt8wk87srejtieqiesh.streamlit.app/'
        )
        st.session_state.oauth_flow = flow
        auth_url, _ = flow.authorization_url(prompt='consent')
        st.markdown(f"[Authenticate here]({auth_url})")
        st.stop()  # Wait for user to authenticate and paste URL

    flow = st.session_state.oauth_flow

    auth_response = st.text_input('Paste the full redirect URL here:')

    if not auth_response:
        st.stop()

    try:
        flow.fetch_token(authorization_response=auth_response)
        creds = flow.credentials
        save_credentials(creds)
        # Clear flow from session_state after success to prevent reuse errors
        del st.session_state.oauth_flow
    except Exception as e:
        st.error(f"Authentication failed: {e}")
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
    "3. Layby",
    "4. Non-Infrastructure",
]
condition = st.selectbox(
    "4️⃣ Bus Stop Condition",
    conditions,
    index=conditions.index(st.session_state.condition)
    if st.session_state.condition in conditions
    else 0,
)
st.session_state.condition = condition

# --------- Activity Category ---------
activity_options = ["", "1. On Board in the Bus", "2. On Ground Location"]
activity_category = st.selectbox(
    "5️⃣ Categorizing Activities",
    activity_options,
    index=activity_options.index(st.session_state.activity_category)
    if st.session_state.activity_category in activity_options
    else 0,
)
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
]
onground_options = [
    "1. Tiada tempat menunggu",
    "2. Tiada tempat berteduh",
    "3. Tiada tempat duduk",
    "4. Tiada papan tanda bas",
    "5. Tiada lampu jalan",
    "6. Tiada lampu amaran",
    "7. Other (Please specify below)",
]

situational_conditions = (
    onboard_options if activity_category == "1. On Board in the Bus" else onground_options
)
if activity_category:
    selected_conditions = st.multiselect(
        "6️⃣ Situational Conditions (Select all that apply)",
        situational_conditions,
        default=list(st.session_state.specific_conditions),
    )
    st.session_state.specific_conditions = set(selected_conditions)
else:
    st.write("Please select an activity category above.")

# --------- Other Text ---------
other_text = st.text_area(
    "If you selected 'Other', please specify here:",
    value=st.session_state.other_text,
)
st.session_state.other_text = other_text.strip()

# --------- Photo Upload ---------
photos = st.file_uploader(
    "📸 Upload Photos (Max 3 images)",
    accept_multiple_files=True,
    type=["jpg", "jpeg", "png"],
    key="photos_upload",
)
# Limit photos to 3
photos = photos[:3] if photos else []

st.session_state.photos = photos

# --------- Submit Button and Processing ---------
def clear_form():
    for key in [
        "staff_id",
        "selected_depot",
        "selected_route",
        "selected_stop",
        "condition",
        "activity_category",
        "specific_conditions",
        "other_text",
        "photos",
        "show_success",
    ]:
        if key == "specific_conditions":
            st.session_state[key] = set()
        elif key == "photos":
            st.session_state[key] = []
        elif key == "show_success":
            st.session_state[key] = False
        else:
            st.session_state[key] = ""

if st.button("Submit"):
    # Validation
    if not staff_id or not staff_id.isdigit() or len(staff_id) != 8:
        st.error("Please enter a valid 8-digit Staff ID.")
    elif not selected_depot or not selected_route or not selected_stop:
        st.error("Please select Depot, Route, and Bus Stop.")
    elif not condition:
        st.error("Please select Bus Stop Condition.")
    elif not activity_category:
        st.error("Please select Activity Category.")
    elif not st.session_state.specific_conditions:
        st.error("Please select at least one Situational Condition.")
    else:
        # Prepare data row
        now = datetime.now(MALAYSIA_ZONE)
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

        situational_cond_str = ", ".join(
            sorted(st.session_state.specific_conditions)
        )
        if "Other" in situational_cond_str and other_text:
            situational_cond_str += f" ({other_text})"

        row = [
            timestamp,
            staff_id,
            selected_depot,
            selected_route,
            selected_stop,
            condition,
            activity_category,
            situational_cond_str,
        ]

        # Upload photos to Drive
        photo_links = []
        if photos:
            folder_id = None  # Or set your folder ID here
            for photo in photos:
                photo_bytes = photo.read()
                photo_name = f"{staff_id}_{selected_route}_{selected_stop}_{photo.name}"
                try:
                    link, _ = gdrive_upload_file(photo_bytes, photo_name, photo.type, folder_id)
                    photo_links.append(link)
                except Exception as e:
                    st.error(f"Failed to upload photo {photo.name}: {e}")

        # Add photo links to row
        row.append(", ".join(photo_links))

        # Find or create Google Sheet
        sheet_name = "Bus_Stop_Survey_Responses"
        sheet_id = find_or_create_gsheet(sheet_name)

        # Header for sheet (if needed)
        header = [
            "Timestamp",
            "Staff ID",
            "Depot",
            "Route Number",
            "Bus Stop",
            "Bus Stop Condition",
            "Activity Category",
            "Situational Conditions",
            "Photo Links",
        ]

        try:
            append_row_to_gsheet(sheet_id, row, header)
            st.success("✅ Survey submitted successfully!")
            clear_form()
        except Exception as e:
            st.error(f"Failed to submit data: {e}")

# --------- Debug info (optional) ---------
# st.write(st.session_state)
