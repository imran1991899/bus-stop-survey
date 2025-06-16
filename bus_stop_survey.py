import streamlit as st
import pandas as pd
from datetime import datetime
import os

# Setup page
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="centered")
st.title("🚌 Bus Stop Assessment Survey")

# Create images folder if not exists
if not os.path.exists("images"):
    os.makedirs("images")

# Load Excel data
try:
    routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"❌ Failed to load Excel file: {e}")
    st.stop()

# Question 1: Depot selection
depots = routes_df["Depot"].dropna().unique()
selected_depot = st.selectbox("1️⃣ Select Depot", depots)

# Question 2: Routes filtered by depot
filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
selected_route = st.selectbox("2️⃣ Select Route Number", filtered_routes)

# Question 3: Stops filtered by route
filtered_stops = stops_df[stops_df["Route Number"] == selected_route]["Stop Name"].dropna().unique()
selected_stop = st.selectbox("3️⃣ Select Bus Stop", filtered_stops)

# Question 4: Condition
condition = st.selectbox("4️⃣ Bus Stop Condition", ["Pole", "Sheltered", "N/A"])

# Question 5: Upload photos (up to 5)
st.markdown("5️⃣ Upload up to 5 photos of the bus stop")

photo_option = st.radio("Choose input method:", ["📷 Take Photos with Camera", "🖼 Upload from Gallery"])

photos = []
max_photos = 5

if photo_option == "📷 Take Photos with Camera":
    for i in range(max_photos):
        photo = st.camera_input(f"Take photo #{i+1} (optional)")
        if photo:
            photos.append(photo)
elif photo_option == "🖼 Upload from Gallery":
    photos = st.file_uploader("Upload photos", type=["jpg","jpeg","png"], accept_multiple_files=True)
    if photos and len(photos) > max_photos:
        st.warning(f"Please upload no more than {max_photos} photos.")
        photos = photos[:max_photos]

# Submit button
if st.button("✅ Submit Survey"):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Save photos locally
    saved_photo_filenames = []
    for idx, photo in enumerate(photos):
        ext = photo.name.split('.')[-1] if hasattr(photo, 'name') else "jpg"
        filename = f"{timestamp}_{idx+1}.{ext}"
        path = os.path.join("images", filename)
        with open(path, "wb") as f:
            f.write(photo.getbuffer())
        saved_photo_filenames.append(filename)

    # Create response record
    response = pd.DataFrame([{
        "Timestamp": timestamp,
        "Depot": selected_depot,
        "Route Number": selected_route,
        "Bus Stop": selected_stop,
        "Condition": condition,
        "Photo Filenames": ";".join(saved_photo_filenames)
    }])

    # Append to CSV or create new
    if os.path.exists("responses.csv"):
        existing = pd.read_csv("responses.csv")
        updated = pd.concat([existing, response], ignore_index=True)
    else:
        updated = response

    updated.to_csv("responses.csv", index=False)

    st.success("✔️ Your response has been recorded!")

    # Preview photos
    for photo in photos:
        st.image(photo, use_container_width=True)

# Divider
st.divider()

# Admin: Show all responses
if st.checkbox("📋 Show all responses"):
    if os.path.exists("responses.csv"):
        df = pd.read_csv("responses.csv")
        st.dataframe(df)
    else:
        st.info("No responses yet.")

# Admin: Download CSV
if st.checkbox("⬇️ Download responses as CSV"):
    if os.path.exists("responses.csv"):
        df = pd.read_csv("responses.csv")
        st.download_button("Download CSV", df.to_csv(index=False), file_name="bus_stop_responses.csv")
