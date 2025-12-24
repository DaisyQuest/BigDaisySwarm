FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
  && apt-get install -y --no-install-recommends postgresql postgresql-client \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY example_server/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN pip install --no-cache-dir . \
  && chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8080

ENV PGDATA=/var/lib/postgresql/data

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "-m", "bigdaisyswarm.example_server", "--host", "0.0.0.0", "--port", "8080"]
