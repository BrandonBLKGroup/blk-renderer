FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create templates directory
RUN mkdir -p /app/templates

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY render.py server.py ./

# Copy template files (from repo root)
COPY BLK_Group_-_LPT_-_Social_Media_-_TEMPLATE.psd /app/templates/
COPY Antro_Vectra.otf /app/templates/

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "--workers", "2", "server:app"]
