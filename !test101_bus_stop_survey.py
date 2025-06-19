import streamlit as st
import pandas as pd
from datetime import datetime
import os, json
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build

# --- App setup ---
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")

# --- Load config.json ---
CONFIG_PATH = "config.json"
if not os.path.exists(CONFIG_PATH):
    st.error("❗ Missing config.json")
    st.stop()
with open(CONFIG_PATH) as f:
    config = json.load(f)

GDRIVE_FOLDER_ID = config.get("gdrive_folder_id")
if not GDRIVE_FOLDER_ID:
    st.error("❗ 'gdrive_folder_id' not found in config.json")
    st.stop()

# --- Authenticate with service account ---
SERVICE_ACCOUNT_FILE = "service_account.json"
if not os.path.exists(SERVICE_ACCOUNT_FILE):
    st.error("❗ Missing service_account.json")
    st.stop()

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=["https://www.googleapis.com/auth/drive.file"]
)
drive_service = build("drive", "v3", credentials=credentials)

def upload_to_gdrive(file_path, filename):
    media = MediaFileUpload(file_path, resumable=True)
    file_metadata = {
        "name": filename,
        "parents": [GDRIVE_FOLDER_ID]
    }
    drive_service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()

# --- Diagnostics ---
st.write("Current working directory:", os.getcwd())
st.write("Loaded GDrive folder ID:", GDRIVE_FOLDER_ID)

# --- Ensure images directory exists ---
os.makedirs("images", exist_ok=True)

# --- Load Excel data ---
try:
    routes_df = pd.read_excel("!test101_bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("!test101_bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"❌ Error reading Excel: {e}")
    st.stop()

# --- Session state defaults ---
defaults = {
    "staff_id": "", "selected_depot": "", "selected_route": "", "selected_stop": "",
    "condition": "1. Covered Bus Stop", "activity_category": "",
    "specific_conditions": set(), "other_text": "", "photos": []
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# --- Survey inputs ---
staff = st.text_input("👤 Staff ID (8 digits)", st.session_state.staff_id)
if staff and (not staff.isdigit() or len(staff) != 8):
    st.warning("⚠️ ID must be exactly 8 digits")
st.session_state.staff_id = staff

depots = list(routes_df["Depot"].dropna().unique())
sel_depot = st.selectbox("1️⃣ Select Depot", depots,
    index=depots.index(st.session_state.selected_depot) if st.session_state.selected_depot in depots else 0)
st.session_state.selected_depot = sel_depot

routes = list(routes_df[routes_df["Depot"] == sel_depot]["Route Number"].dropna().unique())
sel_route = st.selectbox("2️⃣ Select Route Number", routes,
    index=routes.index(st.session_state.selected_route) if st.session_state.selected_route in routes else 0)
st.session_state.selected_route = sel_route

stops_filtered = stops_df[stops_df["Route Number"] == sel_route].dropna(subset=["Stop Name", "Order", "dr"]).sort_values(["dr","Order"])
stop_names = list(stops_filtered["Stop Name"])
sel_stop = st.selectbox("3️⃣ Select Bus Stop", stop_names,
    index=stop_names.index(st.session_state.selected_stop) if st.session_state.selected_stop in stop_names else 0)
st.session_state.selected_stop = sel_stop

cond_opts = ["1. Covered Bus Stop", "2. Pole Only", "3. Layby", "4. Non-Infrastructure"]
condition = st.selectbox("4️⃣ Bus Stop Condition", cond_opts, index=cond_opts.index(st.session_state.condition))
st.session_state.condition = condition

activity_opts = ["", "1. On Board in the Bus", "2. On Ground Location"]
activity = st.selectbox("5️⃣ Activity Category", activity_opts, index=activity_opts.index(st.session_state.activity_category))
st.session_state.activity_category = activity

onboard_opts = [f"{i}. ..." for i in range(1, 13)]
onground_opts = [f"{i}. ..." for i in range(1, 8)]
options = onboard_opts if activity.startswith("1.") else onground_opts if activity.startswith("2.") else []

if options:
    st.markdown("6️⃣ Select situational conditions")
    for opt in options:
        checked = opt in st.session_state.specific_conditions
        selected = st.checkbox(opt, value=checked, key=opt)
        if selected:
            st.session_state.specific_conditions.add(opt)
        elif checked:
            st.session_state.specific_conditions.remove(opt)

other_label = next((o for o in options if "Other" in o), None)
if other_label and other_label in st.session_state.specific_conditions:
    ot = st.text_area("📝 Describe 'Other' (≥2 words)", st.session_state.other_text)
    st.session_state.other_text = ot
    if len(ot.split()) < 2:
        st.warning("🚨 Use at least 2 words")

st.markdown("7️⃣ Add up to 5 photos")
while len(st.session_state.photos) < 5:
    new_photo = st.camera_input(f"📷 Photo #{len(st.session_state.photos)+1}")
    if new_photo:
        st.session_state.photos.append(new_photo)
    up_ph = st.file_uploader(f"📁 Upload photo #{len(st.session_state.photos)+1}", type=["jpg","jpeg","png"])
    if up_ph:
        st.session_state.photos.append(up_ph)

if st.session_state.photos:
    st.subheader("📸 Current photos")
    for idx, ph in enumerate(st.session_state.photos):
        c1, c2 = st.columns([4,1])
        c1.image(ph, caption=f"Photo #{idx+1}", use_container_width=True)
        if c2.button("❌ Delete", key=f"del_{idx}"):
            st.session_state.photos.pop(idx)
            st.experimental_rerun()

# --- Submission logic ---
if st.button("✅ Submit Survey"):
    if not staff or not staff.isdigit() or len(staff) != 8:
        st.warning("❗ Enter a valid Staff ID")
    elif not st.session_state.photos:
        st.warning("❗ Upload at least 1 photo")
    elif not activity:
        st.warning("❗ Choose Activity Category")
    elif other_label in st.session_state.specific_conditions and len(st.session_state.other_text.split()) < 2:
        st.warning("❗ 'Other' needs at least 2 words")
    else:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        img_files = []
        for i, ph in enumerate(st.session_state.photos):
            fn = f"{ts}_photo{i+1}.jpg"
            with open(os.path.join("images", fn), "wb") as f:
                f.write(ph.getbuffer())
            img_files.append(fn)

        conds = list(st.session_state.specific_conditions)
        if other_label in conds:
            conds.remove(other_label)
            conds.append(f"Other: {st.session_state.other_text}")

        record = {
            "Timestamp": ts, "Staff ID": staff,
            "Depot": sel_depot, "Route": sel_route, "Stop": sel_stop,
            "Condition": condition, "Activity": activity,
            "Specific Conditions": "; ".join(conds),
            "Photos": ";".join(img_files)
        }
        df = pd.DataFrame([record])
        CSV = "responses.csv"
        if os.path.exists(CSV):
            df = pd.concat([pd.read_csv(CSV), df], ignore_index=True)
        df.to_csv(CSV, index=False)

        # upload
        upload_to_gdrive(CSV, f"{ts}_response.csv")
        st.success("✅ Survey submitted!")
        st.session_state.update({k: defaults[k] for k in defaults})
        st.experimental_rerun()
