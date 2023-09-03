FROM python:3.10-slim

ENV PYTHONUNBUFFERED 1

WORKDIR /code

RUN apt-get update \
    && apt-get install -y curl unzip \
    && rm -rf /var/lib/apt/lists/*
RUN bash -c "$(curl -L https://github.com/Gozargah/Marzban-scripts/raw/master/install_latest_xray.sh)"

COPY . /code

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

RUN apt-get remove -y curl unzip

CMD ["bash", "-c", "python main.py"]