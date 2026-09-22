from flask import Flask, jsonify, request
import os
import logging
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenTelemetry
resource = Resource(attributes={
    SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "inventory-service")
})

trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

# Configure OTLP exporter
otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
    insecure=True
)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

app = Flask(__name__)

# Auto-instrument Flask
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

# Mock inventory data
INVENTORY = {
    "SKU001": {"name": "Laptop Pro", "quantity": 100, "price": 1299.99},
    "SKU002": {"name": "Wireless Mouse", "quantity": 500, "price": 29.99},
    "SKU003": {"name": "Mechanical Keyboard", "quantity": 200, "price": 149.99},
    "SKU004": {"name": "Monitor 27\"", "quantity": 75, "price": 349.99},
    "SKU005": {"name": "USB-C Hub", "quantity": 300, "price": 49.99},
}

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "inventory"}), 200

@app.route("/inventory/<sku>", methods=["GET"])
def get_inventory(sku):
    with tracer.start_as_current_span("get_inventory") as span:
        span.set_attribute("sku", sku)
        logger.info(f"Checking inventory for SKU: {sku}")
        
        if sku in INVENTORY:
            item = INVENTORY[sku]
            span.set_attribute("item.name", item["name"])
            span.set_attribute("item.quantity", item["quantity"])
            span.set_attribute("item.price", item["price"])
            return jsonify({
                "sku": sku,
                "name": item["name"],
                "quantity": item["quantity"],
                "price": item["price"],
                "available": item["quantity"] > 0
            }), 200
        else:
            span.set_attribute("error", "not_found")
            return jsonify({"error": "SKU not found"}), 404

@app.route("/inventory/<sku>/reserve", methods=["POST"])
def reserve_inventory(sku):
    with tracer.start_as_current_span("reserve_inventory") as span:
        span.set_attribute("sku", sku)
        data = request.get_json() or {}
        quantity = data.get("quantity", 1)
        span.set_attribute("quantity", quantity)
        logger.info(f"Reserving {quantity} units of SKU: {sku}")
        
        if sku not in INVENTORY:
            span.set_attribute("error", "not_found")
            return jsonify({"error": "SKU not found"}), 404
        
        if INVENTORY[sku]["quantity"] < quantity:
            span.set_attribute("error", "insufficient_stock")
            return jsonify({"error": "Insufficient stock"}), 400
        
        INVENTORY[sku]["quantity"] -= quantity
        span.set_attribute("remaining_quantity", INVENTORY[sku]["quantity"])
        
        return jsonify({
            "sku": sku,
            "reserved": quantity,
            "remaining": INVENTORY[sku]["quantity"]
        }), 200

@app.route("/inventory", methods=["GET"])
def list_inventory():
    with tracer.start_as_current_span("list_inventory") as span:
        logger.info("Listing all inventory")
        return jsonify(INVENTORY), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)