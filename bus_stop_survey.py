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

# Initialize session state variables
if "staff_id" not in st.session_state:
    st.session_state.staff_id = ""
if "photos" not in st.session_state:
    st.session_state.photos = []
if "last_photo" not in st.session_state:
    st.session_state.last_photo = None

# 0️⃣ Staff ID (persisted)
staff_id = st.text_input("🆔 Staff ID", value=st.session_state.staff_id)
st.session_state.staff_id = staff_id

# 1️⃣ Select Depot
depots = routes_df["Depot"].dropna().unique()
selected_depot = st.selectbox("1️⃣ Select Depot", depots)

# 2️⃣ Select Route under selected depot
filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
selected_route = st.selectbox("2️⃣ Select Route Number", filtered_routes)

# 3️⃣ Select Stop under selected route
filtered_stops = stops_df[stops_df["Route Number"] == selected_route]["Stop Name"].dropna().unique()
selected_stop = st.selectbox("3️⃣ Select Bus Stop", filtered_stops)

# 4️⃣ Select Condition
condition = st.selectbox("4️⃣ Bus Stop Condition", ["Covered Bus Stop", "Pole Only", "Layby", "Non-Infrastructure"])

# 4.5️⃣ Specific Conditions (multi-select)
specific_conditions_options = [
    "Infrastruktur sudah tiada/musnah​",
    "Terlindung oleh pokok​",
    "Terhalang oleh kenderaan parkir​",
    "Keadaan sekeliling tidak selamat (trafik/tiada lampu)​",
    "Tiada penumpang menunggu​",
    "Tiada isyarat daripada penumpang​",
    "Tidak berhenti/memperlahankan bas​",
    "Salah tempat menunggu ​",
    "Kedudukan bus stop kurang sesuai​",
    "Bas penuh​",
    "Mengejar masa waybill (punctuality)",
    "Kesesakan lalu lintas​",
    "Perubahan nama hentian dengan bangunan sekeliling​",
    "Kekeliruan laluan oleh pemandu baru​",
    "Terdapat laluan tutup atas sebab tertentu (baiki jalan, pokok tumbang, lawatan delegasi dari luar negara)​",
    "Hentian bas terlalu hampir simpang masuk, dan bas sukar untuk kembali semula di laluan yang betul.​",
    "Terdapat arahan untuk tidak berhenti kerana kelewatan jadual atau penjadualan semula​",
    "Hentian berdekatan dengan traffic light"
]
specific_condition = st.multiselect("4.5️⃣ Specific Condition (you can select more than one)", specific_conditions_options)

# 5️⃣ Add up to 5 Photos (Camera Only)
st.markdown("5️⃣ Add up to 5 Photos (Camera Only)")

if len(st.session_state.photos) < 5:
    last_photo = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos) + 1}")
    if last_photo is not None:
        st.session_state.last_photo = last_photo

# Append last snapped photo to photos list and clear last_photo to reset camera
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
        st.experimental_rerun()  # Rerun to refresh UI after deletion

# Submit Button
if st.button("✅ Submit Survey"):
    if staff_id.strip() == "":
        st.warning("Please enter your Staff ID before submitting.")
    elif len(st.session_state.photos) == 0:
        st.warning("Please take at least one photo before submitting.")
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
            "Staff ID": staff_id,
            "Depot": selected_depot,
            "Route Number": selected_route,
            "Bus Stop": selected_stop,
            "Condition": condition,
            "Specific Condition": "; ".join(specific_condition),
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

        # Reset everything except staff_id
        st.session_state.photos = []
        st.experimental_rerun()

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
