import streamlit as st
import pandas as pd
from datetime import datetime
from PIL import Image
import os

# Set up Streamlit UI
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="centered")
st.title("🚌 Bus Stop Assessment Survey")

# Create folders if needed
if not os.path.exists("images"):
    os.makedirs("images")

# Load depot/route/stop info from Excel
try:
    routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"❌ Failed to load Excel file: {e}")
    st.stop()

# Question 1: Select Depot
depots = routes_df["Depot"].dropna().unique()
selected_depot = st.selectbox("1️⃣ Select Depot", depots)

# Question 2: Select Route under selected depot
filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
selected_route = st.selectbox("2️⃣ Select Route Number", filtered_routes)

# Question 3: Select Stop under selected route
filtered_stops = stops_df[stops_df["Route Number"] == selected_route]["Stop Name"].dropna().unique()
selected_stop = st.selectbox("3️⃣ Select Bus Stop", filtered_stops)

# Question 4: Select Condition
condition = st.selectbox("4️⃣ Bus Stop Condition", ["Pole", "Sheltered", "N/A"])

# Question 5: Photo Upload
st.markdown("5️⃣ Upload Bus Stop Photo")
photo_option = st.radio("Choose input method:", ["📷 Take Photo", "🖼 Upload from Gallery"])

camera_photo = None
gallery_upload = None
image_filename = ""

if photo_option == "📷 Take Photo":
    camera_photo = st.camera_input("Take a photo")
elif photo_option == "🖼 Upload from Gallery":
    gallery_upload = st.file_uploader("Choose photo", type=["jpg", "jpeg", "png"])

# Submit Button
if st.button("✅ Submit Survey"):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Save image
    if camera_photo:
        image_filename = f"{timestamp}_camera.jpg"
        with open(os.path.join("images", image_filename), "wb") as f:
            f.write(camera_photo.getbuffer())
    elif gallery_upload:
        image_filename = f"{timestamp}_{gallery_upload.name.replace(' ', '_')}"
        with open(os.path.join("images", image_filename), "wb") as f:
            f.write(gallery_upload.getbuffer())

    # Create record
    response = pd.DataFrame([{
        "Timestamp": timestamp,
        "Depot": selected_depot,
        "Route Number": selected_route,
        "Bus Stop": selected_stop,
        "Condition": condition,
        "Photo Filename": image_filename
    }])

    # Save to CSV
    if os.path.exists("responses.csv"):
        existing = pd.read_csv("responses.csv")
        updated = pd.concat([existing, response], ignore_index=True)
    else:
        updated = response

    updated.to_csv("responses.csv", index=False)
    st.success("✔️ Your response has been recorded!")

    # Preview image
    if camera_photo:
        st.image(camera_photo, caption="📸 Camera Photo", use_column_width=True)
    elif gallery_upload:
        st.image(gallery_upload, caption="🖼 Uploaded Photo", use_column_width=True)

# Admin Tools
st.divider()

if st.checkbox("📋 Show all responses"):
    if os.path.exists("responses.csv"):
        df = pd.read_csv("responses.csv")
        st.dataframe(df)
    else:
        st.info("No responses yet.")

if st.checkbox("⬇️ Download responses as CSV"):
    if os.path.exists("responses.csv"):
        df = pd.read_csv("responses.csv")
        st.download_button("Download CSV", df.to_csv(index=False), file_name="bus_stop_responses.csv") 
