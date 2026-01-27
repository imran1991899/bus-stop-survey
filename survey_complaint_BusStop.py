import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import time
import os
import pickle
from urllib.parse import urlencode

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

# --------- Page Setup ---------
st.set_page_config(page_title="Bus Stop Survey", layout="centered")

# --------- APPLE UI / WHITE THEME CSS ---------
st.markdown("""
    <style>
    /* Global Background & Font */
    .stApp {
        background-color: #F5F5F7 !important;
        color: #1D1D1F !important;
    }

    /* Card Styling for Sections */
    div[data-testid="stVerticalBlock"] > div {
        background-color: transparent;
    }
    
    /* Input & Select Box Styling */
    .stSelectbox, .stTextInput, .stFileUploader {
        background-color: white;
        border-radius: 12px;
    }

    /* Radio Button Containers (The Apple Segmented Control look) */
    div[role="radiogroup"] {
        background-color: #E8E8ED !important;
        padding: 4px !important;
        border-radius: 12px !important;
        gap: 4px !important;
    }

    /* Hide standard radio circles */
    [data-testid="stWidgetSelectionVisualizer"] {
        display: none !important;
    }

    /* Radio Individual Labels */
    div[role="radiogroup"] label {
        background-color: transparent !important;
        border: none !important;
        padding: 8px 20px !important;
        border-radius: 9px !important;
        transition: all 0.2s ease-in-out !important;
        flex: 1;
        justify-content: center;
        margin: 0 !important;
    }

    /* Hover effect */
    div[role="radiogroup"] label:hover {
        background-color: rgba(255, 255, 255, 0.4) !important;
    }

    /* Selected State: Apple White Segment */
    div[role="radiogroup"] label:has(input:checked) {
        background-color: white !important;
        box-shadow: 0px 3px 8px rgba(0,0,0,0.12) !important;
    }
    
    div[role="radiogroup"] label:has(input:checked) p {
        color: #007AFF !important; /* Apple Blue */
        font-weight: 600 !important;
    }

    /* Buttons */
    div.stButton > button {
        background-color: #007AFF !important;
        color: white !important;
        border-radius: 12px !important;
        border: none !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        width: 100%;
        transition: transform 0.1s active;
    }
    
    div.stButton > button:hover {
        background-color: #0062CC !important;
    }

    /* Info Boxes */
    div[data-testid="stMetricValue"] {
        background-color: white;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    
    /* Headers */
    h1, h2, h3 {
        font-weight: 700 !important;
        letter-spacing: -0.5px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# (Keep your existing Google Auth and Logic functions here...)
# [AUTHENTICATION FUNCTIONS REMAIN UNCHANGED]

st.title("🚌 Bus Stop Survey")
st.caption("Internal reporting tool for bus stop compliance and safety.")

# --------- Staff & Bus Stop Selection ---------
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        staff_id = st.selectbox("👤 Staff ID", options=["10005475", "10020779", "10014181"], index=None)
    with col2:
        stop = st.selectbox("📍 Bus Stop", ["AJ106 LRT AMPANG", "DAMANSARA INTAN", "ECOSKY RESIDENCE"], index=None)

if stop:
    st.info(f"**Route:** 123 | **Depot:** KEPONG")

st.divider()

# --------- Survey Questions ---------
def render_question(q, options):
    st.write(f"**{q}**")
    return st.radio(label=q, options=options, index=None, key=f"key_{q}", horizontal=True, label_visibility="collapsed")

st.subheader("Section A: Driver Behavior")
q_a_1 = render_question("1. Driver used mobile phone?", ["Yes", "No"])
q_a_2 = render_question("2. Driver slowed down correctly?", ["Yes", "No"])

st.subheader("Section B: Stop Condition")
q_b_1 = render_question("3. Is the stop obstructed?", ["Yes", "No", "NA"])

st.divider()

# --------- Camera Section ---------
st.subheader("📸 Media Evidence")
# (Your existing photo logic here)
st.camera_input("Take a photo")

if st.button("Submit Report"):
    st.balloons()
    st.success("Report submitted to cloud.")
