# Smart Demand Forecasting — Dockerfile
# ---------------------------------------
# Solves the classic "works on my machine" setup pain (venv creation errors,
# pip timeouts, Windows path issues) with one reproducible environment.
#
# Build:  docker build -t smart-demand-forecasting .
# Run:    docker run -p 8501:8501 smart-demand-forecasting
# Then open http://localhost:8501

FROM python:3.10-slim

WORKDIR /app

# Install system deps needed by xgboost / scientific python wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer caching — only re-installs
# when requirements.txt actually changes, not on every code edit)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# .env is intentionally NOT baked into the image — mount it at runtime instead:
#   docker run -p 8501:8501 -v $(pwd)/.env:/app/.env smart-demand-forecasting
# This keeps real credentials out of the image entirely.

EXPOSE 8501

# Train the model once at container startup if it doesn't exist yet, then launch the app.
CMD ["sh", "-c", "test -f models/model.pkl || python main.py; streamlit run app.py --server.address=0.0.0.0"]
