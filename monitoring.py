# monitoring.py
from prometheus_client import Counter, Histogram

webhook_requests = Counter("wa_webhook_requests_total", "Entradas al webhook")
wa_send_ok = Counter("wa_send_ok_total", "Mensajes enviados OK")
wa_send_error = Counter("wa_send_error_total", "Mensajes enviados con error", ["reason"])
llm_latency = Histogram("llm_latency_seconds", "Latencia de llamada al LLM (s)")
