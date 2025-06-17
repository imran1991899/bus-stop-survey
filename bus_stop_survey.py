import streamlit as st
import pandas as pd
from datetime import datetime
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

# ========== Google Drive Setup ==========

SCOPES = ['https://www.googleapis.com/auth/drive.file']
CREDENTIALS_FILE = "credentials.json"
TOKEN_PICKLE = "token.pkl"
UPLOAD_FOLDER_ID = "YOUR_FOLDER_ID_HERE"  # Replace with your Drive folder ID


def get_drive_service():
    creds = None
    if os.path.exists(TOKEN_PICKLE):
        with open(TOKEN_PICKLE, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PICKLE, 'wb') as token:
            pickle.dump(creds, token)
    service = build('drive', 'v3', credentials=creds)
    return service


def upload_file_to_drive(file_path, file_name, folder_id=None):
    service = get_drive_service()
    file_metadata = {'name': file_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]
    media = MediaFileUpload(file_path, resumable=True)
    uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return uploaded_file.get('id')


# ========== Streamlit App ==========

st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
st.title("🚌 Bus Stop Assessment Survey")

# Create images folder if not exists (for temp storage)
if not os.path.exists("images"):
    os.makedirs("images")

# Load depot/route/stop info from Excel
try:
    routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"❌ Failed to load Excel file: {e}")
    st.stop()

# Staff ID input
if "staff_id" not in st.session_state:
    st.session_state.staff_id = ""

staff_id_input = st.text_input("👤 Staff ID (numbers only)", value=st.session_state.staff_id, key="staff_id")

if staff_id_input and not staff_id_input.isdigit():
    st.warning("⚠️ Staff ID must contain numbers only.")

depots = routes_df["Depot"].dropna().unique()
selected_depot = st.selectbox("1️⃣ Select Depot", depots)

filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
selected_route = st.selectbox("2️⃣ Select Route Number", filtered_routes)

filtered_stops = stops_df[stops_df["Route Number"] == selected_route]["Stop Name"].dropna().unique()
selected_stop = st.selectbox("3️⃣ Select Bus Stop", filtered_stops)

condition = st.selectbox("4️⃣ Bus Stop Condition", [
    "1. Covered Bus Stop",
    "2. Pole Only",
    "3. Layby",
    "4. Non-Infrastructure"
])

activity_category = st.selectbox("4️⃣➕ Categorizing Activities", [
    "1. On Board in the Bus",
    "2. On Ground Location"
])

onboard_options = [
    "1. Tiada penumpang menunggu",
    "2. Tiada isyarat (penumpang tidak menahan bas)",
    "3. Tidak berhenti/memperlahankan bas",
    "4. Salah tempat menunggu",
    "5. Bas penuh",
    "6. Mengejar masa waybill (punctuality)",
    "7. Kesesakan lalu lintas",
    "8. Kekeliruan laluan oleh pemandu baru",
    "9. Terdapat laluan tutup atas sebab tertentu (baiki jalan, pokok tumbang, lawatan delegasi dari luar negara)",
    "10. Hentian terlalu hampir simpang masuk, bas sukar kembali ke laluan asal",
    "11. Hentian berdekatan dengan traffic light",
    "12. Other (Please specify below)"
]

onground_options = [
    "1. Infrastruktur sudah tiada/musnah",
    "2. Terlindung oleh pokok",
    "3. Terhalang oleh kenderaan parkir",
    "4. Keadaan sekeliling tidak selamat tiada lampu",
    "5. Kedudukan bus stop kurang sesuai",
    "6. Perubahan nama hentian dengan bangunan sekeliling",
    "7. Other (Please specify below)"
]

specific_conditions_options = onboard_options if activity_category == "1. On Board in the Bus" else onground_options

st.markdown("5️⃣ Specific Situational Conditions (Select all that apply)")

if "specific_conditions" not in st.session_state:
    st.session_state.specific_conditions = set()

for option in specific_conditions_options:
    checked = option in st.session_state.specific_conditions
    new_checked = st.checkbox(option, value=checked, key=option)
    if new_checked and not checked:
        st.session_state.specific_conditions.add(option)
    elif not new_checked and checked:
        st.session_state.specific_conditions.remove(option)

other_text = ""
other_option_label = next((opt for opt in specific_conditions_options if "Other" in opt), None)
if other_option_label and other_option_label in st.session_state.specific_conditions:
    other_text = st.text_area("📝 Please describe the 'Other' condition (at least 2 words)", height=150)
    word_count = len(other_text.split())
    if word_count < 2:
        st.warning(f"🚨 You have written {word_count} word(s). Please write at least 2 words.")

if "photos" not in st.session_state:
    st.session_state.photos = []
if "last_photo" not in st.session_state:
    st.session_state.last_photo = None

st.markdown("6️⃣ Add up to 5 Photos (Camera Only)")
if len(st.session_state.photos) < 5:
    last_photo = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos) + 1}")
    if last_photo is not None:
        st.session_state.last_photo = last_photo

if st.session_state.last_photo is not None:
    st.session_state.photos.append(st.session_state.last_photo)
    st.session_state.last_photo = None

if st.session_state.photos:
    st.subheader("📸 Saved Photos")
    to_delete = None
    for i, img in enumerate(st.session_state.photos):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.image(img, caption=f"Photo #{i + 1}", use_container_width=True)
        with col2:
            if st.button(f"❌ Delete Photo #{i + 1}", key=f"delete_{i}"):
                to_delete = i
    if to_delete is not None:
        del st.session_state.photos[to_delete]

# --- Submit Button ---

if st.button("✅ Submit Survey"):

    if not staff_id_input.strip():
        st.warning("❗ Please enter your Staff ID.")
    elif not staff_id_input.isdigit():
        st.warning("❗ Staff ID must contain numbers only.")
    elif len(st.session_state.photos) == 0:
        st.warning("❗ Please take at least one photo before submitting.")
    elif other_option_label in st.session_state.specific_conditions and len(other_text.split()) < 2:
        st.warning("❗ 'Other' response must be at least 2 words.")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        photo_drive_links = []

        # Save photos temporarily and upload to Drive
        for idx, photo in enumerate(st.session_state.photos):
            photo_filename = f"{timestamp}_photo{idx + 1}.jpg"
            local_photo_path = os.path.join("images", photo_filename)
            with open(local_photo_path, "wb") as f:
                f.write(photo.getbuffer())
            try:
                photo_id = upload_file_to_drive(local_photo_path, photo_filename, folder_id=UPLOAD_FOLDER_ID)
                photo_drive_links.append(f"https://drive.google.com/file/d/{photo_id}/view")
            except Exception as e:
                st.error(f"Failed to upload photo {photo_filename} to Google Drive: {e}")
                st.stop()

        # Prepare specific conditions list
        specific_conditions_list = list(st.session_state.specific_conditions)
        if other_option_label in specific_conditions_list:
            specific_conditions_list.remove(other_option_label)
            specific_conditions_list.append(f"Other: {other_text.replace(';', ',')}")

        response = pd.DataFrame([{
            "Timestamp": timestamp,
            "Staff ID": staff_id_input,
            "Depot": selected_depot,
            "Route Number": selected_route,
            "Bus Stop": selected_stop,
            "Condition": condition,
            "Activity Category": activity_category,
            "Specific Conditions": "; ".join(specific_conditions_list),
            "Photo Links": "; ".join(photo_drive_links)
        }])

        # Save response CSV locally and upload to Drive
        csv_filename = f"survey_response_{timestamp}.csv"
        local_csv_path = os.path.join("images", csv_filename)
        response.to_csv(local_csv_path, index=False)

        try:
            upload_file_to_drive(local_csv_path, csv_filename, folder_id=UPLOAD_FOLDER_ID)
        except Exception as e:
            st.error(f"Failed to upload CSV response to Google Drive: {e}")
            st.stop()

        st.success("✅ Done! Your survey and photos have been uploaded to Google Drive.")

        # Reset session state except staff_id
        st.session_state.photos = []
        st.session_state.last_photo = None
        st.session_state.specific_conditions = set()


# --- Admin Section (Local CSV only, since Drive upload replaces local) ---
st.divider()
if st.checkbox("📋 Show all responses"):
    st.info("Responses are saved on Google Drive. Download from there.")

if st.checkbox("⬇️ Download responses as CSV"):
    st.info("Responses saved directly to Google Drive. Download from there.")

