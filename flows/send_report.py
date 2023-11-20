from prefect import flow, task
from typing import OrderedDict
from datetime import timedelta
from prefect import get_run_logger
import pandas as pd
import os
from dotenv import load_dotenv

from prefect_email import EmailServerCredentials, email_send_message
from data import fetch_forecast_data
# from database_handling import (
#     get_all_users_from_database,
# )



@task(retries=3, retry_delay_seconds=60)
def get_registered_users_task():
    """Read all registered users from database"""
    # todo: uncomment again: return get_all_users_from_database()
    # for test purpose:
    return [{"name": "test_user", "email": os.getenv("TEST_USER_EMAIL",""), "country_code": "DE"}]


@flow
def send_email_flow(email_address, data):
    assert isinstance(data, str)
    logger = get_run_logger()
    logger.info(data)
    logger.info(email_address)
    email_server_credentials = EmailServerCredentials.load("my-email-credentials")
    # attachment = pathlib.Path(__file__).parent.absolute() / "attachment.txt"
    # with open(attachment, "rb") as f:
    #     attachment_text = f.read()
    
    subject = email_send_message.with_options(name="send-an-email").submit(
        email_server_credentials=email_server_credentials,
        subject="Prefect email notification",
        msg=data,
        email_to=email_address,
        #attachments=["example.txt"]
    )
    return subject

@task(retries=3, retry_delay_seconds=60)
def send_task(data: pd.DataFrame, email: str):
    #create_report_task(data)
    # todo put email block
    # attach report
    # attachment possible? https://discourse.prefect.io/t/how-to-send-an-attachment-within-an-email-task/641
    # https://annageller.com/blog/8-must-know-tricks-to-use-aws-s3-more-effectively-in-python
    # https://github.com/PrefectHQ/prefect-email/blob/main/README.md
    # https://linen.prefect.io/t/2435328/sure-thank-you
    # https://github.com/PrefectHQ/prefect-email/blob/main/prefect_email/message.py
    print(f"email to {email}: {data}")


@task(retries=3, retry_delay_seconds=60)
def create_report_task(data: pd.DataFrame):
    pass


@task(retries=3, retry_delay_seconds=60)
def get_forecast_data_task(country_code: str) -> OrderedDict[str,pd.DataFrame]:
    data_dict = fetch_forecast_data(country_code)
    return data_dict


@flow()
def send_energy_report_flow():
    users = get_registered_users_task()
    logger=get_run_logger()
    for user in users:
        data_dict = get_forecast_data_task(user["country_code"])
        data = data_dict["df_generation_forecast"] # popitem has better TC than accessing last one
        logger.info(data)
        # send_task(data, user["email"])
        send_email_flow(user["email"], data.to_frame().to_html())


if __name__ == "__main__":
    load_dotenv(override=True)
    deploy = False
    if deploy:
        send_energy_report_flow.serve(name="my-first-deployment")
    else:
        send_energy_report_flow()
