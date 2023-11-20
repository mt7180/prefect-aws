FROM prefecthq/prefect:2-python3.10-conda
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY flows/ .
CMD ["python", "rget_report.py"]