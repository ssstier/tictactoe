FROM python:3.9-slim

WORKDIR /app

COPY server.py /app/
COPY tictactoe_pb2.py /app/
COPY requirements.txt /app/
COPY combined_cert.pem /app/
COPY private_key.pem /app/

RUN pip install --trusted-host pypi.python.org -r requirements.txt

EXPOSE 52423

CMD ["python", "server.py"]
