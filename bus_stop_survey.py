import streamlit as st
import pandas as pd
from datetime import datetime
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

# 🆕 Staff ID (Remember using session_state)
if "staff_id" not in st.session_state:
    st.session_state.staff_id = ""

st.text_input("👤 Staff ID", value=st.session_state.staff_id, key="staff_id")

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
condition = st.selectbox("4️⃣ Bus Stop Condition", ["Covered Bus Stop", "Pole Only", "Layby", "Non-Infrastructure"])

# Question 5: Specific Conditions (multi-select)
st.markdown("5️⃣ Specific Situational Conditions (Select all that apply)")
specific_conditions = st.multiselect("Check all relevant reasons below:", [
    "Infrastruktur sudah tiada/musnah",
    "Terlindung oleh pokok",
    "Terhalang oleh kenderaan parkir",
    "Keadaan sekeliling tidak selamat (trafik/tiada lampu)",
    "Tiada penumpang menunggu",
    "Tiada isyarat daripada penumpang",
    "Tidak berhenti/memperlahankan bas",
    "Salah tempat menunggu",
    "Kedudukan bus stop kurang sesuai",
    "Bas penuh",
    "Mengejar masa waybill (punctuality)",
    "Kesesakan lalu lintas",
    "Perubahan nama hentian dengan bangunan sekeliling",
    "Kekeliruan laluan oleh pemandu baru",
    "Terdapat laluan tutup atas sebab tertentu (baiki jalan, pokok tumbang, lawatan delegasi dari luar negara)",
    "Hentian terlalu hampir simpang masuk, bas sukar kembali ke laluan betul",
    "Arahan untuk tidak berhenti kerana kelewatan atau penjadualan semula",
    "Hentian berdekatan dengan traffic light"
])

# Initialize session state for photos
if "photos" not in st.session_state:
    st.session_state.photos = []
if "last_photo" not in st.session_state:
    st.session_state.last_photo = None

# Question 6: Photo capture - up to 5 photos with camera only
st.markdown("6️⃣ Add up to 5 Photos (Camera Only)")

if len(st.session_state.photos) < 5:
    last_photo = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos) + 1}")
    if last_photo is not None:
        st.session_state.last_photo = last_photo

# Append last snapped photo to photos list and reset last photo to keep camera open
if st.session_state.last_photo is not None:
    st.session_state.photos.append(st.session_state.last_photo)
    st.session_state.last_photo = None

# Show saved photos with delete buttons
if st.session_state.photos:
    st.subheader("📸 Saved Photos")
    to_delete = None
    for i, img in enumerate(st.session_state.photos):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.image(img, caption=f"Photo #{i + 1}", use_container_width=True)
        with col2:
            if st.button(f"❌ Delete Photo #{i + 1}", key=f"delete_{i}"):
                to_delete = i
    if to_delete is not None:
        del st.session_state.photos[to_delete]

# Submit Button
if st.button("✅ Submit Survey"):
    if len(st.session_state.photos) == 0:
        st.warning("❗ Please take at least one photo before submitting.")
    elif not st.session_state.staff_id.strip():
        st.warning("❗ Please enter your Staff ID.")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        saved_filenames = []

        # Save photos to disk
        for idx, photo in enumerate(st.session_state.photos):
            filename = f"{timestamp}_photo{idx + 1}.jpg"
            filepath = os.path.join("images", filename)
            with open(filepath, "wb") as f:
                f.write(photo.getbuffer())
            saved_filenames.append(filename)

        # Create record for CSV
        response = pd.DataFrame([{
            "Timestamp": timestamp,
            "Staff ID": st.session_state.staff_id,
            "Depot": selected_depot,
            "Route Number": selected_route,
            "Bus Stop": selected_stop,
            "Condition": condition,
            "Specific Conditions": "; ".join(specific_conditions),
            "Photos": ";".join(saved_filenames)
        }])

        # Append or create CSV
        if os.path.exists("responses.csv"):
            existing = pd.read_csv("responses.csv")
            updated = pd.concat([existing, response], ignore_index=True)
        else:
            updated = response

        updated.to_csv("responses.csv", index=False)

        st.success("✔️ Your response has been recorded!")
        st.balloons()

        # Clear only photos so Staff ID remains
        st.session_state.photos = []

# Admin Tools (Optional)
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
