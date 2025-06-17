import streamlit as st
import pandas as pd
from datetime import datetime
import os
from streamlit_javascript import st_javascript


def main():
    st.set_page_config(page_title="🚌 Bus Stop Survey", layout="wide")
    st.title("🚌 Bus Stop Assessment Survey")

    if not os.path.exists("images"):
        os.makedirs("images")

    try:
        routes_df = pd.read_excel("bus_data.xlsx", sheet_name="routes")
        stops_df = pd.read_excel("bus_data.xlsx", sheet_name="stops")
    except Exception as e:
        st.error(f"❌ Failed to load Excel file: {e}")
        st.stop()

    # Initialize session state
    for key, default in {
        "staff_id": "",
        "specific_conditions": set(),
        "photos": [],
        "reset_form": False,
        "latitude": None,
        "longitude": None
    }.items():
        if key not in st.session_state:
            st.session_state[key] = default

    depots = routes_df["Depot"].dropna().unique()

    if st.session_state.reset_form:
        st.session_state.selected_depot = None
        st.session_state.selected_route = None
        st.session_state.selected_stop = None
        st.session_state.condition = "1. Covered Bus Stop"
        st.session_state.specific_conditions = set()
        st.session_state.photos = []
        st.session_state.latitude = None
        st.session_state.longitude = None
        st.session_state.reset_form = False
        st.rerun()

    # Staff ID
    st.text_input("👤 Staff ID", value=st.session_state.staff_id, key="staff_id")

    # Geolocation
    st.markdown("🌍 Getting your GPS location (requires browser permission)...")
    loc = st_javascript("navigator.geolocation.getCurrentPosition((pos) => { return {lat: pos.coords.latitude, lon: pos.coords.longitude}; })", key="js1")

    if isinstance(loc, dict) and "lat" in loc:
        st.session_state.latitude = loc["lat"]
        st.session_state.longitude = loc["lon"]
        st.success(f"📍 Location: {loc['lat']:.6f}, {loc['lon']:.6f}")
    else:
        st.info("📡 Waiting for GPS permission...")

    # Survey questions
    selected_depot = st.selectbox("1️⃣ Select Depot", depots, key="selected_depot")

    filtered_routes = routes_df[routes_df["Depot"] == selected_depot]["Route Number"].dropna().unique()
    selected_route = st.selectbox("2️⃣ Select Route Number", filtered_routes, key="selected_route")

    filtered_stops = stops_df[stops_df["Route Number"] == selected_route]["Stop Name"].dropna().unique()
    selected_stop = st.selectbox("3️⃣ Select Bus Stop", filtered_stops, key="selected_stop")

    condition = st.selectbox("4️⃣ Bus Stop Condition", [
        "1. Covered Bus Stop", "2. Pole Only", "3. Layby", "4. Non-Infrastructure"
    ], key="condition")

    st.markdown("5️⃣ Specific Situational Conditions (Select all that apply)")
    specific_conditions_options = [
        "1. Infrastruktur sudah tiada/musnah",
        "2. Terlindung oleh pokok",
        "3. Terhalang oleh kenderaan parkir",
        "4. Keadaan sekeliling tidak selamat (trafik/tiada lampu)",
        "5. Tiada penumpang menunggu",
        "6. Tiada isyarat daripada penumpang",
        "7. Tidak berhenti/memperlahankan bas",
        "8. Salah tempat menunggu",
        "9. Kedudukan bus stop kurang sesuai",
        "10. Bas penuh",
        "11. Mengejar masa waybill (punctuality)",
        "12. Kesesakan lalu lintas",
        "13. Perubahan nama hentian dengan bangunan sekeliling",
        "14. Kekeliruan laluan oleh pemandu baru",
        "15. Terdapat laluan tutup atas sebab tertentu (baiki jalan, pokok tumbang, lawatan delegasi dari luar negara)",
        "16. Hentian terlalu hampir simpang masuk, bas sukar kembali ke laluan betul",
        "17. Arahan untuk tidak berhenti kerana kelewatan atau penjadualan semula",
        "18. Hentian berdekatan dengan traffic light"
    ]
    for option in specific_conditions_options:
        checked = option in st.session_state.specific_conditions
        if st.checkbox(option, value=checked, key=f"sc_{option}"):
            st.session_state.specific_conditions.add(option)
        else:
            st.session_state.specific_conditions.discard(option)

    st.markdown("6️⃣ Add up to 5 Photos (Camera Only)")
    if len(st.session_state.photos) < 5:
        photo = st.camera_input(f"📷 Take Photo #{len(st.session_state.photos) + 1}", key="camera_input")
        if photo:
            st.session_state.photos.append(photo)

    # Show photos
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
        if not st.session_state.staff_id.strip():
            st.warning("❗ Please enter your Staff ID.")
        elif len(st.session_state.photos) == 0:
            st.warning("❗ Please take at least one photo before submitting.")
        elif st.session_state.latitude is None or st.session_state.longitude is None:
            st.warning("❗ GPS coordinates not yet retrieved.")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            saved_filenames = []

            for idx, photo in enumerate(st.session_state.photos):
                filename = f"{timestamp}_photo{idx + 1}.jpg"
                filepath = os.path.join("images", filename)
                with open(filepath, "wb") as f:
                    f.write(photo.getbuffer())
                saved_filenames.append(filename)

            response = pd.DataFrame([{
                "Timestamp": timestamp,
                "Staff ID": st.session_state.staff_id,
                "Depot": st.session_state.selected_depot,
                "Route Number": st.session_state.selected_route,
                "Bus Stop": st.session_state.selected_stop,
                "Condition": st.session_state.condition,
                "Specific Conditions": "; ".join(sorted(st.session_state.specific_conditions)),
                "Latitude": st.session_state.latitude,
                "Longitude": st.session_state.longitude,
                "Photos": ";".join(saved_filenames)
            }])

            if os.path.exists("responses.csv"):
                existing = pd.read_csv("responses.csv")
                updated = pd.concat([existing, response], ignore_index=True)
            else:
                updated = response

            updated.to_csv("responses.csv", index=False)

            st.success("✔️ Your response has been recorded!")
            st.balloons()
            st.session_state.reset_form = True
            st.rerun()

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


if __name__ == "__main__":
    main()
