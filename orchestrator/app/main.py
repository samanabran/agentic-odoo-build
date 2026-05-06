import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_client import Counter, Histogram, make_asgi_app

from app.api.admin import router as admin_router
from app.api.health import router as health_router

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Prometheus metrics (G3) — declared at module level, incremented from M4+
# ---------------------------------------------------------------------------
llm_requests_total = Counter(
    "llm_requests_total",
    "LLM requests by provider and outcome",
    ["provider", "model", "outcome"],
)
llm_tokens_total = Counter(
    "llm_tokens_total",
    "LLM tokens consumed",
    ["provider", "model", "direction"],
)
llm_cost_usd_total = Counter(
    "llm_cost_usd_total",
    "Estimated LLM cost in USD",
    ["provider", "model", "user"],
)
tool_calls_total = Counter(
    "tool_calls_total",
    "Tool calls by outcome and approval status",
    ["tool", "outcome", "approved"],
)
tool_latency_seconds = Histogram(
    "tool_latency_seconds",
    "Tool execution latency in seconds",
    ["tool"],
)
rag_queries_total = Counter("rag_queries_total", "RAG queries executed")
rag_latency_seconds = Histogram("rag_latency_seconds", "RAG query latency in seconds")

# ---------------------------------------------------------------------------
# Routing (D3) and production guard (D4)
# ---------------------------------------------------------------------------
_GITHUB_MODEL_PREFIXES = ("github/", "github-")


def get_active_model() -> str:
    """
    Return the LiteLLM virtual model name for the current environment (D3).

    Routing rules (evaluated in order):
      PRIVATE_MODE=true         -> prod-local
      ENVIRONMENT=production    -> prod-default
      ENVIRONMENT=development   -> github-dev
      anything else             -> RuntimeError
    """
    private_mode = os.getenv("PRIVATE_MODE", "false").lower() == "true"
    environment = os.getenv("ENVIRONMENT", "").lower()

    if private_mode:
        return "prod-local"
    if environment == "production":
        return "prod-default"
    if environment == "development":
        return "github-dev"
    raise RuntimeError(
        f"ENVIRONMENT='{os.getenv('ENVIRONMENT', '')}' is not a recognised value. "
        "Valid values: 'production', 'development'. "
        "Set ENVIRONMENT in your .env file. PRIVATE_MODE=true overrides this check."
    )


def _assert_no_github_models_in_production() -> None:
    """
    Startup guard (D4, D7): hard-fail if production is configured to route
    to a GitHub Models endpoint. This is a RuntimeError, not a warning.
    """
    environment = os.getenv("ENVIRONMENT", "").lower()
    if environment != "production":
        return

    default_model = os.getenv("DEFAULT_MODEL", "")
    for prefix in _GITHUB_MODEL_PREFIXES:
        if default_model.lower().startswith(prefix):
            raise RuntimeError(
                f"ENVIRONMENT=production but DEFAULT_MODEL='{default_model}' references a "
                "GitHub Models endpoint. GitHub Models must not serve production traffic — "
                "this violates the Copilot Product Specific Terms and risks account suspension. "
                "Set DEFAULT_MODEL to a licensed provider: openai/*, anthropic/*, or ollama/*."
            )

    if os.getenv("GITHUB_TOKEN"):
        logger.warning(
            "github_token_set_in_production",
            msg="GITHUB_TOKEN is present in production. "
                "It will not be used for LLM routing but should be removed from this environment.",
        )


def _setup_telemetry(app: FastAPI) -> None:
    """Wire OpenTelemetry tracing via OTLP HTTP (G2). No-op if endpoint is unset."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.info("otel_disabled", reason="OTEL_EXPORTER_OTLP_ENDPOINT not set")
        return
    try:
        from opentelemetry import trace  # type: ignore[import-untyped]
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-untyped]
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import (
            FastAPIInstrumentor,  # type: ignore[import-untyped]
        )
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-untyped]
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,  # type: ignore[import-untyped]
        )

        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("otel_enabled", endpoint=endpoint)
    except Exception as exc:
        logger.warning("otel_setup_failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    _assert_no_github_models_in_production()
    _setup_telemetry(app)
    active_model = get_active_model()
    logger.info(
        "orchestrator_started",
        version=app.version,
        environment=os.getenv("ENVIRONMENT", ""),
        active_model=active_model,
        private_mode=os.getenv("PRIVATE_MODE", "false"),
    )
    yield
    logger.info("orchestrator_stopped")


app = FastAPI(
    title="Odoo AI Brain Orchestrator",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(admin_router)
app.mount("/metrics", make_asgi_app())
