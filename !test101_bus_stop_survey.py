import streamlit as st
import pandas as pd
from datetime import datetime
import os

# ========== Page Setup ==========
st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
st.title("🚌 Bus Stop Assessment Survey")

# ========== Create image folder ==========
if not os.path.exists("images"):
    os.makedirs("images")

# ========== Load Excel ==========
try:
    routes_df = pd.read_excel("!test101_bus_data.xlsx", sheet_name="routes")
    stops_df = pd.read_excel("!test101_bus_data.xlsx", sheet_name="stops")
except Exception as e:
    st.error(f"❌ Failed to load Excel file: {e}")
    st.stop()

# ========== State Initialization ==========
if "staff_id" not in st.session_state:
    st.session_state.staff_id = ""
if "selected_depot" not in st.session_state:
    st.session_state.selected_depot = ""
if "selected_route" not in st.session_state:
    st.session_state.selected_route = ""
if "selected_stop" not in st.session_state:
    st.session_state.selected_stop = ""
if "specific_conditions" not in st.session_state:
    st.session_state.specific_conditions = set()
if "photos" not in st.session_state:
    st.session_state.photos = []
if "activity_category" not in st.session_state:
    st.session_state.activity_category = ""
if "other_text" not in st.session_state:
    st.session_state.other_text = ""
if "condition" not in st.session_state:
    st.session_state.condition = "1. Covered Bus Stop"

# ========== Staff ID ==========
staff_id_input = st.text_input("👤 Staff ID (exactly 8 digits)", value=st.session_state.staff_id)
if staff_id_input and (not staff_id_input.isdigit() or len(staff_id_input) != 8):
    st.warning("⚠️ Staff ID must be exactly 8 numeric digits.")
st.session_state.staff_id = staff_id_input

# ========== Depot Selection ==========
depots = routes_df["Depot"].dropna().unique()
selected_depot = st.selectbox(
    "1️⃣ Select Depot",
    depots,
    index=list(depots).index(st.session_state.selected_depot) if st.session_state.selected_depot in depots else 0,
)
st.session_state.selected_depot = selected_depot

# ========== Route Number Selection ==========
filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
selected_route = st.selectbox(
    "2️⃣ Select Route Number",
    filtered_routes,
    index=list(filtered_routes).index(st.session_state.selected_route) if st.session_state.selected_route in filtered_routes else 0,
)
st.session_state.selected_route = selected_route

# ========== Bus Stop Selection (Ordered) ==========
filtered_stops = (
    stops_df[stops_df["Route Number"] == selected_route]
    .dropna(subset=["Stop Name", "Order"])
    .sort_values("Order")["Stop Name"]
    .tolist()
)
if st.session_state.selected_stop not in filtered_stops:
    st.session_state.selected_stop = filtered_stops[0] if filtered_stops else ""
selected_stop = st.selectbox(
    "3️⃣ Select Bus Stop",
    filtered_stops,
    index=filtered_stops.index(st.session_state.selected_stop) if st.session_state.selected_stop in filtered_stops else 0,
)
st.session_state.selected_stop = selected_stop

# ========== Condition ==========
condition_options = [
    "1. Covered Bus Stop",
    "2. Pole Only",
    "3. Layby",
    "4. Non-Infrastructure",
]
condition = st.selectbox(
    "4️⃣ Bus Stop Condition",
    condition_options,
    index=condition_options.index(st.session_state.condition) if st.session_state.condition in condition_options else 0,
)
st.session_state.condition = condition

# ========== Activity Category (with empty initial choice) ==========
activity_cat_options = [
    "",  # empty option for no selection yet
    "1. On Board in the Bus",
    "2. On Ground Location",
]
activity_category = st.selectbox(
    "5️⃣ Categorizing Activities",
    activity_cat_options,
    index=activity_cat_options.index(st.session_state.activity_category) if st.session_state.activity_category in activity_cat_options else 0,
)
st.session_state.activity_category = activity_category

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
    "12. Other (Please specify below)",
]
onground_options = [
    "1. Infrastruktur sudah tiada/musnah",
    "2. Terlindung oleh pokok",
    "3. Terhalang oleh kenderaan parkir",
    "4. Keadaan sekeliling tidak selamat tiada lampu",
    "5. Kedudukan bus stop kurang sesuai",
    "6. Perubahan nama hentian dengan bangunan sekeliling",
    "7. Other (Please specify below)",
]

if activity_category == "1. On Board in the Bus":
    options = onboard_options
elif activity_category == "2. On Ground Location":
    options = onground_options
else:
    options = []

if options:
    st.markdown("6️⃣ Specific Situational Conditions (Select all that apply)")
    # Remove any conditions that no longer apply
    st.session_state.specific_conditions = {cond for cond in st.session_state.specific_conditions if cond in options}

    for opt in options:
        checked = opt in st.session_state.specific_conditions
        new_checked = st.checkbox(opt, value=checked, key=opt)
        if new_checked and not checked:
            st.session_state.specific_conditions.add(opt)
        elif not new_checked and checked:
            st.session_state.specific_conditions.remove(opt)
else:
    st.info("Please select an Activity Category above to see situational conditions.")

# ========== Handle "Other" ==========
other_option_label = next((o for o in options if "Other" in o), None)
if other_option_label and other_option_label in st.session_state.specific_conditions:
    other_text = st.text_area("📝 Please describe the 'Other' condition (at least 2 words)", height=150, value=st.session_state.other_text)
    st.session_state.other_text = other_text
    if len(other_text.split()) < 2:
        st.warning("🚨 'Other' description must be at least 2 words.")
else:
    st.session_state.other_text = ""

# ========== Photo Capture ==========
st.markdown("7️⃣ Add up to 5 Photos (Camera or Upload from device)")
if len(st.session_state.photos) < 5:
    photo = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos) + 1}")
    if photo:
        st.session_state.photos.append(photo)

if len(st.session_state.photos) < 5:
    upload_photo = st.file_uploader(f"📁 Upload Photo #{len(st.session_state.photos) + 1}", type=["png", "jpg", "jpeg"])
    if upload_photo:
        st.session_state.photos.append(upload_photo)

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
    # Validation
    if not staff_id_input.strip():
        st.warning("❗ Please enter your Staff ID.")
    elif not (staff_id_input.isdigit() and len(staff_id_input) == 8):
        st.warning("❗ Staff ID must be exactly 8 numeric digits.")
    elif not st.session_state.photos:
        st.warning("❗ Please take or upload at least one photo.")
    elif activity_category not in ["1. On Board in the Bus", "2. On Ground Location"]:
        st.warning("❗ Please select an Activity Category.")
    elif other_option_label in st.session_state.specific_conditions and len(st.session_state.other_text.split()) < 2:
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
            conds.append(f"Other: {st.session_state.other_text.replace(';', ',')}")

        data = pd.DataFrame(
            [
                {
                    "Timestamp": timestamp,
                    "Staff ID": staff_id_input,
                    "Depot": selected_depot,
                    "Route Number": selected_route,
                    "Bus Stop": selected_stop,
                    "Condition": condition,
                    "Activity Category": activity_category,
                    "Specific Conditions": "; ".join(conds),
                    "Photos": ";".join(saved_photos),
                }
            ]
        )

        if os.path.exists("responses.csv"):
            prev = pd.read_csv("responses.csv")
            updated = pd.concat([prev, data], ignore_index=True)
        else:
            updated = data

        updated.to_csv("responses.csv", index=False)

        st.success("✅ Submission complete! Thank you.")

        # Reset fields except Staff ID (assuming repeated surveys by same user)
        st.session_state.selected_stop = filtered_stops[0] if filtered_stops else ""
        st.session_state.condition = "1. Covered Bus Stop"   # reset Bus Stop Condition
        st.session_state.activity_category = ""
        st.session_state.specific_conditions = set()
        st.session_state.photos = []
        st.session_state.other_text = ""

