# app.py
from flask import Flask, send_from_directory
import os

app = Flask(__name__)

# Serve static files from the current directory
@app.route('/')
def serve_index():
    return send_from_directory(os.getcwd(), 'index.html')

if __name__ == '__main__':
    # Cloud Run will set the PORT environment variable
    port = int(os.environ.get('PORT', 443))
    app.run(host='0.0.0.0', port=port)

