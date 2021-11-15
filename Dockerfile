FROM python:3.8-buster

WORKDIR /working_dir

COPY requirements-docker.txt ./

RUN pip install -r requirements-docker.txt

RUN pip install git+https://github.com/xzmeng/vnpy

COPY ./working_dir/strategies ./strategies

COPY ./working_dir/main.py ./

RUN mkdir .vntrader

CMD ["pwd"]

CMD ["python", "main.py"]
