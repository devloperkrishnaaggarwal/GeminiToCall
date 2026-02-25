FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY agent.py .

# LiveKit agents need a writable temp dir
ENV PYTHONUNBUFFERED=1

CMD ["python", "agent.py", "start"]
