FROM python:3.10
RUN apt update && apt upgrade -y && apt install ffmpeg -y
RUN pip install --upgrade pip --no-cache
WORKDIR /app
COPY ./requirements.txt .
RUN pip install -r requirements.txt
RUN apt-get install flac -y
COPY . .
CMD ["python", "main.py"]