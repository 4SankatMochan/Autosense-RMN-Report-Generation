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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN adduser --disabled-password --gecos "" myuser

COPY --chown=myuser:myuser . .
RUN chown -R myuser:myuser /app

USER myuser

ENV PATH="/home/myuser/.local/bin:$PATH"

EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
