# todo: this is probably an rws-common thing if more apps need sample rate aware instrumentation
import os

from flask import has_request_context, request
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.jinja2 import Jinja2Instrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, Sampler, SamplingResult, TraceIdRatioBased

def sample_rate(endpoint):
    if endpoint == 'heartbeat':
        return 100
    if endpoint == 'api.me':
        return 10
    if endpoint and endpoint.startswith('billing.'):
        return 1
    return 2


class EndpointSampler(Sampler):
    """Keeps 1 in sample_rate(endpoint) traces."""

    def __init__(self):
        self._by_rate = {}

    def should_sample(self, parent_context, trace_id, name, kind=None, attributes=None, links=None, trace_state=None):
        rate = sample_rate(request.endpoint if has_request_context() else None)
        sampler = self._by_rate.setdefault(rate, TraceIdRatioBased(1 / rate))
        result = sampler.should_sample(parent_context, trace_id, name, kind, attributes, links, trace_state)
        if not result.decision.is_sampled():
            return result
        return SamplingResult(result.decision, {**(attributes or {}), 'SampleRate': rate}, result.trace_state)

    def get_description(self):
        return 'EndpointSampler'


class InheritSampleRate(SpanProcessor):
    """Copies SampleRate onto child spans (SQL, templates)"""

    def on_start(self, span, parent_context=None):
        parent_attributes = getattr(trace.get_current_span(parent_context), 'attributes', None) or {}
        if 'SampleRate' in parent_attributes:
            span.set_attribute('SampleRate', parent_attributes['SampleRate'])


def init_app(app):
    if 'OTEL_TRACES_SAMPLER' in os.environ:
        sampler = None
    else:
        endpoint_sampler = EndpointSampler()
        sampler = ParentBased(root=endpoint_sampler, remote_parent_sampled=endpoint_sampler,
                              remote_parent_not_sampled=endpoint_sampler)
    provider = TracerProvider(
        resource=Resource.create({} if 'OTEL_SERVICE_NAME' in os.environ else {'service.name': 'auth'}),
        sampler=sampler,
    )
    provider.add_span_processor(InheritSampleRate())

    if os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT') or os.environ.get('OTEL_EXPORTER_OTLP_TRACES_ENDPOINT'):
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    FlaskInstrumentor().instrument_app(app)
    SQLAlchemyInstrumentor().instrument()
    Jinja2Instrumentor().instrument()
