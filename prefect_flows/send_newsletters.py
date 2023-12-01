from prefect import flow, task, get_run_logger
from prefect.blocks.system import Secret, String
from prefect.task_runners import SequentialTaskRunner
from prefect_email import EmailServerCredentials, email_send_message

from typing import OrderedDict, List, Dict, NamedTuple
import logging
import pandas as pd
from enum import Enum
import pathlib
import sys

from data_extraction.data import DataHandler
from user_management.database_handling import get_all_users_from_database


class User(NamedTuple):
    name: str
    email: str
    country_code: str


@task(retries=3, retry_delay_seconds=60)
def get_registered_users_task() -> List[User]:
    """Read all registered users from database"""
    # todo: users = [User(**user) for user in get_all_users_from_database()]
     # return [User(name="test_user",email=user_email, country_code="DE")]
    # for test purpose:
    user_email = String.load("test-email").value
    return [User("test_user",user_email, "BE")]


@flow(validate_parameters=False)
def send_user_email_flow(user: User, data: str):
    assert isinstance(data, str)
    logger = get_run_logger()
    logger.info(data)
    email_server_credentials = EmailServerCredentials.load("my-email-credentials")
    
    line1 = f"Hello {user.name}, <br>"
    line2 = f"Please find our lastest update for the following region: {user.country_code}<br><br>"
    line3 = f"<h1>Forecast:</h1>"
    subject = email_send_message.with_options(name="send-an-email").submit(
        email_server_credentials=email_server_credentials,
        subject="Prefect Notification",
        msg=line1+line2+line3+data,
        email_to=user.email,
    )
    return subject


@task
def extract_forecast_data_task(country_code: str, entsoe_api_key) -> OrderedDict[str,pd.DataFrame]:
    data_handler = DataHandler(entsoe_api_key)
    data_handler.get_new_data(country_code, forecast=True)
    data_handler.data["chart1_data"] = data_handler.calculate_chart1_data()
    data_handler.data["chart2_data"] = data_handler.calculate_chart2_data()
    return data_handler.data


@flow(retries=3, retry_delay_seconds=60)
def send_userspecific_newsletter_flow(user: User | Dict):
    if isinstance(user, Dict):
        user = User(**user)
    logger = get_run_logger()

    entsoe_api_key = Secret.load("entsoe-api-key").get()
    data_dict = extract_forecast_data_task(user.country_code, entsoe_api_key)
    data = data_dict.get("df_generation_forecast", pd.Series())
    if data.empty:
        # trigger retries
        raise ValueError("No data retrieved from API")
    send_user_email_flow(user, data.to_frame().to_html())


##############
# flow entry point:
##############

@flow(task_runner=SequentialTaskRunner(), retries=5, retry_delay_seconds=5)
def send_newsletters_flow():
    logger = get_run_logger()
    logger.setLevel(logging.INFO)
    users = get_registered_users_task()
    for user in users:
        send_userspecific_newsletter_flow(user)


def main(deploy: bool = False) -> None:
    """ execute or deploy the prefect flow (depends on deploy parameter) 
    to send an newsletter with a report to each registered user
    """

    cfd = pathlib.Path(__file__).parent


    if deploy:
        print("send_newsletters_flow will be deployed ...")

        DeployModes = Enum(
            "DeployModes", ["SERVE", "LOCAL_DOCKER_DEPLOYMENT", "ECS_PUSH_WORK_POOL"]
        )
        # set current deploy_mode manually, 
        # for the sake of demonstration, 3 different modes are shown below
        deploy_mode = DeployModes.ECS_PUSH_WORK_POOL

        ### Deployment via long running serve method locally
        if deploy_mode == DeployModes.SERVE:
            send_newsletters_flow.serve(
                name="my-test-deployment", 
                # cron="0 * * * *",    # every hour
            )
        
        ### Deployment via Docker container running locally
        # helpful for testing docker deployment locally
        elif deploy_mode == DeployModes.LOCAL_DOCKER_DEPLOYMENT:
            from prefect.deployments.runner  import DeploymentImage

            send_newsletters_flow.deploy(
                "test_deploy_newsletter", 
                work_pool_name="newsletter_docker_workpool", 
                #interval=3600,
                image=DeploymentImage(
                    name="newsletter-flow_local",
                    tag="test",
                    dockerfile=cfd.parent / "Dockerfile",
                ),
                push=False
            )

        ### Deployment running a serverless flow on AWS ECS Fargate via push work pool
        elif deploy_mode == DeployModes.ECS_PUSH_WORK_POOL:
            # before deploying this with build=True and push=True you have to login to aws ecr
            # https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html
            # (replace region and account_id)
            # aws ecr get-login-password --region region | docker login --username AWS --password-stdin aws_account_id.dkr.ecr.region.amazonaws.com

            import os

            send_newsletters_flow.deploy(
                "deploy_newsletter_on_ecs_woTaskDef2", 
                # work_pool_name="miras-push-workpool", 
                work_pool_name="Miras-push-workpool-2",
                job_variables={
                    "execution_role_arn": os.getenv("EXECUTION_ROLE", ""),
                    "task_role_arn": os.getenv("TASK_ROLE", ""),
                    "cluster": os.getenv("ECS_CLUSTER"),
                    "vpc_id": os.getenv("VPC_ID", ""),
                    "container_name": "newsletter-flow",
                    "family": "newsletter-flow"
                },
                image=os.getenv("IMAGE_NAME"),
                build=False,
            )
    
    # run flow locally without deployment (default)
    else:
        send_newsletters_flow()


if __name__ == "__main__":
    # Access command-line arguments, if '-deploy' argument is given,
    # prefect flow will be deployed, else locally executed
    if len(sys.argv) > 1 and sys.argv[1] == "-deploy":
        deploy = True
    else:
        deploy = False

    main(deploy=deploy)