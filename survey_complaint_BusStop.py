import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import mimetypes
import time
import os
import pickle
from urllib.parse import urlencode

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

# --------- Page Setup ---------
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
st.title("Bus Stop Complaints Survey")

# --------- Enhanced "iPhone Style" Pill Button CSS ---------
st.markdown("""
    <style>
    div[role="radiogroup"] {
        display: flex;
        flex-direction: row;
        gap: 20px;
        background-color: transparent !important;
    }
    div[role="radiogroup"] label {
        padding: 10px 25px !important;
        border-radius: 50px !important; 
        border: 2px solid #d1d1d6 !important;
        background-color: white !important;
        transition: all 0.3s ease;
    }
    div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
        color: #333 !important;
        font-weight: bold !important;
        font-size: 16px !important;
    }
    div[role="radiogroup"] label:has(input[value="Yes"]):has(input:checked) {
        background-color: #28a745 !important; 
        border-color: #28a745 !important;
    }
    div[role="radiogroup"] label:has(input[value="Yes"]):has(input:checked) p {
        color: white !important;
    }
    div[role="radiogroup"] label:has(input[value="No"]):has(input:checked) {
        background-color: #dc3545 !important; 
        border-color: #dc3545 !important;
    }
    div[role="radiogroup"] label:has(input[value="No"]):has(input:checked) p {
        color: white !important;
    }
    div[role="radiogroup"] label:has(input[value="NA"]):has(input:checked) {
        background-color: #6c757d !important;
        border-color: #6c757d !important;
    }
    div[role="radiogroup"] label:has(input[value="NA"]):has(input:checked) p {
        color: white !important;
    }
    div[role="radiogroup"] [data-testid="stWidgetSelectionVisualizer"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --------- Google Drive Folder ID ---------
FOLDER_ID = "1DjtLxgyQXwgjq_N6I_-rtYcBcnWhzMGp"

# --------- OAuth Setup ---------
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]
CLIENT_SECRETS_FILE = "client_secrets2.json"

def save_credentials(credentials):
    with open("token.pickle", "wb") as token:
        pickle.dump(credentials, token)

def load_credentials():
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            return pickle.load(token)
    return None

def get_authenticated_service():
    creds = load_credentials()
    if creds and creds.valid:
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request()); save_credentials(creds)
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, 
                                       redirect_uri="https://bus-stop-survey-99f8wusughejfcfvrvxmyl.streamlit.app/")
    query_params = st.query_params
    if "code" in query_params:
        full_url = "https://bus-stop-survey-99f8wusughejfcfvrvxmyl.streamlit.app/?" + urlencode(query_params)
        flow.fetch_token(authorization_response=full_url)
        creds = flow.credentials; save_credentials(creds)
    else:
        auth_url, _ = flow.authorization_url(prompt="consent")
        st.markdown(f"[Authenticate here]({auth_url})"); st.stop()
    return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)

drive_service, sheets_service = get_authenticated_service()

def gdrive_upload_file(file_bytes, filename, mimetype, folder_id=None):
    media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype)
    metadata = {"name": filename}
    if folder_id: metadata["parents"] = [folder_id]
    uploaded = drive_service.files().create(body=metadata, media_body=media, fields="id, webViewLink", supportsAllDrives=True).execute()
    return uploaded["webViewLink"]

def find_or_create_gsheet(name, folder_id):
    query = f"'{folder_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.spreadsheet'"
    res = drive_service.files().list(q=query, fields="files(id)").execute()
    if res.get("files"): return res["files"][0]["id"]
    file = drive_service.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.spreadsheet", "parents": [folder_id]}, fields="id").execute()
    return file["id"]

def append_row(sheet_id, row, header):
    sheet = sheets_service.spreadsheets()
    existing = sheet.values().get(spreadsheetId=sheet_id, range="A1:A1").execute()
    if "values" not in existing:
        sheet.values().update(spreadsheetId=sheet_id, range="A1", valueInputOption="RAW", body={"values": [header]}).execute()
    sheet.values().append(spreadsheetId=sheet_id, range="A1", valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": [row]}).execute()

# --------- Load Excel ---------
routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")

# --------- Session State ---------
if "photos" not in st.session_state:
    st.session_state.photos = []

questions = [
    "1. BC menggunakan telefon bimbit?",
    "2. BC memperlahankan/memberhentikan bas?",
    "3. BC memandu di lorong 1 (kiri)?",
    "4. Bas penuh dengan penumpang?",
    "5. BC tidak mengambil penumpang?",
    "6. BC berlaku tidak sopan?"
]

if "kelakuan_kapten" not in st.session_state:
    st.session_state.kelakuan_kapten = {q: None for q in questions}

# --------- Staff ID ---------
staff_id = st.text_input("👤 Staff ID (8 digits)")

# --------- Depot / Route / Stop ---------
depot = st.selectbox("1️⃣ Depot", routes_df["Depot"].dropna().unique())
route = st.selectbox("2️⃣ Route Number", routes_df[routes_df["Depot"] == depot]["Route Number"].unique())
stops = stops_df[stops_df["Route Number"] == route]["Stop Name"].dropna()
stop = st.selectbox("3️⃣ Bus Stop", stops)

condition = st.selectbox("4️⃣ Bus Stop Condition", ["1. Covered Bus Stop", "2. Pole Only", "3. Layby", "4. Non-Infrastructure"])

# --------- Kelakuan Kapten Bas ---------
st.markdown("### 5️⃣ A. KELAKUAN KAPTEN BAS")

for i, q in enumerate(questions):
    st.write(f"**{q}**")
    options = ["Yes", "No", "NA"] if i >= 4 else ["Yes", "No"]
    
    choice = st.radio(
        label=q,
        options=options,
        index=None,
        key=f"q_radio_{i}",
        horizontal=True,
        label_visibility="collapsed"
    )
    st.session_state.kelakuan_kapten[q] = choice
    st.write("---")

# --------- Photos ---------
st.markdown("### 6️⃣ Photos (min 1, max 5)")
photo = st.file_uploader("Upload Photo", type=["jpg", "png", "jpeg"])
if photo and len(st.session_state.photos) < 5:
    st.session_state.photos.append(photo)

cols = st.columns(5)
for i, p in enumerate(st.session_state.photos):
    cols[i].image(p, caption=f"Photo {i+1}")

# --------- Submit ---------
if st.button("✅ Submit Survey"):
    if not staff_id.isdigit() or len(staff_id) != 8:
        st.warning("Staff ID must be 8 digits.")
    elif not st.session_state.photos:
        st.warning("At least one photo required.")
    elif None in st.session_state.kelakuan_kapten.values():
        st.warning("Please complete all Kelakuan Kapten Bas items.")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        photo_links = []
        for i, img in enumerate(st.session_state.photos):
            link = gdrive_upload_file(img.getvalue(), f"{timestamp}_{i}.jpg", "image/jpeg", FOLDER_ID)
            photo_links.append(link)

        # Separate each answer into its own list element
        answers = [st.session_state.kelakuan_kapten[q] for q in questions]

        # Construct Row: Basic Info + Each Answer + Photos
        row = [
            timestamp, 
            staff_id, 
            depot, 
            route, 
            stop, 
            condition
        ] + answers + ["; ".join(photo_links)]

        # Construct Header: Basic Titles + Question Titles + Photos
        header = [
            "Timestamp", 
            "Staff ID", 
            "Depot", 
            "Route", 
            "Bus Stop", 
            "Condition"
        ] + questions + ["Photos"]

        sheet_id = find_or_create_gsheet("survey_responses", FOLDER_ID)
        append_row(sheet_id, row, header)

        st.success("✅ Submission successful!")
        st.session_state.photos = []
        st.session_state.kelakuan_kapten = {q: None for q in questions}
        st.rerun()
