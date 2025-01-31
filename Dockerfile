FROM python:3.11

WORKDIR .

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8080"]