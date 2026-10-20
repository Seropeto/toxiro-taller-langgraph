import os

# Los tests no deben enviar trazas a LangSmith aunque el .env lo active.
os.environ["LANGSMITH_TRACING"] = "false"
