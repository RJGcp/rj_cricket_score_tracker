# app.py
import os
from flask import Flask, send_from_directory, request, jsonify, session
import json
import uuid
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__, static_folder='.')

# --- Firebase (Firestore) Initialization ---
# Firebase config and initial auth token are provided by the Canvas environment
firebase_config_str = os.environ.get('__firebase_config')
initial_auth_token = os.environ.get('__initial_auth_token')
app_id = os.environ.get('__app_id', 'default-app-id') # Get app ID from environment

db_firestore = None

# Initialize Firebase Admin SDK
try:
    if firebase_config_str:
        firebase_config = json.loads(firebase_config_str)
        # In Cloud Run, default credentials (service account) are typically used for Firebase Admin SDK.
        # For backend Admin SDK, `firebase_admin.initialize_app()` without args uses default credentials.
        firebase_admin.initialize_app()
        # Connect to the default Firestore database
        db_firestore = firestore.client() # Connects to the default database
        app.logger.info("Firebase Admin SDK initialized successfully for default database.")
    else:
        app.logger.warning("Firebase config not found. Firestore operations will not work.")
except Exception as e:
    app.logger.error(f"Error initializing Firebase Admin SDK: {e}")

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
    """Saves the current game state to Firestore."""
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
    """Loads the last saved game state from Firestore."""
    if not db_firestore:
        return jsonify({"status": "error", "message": "Firestore not initialized"}), 500

    user_id = get_user_id()
    game_id = session.get('game_id')
    if not game_id:
        return jsonify({"status": "error", "message": "No active game session"}), 404

    try:
        game_ref = get_game_collection_ref(user_id).document(game_id)
        doc = game_ref.get()
        if doc.exists:
            game_data = json.loads(doc.to_dict()["state_data"])
            app.logger.info(f"Game state loaded from Firestore for game_id: {game_id}")
            return jsonify({"status": "success", "game_data": game_data}), 200
        else:
            app.logger.warning(f"Game state not found in Firestore for game_id: {game_id}")
            return jsonify({"status": "error", "message": "Game state not found"}), 404
    except Exception as e:
        app.logger.error(f"Error loading game state from Firestore: {e}")
        return jsonify({"status": "error", "message": "Failed to load game state"}), 500

@app.route('/delete_game', methods=['POST'])
def delete_game():
    """Deletes the current game state from Firestore."""
    if not db_firestore:
        return jsonify({"status": "error", "message": "Firestore not initialized"}), 500

    user_id = get_user_id()
    game_id = session.get('game_id')
    if not game_id:
        return jsonify({"status": "error", "message": "No active game session to delete"}), 404

    try:
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
