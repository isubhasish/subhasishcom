FROM subhasishcloud/encoder:latest

WORKDIR /app

COPY . .

RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["python3", "-m", "bot"]