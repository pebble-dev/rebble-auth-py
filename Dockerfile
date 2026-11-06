FROM python:3.14-slim
ADD . /code
WORKDIR /code
RUN pip install -r requirements.txt
ENV FLASK_APP=auth FLASK_ENV=development FLASK_DEBUG=1
CMD ["flask", "run", "-h", "0.0.0.0"]
