import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import mimetypes
import time

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# timezone setup
try:
    from zoneinfo import ZoneInfo
    MY_ZONE = ZoneInfo("Asia/Kuala_Lumpur")
except ImportError:
    import pytz
    MY_ZONE = pytz.timezone("Asia/Kuala_Lumpur")

# Page setup
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
st.title("🚌 Bus Stop Assessment Survey")

# Load Google Drive credentials and folder ID from secrets
GDRIVE_CREDS = st.secrets["gdrive_service_account"]
GDRIVE_FOLDER_ID = GDRIVE_CREDS["gdrive_folder_id"]

# Create Google API credentials and clients
creds = service_account.Credentials.from_service_account_info(
    GDRIVE_CREDS,
    scopes=[
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ],
)
drive_service = build("drive", "v3", credentials=creds)
sheets_service = build("sheets", "v4", credentials=creds)


# --- Helper: Upload file to Shared Drive ---
def gdrive_upload_file(file_bytes, filename, mimetype, folder_id=GDRIVE_FOLDER_ID):
    """
    Uploads a file to a Shared Drive folder.

    Args:
        file_bytes (bytes): File content in bytes.
        filename (str): Desired filename.
        mimetype (str): MIME type of the file.
        folder_id (str): Google Drive folder ID in the Shared Drive.

    Returns:
        tuple: (webViewLink, fileId)
    """
    media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype=mimetype)
    metadata = {
        'name': filename,
        'parents': [folder_id],  # Important: must be folder inside Shared Drive
    }

    file = drive_service.files().create(
        body=metadata,
        media_body=media,
        fields='id, webViewLink',
        supportsAllDrives=True  # Critical for Shared Drive upload
    ).execute()

    return file.get('webViewLink'), file.get('id')


# --- Helper: Find or create Google Sheet ---
def find_or_create_gsheet(sheet_name, folder_id=GDRIVE_FOLDER_ID):
    query = (
        f"'{folder_id}' in parents and name = '{sheet_name}' "
        "and mimeType = 'application/vnd.google-apps.spreadsheet'"
    )
    resp = drive_service.files().list(
        q=query,
        fields="files(id,name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    files = resp.get("files", [])
    if files:
        return files[0]["id"]
    meta = {
        "name": sheet_name,
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [folder_id],
    }
    created = drive_service.files().create(
        body=meta,
        fields="id",
        supportsAllDrives=True
    ).execute()
    return created["id"]


# --- Helper: Append row to Google Sheet ---
def append_row_to_gsheet(sheet_id, values, header):
    sheet = sheets_service.spreadsheets()
    exists = sheet.values().get(spreadsheetId=sheet_id, range="A1:A1").execute()
    if "values" not in exists:
        sheet.values().update(
            spreadsheetId=sheet_id,
            range="A1",
            valueInputOption="RAW",
            body={"values": [header]},
        ).execute()
        start = 2
    else:
        col = sheet.values().get(spreadsheetId=sheet_id, range="A:A").execute().get("values", [])
        start = len(col) + 1
    sheet.values().append(
        spreadsheetId=sheet_id,
        range=f"A{start}",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [values]},
    ).execute()


# --- Load Reference Data ---
try:
    routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"Failed to load bus_data.xlsx: {e}")
    st.stop()

# --- Session Defaults ---
defaults = {
    "staff_id": "", "selected_depot": "", "selected_route": "",
    "selected_stop": "", "condition": "1. Covered Bus Stop",
    "activity_category": "", "specific_conditions": set(),
    "other_text": "", "photos": [], "show_success": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- Survey Form UI ---
staff_id = st.text_input("👤 Staff ID (8 digits)", value=st.session_state.staff_id)
if staff_id and (not staff_id.isdigit() or len(staff_id) != 8):
    st.warning("⚠️ Staff ID must be exactly 8 digits.")
st.session_state.staff_id = staff_id

depots = routes_df["Depot"].dropna().unique()
selected_depot = st.selectbox("1️⃣ Select Depot", depots, index=0)
st.session_state.selected_depot = selected_depot

filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
selected_route = st.selectbox("2️⃣ Select Route Number", filtered_routes, index=0)
st.session_state.selected_route = selected_route

filtered_stops_df = stops_df[
    (stops_df["Route Number"] == selected_route)
    & stops_df["Stop Name"].notna()
    & stops_df["Order"].notna()
    & stops_df["dr"].notna()
].sort_values(by=["dr", "Order"])
filtered_stops = filtered_stops_df["Stop Name"].tolist()
selected_stop = st.selectbox("3️⃣ Select Bus Stop", filtered_stops, index=0)
st.session_state.selected_stop = selected_stop

conditions = [
    "1. Covered Bus Stop", "2. Pole Only", "3. Layby", "4. Non‑Infrastructure"
]
condition = st.selectbox("4️⃣ Bus Stop Condition", conditions, index=conditions.index(st.session_state.condition))
st.session_state.condition = condition

activity_options = ["", "1. On Board in the Bus", "2. On Ground Location"]
activity_category = st.selectbox("5️⃣ Categorizing Activities", activity_options, index=activity_options.index(st.session_state.activity_category))
st.session_state.activity_category = activity_category

onboard = ["1. Tiada ...", "12. Other (Please specify below)"]
onground = ["1. Infrastruktur ...", "7. Other (Please specify below)"]
options = onboard if activity_category.startswith("1.") else (onground if activity_category.startswith("2.") else [])

if options:
    st.markdown("6️⃣ **Specific Conditions (pick ≥1)***")
    for opt in options:
        checked = opt in st.session_state.specific_conditions
        keep = st.checkbox(opt, value=checked, key=opt)
        if keep:
            st.session_state.specific_conditions.add(opt)
        else:
            st.session_state.specific_conditions.discard(opt)
else:
    st.info("Select an Activity Category to see situational conditions.")

other_label = next((o for o in options if "Other" in o), None)
if other_label and other_label in st.session_state.specific_conditions:
    ot = st.text_area("📝 Describe 'Other' (min 2 words)", value=st.session_state.other_text)
    st.session_state.other_text = ot
    if len(ot.split()) < 2:
        st.warning("🚨 Must be at least 2 words.")
else:
    st.session_state.other_text = ""

st.markdown("7️⃣ Add up to 5 Photos")
while len(st.session_state.photos) < 5:
    p = st.camera_input(f"📷 Photo #{len(st.session_state.photos)+1}")
    if p:
        st.session_state.photos.append(p)
    u = st.file_uploader(f"📁 Upload Photo #{len(st.session_state.photos)+1}", type=["png","jpg","jpeg"])
    if u:
        st.session_state.photos.append(u)
    break

if st.session_state.photos:
    st.subheader("📸 Saved Photos")
    for i, p in enumerate(st.session_state.photos):
        cols = st.columns([4,1])
        cols[0].image(p, caption=f"Photo #{i+1}", use_container_width=True)
        if cols[1].button(f"❌ Delete #{i+1}", key=f"del_{i}"):
            st.session_state["photos"].pop(i)
            st.experimental_rerun()

# --- Form Submission ---
with st.form("survey_form"):
    submit = st.form_submit_button("✅ Submit Survey")

if submit:
    # Validation
    if not (staff_id.isdigit() and len(staff_id)==8):
        st.warning("Staff ID must be exactly 8 digits.")
    elif not st.session_state.photos:
        st.warning("Please add at least one photo.")
    elif not activity_category.startswith(("1.","2.")):
        st.warning("Please select an Activity Category.")
    elif options and not st.session_state.specific_conditions:
        st.warning("Select at least one specific condition.")
    elif other_label in st.session_state.specific_conditions and len(st.session_state.other_text.split())<2:
        st.warning("'Other' description must be minimum 2 words.")
    else:
        try:
            now_my = datetime.now(MY_ZONE)
            ts = now_my.strftime("%Y-%m-%d_%H-%M-%S")
            photo_links = []
            for idx, img in enumerate(st.session_state.photos):
                safe = selected_stop.replace(" ","_").replace("/","_")
                fname = f"{safe}_{ts}_photo{idx+1}.jpg"
                data = img.getvalue() if hasattr(img,"getvalue") else img.read()
                mt = mimetypes.guess_type(fname)[0] or "image/jpeg"
                link, _ = gdrive_upload_file(data, fname, mt)
                photo_links.append(link)

            conds = list(st.session_state.specific_conditions)
            if other_label in conds:
                conds.remove(other_label)
                conds.append("Other: " + st.session_state.other_text.replace(";","\,"))

            row = [
                ts, staff_id, selected_depot, selected_route, selected_stop,
                condition, activity_category, "; ".join(conds), "; ".join(photo_links)
            ]
            header = ["Timestamp","Staff ID","Depot","Route","Stop","Condition","Activity","Conditions","Photos"]
            sheet_name = f"{selected_depot} Bus Survey"
            sheet_id = find_or_create_gsheet(sheet_name)

            append_row_to_gsheet(sheet_id, row, header)

            st.session_state.show_success = True
        except Exception as e:
            st.error(f"Failed to submit survey: {e}")

if st.session_state.show_success:
    st.success("✅ Survey submitted successfully!")
    if photo_links:
        st.markdown("**Photos Uploaded:**")
        for l in photo_links:
            st.markdown(f"- [View Photo]({l})")
    if st.button("Submit another survey"):
        for k in defaults:
            st.session_state[k] = defaults[k]
        st.experimental_rerun()
