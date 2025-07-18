# app.py
import os
from flask import Flask, send_from_directory, request, jsonify, session
import json
import uuid
import firebase_admin
from firebase_admin import credentials, firestore
from pymemcache.client import base # Using pymemcache for Memcached client

app = Flask(__name__, static_folder='.')

# --- Firebase (Firestore) Initialization ---
# Firebase config and initial auth token are provided by the Canvas environment
# We need to parse the JSON string for firebaseConfig
firebase_config_str = os.environ.get('__firebase_config')
initial_auth_token = os.environ.get('__initial_auth_token')
app_id = os.environ.get('__app_id', 'default-app-id') # Get app ID from environment

db_firestore = None
memcached_client = None

# Initialize Firebase Admin SDK
try:
    if firebase_config_str:
        firebase_config = json.loads(firebase_config_str)
        # Use a dictionary to represent the service account credentials
        # This is a common way to initialize Firebase Admin SDK in environments like Cloud Run
        # where you don't have a service account JSON file on disk.
        # The key components (project_id, private_key_id, private_key, client_email, client_id, auth_uri, token_uri, auth_provider_x509_cert_url, client_x509_cert_url)
        # are typically part of the firebase_config JSON.
        # However, for the Canvas environment, the __firebase_config might be a simple API key.
        # We need to adapt the initialization based on the actual content of __firebase_config.
        # Assuming __firebase_config provides sufficient details for `credentials.Certificate`
        # or that default application credentials are used if running in GCP.

        # If __firebase_config is a full service account JSON:
        # cred = credentials.Certificate(firebase_config)
        # firebase_admin.initialize_app(cred)

        # If running in a GCP environment (like Cloud Run), default credentials often work.
        # If __firebase_config is just an API key, it's not used for Admin SDK init directly.
        # For Cloud Run, the default service account will be used for Firestore permissions.
        firebase_admin.initialize_app() # Initializes using default credentials (e.g., Cloud Run service account)
        db_firestore = firestore.client()
        app.logger.info("Firebase Admin SDK initialized successfully.")
    else:
        app.logger.warning("Firebase config not found. Firestore operations will not work.")
except Exception as e:
    app.logger.error(f"Error initializing Firebase Admin SDK: {e}")

# --- Memcached Initialization ---
memcached_host = os.environ.get('MEMCACHED_HOST')
if memcached_host:
    try:
        memcached_client = base.Client((memcached_host, 11211)) # Default Memcached port is 11211
        app.logger.info(f"Memcached client initialized for host: {memcached_host}")
    except Exception as e:
        app.logger.error(f"Error initializing Memcached client: {e}")
else:
    app.logger.warning("MEMCACHED_HOST environment variable not set. Memcached caching will not be used.")


# --- Flask Session Secret Key ---
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_super_secret_key_for_dev_fallback_please_change_in_prod')
if app.secret_key == 'a_super_secret_key_for_dev_fallback_please_change_in_prod' and os.environ.get('K_SERVICE'):
    print("WARNING: Using default Flask secret key in production. Please set FLASK_SECRET_KEY environment variable securely.")


# --- Helper to get user ID ---
def get_user_id():
    """
    Returns a user ID. In a real app, this would come from authenticated user.
    For this example, we'll use a session-based ID or generate a new UUID.
    """
    # If initial_auth_token provides a UID, use it. (This is for Canvas environment specific auth)
    # In a real Cloud Run app, you'd use Firebase Auth to get current_user.uid
    if initial_auth_token:
        # This is a simplified assumption for the Canvas environment.
        # In a real app, you'd decode the token to get the UID.
        # For now, we'll just use a fixed ID derived from the app_id for demo purposes
        # or a session ID if no specific user ID is available from auth.
        pass # We'll rely on session or generate UUID for game_id

    # Use session ID for game persistence across requests for the same user
    if 'user_session_id' not in session:
        session['user_session_id'] = str(uuid.uuid4())
    return session['user_session_id']

# Firestore Collection Path
def get_game_collection_ref(user_id):
    # Data will be stored in /artifacts/{appId}/users/{userId}/game_states
    # This path adheres to Firestore security rules for user-specific private data.
    return db_firestore.collection(f"artifacts/{app_id}/users/{user_id}/game_states")


# --- Routes ---
@app.route('/')
def serve_index():
    """Serves the index.html file."""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/save_game', methods=['POST'])
def save_game():
    """Saves the current game state to Firestore and caches in Memcached."""
    if not db_firestore:
        return jsonify({"status": "error", "message": "Firestore not initialized"}), 500

    game_data = request.json
    if not game_data:
        return jsonify({"status": "error", "message": "No game data provided"}), 400

    user_id = get_user_id()
    game_id = session.get('game_id') # Get game_id from session
    if not game_id:
        game_id = str(uuid.uuid4()) # Generate new game_id if not in session
        session['game_id'] = game_id

    try:
        # Cache in Memcached first
        if memcached_client:
            memcached_client.set(f"game_state:{game_id}", json.dumps(game_data))
            app.logger.info(f"Game state cached in Memcached for game_id: {game_id}")

        # Store in Firestore
        game_ref = get_game_collection_ref(user_id).document(game_id)
        game_ref.set({"state_data": json.dumps(game_data), "timestamp": firestore.SERVER_TIMESTAMP})
        app.logger.info(f"Game state saved to Firestore for game_id: {game_id}")

        return jsonify({"status": "success", "game_id": game_id, "message": "Game state saved"}), 200
    except Exception as e:
        app.logger.error(f"Error saving game state: {e}")
        return jsonify({"status": "error", "message": "Failed to save game state"}), 500

@app.route('/load_game', methods=['GET'])
def load_game():
    """Loads the last saved game state from Memcached or Firestore."""
    if not db_firestore:
        return jsonify({"status": "error", "message": "Firestore not initialized"}), 500

    user_id = get_user_id()
    game_id = session.get('game_id')
    if not game_id:
        return jsonify({"status": "error", "message": "No active game session"}), 404

    game_data = None

    # Try loading from Memcached cache first
    if memcached_client:
        cached_data = memcached_client.get(f"game_state:{game_id}")
        if cached_data:
            game_data = json.loads(cached_data)
            app.logger.info(f"Game state loaded from Memcached for game_id: {game_id}")

    # If not in cache, load from Firestore
    if not game_data:
        try:
            game_ref = get_game_collection_ref(user_id).document(game_id)
            doc = game_ref.get()
            if doc.exists:
                game_data = json.loads(doc.to_dict()["state_data"])
                app.logger.info(f"Game state loaded from Firestore for game_id: {game_id}")
                # Cache in Memcached for future requests
                if memcached_client:
                    memcached_client.set(f"game_state:{game_id}", json.dumps(game_data))
                    app.logger.info(f"Game state cached in Memcached after Firestore load for game_id: {game_id}")
            else:
                app.logger.warning(f"Game state not found in Firestore for game_id: {game_id}")
                return jsonify({"status": "error", "message": "Game state not found"}), 404
        except Exception as e:
            app.logger.error(f"Error loading game state from Firestore: {e}")
            return jsonify({"status": "error", "message": "Failed to load game state"}), 500

    return jsonify({"status": "success", "game_data": game_data}), 200

@app.route('/delete_game', methods=['POST'])
def delete_game():
    """Deletes the current game state from Memcached and Firestore."""
    if not db_firestore:
        return jsonify({"status": "error", "message": "Firestore not initialized"}), 500

    user_id = get_user_id()
    game_id = session.get('game_id')
    if not game_id:
        return jsonify({"status": "error", "message": "No active game session to delete"}), 404

    try:
        # Delete from Memcached
        if memcached_client:
            memcached_client.delete(f"game_state:{game_id}")
            app.logger.info(f"Game state deleted from Memcached for game_id: {game_id}")
        
        # Delete from Firestore
        game_ref = get_game_collection_ref(user_id).document(game_id)
        game_ref.delete()
        app.logger.info(f"Game state deleted from Firestore for game_id: {game_id}")
        
        session.pop('game_id', None) # Clear session game_id
        return jsonify({"status": "success", "message": "Game state deleted"}), 200
    except Exception as e:
        app.logger.error(f"Error deleting game state: {e}")
        return jsonify({"status": "error", "message": "Failed to delete game state"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
