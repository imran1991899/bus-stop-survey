import streamlit as st
import os
import json
import tempfile
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# --- Load config from JSON file ---
CONFIG_PATH = "config.json"  # put your gdrive_folder_id here

if not os.path.exists(CONFIG_PATH):
    st.error(f"Missing config file: {CONFIG_PATH}")
    st.stop()

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

if "gdrive_folder_id" not in config:
    st.error("Missing 'gdrive_folder_id' in config.json")
    st.stop()

GDRIVE_FOLDER_ID = config["gdrive_folder_id"]
st.write("Loaded GDrive folder ID:", GDRIVE_FOLDER_ID)

# --- Authenticate with Google Drive using service account JSON ---

SERVICE_ACCOUNT_FILE = "service_account.json"
if not os.path.exists(SERVICE_ACCOUNT_FILE):
    st.error(f"Missing service account JSON file: {SERVICE_ACCOUNT_FILE}")
    st.stop()

@st.cache_resource
def init_drive():
    gauth = GoogleAuth()
    gauth.service_account_file = SERVICE_ACCOUNT_FILE
    gauth.ServiceAuth()  # authenticate using service account
    return GoogleDrive(gauth)

drive = init_drive()

def upload_to_gdrive(file_path, filename):
    file = drive.CreateFile({
        'title': filename,
        'parents': [{'id': GDRIVE_FOLDER_ID}]
    })
    file.SetContentFile(file_path)
    file.Upload()
    return file['id']

# --- Streamlit UI ---
st.title("Bus Stop Survey")

# Initialize photos list in session state
if "photos" not in st.session_state:
    st.session_state.photos = []

# Example inputs (adjust as needed)
staff_id = st.text_input("👤 Staff ID (8 digits)")
depot = st.selectbox("1️⃣ Select Depot", ["Cheras Selatan", "Depot 2", "Depot 3"])
route_number = st.selectbox("2️⃣ Select Route Number", ["641", "642", "643"])
bus_stop = st.selectbox("3️⃣ Select Bus Stop", ["SJ63 LRT SUBANG JAYA", "Stop 2", "Stop 3"])
bus_stop_condition = st.selectbox("4️⃣ Bus Stop Condition", ["Covered Bus Stop", "Open Bus Stop"])
activity_category = st.selectbox("5️⃣ Activity Category", ["Category 1", "Category 2"])

# --- Photos upload section ---
st.markdown("7️⃣ Add up to 5 photos")

# Show existing photos count
st.write(f"Photos added: {len(st.session_state.photos)} / 5")

for i in range(5 - len(st.session_state.photos)):
    cam_key = f"cam_{len(st.session_state.photos)}"
    upl_key = f"upl_{len(st.session_state.photos)}"

    new_photo = st.camera_input(f"📷 Photo #{len(st.session_state.photos) + 1}", key=cam_key)
    if new_photo:
        st.session_state.photos.append(new_photo)
        continue  # move to next iteration

    upload_photo = st.file_uploader(f"📁 Upload photo #{len(st.session_state.photos) + 1}",
                                    type=["png", "jpg", "jpeg"], key=upl_key)
    if upload_photo:
        st.session_state.photos.append(upload_photo)

# Show thumbnails for uploaded photos
if st.session_state.photos:
    st.markdown("### Uploaded Photos Preview:")
    for idx, photo in enumerate(st.session_state.photos):
        st.image(photo, caption=f"Photo #{idx + 1}", width=200)

# --- Submit button ---
if st.button("Submit Survey"):
    if not staff_id or len(st.session_state.photos) == 0:
        st.error("Please enter Staff ID and upload at least one photo before submitting.")
    else:
        # Save photos temporarily and upload to Google Drive
        for idx, photo in enumerate(st.session_state.photos):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(photo.getbuffer())
                tmp_path = tmp.name
            gdrive_file_id = upload_to_gdrive(tmp_path, f"bus_stop_photo_{staff_id}_{idx+1}.jpg")
            os.unlink(tmp_path)
            st.write(f"Uploaded Photo #{idx+1} to GDrive with ID: {gdrive_file_id}")

        st.success("Survey submitted successfully!")
        st.session_state.photos.clear()  # clear photos after submit
