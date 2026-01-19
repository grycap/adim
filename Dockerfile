FROM python:3.12-alpine3.23

LABEL maintainer="Miguel Caballer <micafer1@upv.es>"
LABEL version="1.0.0"
LABEL description="Container image to run the AWM API service."

RUN mkdir -p /app/awm
WORKDIR /app

RUN pip3 install --no-cache-dir gunicorn==23.0.0

COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r requirements.txt

COPY ./awm /app/awm

EXPOSE 8080
ENV WORKERS=4

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "-k", "uvicorn.workers.UvicornWorker", "awm.__main__:create_app()"]
