FROM --platform=linux/amd64 prefecthq/prefect:2-latest
COPY requirements.txt .
WORKDIR /code
COPY ./requirements.txt ./requirements.txt
RUN pip install --upgrade  -r requirements.txt
COPY /prefect_flows /code/prefect_flows
COPY /data_extraction /code/data_extraction
COPY /user_management /code/user_management
CMD python -m prefect_flows