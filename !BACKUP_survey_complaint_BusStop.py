import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import mimetypes
import time
import os
import pickle
import re
from urllib.parse import urlencode
from PIL import Image, ImageDraw, ImageFont, ExifTags # Added ExifTags
import pytz 

# Essential Google API Imports
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

# --------- Timezone Setup ---------
KL_TZ = pytz.timezone('Asia/Kuala_Lumpur')

# --------- Page Setup ---------
st.set_page_config(page_title="Bus Stop Survey", layout="wide")

# --------- APPLE UI GRID THEME CSS ---------
st.markdown("""
    <style>
    .stApp {
        background-color: #F5F5F7 !important;
        color: #1D1D1F !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }
    .custom-spinner {
        padding: 20px;
        background-color: #FFF9F0;
        border: 2px solid #FFCC80;
        border-radius: 14px;
        color: #E67E22;
        text-align: center;
        font-weight: bold;
        margin-bottom: 20px;
    }
    div[role="radiogroup"] {
        background-color: #E3E3E8 !important; 
        padding: 6px !important; 
        border-radius: 14px !important;
        gap: 8px !important;
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        margin-top: 2px !important; 
        margin-bottom: 28px !important; 
        max-width: 360px; 
    }
    div.stButton > button {
        background-color: #007AFF !important;
        color: white !important;
        height: 60px !important;
        font-weight: 600 !important;
        border-radius: 16px !important;
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# --------- Helper: EXIF & WATERMARK ---------
def add_watermark(image_bytes, stop_name):
    img = Image.open(BytesIO(image_bytes))
    
    # --- Try to get EXIF Date Taken ---
    date_taken = None
    try:
        exif = img._getexif()
        if exif:
            for tag, value in exif.items():
                decoded = ExifTags.TAGS.get(tag, tag)
                if decoded == 'DateTimeOriginal':
                    # Format usually: YYYY:MM:DD HH:MM:SS
                    date_taken = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                    # Localize to KL if naive
                    if date_taken.tzinfo is None:
                        date_taken = KL_TZ.localize(date_taken)
                    break
    except Exception:
        pass

    # Fallback to current time if no EXIF found
    if not date_taken:
        date_taken = datetime.now(KL_TZ)

    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    
    # 2x Bigger Scale (16%)
    font_scale = int(w * 0.16) 
    
    time_str = date_taken.strftime("%I:%M %p")
    info_str = f"{date_taken.strftime('%d/%m/%y')} | {stop_name.upper()}"

    try:
        font_main = ImageFont.truetype("arialbd.ttf", font_scale)
        font_sub = ImageFont.truetype("arialbd.ttf", int(font_scale * 0.4))
    except:
        font_main = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    margin_left = int(w * 0.02)
    margin_bottom = int(h * 0.02)

    sub_bbox = font_sub.getbbox(info_str)
    main_bbox = font_main.getbbox(time_str)
    sub_height = sub_bbox[3] - sub_bbox[1]
    main_height = main_bbox[3] - main_bbox[1]

    y_pos_sub = h - margin_bottom - sub_height
    y_pos_main = y_pos_sub - main_height - 10 

    # Massive Orange Time, White Date/Stop
    draw.text((margin_left, y_pos_main), time_str, font=font_main, fill="orange")
    draw.text((margin_left, y_pos_sub), info_str, font=font_sub, fill="white")
    
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=95)
    return img_byte_arr.getvalue(), date_taken # Returning the detected date too

# --------- Google API Configuration ---------
# (Keep your existing FOLDER_ID, CLIENT_SECRETS, and API functions here...)
FOLDER_ID = "1DjtLxgyQXwgjq_N6I_-rtYcBcnWhzMGp"
CLIENT_SECRETS_FILE = "client_secrets2.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]

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
        creds.refresh(Request())
        save_credentials(creds)
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, 
                                       redirect_uri="https://bus-stop-survey-kwaazvrcnnrtfyniqjwzlc.streamlit.app/")
    query_params = st.query_params
    if "code" in query_params:
        full_url = "https://bus-stop-survey-kwaazvrcnnrtfyniqjwzlc.streamlit.app/?" + urlencode(query_params)
        flow.fetch_token(authorization_response=full_url)
        creds = flow.credentials
        save_credentials(creds)
    else:
        auth_url, _ = flow.authorization_url(prompt="consent")
        st.markdown(f"### Authentication Required\n[Please log in with Google]({auth_url})")
        st.stop()
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

# --------- Main App UI & Logic (Simplified for brevity) ---------
# ... [Keep your Data Preparation, staff_dict, and question lists here] ...

# [Note: Implementation of the Submit Button Logic with the new Date Detection]
if st.button("Submit Survey"):
    total_media = len(st.session_state.photos) + len(st.session_state.videos)
    if total_media != 3:
        st.error("Please provide 3 media items.")
    else:
        saving_placeholder = st.empty()
        saving_placeholder.info("Processing media EXIF data...")
        
        try:
            detected_dates = []
            media_urls = []
            
            for idx, p in enumerate(st.session_state.photos):
                processed_bytes, dt = add_watermark(p.getvalue(), stop)
                detected_dates.append(dt)
                url = gdrive_upload_file(processed_bytes, f"IMG_{idx}.jpg", "image/jpeg", FOLDER_ID)
                media_urls.append(url)
            
            # Use the date from the first photo as the "Actual Survey Date" in the sheet
            actual_survey_time = detected_dates[0].strftime("%Y-%m-%d %H:%M:%S") if detected_dates else datetime.now(KL_TZ).strftime("%Y-%m-%d %H:%M:%S")

            # Update row_data to include 'actual_survey_time' instead of 'now'
            # (Rest of your submission logic remains the same)
            st.success(f"Uploaded! Record timestamped as: {actual_survey_time}")
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")
