import streamlit as st
import pandas as pd
from datetime import datetime
import os

# Set wide layout for better visibility
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
st.title("🚌 Bus Stop Assessment Survey")

# Create images folder if needed
if not os.path.exists("images"):
    os.makedirs("images")

# Load depot/route/stop info from Excel
try:
    routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"❌ Failed to load Excel file: {e}")
    st.stop()

# Staff ID with session_state
if "staff_id" not in st.session_state:
    st.session_state.staff_id = ""
st.text_input("👤 Staff ID", value=st.session_state.staff_id, key="staff_id")

# Question 1: Depot
depots = routes_df["Depot"].dropna().unique()
selected_depot = st.selectbox("1️⃣ Select Depot", depots)

# Question 2: Route
filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
selected_route = st.selectbox("2️⃣ Select Route Number", filtered_routes)

# Question 3: Bus Stop
filtered_stops = stops_df[stops_df["Route Number"] == selected_route]["Stop Name"].dropna().unique()
selected_stop = st.selectbox("3️⃣ Select Bus Stop", filtered_stops)

# Question 4: Condition
condition = st.selectbox("4️⃣ Bus Stop Condition", [
    "1. Covered Bus Stop",
    "2. Pole Only",
    "3. Layby",
    "4. Non-Infrastructure"
])

# Question 4.1: Categorizing Activities
activity_category = st.selectbox("4️⃣➕ Categorizing Activities", [
    "1. On Board in the Bus",
    "2. On Ground Location"
])

# Define condition options based on activity
onboard_options = [
    "1. Tiada penumpang menunggu",
    "2. Tiada isyarat (penumpang tidak menahan bas)",
    "3. Tidak berhenti/memperlahankan bas",
    "4. Salah tempat menunggu",
    "5. Bas penuh",
    "6. Mengejar masa waybill (punctuality)",
    "7. Kesesakan lalu lintas",
    "8. Kekeliruan laluan oleh pemandu baru",
    "9. Terdapat laluan tutup atas sebab tertentu (baiki jalan, pokok tumbang, lawatan delegasi dari luar negara)",
    "10. Hentian terlalu hampir simpang masuk, bas sukar kembali ke laluan asal",
    "11. Hentian berdekatan dengan traffic light",
    "12. Other (Please specify below)"
]

onground_options = [
    "1. Infrastruktur sudah tiada/musnah",
    "2. Terlindung oleh pokok",
    "3. Terhalang oleh kenderaan parkir",
    "4. Keadaan sekeliling tidak selamat tiada lampu",
    "5. Kedudukan bus stop kurang sesuai",
    "6. Perubahan nama hentian dengan bangunan sekeliling",
    "7. Other (Please specify below)"
]

# Choose correct list
if activity_category == "1. On Board in the Bus":
    specific_conditions_options = onboard_options
else:
    specific_conditions_options = onground_options

# Question 5: Specific Situational Conditions
st.markdown("5️⃣ Specific Situational Conditions (Select all that apply)")

# Session state for selections
if "specific_conditions" not in st.session_state:
    st.session_state.specific_conditions = set()

# Display checkboxes
for option in specific_conditions_options:
    checked = option in st.session_state.specific_conditions
    new_checked = st.checkbox(option, value=checked, key=option)
    if new_checked and not checked:
        st.session_state.specific_conditions.add(option)
    elif not new_checked and checked:
        st.session_state.specific_conditions.remove(option)

# Show text area if "Other" selected
other_text = ""
other_option_label = next((opt for opt in specific_conditions_options if "Other" in opt), None)
if other_option_label and other_option_label in st.session_state.specific_conditions:
    other_text = st.text_area("📝 Please describe the 'Other' condition (at least 2 words)", height=150)
    word_count = len(other_text.split())
    if word_count < 2:
        st.warning(f"🚨 You have written {word_count} word(s). Please write at least 2 words.")

# Photos
if "photos" not in st.session_state:
    st.session_state.photos = []
if "last_photo" not in st.session_state:
    st.session_state.last_photo = None

st.markdown("6️⃣ Add up to 5 Photos (Camera Only)")
if len(st.session_state.photos) < 5:
    last_photo = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos) + 1}")
    if last_photo is not None:
        st.session_state.last_photo = last_photo

if st.session_state.last_photo is not None:
    st.session_state.photos.append(st.session_state.last_photo)
    st.session_state.last_photo = None

# Show photos and delete buttons
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

# Submit
if st.button("✅ Submit Survey"):
    if len(st.session_state.photos) == 0:
        st.warning("❗ Please take at least one photo before submitting.")
    elif not st.session_state.staff_id.strip():
        st.warning("❗ Please enter your Staff ID.")
    elif other_option_label in st.session_state.specific_conditions and len(other_text.split()) < 2:
        st.warning("❗ 'Other' response must be at least 2 words.")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        saved_filenames = []

        for idx, photo in enumerate(st.session_state.photos):
            filename = f"{timestamp}_photo{idx + 1}.jpg"
            filepath = os.path.join("images", filename)
            with open(filepath, "wb") as f:
                f.write(photo.getbuffer())
            saved_filenames.append(filename)

        specific_conditions_list = list(st.session_state.specific_conditions)
        if other_option_label in specific_conditions_list:
            specific_conditions_list.remove(other_option_label)
            specific_conditions_list.append(f"Other: {other_text.replace(';', ',')}")

        response = pd.DataFrame([{
            "Timestamp": timestamp,
            "Staff ID": st.session_state.staff_id,
            "Depot": selected_depot,
            "Route Number": selected_route,
            "Bus Stop": selected_stop,
            "Condition": condition,
            "Activity Category": activity_category,
            "Specific Conditions": "; ".join(specific_conditions_list),
            "Photos": ";".join(saved_filenames)
        }])

        if os.path.exists("responses.csv"):
            existing = pd.read_csv("responses.csv")
            updated = pd.concat([existing, response], ignore_index=True)
        else:
            updated = response

        updated.to_csv("responses.csv", index=False)

        st.success("✅ Done!")

        # Reset all except staff_id
        st.session_state.photos = []
        st.session_state.last_photo = None
        st.session_state.specific_conditions = set()

# Admin section
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
