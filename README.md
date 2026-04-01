# Prometheus on Embr

A Prometheus server with native OTLP receiver enabled. Accepts OpenTelemetry metrics via HTTP and provides the standard Prometheus query UI.

## OTLP Endpoint

Send OTLP metrics to:

```
POST https://<your-embr-url>/api/v1/otlp/v1/metrics
Content-Type: application/x-protobuf
```

## Deploy to Embr

```bash
embr quickstart deploy <owner>/prometheus-embr
```
