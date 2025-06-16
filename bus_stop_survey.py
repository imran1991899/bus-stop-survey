import streamlit as st
import pandas as pd
from datetime import datetime
import os

# Set up UI
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="centered")
st.title("🚌 Bus Stop Assessment Survey")

# Setup image storage
if not os.path.exists("images"):
    os.makedirs("images")

# Load Excel data
try:
    routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"❌ Failed to load Excel file: {e}")
    st.stop()

# Survey questions
depots = routes_df["Depot"].dropna().unique()
selected_depot = st.selectbox("1️⃣ Select Depot", depots)

filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
selected_route = st.selectbox("2️⃣ Select Route Number", filtered_routes)

filtered_stops = stops_df[stops_df["Route Number"] == selected_route]["Stop Name"].dropna().unique()
selected_stop = st.selectbox("3️⃣ Select Bus Stop", filtered_stops)

condition = st.selectbox("4️⃣ Bus Stop Condition", ["Pole", "Sheltered", "N/A"])

# Session state setup
if "photos" not in st.session_state:
    st.session_state.photos = []
if "photo_index_to_remove" not in st.session_state:
    st.session_state.photo_index_to_remove = None

# Handle photo removal (safe method without rerun)
if st.session_state.photo_index_to_remove is not None:
    idx = st.session_state.photo_index_to_remove
    if 0 <= idx < len(st.session_state.photos):
        del st.session_state.photos[idx]
    st.session_state.photo_index_to_remove = None

# Capture new photo
st.markdown("5️⃣ Add up to 5 Photos (camera only)")

if len(st.session_state.photos) < 5:
    new_photo = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos)+1}", key=f"camera_{len(st.session_state.photos)}")
    if new_photo:
        st.session_state.photos.append(new_photo)

# Preview photos
if st.session_state.photos:
    st.subheader("📸 Preview Photos")
    for i, img in enumerate(st.session_state.photos):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.image(img, caption=f"Photo #{i+1}", use_container_width=True)
        with col2:
            if st.button(f"❌", key=f"remove_{i}"):
                st.session_state.photo_index_to_remove = i
                st.experimental_rerun()  # <- This is the only place we *safely* rerun after button press

# Submission
submit_clicked = st.button("✅ Submit Survey", key="submit_button")

if submit_clicked and st.session_state.photos:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    saved_photo_filenames = []

    for idx, photo in enumerate(st.session_state.photos):
        ext = photo.type.split("/")[-1] if hasattr(photo, 'type') else "jpg"
        filename = f"{timestamp}_{idx+1}.{ext}"
        path = os.path.join("images", filename)
        with open(path, "wb") as f:
            f.write(photo.getbuffer())
        saved_photo_filenames.append(filename)

    # Save to CSV
    response = pd.DataFrame([{
        "Timestamp": timestamp,
        "Depot": selected_depot,
        "Route Number": selected_route,
        "Bus Stop": selected_stop,
        "Condition": condition,
        "Photo Filenames": ";".join(saved_photo_filenames)
    }])

    if os.path.exists("responses.csv"):
        existing = pd.read_csv("responses.csv")
        updated = pd.concat([existing, response], ignore_index=True)
    else:
        updated = response

    updated.to_csv("responses.csv", index=False)
    st.success("✔️ Your response has been recorded!")

    st.session_state.photos = []

elif submit_clicked and not st.session_state.photos:
    st.warning("📸 Please take at least 1 photo before submitting.")

# Admin tools
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
