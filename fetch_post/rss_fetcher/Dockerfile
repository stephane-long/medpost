FROM python:3.11-slim

WORKDIR /app

# Installer le package partagé
COPY setup.py /shared/setup.py
COPY shared /shared/shared
RUN pip install --no-cache-dir /shared

# Installer les dépendances du service
COPY rss_fetcher/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY rss_fetcher/ .
CMD ["python", "main.py"]
