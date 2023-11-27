FROM --platform=linux/amd64 prefecthq/prefect:2-latest
COPY requirements.txt .
WORKDIR /code
COPY ./requirements.txt ./requirements.txt
RUN pip install --upgrade  -r requirements.txt
COPY /flows /code/flows
CMD python -m flows