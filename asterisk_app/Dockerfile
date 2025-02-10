FROM ubuntu:22.04

# Обновление системы и установка необходимых пакетов
RUN apt-get update && \
    apt-get install -y build-essential wget linux-headers-generic git \
    libxml2-dev libxslt1-dev sqlite3 libsqlite3-dev uuid-dev libjansson-dev \
    libsrtp2-dev libssl-dev libpri-dev libedit-dev curl zlib1g-dev && \
    apt-get clean

# Скачивание и установка Asterisk
RUN mkdir -p /usr/src/asterisk && \
    cd /usr/src/asterisk && \
    wget https://downloads.asterisk.org/pub/telephony/asterisk/asterisk-22.2.0.tar.gz && \
    tar xvzf asterisk-22.2.0.tar.gz && \
    cd asterisk-22.2.0 && \
    ./configure && \
    make && \
    make install && \
    make samples && \
    make config

# Установка службы Asterisk
# RUN ln -sf /usr/sbin/safe_asterisk /usr/local/bin/asterisk

# Настройка рабочей директории
WORKDIR /app

# Запуск Asterisk
CMD ["asterisk", "-f", "-g", "-vvv"]