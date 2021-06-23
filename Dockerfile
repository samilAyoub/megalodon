FROM python:3

WORKDIR /usr/src/app

COPY megalodon.py ./
COPY config.py ./
COPY helper.py ./
COPY keys.json ./
COPY settings.json ./
COPY requirements.txt ./
COPY install_talib.sh ./
COPY trade_log.csv ./

RUN apt-get update &&\
    apt-get install --assume-yes git &&\
    pip install --no-cache-dir -r requirements.txt &&\
    bash install_talib.sh 

CMD ["python3", "megalodon.py"]

