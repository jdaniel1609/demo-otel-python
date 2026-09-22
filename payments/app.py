from flask import Flask, jsonify, request
import os
import logging
import requests
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
    SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "payments-service")
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

INVENTORY_URL = os.getenv("INVENTORY_URL", "http://inventory:5001")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "payments"}), 200

@app.route("/payment/process", methods=["POST"])
def process_payment():
    with tracer.start_as_current_span("process_payment") as span:
        data = request.get_json() or {}
        sku = data.get("sku")
        quantity = data.get("quantity", 1)
        payment_method = data.get("payment_method", "credit_card")
        
        span.set_attribute("sku", sku)
        span.set_attribute("quantity", quantity)
        span.set_attribute("payment_method", payment_method)
        
        logger.info(f"Processing payment for SKU: {sku}, Quantity: {quantity}")
        
        if not sku:
            span.set_attribute("error", "missing_sku")
            return jsonify({"error": "SKU is required"}), 400
        
        # Step 1: Check inventory
        with tracer.start_as_current_span("check_inventory") as inv_span:
            inv_span.set_attribute("sku", sku)
            try:
                resp = requests.get(f"{INVENTORY_URL}/inventory/{sku}", timeout=5)
                inv_span.set_attribute("http.status_code", resp.status_code)
                
                if resp.status_code != 200:
                    inv_span.set_attribute("error", "inventory_not_found")
                    return jsonify({"error": "Product not found"}), 404
                
                inventory_data = resp.json()
                inv_span.set_attribute("item.name", inventory_data.get("name"))
                inv_span.set_attribute("item.price", inventory_data.get("price"))
                
                if not inventory_data.get("available"):
                    inv_span.set_attribute("error", "out_of_stock")
                    return jsonify({"error": "Product out of stock"}), 400
                    
            except requests.RequestException as e:
                inv_span.set_attribute("error", str(e))
                logger.error(f"Inventory service error: {e}")
                return jsonify({"error": "Inventory service unavailable"}), 503
        
        # Step 2: Reserve inventory
        with tracer.start_as_current_span("reserve_inventory") as reserve_span:
            reserve_span.set_attribute("sku", sku)
            reserve_span.set_attribute("quantity", quantity)
            try:
                resp = requests.post(
                    f"{INVENTORY_URL}/inventory/{sku}/reserve",
                    json={"quantity": quantity},
                    timeout=5
                )
                reserve_span.set_attribute("http.status_code", resp.status_code)
                
                if resp.status_code != 200:
                    reserve_span.set_attribute("error", "reservation_failed")
                    return jsonify({"error": "Failed to reserve inventory"}), 400
                    
            except requests.RequestException as e:
                reserve_span.set_attribute("error", str(e))
                logger.error(f"Inventory reservation error: {e}")
                return jsonify({"error": "Inventory service unavailable"}), 503
        
        # Step 3: Process payment (mock)
        with tracer.start_as_current_span("charge_payment") as pay_span:
            pay_span.set_attribute("amount", inventory_data["price"] * quantity)
            pay_span.set_attribute("payment_method", payment_method)
            logger.info(f"Charging payment: ${inventory_data['price'] * quantity}")
            
            # Simulate payment processing
            import time
            time.sleep(0.1)
            
            transaction_id = f"TXN-{sku}-{quantity}-{int(time.time())}"
            pay_span.set_attribute("transaction_id", transaction_id)
        
        return jsonify({
            "success": True,
            "transaction_id": transaction_id,
            "sku": sku,
            "quantity": quantity,
            "total": inventory_data["price"] * quantity,
            "payment_method": payment_method
        }), 200

@app.route("/payment/history", methods=["GET"])
def payment_history():
    with tracer.start_as_current_span("payment_history") as span:
        logger.info("Fetching payment history")
        # Mock history
        return jsonify([
            {"transaction_id": "TXN-SKU001-1-1234567890", "sku": "SKU001", "amount": 1299.99, "status": "completed"},
            {"transaction_id": "TXN-SKU002-2-1234567891", "sku": "SKU002", "amount": 59.98, "status": "completed"},
        ]), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)