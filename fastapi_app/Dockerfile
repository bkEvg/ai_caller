FROM python:3.10-slim
RUN apt update && apt install curl -y
WORKDIR app/
COPY ./requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN chmod +x ./entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]