from fastapi import APIRouter, HTTPException
from app.services.k8s_client import K8sClient
from typing import Optional

router = APIRouter()
k8s_client = K8sClient()

@router.get("/", summary="List all pods across all namespaces")
async def list_all_pods(namespace: Optional[str] = None):
    """
    Get all pods across all namespaces or in a specific namespace
    """
    try:
        if namespace:
            pods = k8s_client.get_pods(namespace)
            pods_list = pods.items
        else:
            pods = k8s_client.core_v1.list_pod_for_all_namespaces()
            pods_list = pods.items

        return {
            "pods": [
                {
                    "kind": "Pod",
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "status": pod.status.phase,
                    "node": pod.spec.node_name if pod.spec.node_name else None,
                    "ip": pod.status.pod_ip,
                    "start_time": pod.status.start_time,
                    "containers": [
                        {
                            "name": cont.name,
                            "ready": cont.ready,
                            "restart_count": cont.restart_count,
                            "image": cont.image,
                            "state": next(iter(cont.state.__dict__.keys())) if cont.state else None
                        }
                        for cont in pod.status.container_statuses
                    ] if pod.status.container_statuses else [],
                    "labels": pod.metadata.labels if hasattr(pod.metadata, 'labels') and pod.metadata.labels else {},
                    "annotations": pod.metadata.annotations if hasattr(pod.metadata, 'annotations') and pod.metadata.annotations else {}
                }
                for pod in pods_list
            ]
        }
    except Exception as e:
        print(f"Error in list_all_pods: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{namespace}", summary="List pods in namespace")
async def list_namespace_pods(namespace: str):
    """
    Get all pods in a specific namespace
    """
    try:
        pods = k8s_client.get_pods(namespace)
        return {
            "pods": [
                {
                    "kind": "Pod",
                    "name": pod.metadata.name,
                    "namespace": namespace,
                    "status": pod.status.phase,
                    "node": pod.spec.node_name if pod.spec.node_name else None,
                    "ip": pod.status.pod_ip,
                    "start_time": pod.status.start_time,
                    "containers": [
                        {
                            "name": cont.name,
                            "ready": cont.ready,
                            "restart_count": cont.restart_count,
                            "image": cont.image,
                            "state": next(iter(cont.state.__dict__.keys())) if cont.state else None
                        }
                        for cont in pod.status.container_statuses
                    ] if pod.status.container_statuses else [],
                    "labels": pod.metadata.labels if hasattr(pod.metadata, 'labels') and pod.metadata.labels else {},
                    "annotations": pod.metadata.annotations if hasattr(pod.metadata, 'annotations') and pod.metadata.annotations else {}
                }
                for pod in pods.items
            ]
        }
    except Exception as e:
        print(f"Error in list_namespace_pods: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{namespace}/{pod_name}/logs", summary="Get pod logs")
async def get_pod_logs(pod_name: str, namespace: str, container: Optional[str] = None):
    """
    Get logs for a specific pod
    """
    try:
        logs = k8s_client.get_pod_logs(pod_name, namespace, container)
        return {"logs": logs}
    except Exception as e:
        print(f"Error getting pod logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{namespace}/{pod_name}/events", summary="Get pod events")
async def get_pod_events(pod_name: str, namespace: str):
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
                    "timestamp": event.last_timestamp,
                    "count": event.count
                }
                for event in events.items
            ]
        }
    except Exception as e:
        print(f"Error getting pod events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 