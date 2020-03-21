FROM python:3.8-buster

WORKDIR /app
COPY nogi/ /app/nogi
COPY blog.py /app/blog.py
COPY blog.sh /app/blog.sh
COPY requirements.txt /app

RUN pip install -r requirements.txt
RUN chmod 755 /app/blog.sh
CMD [ "/app/blog.sh" ]