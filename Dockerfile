FROM python:3.13

RUN mkdir /appdir
RUN cd /appdir

COPY . /.

RUN pip install -r requirements.txt

CMD ["python3", "app.py"]