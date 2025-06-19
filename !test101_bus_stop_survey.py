import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import tempfile
import os

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# --------- Page Setup ---------
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
st.title("🚌 Bus Stop Assessment Survey")

# --------- Google Drive Auth ---------
@st.cache_resource
def init_drive():
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile("mycreds.txt")
    if gauth.credentials is None:
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()
    gauth.SaveCredentialsFile("mycreds.txt")
    return GoogleDrive(gauth)

drive = init_drive()

# --------- Google Drive File Upload ---------
def upload_to_drive(filename, content_bytes):
    tmp_path = os.path.join(tempfile.gettempdir(), filename)
    with open(tmp_path, "wb") as f:
        f.write(content_bytes)

    file_drive = drive.CreateFile({'title': filename})
    file_drive.SetContentFile(tmp_path)
    file_drive.Upload()

    file_drive.InsertPermission({
        'type': 'anyone',
        'value': 'anyone',
        'role': 'reader'
    })

    return file_drive['alternateLink']

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
    "photos": []
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
    (stops_df["Route Number"] == selected_route)
    & stops_df["Stop Name"].notna()
    & stops_df["Order"].notna()
    & stops_df["dr"].notna()
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
    "1. Tiada penumpang menunggu", "2. Tiada isyarat (penumpang tidak menahan bas)",
    "3. Tidak berhenti/memperlahankan bas", "4. Salah tempat menunggu", "5. Bas penuh",
    "6. Mengejar masa waybill (punctuality)", "7. Kesesakan lalu lintas",
    "8. Kekeliruan laluan oleh pemandu baru",
    "9. Terdapat laluan tutup atas sebab tertentu (baiki jalan, pokok tumbang, lawatan delegasi)",
    "10. Hentian terlalu hampir simpang masuk", "11. Hentian berdekatan dengan traffic light",
    "12. Other (Please specify below)",
]
onground_options = [
    "1. Infrastruktur sudah tiada/musnah", "2. Terlindung oleh pokok",
    "3. Terhalang oleh kenderaan parkir", "4. Keadaan sekeliling tidak selamat tiada lampu",
    "5. Kedudukan bus stop kurang sesuai", "6. Perubahan nama hentian",
    "7. Other (Please specify below)",
]

options = onboard_options if activity_category == "1. On Board in the Bus" else (
    onground_options if activity_category == "2. On Ground Location" else [])

if options:
    st.markdown("6️⃣ Specific Situational Conditions (Select all that apply)")
    st.session_state.specific_conditions = {c for c in st.session_state.specific_conditions if c in options}
    for opt in options:
        checked = opt in st.session_state.specific_conditions
        new_checked = st.checkbox(opt, value=checked, key=opt)
        if new_checked:
            st.session_state.specific_conditions.add(opt)
        else:
            st.session_state.specific_conditions.discard(opt)
else:
    st.info("Please select an Activity Category above to see situational conditions.")

# --------- 'Other' Description ---------
other_label = next((opt for opt in options if "Other" in opt), None)
if other_label and other_label in st.session_state.specific_conditions:
    other_text = st.text_area("📝 Please describe the 'Other' condition (at least 2 words)",
                              height=150, value=st.session_state.other_text)
    st.session_state.other_text = other_text
    if len(other_text.split()) < 2:
        st.warning("🚨 'Other' description must be at least 2 words.")
else:
    st.session_state.other_text = ""

# --------- Photo Upload ---------
st.markdown("7️⃣ Add up to 5 Photos (Camera or Upload from device)")
if len(st.session_state.photos) < 5:
    photo = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos) + 1}")
    if photo:
        st.session_state.photos.append(photo)

if len(st.session_state.photos) < 5:
    upload_photo = st.file_uploader(f"📁 Upload Photo #{len(st.session_state.photos) + 1}", type=["png", "jpg", "jpeg"])
    if upload_photo:
        st.session_state.photos.append(upload_photo)

if st.session_state.photos:
    st.subheader("📸 Saved Photos")
    to_delete = None
    for i, p in enumerate(st.session_state.photos):
        cols = st.columns([4, 1])
        cols[0].image(p, caption=f"Photo #{i + 1}", use_container_width=True)
        if cols[1].button(f"❌ Delete #{i + 1}", key=f"del_{i}"):
            to_delete = i
    if to_delete is not None:
        st.session_state.photos.pop(to_delete)

# --------- Submit Button ---------
if st.button("✅ Submit Survey"):
    if not staff_id.strip():
        st.warning("❗ Please enter your Staff ID.")
    elif not (staff_id.isdigit() and len(staff_id) == 8):
        st.warning("❗ Staff ID must be exactly 8 numeric digits.")
    elif not st.session_state.photos:
        st.warning("❗ Please add at least one photo.")
    elif activity_category not in ["1. On Board in the Bus", "2. On Ground Location"]:
        st.warning("❗ Please select an Activity Category.")
    elif other_label in st.session_state.specific_conditions and len(st.session_state.other_text.split()) < 2:
        st.warning("❗ 'Other' description must be at least 2 words.")
    else:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            photo_links = []
            for idx, img in enumerate(st.session_state.photos):
                filename = f"{timestamp}_photo{idx+1}.jpg"
                content = img.read() if isinstance(img, BytesIO) else img.getbuffer()
                link = upload_to_drive(filename, content)
                photo_links.append(link)

            cond_list = list(st.session_state.specific_conditions)
            if other_label in cond_list:
                cond_list.remove(other_label)
                cond_list.append(f"Other: {st.session_state.other_text.replace(';', ',')}")

            row = [
                timestamp, staff_id, selected_depot, selected_route, selected_stop,
                condition, activity_category, "; ".join(cond_list), "; ".join(photo_links)
            ]
            df = pd.DataFrame([row], columns=[
                "Timestamp", "Staff ID", "Depot", "Route", "Bus Stop",
                "Condition", "Activity", "Situational Conditions", "Photos"
            ])

            # Try loading existing Drive CSV
            csv_filename = "survey_responses.csv"
            csv_path = os.path.join(tempfile.gettempdir(), csv_filename)

            existing_files = drive.ListFile({'q': f"title='{csv_filename}'"}).GetList()
            if existing_files:
                existing_file = existing_files[0]
                existing_file.GetContentFile(csv_path)
                existing_df = pd.read_csv(csv_path)
                df = pd.concat([existing_df, df], ignore_index=True)

            df.to_csv(csv_path, index=False)
            with open(csv_path, "rb") as f:
                upload_to_drive(csv_filename, f.read())

            st.success("✅ Submission complete! Thank you.")
            st.session_state.update({
                "selected_depot": selected_depot,
                "selected_route": selected_route,
                "selected_stop": filtered_stops[0] if filtered_stops else "",
                "condition": "1. Covered Bus Stop",
                "activity_category": "",
                "specific_conditions": set(),
                "other_text": "",
                "photos": []
            })
        except Exception as e:
            st.error(f"❌ Failed to submit: {e}")

# --------- Keep Session Alive ---------
st.components.v1.html("""
<script>
    setInterval(() => {
        fetch('/_stcore/health');
    }, 300000);
</script>
""", height=0)
