import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
import tempfile
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# ========== Google Drive Setup ==========
@st.cache_resource
def init_drive():
    service_account_info = json.loads(st.secrets["gdrive_service_account"])
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp:
        json.dump(service_account_info, tmp)
        tmp.flush()
        gauth = GoogleAuth()
        gauth.LoadServiceConfigFile(tmp.name)
        gauth.ServiceAuth()
        return GoogleDrive(gauth)

drive = init_drive()

def upload_to_gdrive(file_path, filename):
    folder_id = st.secrets["gdrive_folder_id"]
    file_drive = drive.CreateFile({'title': filename, 'parents': [{'id': folder_id}]})
    file_drive.SetContentFile(file_path)
    file_drive.Upload()
    return file_drive['id']

# ========== Page Setup ==========
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
st.title("🚌 Bus Stop Assessment Survey")

if not os.path.exists("images"):
    os.makedirs("images")

# ========== Load Excel ==========
try:
    routes_df = pd.read_excel("!test101_bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("!test101_bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"❌ Failed to load Excel file: {e}")
    st.stop()

# ========== State ==========
for key, default in {
    "staff_id": "", "selected_depot": "", "selected_route": "", "selected_stop": "",
    "specific_conditions": set(), "photos": [], "activity_category": "",
    "other_text": "", "condition": "1. Covered Bus Stop"
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ========== Inputs ==========
staff_id_input = st.text_input("👤 Staff ID (exactly 8 digits)", value=st.session_state.staff_id)
if staff_id_input and (not staff_id_input.isdigit() or len(staff_id_input) != 8):
    st.warning("⚠️ Staff ID must be exactly 8 numeric digits.")
st.session_state.staff_id = staff_id_input

depots = routes_df["Depot"].dropna().unique()
selected_depot = st.selectbox("1️⃣ Select Depot", depots, index=list(depots).index(st.session_state.selected_depot) if st.session_state.selected_depot in depots else 0)
st.session_state.selected_depot = selected_depot

filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
selected_route = st.selectbox("2️⃣ Select Route Number", filtered_routes, index=list(filtered_routes).index(st.session_state.selected_route) if st.session_state.selected_route in filtered_routes else 0)
st.session_state.selected_route = selected_route

filtered_stops_df = stops_df[stops_df["Route Number"] == selected_route].dropna(subset=["Stop Name", "Order", "dr"]).sort_values(by=["dr", "Order"])
filtered_stops = filtered_stops_df["Stop Name"].tolist()
if st.session_state.selected_stop not in filtered_stops:
    st.session_state.selected_stop = filtered_stops[0] if filtered_stops else ""
selected_stop = st.selectbox("3️⃣ Select Bus Stop", filtered_stops, index=filtered_stops.index(st.session_state.selected_stop) if st.session_state.selected_stop in filtered_stops else 0)
st.session_state.selected_stop = selected_stop

condition_options = ["1. Covered Bus Stop", "2. Pole Only", "3. Layby", "4. Non-Infrastructure"]
condition = st.selectbox("4️⃣ Bus Stop Condition", condition_options, index=condition_options.index(st.session_state.condition) if st.session_state.condition in condition_options else 0)
st.session_state.condition = condition

activity_cat_options = ["", "1. On Board in the Bus", "2. On Ground Location"]
activity_category = st.selectbox("5️⃣ Categorizing Activities", activity_cat_options, index=activity_cat_options.index(st.session_state.activity_category) if st.session_state.activity_category in activity_cat_options else 0)
st.session_state.activity_category = activity_category

onboard_options = [
    "1. Tiada penumpang menunggu", "2. Tiada isyarat (penumpang tidak menahan bas)", "3. Tidak berhenti/memperlahankan bas",
    "4. Salah tempat menunggu", "5. Bas penuh", "6. Mengejar masa waybill (punctuality)", "7. Kesesakan lalu lintas",
    "8. Kekeliruan laluan oleh pemandu baru", "9. Terdapat laluan tutup atas sebab tertentu (baiki jalan, pokok tumbang, lawatan delegasi dari luar negara)",
    "10. Hentian terlalu hampir simpang masuk, bas sukar kembali ke laluan asal", "11. Hentian berdekatan dengan traffic light", "12. Other (Please specify below)"
]
onground_options = [
    "1. Infrastruktur sudah tiada/musnah", "2. Terlindung oleh pokok", "3. Terhalang oleh kenderaan parkir",
    "4. Keadaan sekeliling tidak selamat tiada lampu", "5. Kedudukan bus stop kurang sesuai",
    "6. Perubahan nama hentian dengan bangunan sekeliling", "7. Other (Please specify below)"
]

options = onboard_options if activity_category == "1. On Board in the Bus" else onground_options if activity_category == "2. On Ground Location" else []
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

other_option_label = next((o for o in options if "Other" in o), None)
if other_option_label and other_option_label in st.session_state.specific_conditions:
    other_text = st.text_area("📝 Please describe the 'Other' condition (at least 2 words)", height=150, value=st.session_state.other_text)
    st.session_state.other_text = other_text
    if len(other_text.split()) < 2:
        st.warning("🚨 'Other' description must be at least 2 words.")
else:
    st.session_state.other_text = ""

# ========== Photo Input ==========
st.markdown("7️⃣ Add up to 5 Photos (Camera or Upload from device)")
if len(st.session_state.photos) < 5:
    photo = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos)+1}")
    if photo:
        st.session_state.photos.append(photo)
if len(st.session_state.photos) < 5:
    uploaded = st.file_uploader(f"📁 Upload Photo #{len(st.session_state.photos)+1}", type=["jpg", "jpeg", "png"])
    if uploaded:
        st.session_state.photos.append(uploaded)

if st.session_state.photos:
    st.subheader("📸 Saved Photos")
    for i, img in enumerate(st.session_state.photos):
        col1, col2 = st.columns([4, 1])
        col1.image(img, caption=f"Photo #{i+1}", use_container_width=True)
        if col2.button(f"❌ Delete Photo #{i+1}", key=f"del_{i}"):
            st.session_state.photos.pop(i)
            st.experimental_rerun()

# ========== Submit ==========
if st.button("✅ Submit Survey"):
    if not staff_id_input.strip():
        st.warning("❗ Please enter your Staff ID.")
    elif not (staff_id_input.isdigit() and len(staff_id_input) == 8):
        st.warning("❗ Staff ID must be exactly 8 digits.")
    elif not st.session_state.photos:
        st.warning("❗ At least one photo is required.")
    elif activity_category not in activity_cat_options[1:]:
        st.warning("❗ Please choose an Activity Category.")
    elif other_option_label in st.session_state.specific_conditions and len(st.session_state.other_text.split()) < 2:
        st.warning("❗ Please complete the 'Other' field with at least 2 words.")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        saved_photos = []

        for idx, p in enumerate(st.session_state.photos):
            filename = f"{timestamp}_photo{idx+1}.jpg"
            path = os.path.join("images", filename)
            with open(path, "wb") as f:
                f.write(p.getbuffer())
            saved_photos.append(filename)
            (path, filename)

        conds = list(st.session_state.specific_conditions)
        if other_option_label in conds:
            conds.remove(other_option_label)
            conds.append(f"Other: {st.session_state.other_text.replace(';', ',')}")

        data = pd.DataFrame([{
            "Timestamp": timestamp,
            "Staff ID": staff_id_input,
            "Depot": selected_depot,
            "Route Number": selected_route,
            "Bus Stop": selected_stop,
            "Condition": condition,
            "Activity Category": activity_category,
            "Specific Conditions": "; ".join(conds),
            "Photos": ";".join(saved_photos),
        }])

        csv_path = "responses.csv"
        if os.path.exists(csv_path):
            prev = pd.read_csv(csv_path)
            data = pd.concat([prev, data], ignore_index=True)
        data.to_csv(csv_path, index=False)

        # Upload CSV to Drive
        upload_to_gdrive(csv_path, f"{timestamp}_response.csv")

        st.success("✅ Submission complete! Thank you!")

        # Reset state
        st.session_state.selected_stop = filtered_stops[0] if filtered_stops else ""
        st.session_state.condition = "1. Covered Bus Stop"
        st.session_state.activity_category = ""
        st.session_state.specific_conditions = set()
        st.session_state.photos = []
        st.session_state.other_text = ""

# ========== Keep Session Alive ==========
st.components.v1.html("""
<script>
    function keepAlive() {
        fetch('/_stcore/health');
    }
    setInterval(keepAlive, 300000);
</script>
""")
