from prefect import flow, task, get_run_logger
from prefect.blocks.system import Secret, String
from prefect.task_runners import SequentialTaskRunner
from prefect_email import EmailServerCredentials, email_send_message

from typing import OrderedDict, NamedTuple, List
import pandas as pd
from dotenv import load_dotenv

from data import fetch_forecast_data
# from database_handling import (
#     get_all_users_from_database,
# )

class User(NamedTuple):
    name: str
    email: str
    country_code: str


@task(retries=3, retry_delay_seconds=60)
def get_registered_users_task() -> List[User]:
    """Read all registered users from database"""
    # todo: users=[Users(**user) for user in get_all_users_from_database()]
    # todo: uncomment again: return get_all_users_from_database()
    # for test purpose:
    return [User("test_user",String.load("test-email"), "DE")]


@flow
def send_email_flow(user: User, data: str):
    assert isinstance(data, str)
    logger = get_run_logger()
    logger.info(data)
    logger.info(user.email)
    email_server_credentials = EmailServerCredentials.load("my-email-credentials")
    # attachment = pathlib.Path(__file__).parent.absolute() / "attachment.txt"
    # with open(attachment, "rb") as f:
    #     attachment_text = f.read()
    line1 = f"Hello {user.name}, <br>"
    line2 = f"Please find our lastest update for the following region: {user.country_code}<br><br>"
    line3 = f"<h1>Forecast:</h1>"
    subject = email_send_message.with_options(name="send-an-email").submit(
        email_server_credentials=email_server_credentials,
        subject="Prefect Notification",
        msg=line1+line2+line3+data,
        email_to=user.email,
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
    entsoe_api_key = Secret.load("entsoe-api-key").get()
    data_dict = fetch_forecast_data(country_code, entsoe_api_key)
    return data_dict


@flow(task_runner=SequentialTaskRunner(), retries=5, retry_delay_seconds=5)
def send_energy_report_flow():
    users = get_registered_users_task()
    logger=get_run_logger()
    for user in users:
        data_dict = get_forecast_data_task(user.country_code)
        data = data_dict["df_generation_forecast"] # popitem has better TC than accessing last one
        logger.info(data)
        # send_task(data, user["email"])
        send_email_flow(user, data.to_frame().to_html())


if __name__ == "__main__":
    load_dotenv(override=True)
    deploy = True
    if deploy:
        send_energy_report_flow.serve(name="my-energy_report-deployment", cron="0 * * * 1")
    else:
        send_energy_report_flow()
