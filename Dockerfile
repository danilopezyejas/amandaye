FROM python:3.9

WORKDIR /app

ENV PYTHONPATH="/app:${PYTHONPATH}"

COPY amandaye_backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY amandaye_backend/ ./amandaye_backend/

WORKDIR /app/amandaye_backend

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
