from prefect import flow, task, get_run_logger
from prefect.blocks.system import Secret, String
from prefect.task_runners import SequentialTaskRunner
from prefect_email import EmailServerCredentials, email_send_message

from typing import OrderedDict, List, Dict, NamedTuple
import pandas as pd
import sys

from flows.data import extract_forecast_data_task

#from data import fetch_forecast_data
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
    user_email = String.load("test-email").value
    # return [User(name="test_user",email=user_email, country_code="DE")]
    return [User("test_user",user_email, "BE")]


@flow(validate_parameters=False)
def send_email_flow(user: User, data: str):
    assert isinstance(data, str)
    logger = get_run_logger()
    logger.info(data)
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


@flow(retries=3, retry_delay_seconds=60)
def extract_data_flow(country_code: str) -> OrderedDict[str,pd.DataFrame]:
    entsoe_api_key = Secret.load("entsoe-api-key").get()
    data_dict = extract_forecast_data_task(country_code, entsoe_api_key)
    return data_dict

########################
# entry_point:

@flow(task_runner=SequentialTaskRunner(), retries=5, retry_delay_seconds=5)
def send_energy_report_flow():
    users = get_registered_users_task()
    logger = get_run_logger()
    for user in users:
        data_dict = extract_data_flow(user.country_code)
        data: pd.DataFrame = data_dict.get("df_generation_forecast", pd.Series())
        logger.info(data)
        # send_task(data, user["email"])
        send_email_flow(user, data.to_frame().to_html())

#########################

def main(deploy: bool = False) -> None:
    """ execute or deploy (depends on deploy parameter) the prefect flow to send an email with an 
    updated dashboard report to each registered user
    """
    from prefect.deployments.runner  import DeploymentImage
    import pathlib

    # load_dotenv(override=True)
    cfd = pathlib.Path(__file__).parent
    if deploy:
        # send_energy_report_flow.serve(
        #     name="my-test-deployment", 
        #    # cron="0 * * * *",    # every hour
        #    # pause_on_shutdown=False,
        # )
        print("flow will be deployed ...")
        send_energy_report_flow.deploy(
            "test_deploy_newsletter", 
            work_pool_name="newsletter_docker_workpool", 
            #interval=3600,
            image=DeploymentImage(
                name="newsletter-flow-ghcr",
                tag="test",
                dockerfile=cfd.parent / "Dockerfile",
            ),
            push=False
        )
    else:
        send_energy_report_flow()

if __name__ == "__main__":
    

    # Access command-line arguments, if '-deploy' argument is given,
    # prefect flow will be deployed, else locally executed
    if len(sys.argv) > 1 and sys.argv[1] == "-deploy":
        deploy = True
    else:
        deploy = False

    # execute or deploy (depends on deploy parameter) the prefect flow to send an
    #  email with an updated dashboard report to each registered user
    main(deploy=deploy)


#######
# A deployment created with the Python *flow.serve* method or the serve 
# function runs flows in a subprocess on the same machine where the deployment 
# is created. It does not use a work pool or worker.

# https://docs.prefect.io/latest/guides/prefect-deploy/
#  flow.deploy(
#         name="my-code-baked-into-an-image-deployment", 
#         work_pool_name="my-docker-pool", 
#         image="my_registry/my_image:my_image_tag"
#     )

# if no image:
# flow.from_source(
#         "https://github.com/my_github_account/my_repo/my_file.git",
#         entrypoint="flows/no-image.py:hello_world",
#     ).deploy(
#         name="no-image-deployment",
#         work_pool_name="my_pool",
#         build=False
#     )

# ECS Worker Guide
# https://prefecthq.github.io/prefect-aws/ecs_guide/

# https://docs.prefect.io/latest/tutorial/workers/