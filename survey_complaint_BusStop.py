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

# --------- Google Drive Folder ID ---------
FOLDER_ID = "1DjtLxgyQXwgjq_N6I_-rtYcBcnWhzMGp"

# --------- OAuth Setup ---------
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]

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
        return (
            build("drive", "v3", credentials=creds),
            build("sheets", "v4", credentials=creds),
        )

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)
        return (
            build("drive", "v3", credentials=creds),
            build("sheets", "v4", credentials=creds),
        )

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri="https://bus-stop-survey-99f8wusughejfcfvrvxmyl.streamlit.app/",
    )

    query_params = st.query_params

    if "code" in query_params:
        base_url = "https://bus-stop-survey-99f8wusughejfcfvrvxmyl.streamlit.app/"
        full_url = base_url + "?" + urlencode(query_params)

        flow.fetch_token(authorization_response=full_url)
        creds = flow.credentials
        save_credentials(creds)
    else:
        auth_url, _ = flow.authorization_url(prompt="consent")
        st.markdown(f"[Authenticate here]({auth_url})")
        st.stop()

    return (
        build("drive", "v3", credentials=creds),
        build("sheets", "v4", credentials=creds),
    )


drive_service, sheets_service = get_authenticated_service()


def gdrive_upload_file(file_bytes, filename, mimetype, folder_id=None):
    media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype)
    metadata = {"name": filename}
    if folder_id:
        metadata["parents"] = [folder_id]

    uploaded = drive_service.files().create(
        body=metadata,
        media_body=media,
        fields="id, webViewLink",
        supportsAllDrives=True,
    ).execute()
    return uploaded["webViewLink"]


def find_or_create_gsheet(name, folder_id):
    query = (
        f"'{folder_id}' in parents and "
        f"name='{name}' and "
        "mimeType='application/vnd.google-apps.spreadsheet'"
    )

    res = drive_service.files().list(q=query, fields="files(id)").execute()
    if res.get("files"):
        return res["files"][0]["id"]

    file = drive_service.files().create(
        body={
            "name": name,
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": [folder_id],
        },
        fields="id",
    ).execute()
    return file["id"]


def append_row(sheet_id, row, header):
    sheet = sheets_service.spreadsheets()
    existing = sheet.values().get(
        spreadsheetId=sheet_id, range="A1:A1"
    ).execute()

    if "values" not in existing:
        sheet.values().update(
            spreadsheetId=sheet_id,
            range="A1",
            valueInputOption="RAW",
            body={"values": [header]},
        ).execute()

    sheet.values().append(
        spreadsheetId=sheet_id,
        range="A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


# --------- Load Excel ---------
routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")

# --------- Session State ---------
if "photos" not in st.session_state:
    st.session_state.photos = []

# New Questions List
questions = [
    "1. Adakah BC menggunakan telefon bimbit semasa pemanduan?",
    "2. Adakah BC memperlahankan dan/atau memberhentikan bas ketika menghampiri hentian bas?",
    "3. Adakah BC memandu di lorong 1 (kiri) ketika menghampiri hentian bas?",
    "4. Adakah bas penuh dengan penumpang semasa tiba di hentian?",
    "5. Adakah BC tidak mengambil penumpang di hentian bas (Jika tiada penumpang menunggu semasa pemerhatian, sila pilih 'NA')",
    "6. Adakah BC berlaku tidak sopan terhadap penumpang? (Jika tiada penumpang menunggu semasa pemerhatian, sila pilih 'NA')"
]

if "kelakuan_kapten" not in st.session_state:
    st.session_state.kelakuan_kapten = {q: None for q in questions}

# --------- Staff ID ---------
staff_id = st.text_input("👤 Staff ID (8 digits)")

# --------- Depot / Route / Stop ---------
depot = st.selectbox("1️⃣ Depot", routes_df["Depot"].dropna().unique())
route = st.selectbox(
    "2️⃣ Route Number",
    routes_df[routes_df["Depot"] == depot]["Route Number"].unique(),
)

stops = stops_df[stops_df["Route Number"] == route]["Stop Name"].dropna()
stop = st.selectbox("3️⃣ Bus Stop", stops)

# --------- Condition ---------
condition = st.selectbox(
    "4️⃣ Bus Stop Condition",
    [
        "1. Covered Bus Stop",
        "2. Pole Only",
        "3. Layby",
        "4. Non-Infrastructure",
    ],
)

# --------- Kelakuan Kapten Bas ---------
st.markdown("### 5️⃣ A. KELAKUAN KAPTEN BAS")

for i, q in enumerate(questions):
    st.write(f"**{q}**")
    
    # Questions 5 and 6 (index 4 and 5) get the NA option
    options = ["Yes", "No", "NA"] if i >= 4 else ["Yes", "No"]
    
    choice = st.radio(
        f"Select for Q{i}",
        options,
        index=None, 
        key=f"q_radio_{i}",
        horizontal=True,
        label_visibility="collapsed"
    )
    st.session_state.kelakuan_kapten[q] = choice

# --------- Photos ---------
st.markdown("### 6️⃣ Photos (min 1, max 5)")
photo = st.file_uploader("Upload Photo", type=["jpg", "png", "jpeg"])
if photo and len(st.session_state.photos) < 5:
    st.session_state.photos.append(photo)

for i, p in enumerate(st.session_state.photos):
    st.image(p, caption=f"Photo {i+1}")

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
            content = img.getvalue()
            link = gdrive_upload_file(
                content, f"{timestamp}_{i}.jpg", "image/jpeg", FOLDER_ID
            )
            photo_links.append(link)

        behaviour_text = "; ".join(
            f"{k}: {v}" for k, v in st.session_state.kelakuan_kapten.items()
        )

        row = [
            timestamp,
            staff_id,
            depot,
            route,
            stop,
            condition,
            behaviour_text,
            "; ".join(photo_links),
        ]

        header = [
            "Timestamp",
            "Staff ID",
            "Depot",
            "Route",
            "Bus Stop",
            "Condition",
            "Kelakuan Kapten Bas",
            "Photos",
        ]

        sheet_id = find_or_create_gsheet("survey_responses", FOLDER_ID)
        append_row(sheet_id, row, header)

        st.success("✅ Submission successful!")
        # Clear session state
        st.session_state.photos = []
        st.session_state.kelakuan_kapten = {q: None for q in questions}
        st.rerun()
