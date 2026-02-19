# Use Python 3.11
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install system dependencies for CrewAI
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your code (main.py)
COPY . .

# Hugging Face uses port 7860 by default
EXPOSE 7860

# Run the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]