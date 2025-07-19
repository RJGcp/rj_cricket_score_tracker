How to use this application
1. Local Testing with Docker
To test your Cricket Score Tracker application locally using Docker, follow these steps:

Install Docker: If you don't have Docker Desktop (for Windows/macOS) or Docker Engine (for Linux) installed, download it from the official Docker website: https://www.docker.com/products/docker-desktop

Create Project Files: Ensure you have index.html, app.py, requirements.txt, and Dockerfile in the same directory.

Navigate to Project Directory: Open your terminal or command prompt and navigate to the directory where your project files are located.

Build the Docker Image:
This command builds the Docker image based on your Dockerfile and tags it as cricket-tracker-local.

docker build -t cricket-tracker-local .

Run the Docker Container:
This command runs a container from your newly built image. The -p 8080:8080 flag maps port 8080 on your local machine to port 8080 inside the container, allowing you to access the web app.

docker run -p 8080:8080 cricket-tracker-local

Access the Application:
Open your web browser and go to:

http://localhost:8080

You should see your Cricket Score Tracker running. Check your terminal for any error messages if the page doesn't load.

2. Pushing to Google Cloud Artifact Registry
Google Cloud Artifact Registry is a universal package manager that supports Docker images. It's the recommended way to store your container images on GCP.

Set up Google Cloud SDK:
If you haven't already, install the Google Cloud SDK: https://cloud.google.com/sdk/docs/install

Then, initialize it and set your project:

gcloud init
gcloud config set project YOUR_PROJECT_ID # Replace YOUR_PROJECT_ID with your actual Google Cloud Project ID

Enable Artifact Registry API:
Ensure the Artifact Registry API is enabled for your project.

gcloud services enable artifactregistry.googleapis.com

Create an Artifact Registry Repository:
Create a Docker repository in Artifact Registry. Choose a region (e.g., us-central1, asia-south1) and a repository name (e.g., my-docker-repo).

gcloud artifacts repositories create my-docker-repo --repository-format=docker \
    --location=us-central1 --description="Docker repository for cricket tracker"

Replace us-central1 with your desired region.

Configure Docker to Authenticate:
Configure Docker to authenticate with Artifact Registry. This command updates your Docker configuration to use gcloud as a credential helper.

gcloud auth configure-docker us-central1-docker.pkg.dev

Replace us-central1 with your repository's region.

Tag Your Docker Image:
Tag your locally built Docker image with the Artifact Registry path.

docker tag cricket-tracker-local us-central1-docker.pkg.dev/YOUR_PROJECT_ID/my-docker-repo/cricket-tracker:latest

Replace YOUR_PROJECT_ID with your Google Cloud Project ID.

Replace us-central1 with your repository's region.

cricket-tracker:latest is the image name and tag you'll use.

Push the Docker Image:
Push the tagged image to your Artifact Registry repository.

docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/my-docker-repo/cricket-tracker:latest

This will upload your container image to Google Cloud.

3. Deploying to Cloud Run
Once your Docker image is in Artifact Registry, you can deploy it to Cloud Run.

Enable Cloud Run API:
Ensure the Cloud Run API is enabled for your project.

gcloud services enable run.googleapis.com

Deploy the Service:
Use the gcloud run deploy command, referencing the image path in Artifact Registry.

gcloud run deploy cricket-tracker --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/my-docker-repo/cricket-tracker:latest \
    --platform managed --region us-central1 --allow-unauthenticated

cricket-tracker: The name of your Cloud Run service.

--image: The full path to your image in Artifact Registry.

--platform managed: Specifies that you want to use the fully managed Cloud Run environment.

--region us-central1: Choose the Google Cloud region where you want to deploy your service (ideally the same as your Artifact Registry repo for performance).

--allow-unauthenticated: Makes your web app publicly accessible. Remove this flag if you want to restrict access and configure authentication later.

After the deployment is complete, Cloud Run will provide you with a URL where your Cricket Score Tracker web app is live!

Troubleshooting Common Deployment Issues:

403 Forbidden / Permission Denied:
This error often means the service account used by Cloud Build (or your user account) lacks necessary permissions.

Go to IAM & Admin > IAM in the Google Cloud Console.

Find the service account associated with Cloud Build (usually ends with @cloudbuild.gserviceaccount.com).

Ensure it has roles like Cloud Build Service Account, Storage Object Admin, and Artifact Registry Writer (for pushing to AR).

For your user account, ensure you have roles like Cloud Run Admin, Service Account User, and Artifact Registry Reader.

"bucket does not exist" Error:
This occurs if the default Cloud Build storage bucket (YOUR_PROJECT_ID_cloudbuild) is missing.

Ensure the Cloud Build API is enabled in your project.

If it's still missing, manually create a bucket with the exact name YOUR_PROJECT_ID_cloudbuild in Cloud Storage and grant the Cloud Build service account Storage Object Creator and Storage Object Viewer roles.

"Revision is not ready" / Container failed to start:
This means your container didn't start successfully or didn't listen on the expected port (8080).

Check Cloud Run Logs: In the Google Cloud Console, navigate to your Cloud Run service, then go to the Logs tab. This is the most important step for diagnosing startup failures. Look for Python tracebacks or Gunicorn errors.

Verify Dockerfile and app.py: Ensure CMD in Dockerfile is correct (CMD gunicorn --bind 0.0.0.0:$PORT app:app) and that app.py is correctly defined and accessible in the container's /app directory.

Test Locally: Always test your Docker image locally using docker build and docker run before deploying to Cloud Run. This helps isolate issues to your application code or Dockerfile.

Test this in local dev machine:
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    gcloud auth application-default login
    export FLASK_SECRET_KEY="f9264b6c5c6c448da9ec4ee1291e9e495146a2c8b8b42be71adandansdbasfbasou"
    export __firebase_config="{}" # Empty JSON string for local testing
    export __initial_auth_token=""
    export __app_id="local-test-app"
    export PORT=8080 # Optional, but good practice
    python3 app.py