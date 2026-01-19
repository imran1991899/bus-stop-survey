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

if "driver_behaviour" not in st.session_state:
    st.session_state.driver_behaviour = {
        "Guna telefon bimbit semasa memandu": "",
        "Sikap terhadap pelanggan": "",
        "Bas penuh": "",
        "Kekeliruan hentian (hentian baru / papan tanda tidak jelas / tiang tercabut)": "",
        "Memandu secara selamat (kelajuan, brek, lorong)": "",
        "Berhenti sepenuhnya di hentian": "",
    }

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

# --------- Driver Behaviour ---------
st.markdown("### 5️⃣ TINGKAH LAKU PEMANDU")

for item in st.session_state.driver_behaviour:
    c1, c2, c3 = st.columns([6, 2, 2])
    c1.write(item)

    comply = c2.checkbox("Comply", key=f"{item}_c")
    not_comply = c3.checkbox("Not Comply", key=f"{item}_n")

    if comply:
        st.session_state.driver_behaviour[item] = "Comply"
        st.session_state[f"{item}_n"] = False
    elif not_comply:
        st.session_state.driver_behaviour[item] = "Not Comply"
        st.session_state[f"{item}_c"] = False
    else:
        st.session_state.driver_behaviour[item] = ""

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
    elif "" in st.session_state.driver_behaviour.values():
        st.warning("Please complete all Tingkah Laku Pemandu items.")
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
            f"{k}: {v}" for k, v in st.session_state.driver_behaviour.items()
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
            "Tingkah Laku Pemandu",
            "Photos",
        ]

        sheet_id = find_or_create_gsheet("survey_responses", FOLDER_ID)
        append_row(sheet_id, row, header)

        st.success("✅ Submission successful!")
        st.session_state.photos = []
        st.session_state.driver_behaviour = {
            k: "" for k in st.session_state.driver_behaviour
        }
