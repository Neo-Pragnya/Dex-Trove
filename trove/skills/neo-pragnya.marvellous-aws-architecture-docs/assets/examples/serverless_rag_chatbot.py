"""Example spec: a serverless RAG chatbot on AWS, built up in four releases.

    python scripts/build_arch.py assets/examples/serverless_rag_chatbot.py --out /tmp/rag-docs --title "Serverless RAG chatbot"

Grid: x = column, y = row (fractions allowed). Stage = the release that introduces a node or flow.
"""
from archlib import Flow, Group, Node, Spec, Stage

STAGES = [
    Stage(0, "Static web app", "Release 1", "React app on S3 behind CloudFront and WAF"),
    Stage(1, "Sign-in and API", "Release 2", "Cognito sign-in, API Gateway, a chat Lambda calling Bedrock"),
    Stage(2, "Answers from your documents", "Release 3", "Document ingestion, embeddings and OpenSearch retrieval"),
    Stage(3, "Run it like a product", "Release 4", "Chat history, tracing, metrics and alarms"),
]

RAG = Spec(
    id="rag-chatbot",
    title="Serverless RAG chatbot — answers grounded in your own documents",
    subtitle="A React front end, a Cognito-protected API, a Lambda that retrieves from OpenSearch and asks Bedrock, and observability from day one.",
    cols=8.6, rows=4.6, stages=STAGES,
    groups=[
        Group("cloud", "AWS Cloud · us-east-1", 0.78, -0.35, 7.9, 3.85, "cloud", 0),
        Group("edge", "Edge & front end", 1, 0.2, 2.2, 0.2, "logic", 0),
        Group("api", "Chat API", 3.2, 1.2, 4.6, 1.2, "logic", 1),
        Group("kb", "Knowledge ingestion pipeline", 2.2, 2.9, 5.2, 2.9, "logic", 2),
        Group("ops", "Operate", 6.4, 2.9, 7.6, 2.9, "logic", 3),
    ],
    nodes=[
        Node("user", "user", "Employee", "browser", 0, 1.2),
        Node("admin", "users", "Content owner", "uploads documents", 0, 2.9),
        Node("cf", "cloudfront", "Amazon CloudFront", "HTTPS · caching", 1, 0.2),
        Node("waf", "waf", "AWS WAF", "rate limits · rules", 1, 1.2),
        Node("site", "s3", "Amazon S3", "React static files", 2.2, 0.2),
        Node("cog", "cognito", "Amazon Cognito", "user pool · JWT", 2.2, 1.2, 1),
        Node("apigw", "api-gateway", "API Gateway", "JWT authorizer", 3.2, 1.2, 1),
        Node("chat", "lambda", "Chat Lambda", "retrieve → prompt → answer", 4.6, 1.2, 1),
        Node("llm", "bedrock", "Amazon Bedrock", "Nova Pro · guardrails", 6.0, 0.2, 1),
        Node("docs", "s3-bucket", "Documents bucket", "PDF · HTML · DOCX", 2.2, 2.9, 2),
        Node("ingest", "lambda-fn", "Ingestion Lambda", "chunk + embed", 3.7, 2.9, 2),
        Node("emb", "bedrock", "Titan Embeddings", "1,024-d vectors", 3.7, 1.95, 2),
        Node("os", "opensearch", "OpenSearch Serverless", "vector index", 5.2, 2.9, 2),
        Node("ddb", "dynamodb", "DynamoDB", "chat history · TTL", 6.0, 1.2, 3),
        Node("cw", "cloudwatch", "CloudWatch", "metrics · alarms", 6.4, 2.9, 3),
        Node("xray", "x-ray", "AWS X-Ray", "end-to-end traces", 7.6, 2.9, 3),
    ],
    flows=[
        Flow(1, "user", "waf", "The employee opens the chat app; AWS WAF filters abusive traffic first.", "HTTPS", 0, "r", "l"),
        Flow(2, "waf", "cf", "CloudFront serves the app over HTTPS from the edge.", "", 0, "t", "b"),
        Flow(3, "cf", "site", "Static React files come from a private S3 bucket (origin access control).", "", 0),
        Flow(4, "user", "cog", "The user signs in with Cognito and receives a short-lived JWT.", "sign-in", 1, "b", "b", via=1.85),
        Flow(5, "cog", "apigw", "Each chat request carries the JWT; API Gateway's authorizer validates it.", "", 1),
        Flow(6, "apigw", "chat", "Valid requests reach the chat Lambda.", "", 1),
        Flow(7, "chat", "llm", "The Lambda asks Bedrock for an answer, with Bedrock Guardrails applied.", "Converse", 1, "t", "l", bidir=True),
        Flow(8, "admin", "docs", "Content owners upload documents to the documents bucket.", "", 2),
        Flow(9, "docs", "ingest", "An S3 event triggers ingestion: documents are split into chunks.", "S3 event", 2),
        Flow(10, "ingest", "emb", "Each chunk is embedded with Titan Embeddings.", "", 2, "t", "b"),
        Flow(11, "ingest", "os", "Vectors and metadata are indexed in OpenSearch Serverless.", "", 2),
        Flow(12, "chat", "os", "At question time the Lambda retrieves the most relevant chunks, with their sources.", "k-NN", 2, "b", "t", via=2.12),
        Flow(13, "chat", "ddb", "The conversation is stored per user, expiring after 30 days.", "", 3),
        Flow(14, "chat", "cw", "Latency, tokens and errors go to CloudWatch; alarms page the on-call.", "", 3, "b", "t", via=2.3, so=18),
        Flow(15, "cw", "xray", "X-Ray traces each request across API Gateway, Lambda and Bedrock.", "", 3),
    ],
)

SPECS = [RAG]
