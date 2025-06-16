import streamlit as st
import pandas as pd
from datetime import datetime
import os

# --- Page setup ---
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="centered")
st.title("🚌 Bus Stop Assessment Survey")

# --- Ensure image folder exists ---
if not os.path.exists("images"):
    os.makedirs("images")

# --- Load depot/route/stop info ---
try:
    routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"❌ Failed to load Excel file: {e}")
    st.stop()

# --- Session State Init ---
if "photos" not in st.session_state:
    st.session_state.photos = []

# --- Survey Questions ---
depots = routes_df["Depot"].dropna().unique()
selected_depot = st.selectbox("1️⃣ Select Depot", depots)

filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
selected_route = st.selectbox("2️⃣ Select Route Number", filtered_routes)

filtered_stops = stops_df[stops_df["Route Number"] == selected_route]["Stop Name"].dropna().unique()
selected_stop = st.selectbox("3️⃣ Select Bus Stop", filtered_stops)

condition = st.selectbox("4️⃣ Bus Stop Condition", ["Pole", "Sheltered", "N/A"])

# --- Take Up to 5 Photos ---
st.markdown("5️⃣ Add up to 5 Photos (Camera Only)")

if len(st.session_state.photos) < 5:
    new_photo = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos) + 1}")
    if new_photo:
        st.session_state.photos.append(new_photo)

# --- Display and Delete Photos (no rerun) ---
if st.session_state.photos:
    st.subheader("📸 Preview Photos")
    to_delete = None  # Track index to delete
    for i, img in enumerate(st.session_state.photos):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.image(img, caption=f"Photo #{i+1}", use_container_width=True)
        with col2:
            if st.button(f"❌ Delete Photo #{i+1}", key=f"delete_{i}"):
                to_delete = i

    # Delete after loop (avoids mid-render issues)
    if to_delete is not None:
        del st.session_state.photos[to_delete]

# --- Submit Survey ---
if st.button("✅ Submit Survey"):
    if not st.session_state.photos:
        st.warning("📸 Please take at least 1 photo before submitting.")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        saved_photo_filenames = []

        for idx, photo in enumerate(st.session_state.photos):
            ext = photo.type.split("/")[-1] if hasattr(photo, 'type') else "jpg"
            filename = f"{timestamp}_{idx+1}.{ext}"
            filepath = os.path.join("images", filename)
            with open(filepath, "wb") as f:
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

        # Append to CSV
        if os.path.exists("responses.csv"):
            existing = pd.read_csv("responses.csv")
            updated = pd.concat([existing, response], ignore_index=True)
        else:
            updated = response

        updated.to_csv("responses.csv", index=False)
        st.success("✔️ Your response has been recorded!")

        # Reset photos
        st.session_state.photos = []

# --- Admin Tools ---
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
