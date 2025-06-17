import streamlit as st
import pandas as pd
from datetime import datetime
import os

# ========== Trigger a clean rerun ==========
if "trigger_rerun" in st.session_state and st.session_state.trigger_rerun:
    st.session_state.trigger_rerun = False
    for key in list(st.session_state.keys()):
        if key not in ("staff_id", "selected_depot", "selected_route"):
            del st.session_state[key]
    st.experimental_rerun()

# ========== Page Setup ==========
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
st.title("🚌 Bus Stop Assessment Survey")

# Create folder for images
if not os.path.exists("images"):
    os.makedirs("images")

# ========== Load Excel ==========
try:
    routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"❌ Failed to load Excel file: {e}")
    st.stop()

# ========== Staff ID ==========
if "staff_id" not in st.session_state:
    st.session_state.staff_id = ""

staff_id_input = st.text_input("👤 Staff ID (numbers only)", value=st.session_state.staff_id)
if staff_id_input and not staff_id_input.isdigit():
    st.warning("⚠️ Staff ID must contain numbers only.")
st.session_state.staff_id = staff_id_input

# ========== Depot Selection ==========
if "selected_depot" not in st.session_state:
    st.session_state.selected_depot = ""

depots = routes_df["Depot"].dropna().unique()
selected_depot = st.selectbox("1️⃣ Select Depot", depots, index=list(depots).index(st.session_state.selected_depot) if st.session_state.selected_depot in depots else 0)
st.session_state.selected_depot = selected_depot

# ========== Route Number Selection ==========
filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
if "selected_route" not in st.session_state:
    st.session_state.selected_route = ""

selected_route = st.selectbox("2️⃣ Select Route Number", filtered_routes, index=list(filtered_routes).index(st.session_state.selected_route) if st.session_state.selected_route in filtered_routes else 0)
st.session_state.selected_route = selected_route

# ========== Bus Stop Selection (Ordered) ==========
filtered_stops = (
    stops_df[stops_df["Route Number"] == selected_route]
    .dropna(subset=["Stop Name", "Order"])
    .sort_values("Order")["Stop Name"]
    .tolist()
)
selected_stop = st.selectbox("3️⃣ Select Bus Stop", filtered_stops)

# ========== Condition ==========
condition = st.selectbox("4️⃣ Bus Stop Condition", [
    "1. Covered Bus Stop",
    "2. Pole Only",
    "3. Layby",
    "4. Non-Infrastructure"
])

# ========== Activity Category ==========
activity_category = st.selectbox("4️⃣➕ Categorizing Activities", [
    "1. On Board in the Bus",
    "2. On Ground Location"
])

# ========== Situational Conditions ==========
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

options = onboard_options if activity_category == "1. On Board in the Bus" else onground_options

st.markdown("5️⃣ Specific Situational Conditions (Select all that apply)")
if "specific_conditions" not in st.session_state:
    st.session_state.specific_conditions = set()

for opt in options:
    checked = opt in st.session_state.specific_conditions
    new_checked = st.checkbox(opt, value=checked, key=opt)
    if new_checked and not checked:
        st.session_state.specific_conditions.add(opt)
    elif not new_checked and checked:
        st.session_state.specific_conditions.remove(opt)

# ========== Handle "Other" ==========
other_text = ""
other_option_label = next((o for o in options if "Other" in o), None)
if other_option_label and other_option_label in st.session_state.specific_conditions:
    other_text = st.text_area("📝 Please describe the 'Other' condition (at least 2 words)", height=150)
    if len(other_text.split()) < 2:
        st.warning("🚨 'Other' description must be at least 2 words.")

# ========== Photo Capture ==========
if "photos" not in st.session_state:
    st.session_state.photos = []

if "last_photo" not in st.session_state:
    st.session_state.last_photo = None

st.markdown("6️⃣ Add up to 5 Photos (Camera Only)")
if len(st.session_state.photos) < 5:
    photo = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos)+1}")
    if photo:
        st.session_state.photos.append(photo)

# Show Saved Photos
if st.session_state.photos:
    st.subheader("📸 Saved Photos")
    to_delete = None
    for i, img in enumerate(st.session_state.photos):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.image(img, caption=f"Photo #{i + 1}", use_container_width=True)
        with col2:
            if st.button(f"❌ Delete Photo #{i + 1}", key=f"del_{i}"):
                to_delete = i
    if to_delete is not None:
        del st.session_state.photos[to_delete]

# ========== Submit Button ==========
if st.button("✅ Submit Survey"):
    if not staff_id_input.strip():
        st.warning("❗ Please enter your Staff ID.")
    elif not staff_id_input.isdigit():
        st.warning("❗ Staff ID must contain numbers only.")
    elif not st.session_state.photos:
        st.warning("❗ Please take at least one photo.")
    elif other_option_label in st.session_state.specific_conditions and len(other_text.split()) < 2:
        st.warning("❗ 'Other' response must be at least 2 words.")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        saved_photos = []
        for idx, p in enumerate(st.session_state.photos):
            filename = f"{timestamp}_photo{idx + 1}.jpg"
            path = os.path.join("images", filename)
            with open(path, "wb") as f:
                f.write(p.getbuffer())
            saved_photos.append(filename)

        conds = list(st.session_state.specific_conditions)
        if other_option_label in conds:
            conds.remove(other_option_label)
            conds.append(f"Other: {other_text.replace(';', ',')}")

        data = pd.DataFrame([{
            "Timestamp": timestamp,
            "Staff ID": staff_id_input,
            "Depot": selected_depot,
            "Route Number": selected_route,
            "Bus Stop": selected_stop,
            "Condition": condition,
            "Activity Category": activity_category,
            "Specific Conditions": "; ".join(conds),
            "Photos": ";".join(saved_photos)
        }])

        if os.path.exists("responses.csv"):
            prev = pd.read_csv("responses.csv")
            updated = pd.concat([prev, data], ignore_index=True)
        else:
            updated = data
        updated.to_csv("responses.csv", index=False)

        st.success("✅ Submission complete! Thank you.")
        st.session_state.trigger_rerun = True
