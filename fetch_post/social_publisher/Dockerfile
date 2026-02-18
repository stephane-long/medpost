FROM python:3.11-slim

WORKDIR /app

# Installer le package partagé
COPY setup.py /shared/setup.py
COPY shared /shared/shared
RUN pip install --no-cache-dir /shared

# Installer les dépendances du service
COPY social_publisher/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY social_publisher/ .
CMD ["python", "main.py"]
