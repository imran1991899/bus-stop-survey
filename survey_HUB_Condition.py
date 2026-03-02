# --- Google API Setup ---
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

FOLDER_ID = "1JKwlnKUVO3U74wTRu9U46ARF49dcglp7"
CLIENT_SECRETS_FILE = "client_secrets3.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]

def save_credentials(creds):
    with open("token.pickle", "wb") as t: pickle.dump(creds, t)

def load_credentials():
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as t: return pickle.load(t)
    return None

def get_authenticated_service():
    creds = load_credentials()
    
    # 1. Check if we already have valid credentials in a pickle file
    if creds and creds.valid:
        return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
    
    # 2. If expired but refreshable, refresh them
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
        except Exception:
            pass # If refresh fails, proceed to re-auth

    # 3. HANDSHAKE FIX: Store the Flow in session_state
    # This prevents "Missing code verifier" by keeping the same flow object across reruns
    if "oauth_flow" not in st.session_state:
        st.session_state.oauth_flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, 
            scopes=SCOPES, 
            redirect_uri="https://bus-stop-survey-fwaavwf7uxvxrfbjeqv9nq.streamlit.app/"
        )
    
    flow = st.session_state.oauth_flow

    # 4. Check if we are returning from Google with an auth code
    if "code" in st.query_params:
        try:
            # We use the flow object from session_state which holds the correct PKCE verifier
            flow.fetch_token(code=st.query_params["code"])
            creds = flow.credentials
            save_credentials(creds)
            
            # Clean up the URL so the code isn't used again
            st.query_params.clear() 
            return build("drive", "v3", credentials=creds), build("sheets", "v4", credentials=creds)
        except Exception as e:
            st.error(f"Authentication failed: {e}")
            st.query_params.clear()
            st.stop()
    else:
        # 5. No code in URL and no valid creds: Show the Login Link
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
        st.markdown(f"### Authentication Required\n[Please log in with Google]({auth_url})")
        st.stop()

# Initialize services
drive_service, sheets_service = get_authenticated_service()
