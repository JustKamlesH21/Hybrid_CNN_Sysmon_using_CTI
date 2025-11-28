# Use an official Python runtime as a parent image
# Slim version is lighter and faster
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements_docker.txt .

# Upgrade pip to the latest version to fix large file download hash errors
RUN pip install --no-cache-dir --upgrade pip

# Install any needed packages specified in requirements_docker.txt
# We use --no-cache-dir to keep the image small and --default-timeout to prevent large file corruption
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements_docker.txt

# Copy the rest of the application code
COPY src/ ./src/
COPY *.jpg ./
# We do NOT copy the 'data' folder yet. We will mount it dynamically.

# Create directory for data and models
RUN mkdir data

# Set the entrypoint to python
# This allows you to run "docker run my-image src/train.py"
ENTRYPOINT ["python"]