import json
import os
from typing import Dict, Any, List

# Load golden benchmark dataset if present
DATASET_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/golden_incidents.json"))

def _get_service_telemetry(service_name: str) -> Dict[str, Any]:
    if os.path.exists(DATASET_PATH):
        try:
            with open(DATASET_PATH, "r", encoding="utf-8") as f:
                incidents = json.load(f)
                for inc in incidents:
                    if inc.get("target_service") == service_name:
                        return inc.get("telemetry", {})
        except Exception:
            pass
    return {}

def get_service_status(service_name: str) -> Dict[str, Any]:
    telemetry = _get_service_telemetry(service_name)
    if "status" in telemetry:
        res = {"service": service_name}
        res.update(telemetry["status"])
        return res

    if service_name == "payment-service":
        return {
            'service': service_name, 
            'status': "UNHEALTHY",
            'replicas_ready': '1/3'
        }
    return {
        'service': service_name,
        'status': "HEALTHY",
        'replicas_ready': '3/3'
    }

def query_logs(service_name: str, limit: int = 3) -> List[str]:
    telemetry = _get_service_telemetry(service_name)
    if "logs" in telemetry:
        return telemetry["logs"][:limit]

    if service_name == "payment-service":
        return [
            "INFO: Received POST /checkout request",
            "WARN: Database pool acquisition took 2500ms",
            "ERROR: Database connection pool exhausted - timeout after 5000ms"
        ]
    return ["INFO: Service operational - 200 OK"]

def query_metrics(service_name: str, metric_name: str = 'db_latency') -> Dict[str, Any]:
    telemetry = _get_service_telemetry(service_name)
    if "metrics" in telemetry:
        res = {"service": service_name}
        res.update(telemetry["metrics"])
        return res

    if service_name == "payment-service":
        return {
            "service": service_name,
            "metric": metric_name,
            "value": 4850,
            "unit": "ms",
            "threshold": 200,
            "alert": "CRITICAL"
        }
    return {
        "service": service_name,
        "metric": metric_name,
        "value": 25,
        "unit": "ms",
        "threshold": 200,
        "alert": "NORMAL"
    }



def remediate_service(service_name:str,action:str='restart_pool')->Dict[str,any]:

    return {
        'service':service_name,
        'action':action,
        'status':'success',
        'message':f'successfully applied {action} to {service_name}. Pool cleared, services recovered.'
    }


def verify_service_health(service_name:str,
has_remediated:bool=True)->Dict[str,Any]:

    if has_remediated:
        return {
            'service':service_name,
            'status':'HEALTHY',
            'latency_ms':28,
            'error_rate':'0.0%',
            'verified':True
        }
    return {
        'service':service_name,
        'status':'UNHEALTHY',
        'latency_ms':4500,
        'error_rate':'18.2%',
        'verified':False
    }

    