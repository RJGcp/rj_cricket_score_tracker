import os
import uuid
from flask import Flask, render_template, request, jsonify, session
from google.cloud import secretmanager

# Conditional import for firebase_admin and firestore
# This helps in local development if you don't have the SDK configured
# but will always try to initialize on Cloud Run.
firebase_admin_available = False
try:
    import firebase_admin
    from firebase_admin import credentials, firestore as firebase_firestore
    firebase_admin_available = True
    print("Firebase Admin SDK modules imported successfully.")
except ImportError as e:
    print(f"WARNING: Firebase Admin SDK modules not found: {e}. Firestore functionality will be disabled.")
    firebase_admin = None
    firebase_firestore = None

app = Flask(__name__)

# --- Secret Manager and Flask Secret Key Configuration ---
try:
    client = secretmanager.SecretManagerServiceClient()
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
    
    if not project_id:
        print("WARNING: GOOGLE_CLOUD_PROJECT environment variable not set. Cannot fetch Flask secret key from Secret Manager.")
        # Fallback for local development if project_id is missing
        app.secret_key = 'super-secret-fallback-key-for-dev-only'
        print("Using a fallback Flask secret key. This is NOT secure for production.")
    else:
        secret_name = "cricket-tracker-service-flask-secret-key"
        secret_version_name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        
        try:
            response = client.access_secret_version(request={"name": secret_version_name})
            app.secret_key = response.payload.data.decode("UTF-8")
            print("Flask secret key loaded successfully from Secret Manager.")
        except Exception as e:
            print(f"ERROR: Failed to access Secret Manager secret '{secret_name}': {e}")
            print("Please ensure the Cloud Run service account has 'Secret Manager Secret Accessor' role for this secret.")
            app.secret_key = 'super-secret-fallback-key-for-dev-only'
            print("Using a fallback Flask secret key. This is NOT secure for production.")

except Exception as e:
    print(f"CRITICAL ERROR: Failed to initialize Secret Manager client: {e}")
    app.secret_key = 'super-secret-fallback-key-for-dev-only'
    print("Using a fallback Flask secret key. This is NOT secure for production.")

# --- Firebase and Firestore Initialization ---
db = None # Initialize db to None
if firebase_admin_available:
    try:
        # On Google Cloud Run, ApplicationDefault() credentials are automatically provided
        # to the service account your Cloud Run service runs as.
        firebase_admin.initialize_app(credentials.ApplicationDefault())
        db = firebase_firestore.client()
        print("Firestore client initialized successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to initialize Firebase Admin SDK or Firestore client: {e}")
        print("Please ensure your Cloud Run service account has 'Cloud Datastore User' role.")
        print("Also verify GOOGLE_CLOUD_PROJECT environment variable is correctly set in Cloud Run.")
else:
    print("Firebase Admin SDK not available, Firestore will not be used.")


# Define the base collection path for storing game states
# __app_id is a special environment variable provided by the Canvas environment
# If running locally or in a non-Canvas environment, it defaults to 'default-app-id'
APP_ID = os.environ.get('__app_id', 'default-app-id')
print(f"Application ID (APP_ID): {APP_ID}")

# --- Helper function to get user-specific Firestore document reference ---
def get_user_game_doc_ref():
    # Get user_id from session, create if not exists
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        print(f"New user session created: {session['user_id']}")
    
    user_id = session['user_id']
    
    # Path: artifacts/{appId}/users/{userId}/game_states/current_game
    # This structure is recommended for user-specific data in a collaborative environment.
    return db.collection('artifacts').document(APP_ID).collection('users').document(user_id).collection('game_states').document('current_game')

# --- Flask Routes ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/save_game', methods=['POST'])
def save_game():
    """Saves the current game state to Firestore."""
    if db is None:
        return jsonify({"status": "error", "message": "Firestore is not initialized. Check server logs for details."}), 500

    try:
        game_data = request.json
        doc_ref = get_user_game_doc_ref()
        doc_ref.set(game_data)
        print(f"Game state saved for user {session.get('user_id')}")
        return jsonify({"status": "success", "message": "Game state saved."})
    except Exception as e:
        print(f"Error saving game state for user {session.get('user_id')}: {e}")
        return jsonify({"status": "error", "message": f"Error saving game: {str(e)}"}), 500

@app.route('/load_game', methods=['GET'])
def load_game():
    """Loads the game state from Firestore."""
    if db is None:
        return jsonify({"status": "error", "message": "Firestore is not initialized. Check server logs for details."}), 500

    try:
        doc_ref = get_user_game_doc_ref()
        doc = doc_ref.get()
        if doc.exists:
            print(f"Game state loaded for user {session.get('user_id')}")
            return jsonify({"status": "success", "game_data": doc.to_dict()})
        else:
            print(f"No saved game state found for user {session.get('user_id')}")
            return jsonify({"status": "error", "message": "No saved game state found."}), 404
    except Exception as e:
        print(f"Error loading game state for user {session.get('user_id')}: {e}")
        return jsonify({"status": "error", "message": f"Error loading game: {str(e)}"}), 500

@app.route('/delete_game', methods=['POST'])
def delete_game():
    """Deletes the current user's game state from Firestore."""
    if db is None:
        return jsonify({"status": "error", "message": "Firestore is not initialized. Check server logs for details."}), 500

    try:
        doc_ref = get_user_game_doc_ref()
        doc_ref.delete()
        print(f"Game state deleted for user {session.get('user_id')}")
        return jsonify({"status": "success", "message": "Game state deleted."})
    except Exception as e:
        print(f"Error deleting game state for user {session.get('user_id')}: {e}")
        return jsonify({"status": "error", "message": f"Error deleting game: {str(e)}"}), 500

if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used in production.
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)

