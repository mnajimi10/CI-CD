FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY cafe_atlas/ cafe_atlas/
COPY data/raw/ data/raw/

ENTRYPOINT ["python", "-m", "cafe_atlas.pipeline"]
