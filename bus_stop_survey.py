import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="🚌 Bus Stop Survey", layout="centered")
st.title("🚌 Bus Stop Assessment Survey")

if not os.path.exists("images"):
    os.makedirs("images")

# Load Excel data
try:
    routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"❌ Failed to load Excel file: {e}")
    st.stop()

# Questions 1-4
depots = routes_df["Depot"].dropna().unique()
selected_depot = st.selectbox("1️⃣ Select Depot", depots)

filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
selected_route = st.selectbox("2️⃣ Select Route Number", filtered_routes)

filtered_stops = stops_df[stops_df["Route Number"] == selected_route]["Stop Name"].dropna().unique()
selected_stop = st.selectbox("3️⃣ Select Bus Stop", filtered_stops)

condition = st.selectbox("4️⃣ Bus Stop Condition", ["Pole", "Sheltered", "N/A"])

# Photo taking with session state
if "photos" not in st.session_state:
    st.session_state.photos = []

if "last_photo_added" not in st.session_state:
    st.session_state.last_photo_added = False

max_photos = 5

st.markdown("5️⃣ Take up to 5 photos (one at a time)")

if len(st.session_state.photos) < max_photos:
    photo = st.camera_input(f"Take photo #{len(st.session_state.photos)+1}")

    if photo is not None and not st.session_state.last_photo_added:
        st.session_state.photos.append(photo)
        st.session_state.last_photo_added = True
        st.experimental_rerun()
    else:
        st.session_state.last_photo_added = False
else:
    st.info(f"You have taken {max_photos} photos.")

# Show thumbnails of taken photos with option to remove
if st.session_state.photos:
    st.write("📸 Photos taken:")
    for i, p in enumerate(st.session_state.photos):
        cols = st.columns([1, 10])
        cols[1].image(p, use_container_width=True)
        if cols[0].button(f"Remove #{i+1}"):
            st.session_state.photos.pop(i)
            st.experimental_rerun()

# Submit button (enabled only if at least one photo taken)
if st.button("✅ Submit Survey", disabled=(len(st.session_state.photos) == 0)):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    saved_photo_filenames = []
    for idx, photo in enumerate(st.session_state.photos):
        ext = photo.type.split("/")[-1] if hasattr(photo, 'type') else "jpg"
        filename = f"{timestamp}_{idx+1}.{ext}"
        path = os.path.join("images", filename)
        with open(path, "wb") as f:
            f.write(photo.getbuffer())
        saved_photo_filenames.append(filename)

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

    # Clear photos from session state for next user
    st.session_state.photos = []
    st.experimental_rerun()

# Divider and admin tools
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
