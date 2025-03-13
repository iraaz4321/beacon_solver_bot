FROM python:3.11-slim-buster

WORKDIR /app

# Copy all required files
COPY beacons.starscape .
COPY requirements.txt .
COPY main.py .
COPY starscape_pro.db .

# Install dependencies in a single step to minimize layers
RUN apt-get update && \
    apt-get install -y git libgl1 libglib2.0-0 && \
    apt-get clean && rm -rf /var/lib/apt/lists/

# Upgrade pip and install Python dependencies
RUN pip3 install --upgrade pip && \
    pip3 install -r requirements.txt

# Use JSON array syntax for CMD
CMD ["python", "main.py"]