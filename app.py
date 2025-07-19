import os
import uuid
from flask import Flask, render_template, request, jsonify, session
from google.cloud import secretmanager

# Conditional import for firebase_admin and firestore
# This helps in local development if you don't have the SDK configured
# but will always try to initialize on Cloud Run.
try:
    import firebase_admin
    from firebase_admin import credentials, firestore as firebase_firestore
    print("Firebase Admin SDK modules imported successfully.")
except ImportError:
    print("Firebase Admin SDK not found. Firestore functionality will be disabled.")
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
        
        response = client.access_secret_version(request={"name": secret_version_name})
        app.secret_key = response.payload.data.decode("UTF-8")
        print("Flask secret key loaded successfully from Secret Manager.")
except Exception as e:
    print(f"Error loading Flask secret key from Secret Manager: {e}")
    app.secret_key = 'super-secret-fallback-key-for-dev-only'
    print("Using a fallback Flask secret key. This is NOT secure for production.")

# --- Firebase and Firestore Initialization ---
db = None # Initialize db to None
if firebase_admin:
    try:
        # On Google Cloud Run, ApplicationDefault() credentials are automatically provided
        # to the service account your Cloud Run service runs as.
        firebase_admin.initialize_app(credentials.ApplicationDefault())
        db = firebase_firestore.client()
        print("Firestore client initialized successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to initialize Firebase Admin SDK or Firestore client: {e}")
        print("Please ensure your Cloud Run service account has 'Cloud Datastore User' role and 'Secret Manager Secret Accessor' role.")
        print("Also verify GOOGLE_CLOUD_PROJECT environment variable is correctly set.")
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



# # app.py
# import os
# from flask import Flask, send_from_directory, request, jsonify, session
# import json
# import uuid
# import firebase_admin
# from firebase_admin import credentials, firestore

# app = Flask(__name__, static_folder='.')

# # --- Firebase (Firestore) Initialization ---
# # Firebase config and initial auth token are provided by the Canvas environment
# firebase_config_str = os.environ.get('__firebase_config')
# initial_auth_token = os.environ.get('__initial_auth_token')
# app_id = os.environ.get('__app_id', 'default-app-id') # Get app ID from environment

# db_firestore = None

# # Initialize Firebase Admin SDK
# try:
#     if firebase_config_str:
#         firebase_config = json.loads(firebase_config_str)
#         # In Cloud Run, default credentials (service account) are typically used for Firebase Admin SDK.
#         # For backend Admin SDK, `firebase_admin.initialize_app()` without args uses default credentials.
#         firebase_admin.initialize_app()
#         # Connect to the default Firestore database
#         db_firestore = firestore.client() # Connects to the default database
#         app.logger.info("Firebase Admin SDK initialized successfully for default database.")
#     else:
#         app.logger.warning("Firebase config not found. Firestore operations will not work.")
# except Exception as e:
#     app.logger.error(f"Error initializing Firebase Admin SDK: {e}")

# # --- Flask Session Secret Key ---
# app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_super_secret_key_for_dev_fallback_please_change_in_prod')
# if app.secret_key == 'a_super_secret_key_for_dev_fallback_please_change_in_prod' and os.environ.get('K_SERVICE'):
#     print("WARNING: Using default Flask secret key in production. Please set FLASK_SECRET_KEY environment variable securely.")


# # --- Helper to get user ID ---
# def get_user_id():
#     """
#     Returns a user ID. In a real app, this would come from authenticated user.
#     For this example, we'll use a session-based ID or generate a new UUID.
#     """
#     # Use session ID for game persistence across requests for the same user
#     if 'user_session_id' not in session:
#         session['user_session_id'] = str(uuid.uuid4())
#     return session['user_session_id']

# # Firestore Collection Path
# def get_game_collection_ref(user_id):
#     # Data will be stored in /artifacts/{appId}/users/{userId}/game_states
#     # This path adheres to Firestore security rules for user-specific private data.
#     return db_firestore.collection(f"artifacts/{app_id}/users/{user_id}/game_states")


# # --- Routes ---
# @app.route('/')
# def serve_index():
#     """Serves the index.html file."""
#     return send_from_directory(app.static_folder, 'index.html')

# @app.route('/save_game', methods=['POST'])
# def save_game():
#     """Saves the current game state to Firestore."""
#     if not db_firestore:
#         return jsonify({"status": "error", "message": "Firestore not initialized"}), 500

#     game_data = request.json
#     if not game_data:
#         return jsonify({"status": "error", "message": "No game data provided"}), 400

#     user_id = get_user_id()
#     game_id = session.get('game_id') # Get game_id from session
#     if not game_id:
#         game_id = str(uuid.uuid4()) # Generate new game_id if not in session
#         session['game_id'] = game_id

#     try:
#         # Store in Firestore
#         game_ref = get_game_collection_ref(user_id).document(game_id)
#         game_ref.set({"state_data": json.dumps(game_data), "timestamp": firestore.SERVER_TIMESTAMP})
#         app.logger.info(f"Game state saved to Firestore for game_id: {game_id}")

#         return jsonify({"status": "success", "game_id": game_id, "message": "Game state saved"}), 200
#     except Exception as e:
#         app.logger.error(f"Error saving game state: {e}")
#         return jsonify({"status": "error", "message": "Failed to save game state"}), 500

# @app.route('/load_game', methods=['GET'])
# def load_game():
#     """Loads the last saved game state from Firestore."""
#     if not db_firestore:
#         return jsonify({"status": "error", "message": "Firestore not initialized"}), 500

#     user_id = get_user_id()
#     game_id = session.get('game_id')
#     if not game_id:
#         return jsonify({"status": "error", "message": "No active game session"}), 404

#     try:
#         game_ref = get_game_collection_ref(user_id).document(game_id)
#         doc = game_ref.get()
#         if doc.exists:
#             game_data = json.loads(doc.to_dict()["state_data"])
#             app.logger.info(f"Game state loaded from Firestore for game_id: {game_id}")
#             return jsonify({"status": "success", "game_data": game_data}), 200
#         else:
#             app.logger.warning(f"Game state not found in Firestore for game_id: {game_id}")
#             return jsonify({"status": "error", "message": "Game state not found"}), 404
#     except Exception as e:
#         app.logger.error(f"Error loading game state from Firestore: {e}")
#         return jsonify({"status": "error", "message": "Failed to load game state"}), 500

# @app.route('/delete_game', methods=['POST'])
# def delete_game():
#     """Deletes the current game state from Firestore."""
#     if not db_firestore:
#         return jsonify({"status": "error", "message": "Firestore not initialized"}), 500

#     user_id = get_user_id()
#     game_id = session.get('game_id')
#     if not game_id:
#         return jsonify({"status": "error", "message": "No active game session to delete"}), 404

#     try:
#         game_ref = get_game_collection_ref(user_id).document(game_id)
#         game_ref.delete()
#         app.logger.info(f"Game state deleted from Firestore for game_id: {game_id}")
        
#         session.pop('game_id', None) # Clear session game_id
#         return jsonify({"status": "success", "message": "Game state deleted"}), 200
#     except Exception as e:
#         app.logger.error(f"Error deleting game state: {e}")
#         return jsonify({"status": "error", "message": "Failed to delete game state"}), 500


# if __name__ == '__main__':
#     port = int(os.environ.get('PORT', 8080))
#     app.run(debug=False, host='0.0.0.0', port=port)


# # app.py
# import os
# from flask import Flask, send_from_directory, request, jsonify, session
# import json
# import uuid
# import firebase_admin
# from firebase_admin import credentials, firestore

# app = Flask(__name__, static_folder='.')

# # --- Firebase (Firestore) Initialization ---
# # Firebase config and initial auth token are provided by the Canvas environment
# firebase_config_str = os.environ.get('__firebase_config')
# initial_auth_token = os.environ.get('__initial_auth_token')
# app_id = os.environ.get('__app_id', 'default-app-id') # Get app ID from environment

# db_firestore = None

# # Initialize Firebase Admin SDK
# try:
#     if firebase_config_str:
#         firebase_config = json.loads(firebase_config_str)
#         # In Cloud Run, default credentials (service account) are typically used for Firebase Admin SDK.
#         # The __firebase_config and __initial_auth_token are usually for frontend client-side auth.
#         # For backend Admin SDK, `firebase_admin.initialize_app()` without args uses default credentials.
#         firebase_admin.initialize_app()
#         # Connect to the default Firestore database (assuming it was created via Firebase)
#         db_firestore = firestore.client() # Removed database="rjdb"
#         app.logger.info("Firebase Admin SDK initialized successfully for default database.")
#     else:
#         app.logger.warning("Firebase config not found. Firestore operations will not work.")
# except Exception as e:
#     app.logger.error(f"Error initializing Firebase Admin SDK: {e}")

# # --- Flask Session Secret Key ---
# app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_super_secret_key_for_dev_fallback_please_change_in_prod')
# if app.secret_key == 'a_super_secret_key_for_dev_fallback_please_change_in_prod' and os.environ.get('K_SERVICE'):
#     print("WARNING: Using default Flask secret key in production. Please set FLASK_SECRET_KEY environment variable securely.")


# # --- Helper to get user ID ---
# def get_user_id():
#     """
#     Returns a user ID. In a real app, this would come from authenticated user.
#     For this example, we'll use a session-based ID or generate a new UUID.
#     """
#     # Use session ID for game persistence across requests for the same user
#     if 'user_session_id' not in session:
#         session['user_session_id'] = str(uuid.uuid4())
#     return session['user_session_id']

# # Firestore Collection Path
# def get_game_collection_ref(user_id):
#     # Data will be stored in /artifacts/{appId}/users/{userId}/game_states
#     # This path adheres to Firestore security rules for user-specific private data.
#     return db_firestore.collection(f"artifacts/{app_id}/users/{user_id}/game_states")


# # --- Routes ---
# @app.route('/')
# def serve_index():
#     """Serves the index.html file."""
#     return send_from_directory(app.static_folder, 'index.html')

# @app.route('/save_game', methods=['POST'])
# def save_game():
#     """Saves the current game state to Firestore."""
#     if not db_firestore:
#         return jsonify({"status": "error", "message": "Firestore not initialized"}), 500

#     game_data = request.json
#     if not game_data:
#         return jsonify({"status": "error", "message": "No game data provided"}), 400

#     user_id = get_user_id()
#     game_id = session.get('game_id') # Get game_id from session
#     if not game_id:
#         game_id = str(uuid.uuid4()) # Generate new game_id if not in session
#         session['game_id'] = game_id

#     try:
#         # Store in Firestore
#         game_ref = get_game_collection_ref(user_id).document(game_id)
#         game_ref.set({"state_data": json.dumps(game_data), "timestamp": firestore.SERVER_TIMESTAMP})
#         app.logger.info(f"Game state saved to Firestore for game_id: {game_id}")

#         return jsonify({"status": "success", "game_id": game_id, "message": "Game state saved"}), 200
#     except Exception as e:
#         app.logger.error(f"Error saving game state: {e}")
#         return jsonify({"status": "error", "message": "Failed to save game state"}), 500

# @app.route('/load_game', methods=['GET'])
# def load_game():
#     """Loads the last saved game state from Firestore."""
#     if not db_firestore:
#         return jsonify({"status": "error", "message": "Firestore not initialized"}), 500

#     user_id = get_user_id()
#     game_id = session.get('game_id')
#     if not game_id:
#         return jsonify({"status": "error", "message": "No active game session"}), 404

#     try:
#         game_ref = get_game_collection_ref(user_id).document(game_id)
#         doc = game_ref.get()
#         if doc.exists:
#             game_data = json.loads(doc.to_dict()["state_data"])
#             app.logger.info(f"Game state loaded from Firestore for game_id: {game_id}")
#             return jsonify({"status": "success", "game_data": game_data}), 200
#         else:
#             app.logger.warning(f"Game state not found in Firestore for game_id: {game_id}")
#             return jsonify({"status": "error", "message": "Game state not found"}), 404
#     except Exception as e:
#         app.logger.error(f"Error loading game state from Firestore: {e}")
#         return jsonify({"status": "error", "message": "Failed to load game state"}), 500

# @app.route('/delete_game', methods=['POST'])
# def delete_game():
#     """Deletes the current game state from Firestore."""
#     if not db_firestore:
#         return jsonify({"status": "error", "message": "Firestore not initialized"}), 500

#     user_id = get_user_id()
#     game_id = session.get('game_id')
#     if not game_id:
#         return jsonify({"status": "error", "message": "No active game session to delete"}), 404

#     try:
#         game_ref = get_game_collection_ref(user_id).document(game_id)
#         game_ref.delete()
#         app.logger.info(f"Game state deleted from Firestore for game_id: {game_id}")
        
#         session.pop('game_id', None) # Clear session game_id
#         return jsonify({"status": "success", "message": "Game state deleted"}), 200
#     except Exception as e:
#         app.logger.error(f"Error deleting game state: {e}")
#         return jsonify({"status": "error", "message": "Failed to delete game state"}), 500


# if __name__ == '__main__':
#     port = int(os.environ.get('PORT', 8080))
#     app.run(debug=False, host='0.0.0.0', port=port)
