from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Google Cloud
    google_api_key: str = ""
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    google_genai_use_vertexai: bool = False  # False = AI Studio (dev), True = Vertex AI (prod)

    # Firestore
    firestore_database: str = "(default)"
    firestore_collection_knowledge: str = "ux_knowledge"
    firestore_collection_sessions: str = "agent_sessions"
    firestore_collection_trajectories: str = "trajectories"

    # GCS
    gcs_bucket_screenshots: str = "design-ops-screenshots"

    # Figma
    figma_access_token: str = ""

    # CopilotKit
    copilotkit_api_key: str = ""

    # Team docs path (for filesystem MCP — Tier 2 knowledge)
    team_docs_path: str = "./knowledge/team_docs"

    # GCP credentials (local dev only; Cloud Run uses attached service account)
    google_application_credentials: str = ""

    # CORS — comma-separated origins. Defaults to localhost for safety.
    # Production: set ALLOWED_ORIGINS to your Vercel domain, e.g. "https://design-ops.vercel.app"
    allowed_origins: str = "http://localhost:3000"

    # Jina AI Reader — URL → clean markdown ingestion
    # Get your free key at: https://jina.ai/reader/
    jina_api_key: str = ""

    # Optional integrations
    github_token: str = ""
    magic_api_key: str = ""
    agentops_api_key: str = ""

    # Auth — set AUTH_REQUIRED=false in .env to skip Firebase token verification in local dev
    auth_required: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
