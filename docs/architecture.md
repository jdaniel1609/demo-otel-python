# Arquitectura de la demo OTel Python

La demo presenta un flujo simple de microservicios en Python con trazas distribuidas usando OpenTelemetry y Zipkin.

## Diagrama de conexiones

```text
Load Generator (5003)
        |
        | HTTP POST /payment/process
        v
Payments Service (5002)
        |
        | GET /inventory/{sku}
        | POST /inventory/{sku}/reserve
        v
Inventory Service (5001)
        |
        +--------------------+
        |                    |
        v                    v
   OTLP gRPC          OTLP gRPC
   traces to          traces to
   OTel Collector     OTel Collector
        |
        | Zipkin exporter
        v
     Zipkin UI (9411)
```

## Componentes

### 1. Load Generator
- Servicio HTTP en Flask
- Genera tráfico artificial contra Payments
- Expone endpoints:
  - /health
  - /load/start
  - /load/stop
  - /load/status

### 2. Payments Service
- Servicio HTTP en Flask
- Recibe solicitudes de compra
- Consulta inventario antes de aceptar la operación
- Reserva stock en Inventory
- Simula el cobro del pago
- Exporta trazas al collector mediante OTLP

### 3. Inventory Service
- Servicio HTTP en Flask
- Mantiene SKU y cantidades en memoria
- Responde a consultas y reservas de inventario
- Emite spans para `get_inventory` y `reserve_inventory`

### 4. OpenTelemetry Collector
- Recibe trazas por OTLP en los puertos 4317/4318
- Exporta spans a Zipkin
- Expones métricas en 8888 y zPages en 55679

### 5. Zipkin
- Interfaz web para revisar trazas distribuidas
- Disponible en http://localhost:9411
- Permite filtrar por operación y servicio

## Flujo típico

1. El Load Generator envía una petición a Payments.
2. Payments verifica disponibilidad de un SKU en Inventory.
3. Payments reserva el producto y emite un span de pago.
4. Todos los servicios envían trazas al collector.
5. El collector exporta esas trazas a Zipkin.
6. El usuario revisa el flujo completo en la UI de Zipkin.

## Comandos útiles

```bash
# Levantar stack
docker compose up --build -d

# Ver estado
docker compose ps

# Ver logs
docker compose logs -f

# Probar endpoints
curl http://localhost:5001/health
curl http://localhost:5002/health
curl http://localhost:5003/health
curl http://localhost:9411/health
```

## URLs de acceso

- Zipkin: http://localhost:9411
- Inventory: http://localhost:5001
- Payments: http://localhost:5002
- Load Generator: http://localhost:5003
- Collector metrics: http://localhost:8888/metrics
