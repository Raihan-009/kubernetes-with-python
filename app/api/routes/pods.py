from fastapi import APIRouter, HTTPException
from app.services.k8s_client import K8sClient
from typing import Optional

router = APIRouter()
k8s_client = K8sClient()

@router.get("/", summary="List all pods")
async def list_pods(namespace: str = "default"):
    """
    Get all pods in the specified namespace
    """
    try:
        pods = k8s_client.get_pods(namespace)
        return {
            "pods": [
                {
                    "name": pod.metadata.name,
                    "status": pod.status.phase,
                    "namespace": pod.metadata.namespace
                }
                for pod in pods.items
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{pod_name}/logs", summary="Get pod logs")
async def get_pod_logs(pod_name: str, namespace: str = "default", container: Optional[str] = None):
    """
    Get logs for a specific pod
    """
    try:
        logs = k8s_client.get_pod_logs(pod_name, namespace, container)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{pod_name}/events", summary="Get pod events")
async def get_pod_events(pod_name: str, namespace: str = "default"):
    """
    Get events for a specific pod
    """
    try:
        events = k8s_client.get_pod_events(pod_name, namespace)
        return {
            "events": [
                {
                    "type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "timestamp": event.last_timestamp
                }
                for event in events.items
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 