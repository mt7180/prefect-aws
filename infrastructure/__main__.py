import pulumi
import pulumi_aws as aws
import json
import os


cluster_name = "newsletter_ecs_cluster"
project_name = "newsletter-flow"
image = os.getenv("IMAGE","")
aws_accout_id = aws.get_caller_identity().account_id
aws_region = aws.get_region()


# Create an ECS Cluster
ecs_cluster = aws.ecs.Cluster("ecs_cluster")

log_group = aws.cloudwatch.LogGroup(
    project_name,
    retention_in_days=7,
)

vpc = aws.ec2.Vpc(
    "newsletter_vpc", 
    cidr_block="10.0.0.0/16",
    enable_dns_support=True,
    enable_dns_hostnames=True,
)

igw = aws.ec2.InternetGateway(
    "newsletter_internet_gateway", 
    vpc_id=vpc.id
)

# Attach the Internet Gateway to the VPC
vpc_gateway_attachment = aws.ec2.VpcGatewayAttachment(
    "newsletter-igw-attachment",
    vpc_id=vpc.id,
    internet_gateway_id=igw.id
)

route_table = aws.ec2.RouteTable(
    "newsletter_route_table", 
    vpc_id=vpc.id
)

route = aws.ec2.Route(
    "newsletter_route", 
    route_table_id=route_table.id, 
    destination_cidr_block="0.0.0.0/0", 
    gateway_id=igw.id,
)

ecs_service_subnet = aws.ec2.Subnet(
    "newsletter_subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.0.0/16",
    map_public_ip_on_launch=True,
    availability_zone="eu-central-1a",
)


# Associate the Route Table with the Subnet
route_table_association = aws.ec2.RouteTableAssociation(
    "newsletter_route_table_association", 
    subnet_id=ecs_service_subnet.id, 
    route_table_id=route_table.id,
)


execution_role = aws.iam.Role(
    "newsletter_execution_role",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                }
            ],
        }
    ),
)

execution_role_policy = aws.iam.Policy(
    "newsletter_execution_role_policy",
    policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": [
                        "logs:CreateLogStream",
                        "logs:CreateLogGroup",
                        "logs:PutLogEvents",
                    ],
                    "Effect": "Allow",
                    "Resource": "arn:aws:logs:*:*:*",
                },
                {
                    "Effect": "Allow",
                    "Action": "ssm:GetParameters",
                    "Resource": "*",
                },
            ],
        }
    ),
)


execution_role_policy_attachment = aws.iam.RolePolicyAttachment(
    "news_execution_role_policy_attachment",
    policy_arn=execution_role_policy.arn,
    role=execution_role.name,
    #policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
)

task_role = aws.iam.Role(
    "newsletter_task_role",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                }
            ],
        }
    ),
)

task_role_policy = aws.iam.Policy(
    "newsletter_task_role_policy",
    policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": [
                        "logs:CreateLogStream",
                        "ecs:RegisterTaskDefinition",
                        "ecs:DeregisterTaskDefinition",
                        "ecs:DescribeTasks",
                        "ecs:RunTask",
                        "logs:GetLogEvents",
                        "ec2:DescribeSubnets",
                        "ec2:DescribeVpcs",
                    ],
                    "Effect": "Allow",
                    "Resource": "*",
                },
            ],
        }
    ),
)

task_role_policy_attachment = aws.iam.RolePolicyAttachment(
    "news_task_role_policy_attachment",
    policy_arn=execution_role_policy.arn,
    role=execution_role.name,
)


#### ECS Task Definition ######
ecs_task_definition = aws.ecs.TaskDefinition(
    "newsletter_ecs_task_definition",
    family=project_name,
    cpu="256",
    memory="512",
    network_mode="awsvpc",
    execution_role_arn=execution_role.arn,
    task_role_arn=task_role.arn,
    requires_compatibilities=["FARGATE"],
    container_definitions=f"""
    [
        {{
            "name": {project_name},
            "image": {image},
            "logConfiguration": {{
                "logDriver": "awslogs",
                "options": {{
                    "awslogs-group" : "{log_group.name}",
                    "awslogs-region" : "{aws_region}",
                    "awslogs-stream-prefix" : {project_name}
                }}
            }},
            "secrets": [
                {{ 
                    "name": "PREFECT_API_URL",
                    "valueFrom": "arn:aws:ssm:{aws_region}:{aws_accout_id}:parameter/PREFECT_API_URL"
                }},{{
                    "name": "PREFECT_API_KEY",
                    "valueFrom": "arn:aws:ssm:{aws_region}:{aws_accout_id}:parameter/PREFECT_API_KEY"
                }}
            ]
            "essential": True,
        
        }}
    ]
    """,
)

pulumi.export("vpc_id", vpc.id)
pulumi.export("ecs_cluster_arn", ecs_cluster.arn)
pulumi.export("task_role_arn", task_role.arn)
pulumi.export("execution_role_arn", execution_role.arn)
pulumi.export("task_definition_arn", ecs_task_definition.arn)
