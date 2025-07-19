# Dockerfile
# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Add a pip check to verify installed dependencies
# This command will exit with an error if there are unsatisfied dependencies
RUN pip check

# Copy the Flask application file (app.py)
COPY app.py .

# Create the 'templates' directory and copy index.html into it
RUN mkdir -p templates
COPY index.html templates/

# Cloud Run expects the application to listen on the port specified by the PORT environment variable
# Set a default port for local testing, but Cloud Run will override it.
EXPOSE 443
ENV PORT 443

# Run the Flask application using Gunicorn
# Use the -b 0.0.0.0:$(PORT) to bind to all interfaces and the dynamic port
CMD ["gunicorn", "--bind", "0.0.0.0:443", "app:app"]
