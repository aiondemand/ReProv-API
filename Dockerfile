FROM python:3.10

WORKDIR /app

COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && \
    apt-get install -y graphviz

COPY ./src /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9090"]
