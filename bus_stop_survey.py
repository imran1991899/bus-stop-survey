import streamlit as st
import pandas as pd
from datetime import datetime
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# -----------------------
# CONFIG - Replace with your Google Sheet & Drive Folder IDs
GSHEET_ID = "https://docs.google.com/spreadsheets/d/15CEY68rIP4cjN8Cgqn6tRtLwIzOInTxd0_YQ804NSMo/edit?gid=0#gid=0"
GDRIVE_FOLDER_ID = "15CEY68rIP4cjN8Cgqn6tRtLwIzOInTxd0_YQ804NSMo"

# -----------------------
# Load Google Service Account credentials from Streamlit secrets
SERVICE_ACCOUNT_INFO = st.secrets["google_service_account"]
SCOPES = ['https://www.googleapis.com/auth/drive',
          'https://www.googleapis.com/auth/spreadsheets']

credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO, scopes=SCOPES)

# Build the service clients
drive_service = build('drive', 'v3', credentials=credentials)
sheets_service = build('sheets', 'v4', credentials=credentials)

# -----------------------
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="centered")
st.title("🚌 Bus Stop Assessment Survey")

# -----------------------
# Sample static data - you can replace with your Excel load or API call
depots = ["Depot A", "Depot B", "Depot C"]
routes = {
    "Depot A": ["Route 1", "Route 2"],
    "Depot B": ["Route 3"],
    "Depot C": ["Route 4", "Route 5"]
}
stops = {
    "Route 1": ["Stop 1", "Stop 2"],
    "Route 2": ["Stop 3"],
    "Route 3": ["Stop 4", "Stop 5"],
    "Route 4": ["Stop 6"],
    "Route 5": ["Stop 7", "Stop 8"]
}

selected_depot = st.selectbox("1️⃣ Select Depot", depots)
selected_route = st.selectbox("2️⃣ Select Route Number", routes[selected_depot])
selected_stop = st.selectbox("3️⃣ Select Bus Stop", stops[selected_route])
condition = st.selectbox("4️⃣ Bus Stop Condition", ["Pole", "Sheltered", "N/A"])

# Photo upload section with multiple photos allowed (max 5)
st.markdown("5️⃣ Take up to 5 photos (Camera only)")

if "photos" not in st.session_state:
    st.session_state.photos = []

def add_photo():
    if st.session_state.new_photo is not None and len(st.session_state.photos) < 5:
        st.session_state.photos.append(st.session_state.new_photo)
        st.session_state.new_photo = None

st.camera_input("Take a photo", key="new_photo", on_change=add_photo)

# Show photos taken with option to delete each
for i, photo in enumerate(st.session_state.photos):
    st.image(photo, use_container_width=True, caption=f"Photo {i+1}")
    if st.button(f"Delete Photo {i+1}", key=f"del_{i}"):
        st.session_state.photos.pop(i)
        st.experimental_rerun()

if len(st.session_state.photos) == 5:
    st.info("Maximum 5 photos reached.")

# Submit button logic
if st.button("✅ Submit Survey"):

    if len(st.session_state.photos) == 0:
        st.warning("Please take at least one photo before submitting.")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        responses = []

        # Upload photos to Google Drive
        photo_filenames = []
        for idx, photo in enumerate(st.session_state.photos):
            photo_bytes = photo.getvalue()
            file_name = f"{timestamp}_photo{idx+1}.jpg"

            file_metadata = {
                'name': file_name,
                'parents': [GDRIVE_FOLDER_ID]
            }

            media = MediaIoBaseUpload(io.BytesIO(photo_bytes), mimetype='image/jpeg')
            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            photo_filenames.append(file_name)

        # Prepare the row to append to Google Sheet
        new_row = [
            timestamp,
            selected_depot,
            selected_route,
            selected_stop,
            condition,
            ", ".join(photo_filenames)
        ]

        # Append data to Google Sheet
        sheets_service.spreadsheets().values().append(
            spreadsheetId=GSHEET_ID,
            range="Sheet1!A:F",
            valueInputOption="USER_ENTERED",
            body={"values": [new_row]}
        ).execute()

        # Clear photos after submit
        st.session_state.photos = []
        st.success("✔️ Your response and photos have been saved successfully!")
