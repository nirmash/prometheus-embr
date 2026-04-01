#!/bin/bash
set -e

PROM_VERSION=3.3.0

# Download and extract Prometheus
echo "Downloading Prometheus v${PROM_VERSION}..."
curl -sL "https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz" \
  | tar xz -C /tmp

echo "Starting Prometheus with OTLP receiver enabled..."
exec /tmp/prometheus-${PROM_VERSION}.linux-amd64/prometheus \
  --config.file=/output/prometheus.yml \
  --web.listen-address=0.0.0.0:8080 \
  --web.enable-otlp-receiver \
  --web.enable-lifecycle \
  --storage.tsdb.path=/tmp/prometheus-data
