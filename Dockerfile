# app/Dockerfile

FROM python:3.11.1-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    # build-essential \
    # curl \
    # software-properties-common \
    git
    # && rm -rf /var/lib/apt/lists/*


RUN git clone https://github.com/juancotrino/connecta-analytics.git .

COPY firebase_key.json firebase_key.json

RUN pip install -r requirements.txt

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "00_Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
