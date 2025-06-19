import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
import tempfile
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# --- Show current working directory ---
st.write("Current working directory:", os.getcwd())

# --- Load config.json ---
config_path = "config.json"
if not os.path.exists(config_path):
    st.error(f"❗ Missing config file: {config_path}")
    st.stop()

with open(config_path, "r") as f:
    config = json.load(f)

folder_id = config.get("gdrive_folder_id")
if not folder_id:
    st.error("❗ 'gdrive_folder_id' not found in config.json")
    st.stop()

st.write("Loaded gdrive_folder_id:", folder_id)

# --- Load service account JSON file ---
sa_path = "service_account.json"
if not os.path.exists(sa_path):
    st.error(f"❗ Missing service account JSON file: {sa_path}")
    st.stop()

with open(sa_path, "r") as f:
    sa_info = json.load(f)

# --- Initialize Google Drive client ---
@st.cache_resource
def init_drive():
    # Save service account JSON to temp file for PyDrive2
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp:
        json.dump(sa_info, tmp)
        tmp.flush()

        gauth = GoogleAuth()
        gauth.LoadServiceConfigFile(tmp.name)
        gauth.ServiceAuth()

        return GoogleDrive(gauth)

drive = init_drive()

def upload_to_gdrive(file_path, filename):
    file = drive.CreateFile({'title': filename, 'parents': [{'id': folder_id}]})
    file.SetContentFile(file_path)
    file.Upload()
    return file['id']

# --- Streamlit UI and logic below ---

st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
st.title("🚌 Bus Stop Assessment Survey")

os.makedirs("images", exist_ok=True)

# --- Load Excel data ---
try:
    routes_df = pd.read_excel("!test101_bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("!test101_bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"❌ Error loading Excel: {e}")
    st.stop()

# --- Initialize session state ---
defaults = {
    "staff_id": "", "selected_depot": "", "selected_route": "", "selected_stop": "",
    "condition": "1. Covered Bus Stop", "activity_category": "",
    "specific_conditions": set(), "other_text": "", "photos": []
}
for k, val in defaults.items():
    st.session_state.setdefault(k, val)

# --- Staff ID input ---
staff = st.text_input("👤 Staff ID (8 digits)", st.session_state.staff_id)
if staff and (not staff.isdigit() or len(staff) != 8):
    st.warning("⚠️ ID must be exactly 8 digits.")
st.session_state.staff_id = staff

# --- Depot / Route / Stop selectors ---
depots = list(routes_df["Depot"].dropna().unique())
sel_depot = st.selectbox(
    "1️⃣ Select Depot", depots,
    index=depots.index(st.session_state.selected_depot) if st.session_state.selected_depot in depots else 0
)
st.session_state.selected_depot = sel_depot

routes = list(routes_df[routes_df["Depot"] == sel_depot]["Route Number"].dropna().unique())
sel_route = st.selectbox(
    "2️⃣ Select Route Number", routes,
    index=routes.index(st.session_state.selected_route) if st.session_state.selected_route in routes else 0
)
st.session_state.selected_route = sel_route

stops_filtered = stops_df[stops_df["Route Number"] == sel_route].dropna(subset=["Stop Name", "Order", "dr"]).sort_values(by=["dr", "Order"])
stop_names = list(stops_filtered["Stop Name"])
sel_stop = st.selectbox(
    "3️⃣ Select Bus Stop", stop_names,
    index=stop_names.index(st.session_state.selected_stop) if st.session_state.selected_stop in stop_names else 0
)
st.session_state.selected_stop = sel_stop

# --- Condition and Activity ---
cond_opts = ["1. Covered Bus Stop", "2. Pole Only", "3. Layby", "4. Non-Infrastructure"]
condition = st.selectbox("4️⃣ Bus Stop Condition", cond_opts, index=cond_opts.index(st.session_state.condition))
st.session_state.condition = condition

activity_opts = ["", "1. On Board in the Bus", "2. On Ground Location"]
activity = st.selectbox("5️⃣ Activity Category", activity_opts, index=activity_opts.index(st.session_state.activity_category))
st.session_state.activity_category = activity

# --- Specific condition options ---
onboard_opts = [f"{i}. ..." for i in range(1, 13)]  # Replace with real descriptions
onground_opts = [f"{i}. ..." for i in range(1, 8)]  # Replace with real descriptions
options = onboard_opts if activity.startswith("1.") else onground_opts if activity.startswith("2.") else []

if options:
    st.markdown("6️⃣ Select situational conditions")
    for opt in options:
        checked = opt in st.session_state.specific_conditions
        val = st.checkbox(opt, value=checked, key=opt)
        if val:
            st.session_state.specific_conditions.add(opt)
        elif checked:
            st.session_state.specific_conditions.remove(opt)

other_label = next((o for o in options if "Other" in o), None)
if other_label and other_label in st.session_state.specific_conditions:
    ot = st.text_area("📝 Describe 'Other' (≥2 words)", st.session_state.other_text)
    st.session_state.other_text = ot
    if len(ot.split()) < 2:
        st.warning("🚨 Please use at least 2 words here.")

# --- Photos upload ---
st.markdown("7️⃣ Add up to 5 photos")
while len(st.session_state.photos) < 5:
    new_photo = st.camera_input(f"📷 Photo #{len(st.session_state.photos) + 1}")
    if new_photo:
        st.session_state.photos.append(new_photo)
    upload_photo = st.file_uploader(f"📁 Upload photo #{len(st.session_state.photos) + 1}", type=["png", "jpg", "jpeg"])
    if upload_photo:
        st.session_state.photos.append(upload_photo)

if st.session_state.photos:
    st.subheader("📸 Current photos")
    for idx, ph in enumerate(st.session_state.photos):
        col1, col2 = st.columns([4, 1])
        col1.image(ph, caption=f"Photo #{idx + 1}", use_container_width=True)
        if col2.button("❌ Delete", key=f"del_{idx}"):
            st.session_state.photos.pop(idx)
            st.experimental_rerun()

# --- Submission ---
if st.button("✅ Submit Survey"):
    # Validation
    if not staff or not staff.isdigit() or len(staff) != 8:
        st.warning("❗ Enter valid Staff ID.")
    elif not st.session_state.photos:
        st.warning("❗ At least 1 photo required.")
    elif not activity:
        st.warning("❗ Choose Activity Category.")
    elif other_label in st.session_state.specific_conditions and len(st.session_state.other_text.split()) < 2:
        st.warning("❗ 'Other' needs at least 2 words.")
    else:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        img_filenames = []
        for i, p in enumerate(st.session_state.photos):
            fn = f"{ts}_photo{i + 1}.jpg"
            with open(f"images/{fn}", "wb") as f:
                f.write(p.getbuffer())
            img_filenames.append(fn)

        conds = list(st.session_state.specific_conditions)
        if other_label in conds:
            conds.remove(other_label)
            conds.append(f"Other: {st.session_state.other_text}")

        record = {
            "Timestamp": ts, "Staff ID": staff,
            "Depot": sel_depot, "Route": sel_route, "Stop": sel_stop,
            "Condition": condition, "Activity": activity,
            "Specific Conditions": "; ".join(conds),
            "Photos": ";".join(img_filenames)
        }
        df = pd.DataFrame([record])

        # Write CSV file locally
        csv_fp = "responses.csv"
        if os.path.exists(csv_fp):
            existing_df = pd.read_csv(csv_fp)
            df = pd.concat([existing_df, df], ignore_index=True)
        df.to_csv(csv_fp, index=False)

        # Upload CSV to Google Drive
        upload_to_gdrive(csv_fp, f"{ts}_response.csv")

        st.success("✅ Submission complete!")

        # Reset session state
        st.session_state.update({k: defaults[k] for k in defaults})
        st.experimental_rerun()
