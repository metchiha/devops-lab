import logging

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from config import OTEL_ENDPOINT, SERVICE_NAME


def setup_telemetry() -> TracerProvider:
    """
    Configure the global tracer provider, OTLP export to the collector,
    and log-to-trace correlation. Must run before any spans are recorded.
    """
    # 1. Define the resource (who is sending this telemetry?)
    resource = Resource.create({"service.name": SERVICE_NAME})

    # 2. Set up the tracer provider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    # 3. Add the OTLP exporter — sends traces to the OTel Collector
    otlp_exporter = OTLPSpanExporter(endpoint=f"{OTEL_ENDPOINT}/v1/traces")
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # 4. Instrument logging — injects trace_id and span_id into every log line
    #    This is what enables log-to-trace correlation in Grafana
    LoggingInstrumentor().instrument(set_logging_format=True)

    # 5. Set up structured logging
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s [%(name)s] "
            "[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] "
            "%(message)s"
        ),
    )

    return tracer_provider


def instrument_app(app: FastAPI, tracer_provider: TracerProvider) -> None:
    """Auto-instrument FastAPI — creates a span for every request."""
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
