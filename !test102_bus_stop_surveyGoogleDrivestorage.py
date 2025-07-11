import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import json
import mimetypes
import time
from google.oauth2 import service_account
import streamlit as st


# timezone
try:
    from zoneinfo import ZoneInfo
    MY_ZONE = ZoneInfo("Asia/Kuala_Lumpur")
except ImportError:
    import pytz
    MY_ZONE = pytz.timezone("Asia/Kuala_Lumpur")

# Page setup
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
st.title("🚌 Bus Stop Assessment Survey")

# --- Google API Setup ---
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# 🔑 IMPORTANT: 
# Paste your Google service account JSON info as JSON string in Streamlit secrets under key "gdrive_service_account"
# Example (in .streamlit/secrets.toml or Streamlit cloud UI):
# [gdrive_service_account]
# type = "service_account"
# project_id = "your-project-id"
# private_key_id = "your-private-key-id"
# private_key = """
# -----BEGIN PRIVATE KEY-----
# YOUR_PRIVATE_KEY_CONTENT
# -----END PRIVATE KEY-----
# """
# client_email = "your-service-account-email@your-project.iam.gserviceaccount.com"
# ...

GDRIVE_CREDS = st.secrets["gdrive_service_account"]

type = "service_account"
project_id = "my-project05-465612"
private_key_id = "33d6d88ec537d19abcfc3248c924773545a4ce1f"
private_key = """
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCksJMe9jLOwEx2
vLVbGC8db97Rj+0qrkvxnplGOb+rNwAL3lZcP1hMKkxORNAJAl7g5nC50Bi2iMGG
O01mhO2OK7bh6oh5AbvlXki4eTs3AHGcbtjJ6VX3EjmNg/qMg0IIBjflID7QUTdP
xnbG8pB7vg96BUlVFP3DwuQ7Adt4FLtNfU5rc+h1RkRSSOkhki8336KywxGA5rHK
gvJeXwjaZVA580UvjqgNiuyugjgO+yLSDEXGXFI+4PcwMk8ADvsM3QgCADu2LPkL
ogtRyN51sNXnowpkf9t7Vvwknp3in+SMo7mak+0zb86XOyn47fmz9Uo5CUY4dUHF
7wedrfTpAgMBAAECggEABLoeaEGuo3wQsHTKAM9wz20TWHEDi0QoS7W0FmMDHciM
8LTvm3i5pwACI4SlSFOVgmo4MJZ+QG5W8wHMlDAluxJapAvjDGlwvvc7P55ChUQ2
6UOjkdISegO/e/tz4NNwp6x5WhMtnQruZeoJ+pEM9XGhs0HSa8XX4yX60+MXAqXh
Noy98EnFH/LJmjm1C05RbXJn8i99Pgs9ER1UuOFPw5pwwjXdGHloMN0DD7T1xgTe
fqk8zhpi2UMEfZ35bxRLKMpcuwNDGiZPOZlrdFt1Ixp6oZanc0AGueLLwGErGRvA
14TAulTRceMIEq6G85G9m6pDMQufUbCnUJorvQrenQKBgQDZ6ebzHHqwe3UsUbbG
GoX675aZ2x79toxnhzRgmHfkxph/O7Dk3jdu6WBge3BjVoFUs4uQpwuT5yGsJiDt
+KbIrNguF/1eEECTN9CjysGfYdMJY7I44q6VSWUF9bocm3ff4a0THQrzgoiRG7ta
gTXtMl/FkQpEuGZ1MsFzv9UMPQKBgQDBeUcESPfqOfNb+nMvQz3eX1SDzNd+7Jf+
HesTE6+kJrv+an4IlVF2UrdMq+qPTihIx3OonLtjrJWr33y8tqakS46P2hEYLftc
u6dBBWmv2BKApXifE1Br0zjnSpBtDaezp/2Xbe9YypI2AJsoeEs7DRK1R0tQqcMn
cw0M+Hj6HQKBgFvw3ztlobJCdJ6dX3NYD31fhvglRn8ffT/VANlcmwFQdVkBU1JN
G7BVEQ/EJRgUkH6vPkxq3myp0UAz2iLtjVkP7CoOfx0n2EcE/qeMzYK0oHjOsoxj
v+tGyzPniH23bq1sJzzwPQWe5oXq4HKAH8OTRGs0FdQGxVvfbVWr83S1AoGBALkQ
6jaWGdcKQdhMtJuUBX1N0QkWC1hUtnsUYUVpQkyR5KfTc+V/92Foc/+6Pu9/gpdD
ekXiTnlkn/K9H5NgX/yubZr6q/lmGpg0xCM1K0hSNjiqj7wSfI33iOntcENwmWcH
nVKZjSZw9vUDFWfb0ZKVybxviwKIsK1upyAuGYKdAoGAGofL3m88AlOxOuyMpAKT
NjWzJKosCNNtKo/tSMtA2D/64iCarODmpyDwACqf8PjK9xZLW/vveWjQq5DqwjC2
0mW5nNaAAAuHF4SCel5w0St+nWORqrLDUm2uMQl9u7Lxlw3ndJMssooohX5giY0G
47dJZ0LCu42gkiDyl4QDtAc=
-----END PRIVATE KEY-----
"""
client_email = "surveybusstop-sa@my-project05-465612.iam.gserviceaccount.com"
client_id = "110889601544152134220"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/surveybusstop-sa@my-project05-465612.iam.gserviceaccount.com"


# 🔑 IMPORTANT:
# Paste your Google Drive Shared Folder ID here in Streamlit secrets under key "gdrive_folder_id"
GDRIVE_CREDS = st.secrets["gdrive_service_account"]
GDRIVE_FOLDER_ID = GDRIVE_CREDS["gdrive_folder_id"]



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
    media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype)
    metadata = {"name": filename, "parents": [folder_id]}
    res = drive_service.files().create(
        body=metadata,
        media_body=media,
        fields="id, webViewLink",
        supportsAllDrives=True
    ).execute()
    return res.get("webViewLink"), res.get("id")

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
            sheet_id = find_or_create_gsheet("survey_responses", GDRIVE_FOLDER_ID)
            append_row_to_gsheet(sheet_id, row, header)

            # reset
            st.session_state.update({
                "condition":"1. Covered Bus Stop","activity_category":"", "specific_conditions":set(),
                "other_text":"", "photos":[], "show_success":True
            })
        except Exception as e:
            st.error(f"Failed to submit: {e}")

if st.session_state.show_success:
    placeholder = st.empty()
    placeholder.success("✅ Submitted successfully!")
    time.sleep(2)
    placeholder.empty()
    st.session_state.show_success = False

# keep session alive
st.components.v1.html(
    """
    <script>
      setInterval(()=>fetch('/_stcore/health'),300000);
    </script>
    """,
    height=0
)
