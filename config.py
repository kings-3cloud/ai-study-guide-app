from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Azure AI Foundry project connection string
    PROJECT_CONNECTION_STRING: str

    # Azure OpenAI model deployment names
    AZURE_OPENAI_DEPLOYMENT_GPT4O: str = "gpt-4o"
    AZURE_OPENAI_DEPLOYMENT_GPT4O_MINI: str = "gpt-4o-mini"

    # Local data storage
    PROGRESS_DATA_DIR: str = "data/progress"

    # Default user identifier
    DEFAULT_USER_ID: str = "default_user"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
