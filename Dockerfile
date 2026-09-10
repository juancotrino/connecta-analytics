# app/Dockerfile

FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*


RUN git clone -b dev https://github.com/juancotrino/connecta-analytics.git .

# COPY firebase_key.json firebase_key.json

RUN pip install -r requirements.txt

ENV PORT=8080

EXPOSE ${PORT}

HEALTHCHECK CMD curl --fail http://localhost:${PORT}/_stcore/health

ENTRYPOINT ["sh", "-c", "exec streamlit run main.py --server.port=${PORT} --server.address=0.0.0.0"]
