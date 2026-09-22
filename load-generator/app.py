from flask import Flask, jsonify
import os
import logging
import requests
import threading
import time
import random
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
    SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "load-generator")
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

# Auto-instrument Flask and Requests
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://payments:5002")
LOAD_RPS = int(os.getenv("LOAD_RPS", "10"))
LOAD_DURATION = int(os.getenv("LOAD_DURATION", "300"))

SKUS = ["SKU001", "SKU002", "SKU003", "SKU004", "SKU005"]
PAYMENT_METHODS = ["credit_card", "debit_card", "paypal", "apple_pay"]

load_thread = None
stop_load = threading.Event()

def generate_load():
    """Generate continuous load against payments service"""
    logger.info(f"Starting load generator: {LOAD_RPS} RPS for {LOAD_DURATION}s")
    start_time = time.time()
    request_count = 0
    
    while not stop_load.is_set() and (time.time() - start_time) < LOAD_DURATION:
        with tracer.start_as_current_span("load_generator_request") as span:
            sku = random.choice(SKUS)
            quantity = random.randint(1, 5)
            payment_method = random.choice(PAYMENT_METHODS)
            
            span.set_attribute("sku", sku)
            span.set_attribute("quantity", quantity)
            span.set_attribute("payment_method", payment_method)
            span.set_attribute("request_id", request_count)
            
            try:
                resp = requests.post(
                    f"{PAYMENTS_URL}/payment/process",
                    json={
                        "sku": sku,
                        "quantity": quantity,
                        "payment_method": payment_method
                    },
                    timeout=10
                )
                span.set_attribute("http.status_code", resp.status_code)
                
                if resp.status_code == 200:
                    logger.info(f"Request {request_count}: SUCCESS - {sku} x{quantity}")
                else:
                    logger.warning(f"Request {request_count}: FAILED - {resp.status_code} - {resp.text}")
                    
            except requests.RequestException as e:
                span.set_attribute("error", str(e))
                logger.error(f"Request {request_count}: ERROR - {e}")
            
            request_count += 1
        
        # Sleep to maintain RPS
        time.sleep(1.0 / LOAD_RPS)
    
    logger.info(f"Load generator finished. Total requests: {request_count}")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "load-generator"}), 200

@app.route("/load/start", methods=["POST"])
def start_load():
    global load_thread
    
    if load_thread and load_thread.is_alive():
        return jsonify({"error": "Load generator already running"}), 400
    
    stop_load.clear()
    load_thread = threading.Thread(target=generate_load, daemon=True)
    load_thread.start()
    
    return jsonify({
        "message": "Load generator started",
        "rps": LOAD_RPS,
        "duration": LOAD_DURATION
    }), 200

@app.route("/load/stop", methods=["POST"])
def stop_load_endpoint():
    stop_load.set()
    return jsonify({"message": "Load generator stopped"}), 200

@app.route("/load/status", methods=["GET"])
def load_status():
    return jsonify({
        "running": load_thread.is_alive() if load_thread else False,
        "rps": LOAD_RPS,
        "duration": LOAD_DURATION
    }), 200

if __name__ == "__main__":
    # Auto-start load generation
    time.sleep(10)  # Wait for services to be ready
    stop_load.clear()
    load_thread = threading.Thread(target=generate_load, daemon=True)
    load_thread.start()
    
    app.run(host="0.0.0.0", port=5003)