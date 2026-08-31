# FROM python:3.13-slim
# WORKDIR /app

# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# RUN adduser --disabled-password --gecos "" myuser && \
#     chown -R myuser:myuser /app

# COPY . .

# USER myuser

# ENV PATH="/home/myuser/.local/bin:$PATH"

# CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]

FROM python:3.13-slim

WORKDIR /app

# Install system deps for matplotlib/pdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN adduser --disabled-password --gecos "" myuser

COPY --chown=myuser:myuser . .
RUN chown -R myuser:myuser /app

USER myuser

ENV PATH="/home/myuser/.local/bin:$PATH"
# Suppress matplotlib interactive backend warnings
ENV MPLBACKEND=Agg

EXPOSE 8080

# Use main_cloudrun.py — custom report generation API + HTML test UI
CMD ["sh", "-c", "uvicorn main_cloudrun:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-keep-alive 3600"]
