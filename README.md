# OpenTelemetry Python Demo

A complete microservices demo with distributed tracing using OpenTelemetry, featuring:
- **Payments Service** - Processes payments, calls Inventory
- **Inventory Service** - Manages product stock
- **Load Generator** - Generates continuous traffic
- **OpenTelemetry Collector** - Receives, processes, exports telemetry
- **Zipkin** - Distributed tracing UI

## Architecture

```
┌─────────────┐     HTTP      ┌─────────────┐     HTTP      ┌─────────────┐
│ Load        │ ─────────────▶ │ Payments    │ ─────────────▶ │ Inventory   │
│ Generator   │  :5003         │ Service     │  :5002         │ Service     │
│ (Port 5003) │                │ (Port 5002) │                │ (Port 5001) │
└─────────────┘                └──────┬──────┘                └─────────────┘
                                      │
                                      │ OTLP gRPC (4317)
                                      ▼
                              ┌─────────────────┐
                              │ OTel Collector  │
                              │ (Ports 4317,    │
                              │  4318, 8888)    │
                              └────────┬────────┘
                                       │ Zipkin Exporter
                                       ▼
                              ┌─────────────────┐
                              │ Zipkin UI       │
                              │ (Port 9411)     │
                              └─────────────────┘
```

![Architecture Diagram](diagrams/architecture.drawio)

## Quick Start

### Option 1: GitHub Codespaces (Recommended)

```bash
# From the repository root inside the Codespace
cd /workspaces/demo-otel-python

docker compose up --build -d

docker compose ps

docker compose logs -f
```

Then open the forwarded ports in the Codespaces panel or browse to:

- Zipkin UI: http://localhost:9411
- Inventory: http://localhost:5001
- Payments: http://localhost:5002
- Load Generator: http://localhost:5003
- OTel Collector metrics: http://localhost:8888

### Option 2: Local Docker Compose

```bash
# Clone the repo
git clone https://github.com/jdaniel1609/demo-otel-python.git
cd demo-otel-python

# Start all services
docker compose up --build -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

## Service URLs

| Service | Local URL | Codespaces URL | Description |
|---------|-----------|----------------|-------------|
| **Zipkin UI** | http://localhost:9411 | Auto-opens in browser | **Main tracing dashboard** |
| Inventory | http://localhost:5001 | Forwarded port 5001 | Product inventory API |
| Payments | http://localhost:5002 | Forwarded port 5002 | Payment processing API |
| Load Generator | http://localhost:5003 | Forwarded port 5003 | Traffic generator API |
| OTel Collector Metrics | http://localhost:8888 | Forwarded port 8888 | Prometheus metrics |
| OTel Collector zPages | http://localhost:55679 | Forwarded port 55679 | Debug endpoints |

## API Endpoints

### Inventory Service (Port 5001)

```bash
# Health check
curl http://localhost:5001/health

# List all inventory
curl http://localhost:5001/inventory

# Get specific SKU
curl http://localhost:5001/inventory/SKU001

# Reserve inventory
curl -X POST http://localhost:5001/inventory/SKU001/reserve \
  -H "Content-Type: application/json" \
  -d '{"quantity": 2}'
```

### Payments Service (Port 5002)

```bash
# Health check
curl http://localhost:5002/health

# Process payment (calls inventory internally)
curl -X POST http://localhost:5002/payment/process \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "SKU001",
    "quantity": 1,
    "payment_method": "credit_card"
  }'

# Payment history
curl http://localhost:5002/payment/history
```

### Load Generator (Port 5003)

```bash
# Health check
curl http://localhost:5003/health

# Start load generation (10 RPS for 5 minutes)
curl -X POST http://localhost:5003/load/start

# Check status
curl http://localhost:5003/load/status

# Stop load generation
curl -X POST http://localhost:5003/load/stop
```

**Environment Variables:**
- `LOAD_RPS` - Requests per second (default: 10)
- `LOAD_DURATION` - Duration in seconds (default: 300)

## Viewing Traces in Zipkin

1. Open **http://localhost:9411** (auto-opens in Codespaces)
2. Click **"Run Query"** to see all traces
3. Click any trace to see detailed span timeline
4. Use **Service** dropdown to filter by service
5. Use **Operation** dropdown to filter by operation

### Key Traces to Look For

- `process_payment` - Full payment flow (payments → inventory ×2)
- `check_inventory` - Inventory lookup
- `reserve_inventory` - Stock reservation
- `charge_payment` - Payment processing
- `load_generator_request` - Synthetic traffic

## OpenTelemetry Collector

The collector receives traces via OTLP (gRPC on 4317, HTTP on 4318) and exports to Zipkin.

### Collector Endpoints

```bash
# Check collector health
curl http://localhost:55679/healthz

# View metrics (Prometheus format)
curl http://localhost:8888/metrics

# View zPages (debug)
curl http://localhost:55679/debug/tracez
```

### Configuration

Edit `otel-collector/otel-collector-config.yaml` to:
- Add/remove exporters (Jaeger, Tempo, etc.)
- Adjust sampling rates
- Add processors (tail sampling, span filtering)
- Configure resource attributes

## Project Structure

```
demo-otel-python/
├── docker-compose.yml           # Main orchestration
├── .devcontainer/               # Codespaces config
├── otel-collector/
│   └── otel-collector-config.yaml
├── inventory/                   # Inventory microservice
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── payments/                    # Payments microservice
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── load-generator/              # Load generator
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── diagrams/
│   └── architecture.drawio      # Architecture diagram
└── README.md
```

## Instrumentation Details

Each service uses:
- **FlaskInstrumentor** - Auto-instruments Flask routes
- **RequestsInstrumentor** - Auto-instruments outbound HTTP calls
- **OTLP Exporter** - Sends traces to collector via gRPC
- **Custom Spans** - Business logic spans for key operations

### Adding Custom Spans

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("my_operation") as span:
    span.set_attribute("key", "value")
    # Your code here
```

## Troubleshooting

### Services won't start
```bash
# Check logs
docker-compose logs payments
docker-compose logs inventory
docker-compose logs otel-collector
```

### No traces in Zipkin
1. Verify collector is running: `docker-compose ps otel-collector`
2. Check collector logs: `docker-compose logs otel-collector`
3. Verify services have `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317`
4. Check Zipkin: `curl http://localhost:9411/api/v2/services`

### Port conflicts
Change ports in `docker-compose.yml` if 5001, 5002, 5003, 9411 are in use.

## Development

### Rebuild a service
```bash
docker-compose build payments
docker-compose up -d payments
```

### Run tests locally (outside Docker)
```bash
cd payments
pip install -r requirements.txt
python app.py
```

### View architecture diagram
Open `diagrams/architecture.drawio` in [draw.io](https://app.diagrams.net/) or VS Code with Draw.io extension.

## License

MIT