"""Vendor architecture icons into a folder: official AWS Architecture Icons (+ Kubernetes and a few tech logos),
resized to 64 px and colour-quantised so a full diagram stays ~80 KB.

    python scripts/fetch_icons.py                         # (re)build assets/icons from the catalog below
    python scripts/fetch_icons.py --out diagrams/icons    # into a project
    python scripts/fetch_icons.py --add myq=aws/ml/q.png  # add an extra key from the icon pack

Source: the `diagrams` Python package (MIT) redistributes the AWS Architecture Icons; the wheel is downloaded with
`pip download --no-deps` (nothing is installed). Needs Pillow. Writes CATALOG.md and SOURCE.md next to the icons.
"""
from __future__ import annotations

import argparse
import io
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "assets" / "icons"

# key -> (path inside resources/, human label, category)
CATALOG: dict[str, tuple[str, str, str]] = {
    # people & clients
    "user": ("aws/general/user.png", "User", "People"), "users": ("aws/general/users.png", "Users / team", "People"),
    "client": ("aws/general/client.png", "Client / laptop", "People"), "mobile-client": ("aws/general/mobile-client.png", "Mobile client", "People"),
    "internet": ("aws/general/internet-alt1.png", "Internet", "People"), "office": ("aws/general/office-building.png", "Corporate data centre", "People"),
    "server": ("aws/general/traditional-server.png", "On-prem server", "People"), "generic-db": ("aws/general/generic-database.png", "Generic database", "People"),
    # compute & containers
    "ec2": ("aws/compute/ec2-instance.png", "EC2 instance", "Compute"), "ec2-asg": ("aws/compute/ec2-auto-scaling.png", "EC2 Auto Scaling", "Compute"),
    "lambda": ("aws/compute/lambda.png", "AWS Lambda", "Compute"), "lambda-fn": ("aws/compute/lambda-function.png", "Lambda function", "Compute"),
    "ecs": ("aws/compute/elastic-container-service.png", "Amazon ECS", "Containers"), "fargate": ("aws/compute/fargate.png", "AWS Fargate", "Containers"),
    "eks": ("aws/compute/elastic-kubernetes-service.png", "Amazon EKS", "Containers"), "ecr": ("aws/compute/ec2-container-registry.png", "Amazon ECR", "Containers"),
    "app-runner": ("aws/compute/app-runner.png", "AWS App Runner", "Containers"), "batch": ("aws/compute/batch.png", "AWS Batch", "Compute"),
    "beanstalk": ("aws/compute/elastic-beanstalk.png", "Elastic Beanstalk", "Compute"),
    # storage
    "s3": ("aws/storage/simple-storage-service-s3.png", "Amazon S3", "Storage"), "s3-bucket": ("aws/storage/simple-storage-service-s3-bucket-with-objects.png", "S3 bucket", "Storage"),
    "glacier": ("aws/storage/s3-glacier.png", "S3 Glacier", "Storage"), "efs": ("aws/storage/elastic-file-system-efs.png", "Amazon EFS", "Storage"),
    "ebs": ("aws/storage/elastic-block-store-ebs.png", "Amazon EBS", "Storage"), "backup": ("aws/storage/backup.png", "AWS Backup", "Storage"),
    # databases
    "dynamodb": ("aws/database/dynamodb.png", "Amazon DynamoDB", "Database"), "dynamodb-table": ("aws/database/dynamodb-table.png", "DynamoDB table", "Database"),
    "rds": ("aws/database/rds.png", "Amazon RDS", "Database"), "aurora": ("aws/database/aurora.png", "Amazon Aurora", "Database"),
    "elasticache": ("aws/database/elasticache.png", "ElastiCache", "Database"), "documentdb": ("aws/database/documentdb-mongodb-compatibility.png", "DocumentDB", "Database"),
    "neptune": ("aws/database/neptune.png", "Amazon Neptune", "Database"), "timestream": ("aws/database/timestream.png", "Timestream", "Database"),
    # analytics
    "athena": ("aws/analytics/athena.png", "Amazon Athena", "Analytics"), "glue": ("aws/analytics/glue.png", "AWS Glue", "Analytics"),
    "glue-catalog": ("aws/analytics/glue-data-catalog.png", "Glue Data Catalog", "Analytics"), "glue-crawler": ("aws/analytics/glue-crawlers.png", "Glue crawler", "Analytics"),
    "lake-formation": ("aws/analytics/lake-formation.png", "Lake Formation", "Analytics"), "emr": ("aws/analytics/emr.png", "Amazon EMR", "Analytics"),
    "kinesis": ("aws/analytics/kinesis-data-streams.png", "Kinesis Data Streams", "Analytics"), "firehose": ("aws/analytics/kinesis-data-firehose.png", "Data Firehose", "Analytics"),
    "redshift": ("aws/analytics/redshift.png", "Amazon Redshift", "Analytics"), "opensearch": ("aws/analytics/amazon-opensearch-service.png", "OpenSearch Service", "Analytics"),
    "quicksight": ("aws/analytics/quicksight.png", "Amazon QuickSight", "Analytics"), "msk": ("aws/analytics/managed-streaming-for-kafka.png", "Amazon MSK", "Analytics"),
    # AI / ML
    "bedrock": ("aws/ml/bedrock.png", "Amazon Bedrock", "AI/ML"), "sagemaker": ("aws/ml/sagemaker.png", "Amazon SageMaker", "AI/ML"),
    "sagemaker-notebook": ("aws/ml/sagemaker-notebook.png", "SageMaker notebook", "AI/ML"), "sagemaker-model": ("aws/ml/sagemaker-model.png", "SageMaker model", "AI/ML"),
    "sagemaker-training": ("aws/ml/sagemaker-training-job.png", "SageMaker training job", "AI/ML"), "q": ("aws/ml/q.png", "Amazon Q", "AI/ML"),
    "kendra": ("aws/ml/kendra.png", "Amazon Kendra", "AI/ML"), "comprehend": ("aws/ml/comprehend.png", "Amazon Comprehend", "AI/ML"),
    "textract": ("aws/ml/textract.png", "Amazon Textract", "AI/ML"), "rekognition": ("aws/ml/rekognition.png", "Amazon Rekognition", "AI/ML"),
    "transcribe": ("aws/ml/transcribe.png", "Amazon Transcribe", "AI/ML"), "polly": ("aws/ml/polly.png", "Amazon Polly", "AI/ML"),
    "lex": ("aws/ml/lex.png", "Amazon Lex", "AI/ML"), "personalize": ("aws/ml/personalize.png", "Amazon Personalize", "AI/ML"),
    # integration
    "sqs": ("aws/integration/simple-queue-service-sqs.png", "Amazon SQS", "Integration"), "sns": ("aws/integration/simple-notification-service-sns.png", "Amazon SNS", "Integration"),
    "step-functions": ("aws/integration/step-functions.png", "Step Functions", "Integration"), "eventbridge": ("aws/integration/eventbridge.png", "Amazon EventBridge", "Integration"),
    "scheduler": ("aws/integration/eventbridge-scheduler.png", "EventBridge Scheduler", "Integration"), "appsync": ("aws/integration/appsync.png", "AWS AppSync", "Integration"),
    "mq": ("aws/integration/mq.png", "Amazon MQ", "Integration"),
    # networking & edge
    "vpc": ("aws/network/vpc.png", "Amazon VPC", "Networking"), "api-gateway": ("aws/network/api-gateway.png", "API Gateway", "Networking"),
    "cloudfront": ("aws/network/cloudfront.png", "Amazon CloudFront", "Networking"), "route53": ("aws/network/route-53.png", "Route 53", "Networking"),
    "alb": ("aws/network/elb-application-load-balancer.png", "Application Load Balancer", "Networking"),
    "nlb": ("aws/network/elb-network-load-balancer.png", "Network Load Balancer", "Networking"), "nat": ("aws/network/nat-gateway.png", "NAT gateway", "Networking"),
    "igw": ("aws/network/internet-gateway.png", "Internet gateway", "Networking"), "privatelink": ("aws/network/privatelink.png", "PrivateLink", "Networking"),
    "vpc-endpoint": ("aws/network/endpoint.png", "VPC endpoint", "Networking"), "tgw": ("aws/network/transit-gateway.png", "Transit Gateway", "Networking"),
    # security
    "iam": ("aws/security/identity-and-access-management-iam.png", "AWS IAM", "Security"), "iam-role": ("aws/security/identity-and-access-management-iam-role.png", "IAM role", "Security"),
    "sts": ("aws/security/identity-and-access-management-iam-aws-sts.png", "AWS STS", "Security"), "secrets": ("aws/security/secrets-manager.png", "Secrets Manager", "Security"),
    "kms": ("aws/security/key-management-service.png", "AWS KMS", "Security"), "cognito": ("aws/security/cognito.png", "Amazon Cognito", "Security"),
    "waf": ("aws/security/waf.png", "AWS WAF", "Security"), "shield": ("aws/security/shield.png", "AWS Shield", "Security"),
    "acm": ("aws/security/certificate-manager.png", "Certificate Manager", "Security"), "guardduty": ("aws/security/guardduty.png", "GuardDuty", "Security"),
    "macie": ("aws/security/macie.png", "Amazon Macie", "Security"), "security-hub": ("aws/security/security-hub.png", "Security Hub", "Security"),
    "inspector": ("aws/security/inspector.png", "Amazon Inspector", "Security"),
    # management & DevOps
    "cloudwatch": ("aws/management/cloudwatch.png", "Amazon CloudWatch", "Management"), "cloudwatch-logs": ("aws/management/cloudwatch-logs.png", "CloudWatch Logs", "Management"),
    "cloudwatch-alarm": ("aws/management/cloudwatch-alarm.png", "CloudWatch alarm", "Management"), "cloudtrail": ("aws/management/cloudtrail.png", "AWS CloudTrail", "Management"),
    "cloudformation": ("aws/management/cloudformation.png", "CloudFormation", "Management"), "ssm": ("aws/management/systems-manager.png", "Systems Manager", "Management"),
    "parameter-store": ("aws/management/systems-manager-parameter-store.png", "Parameter Store", "Management"), "config": ("aws/management/config.png", "AWS Config", "Management"),
    "organizations": ("aws/management/organizations.png", "AWS Organizations", "Management"), "grafana": ("aws/management/amazon-managed-grafana.png", "Managed Grafana", "Management"),
    "prometheus": ("aws/management/amazon-managed-prometheus.png", "Managed Prometheus", "Management"),
    "codebuild": ("aws/devtools/codebuild.png", "AWS CodeBuild", "DevOps"), "codepipeline": ("aws/devtools/codepipeline.png", "AWS CodePipeline", "DevOps"),
    "codecommit": ("aws/devtools/codecommit.png", "AWS CodeCommit", "DevOps"), "codedeploy": ("aws/devtools/codedeploy.png", "AWS CodeDeploy", "DevOps"),
    "cdk": ("aws/devtools/cloud-development-kit.png", "AWS CDK", "DevOps"), "x-ray": ("aws/devtools/x-ray.png", "AWS X-Ray", "DevOps"),
    "amplify": ("aws/mobile/amplify.png", "AWS Amplify", "Front-end"), "workspaces": ("aws/enduser/workspaces.png", "WorkSpaces", "Front-end"),
    # Kubernetes objects
    "pod": ("k8s/compute/pod.png", "Kubernetes pod", "Kubernetes"), "deploy": ("k8s/compute/deploy.png", "K8s Deployment", "Kubernetes"),
    "job": ("k8s/compute/job.png", "K8s Job", "Kubernetes"), "svc": ("k8s/network/svc.png", "K8s Service", "Kubernetes"),
    "ingress": ("k8s/network/ing.png", "K8s Ingress", "Kubernetes"), "k8s-secret": ("k8s/podconfig/secret.png", "K8s Secret", "Kubernetes"),
    "cm": ("k8s/podconfig/cm.png", "K8s ConfigMap", "Kubernetes"),
    # technology logos (identify the tech only)
    "python": ("programming/language/python.png", "Python", "Tech"), "fastapi": ("programming/framework/fastapi.png", "FastAPI", "Tech"),
    "react": ("programming/framework/react.png", "React", "Tech"), "duckdb": ("onprem/database/duckdb.png", "DuckDB", "Tech"),
    "parquet": ("gis/format/geoparquet.png", "Parquet files", "Tech"), "postgres": ("onprem/database/postgresql.png", "PostgreSQL", "Tech"),
    "redis": ("onprem/inmemory/redis.png", "Redis", "Tech"), "kafka": ("onprem/queue/kafka.png", "Kafka", "Tech"),
    "github": ("onprem/vcs/github.png", "GitHub", "Tech"), "github-actions": ("onprem/ci/github-actions.png", "GitHub Actions", "Tech"),
}

SOURCE_MD = """# Icon sources

* AWS service icons: official **AWS Architecture Icons**, as redistributed in the `diagrams` Python package (MIT).
  AWS permits their use in architecture diagrams: https://aws.amazon.com/architecture/icons/
* Kubernetes icons: Kubernetes community icon set (Apache-2.0), via `diagrams`.
* Technology logos (Python, FastAPI, React, DuckDB, PostgreSQL, Redis, Kafka, GitHub): their projects' marks, used only
  to identify the technology.

Regenerate or extend with `scripts/fetch_icons.py` - don't edit the PNGs by hand.
"""


def fetch_resources(tmp: Path) -> Path:
    subprocess.run([sys.executable, "-m", "pip", "download", "--no-deps", "-q", "-d", str(tmp), "diagrams"], check=True)
    wheel = next(tmp.glob("diagrams-*.whl"))
    with zipfile.ZipFile(wheel) as z:
        z.extractall(tmp / "x")
    return tmp / "x" / "resources"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--resources", help="an already-extracted diagrams/resources folder (skips the download)")
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--add", nargs="*", default=[], help="extra key=path-inside-resources pairs")
    a = ap.parse_args()
    from PIL import Image
    cat = dict(CATALOG)
    for kv in a.add:
        k, p = kv.split("=", 1)
        cat[k] = (p, k, "Extra")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        res = Path(a.resources) if a.resources else fetch_resources(Path(t))
        missing = []
        for k, (rel, _, _) in cat.items():
            src = res / rel
            if not src.exists():
                missing.append(f"{k} ({rel})")
                continue
            im = Image.open(src).convert("RGBA")
            im.thumbnail((a.size, a.size), Image.LANCZOS)
            im.quantize(colors=64, method=Image.Quantize.FASTOCTREE).save(out / f"{k}.png", optimize=True)
    rows = ["| Key | Service | Category |", "|---|---|---|"] + [f"| `{k}` | {lbl} | {c} |" for k, (_, lbl, c) in
                                                                  sorted(cat.items(), key=lambda kv: (kv[1][2], kv[0]))
                                                                  if (out / f"{k}.png").exists()]
    (out / "CATALOG.md").write_text("# Icon catalog\n\nUse the key as `Node(icon=...)`. `None` draws a text box.\n\n" + "\n".join(rows) + "\n")
    (out / "SOURCE.md").write_text(SOURCE_MD)
    n = len(list(out.glob("*.png")))
    print(f"{n} icons in {out} ({sum(p.stat().st_size for p in out.glob('*.png')) // 1024} KB)" +
          (f"; missing: {', '.join(missing)}" if missing else ""))


if __name__ == "__main__":
    main()
