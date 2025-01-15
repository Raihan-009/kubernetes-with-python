from fastapi import APIRouter, HTTPException
from app.services.k8s_client import K8sClient
from typing import Dict, List, Any

router = APIRouter()
k8s_client = K8sClient()

@router.get("/health", summary="Get unhealthy resources across cluster")
async def get_unhealthy_resources():
    """
    Get all unhealthy resources (Failed/Pending pods, Unhealthy deployments, etc.)
    """
    try:
        # Get all namespaces
        namespaces = k8s_client.core_v1.list_namespace()
        unhealthy_resources = {
            "pods": [],
            "deployments": [],
            "total_unhealthy": 0
        }

        for ns in namespaces.items:
            namespace = ns.metadata.name

            # Check pods
            pods = k8s_client.core_v1.list_namespaced_pod(namespace)
            for pod in pods.items:
                if pod.status.phase in ["Failed", "Pending"] or any(
                    container.ready is False 
                    for container in (pod.status.container_statuses or [])
                ):
                    container_statuses = []
                    for container in (pod.status.container_statuses or []):
                        state = next(iter(container.state.__dict__.keys()))
                        state_obj = getattr(container.state, state)
                        
                        status = {
                            "name": container.name,
                            "ready": container.ready,
                            "restart_count": container.restart_count,
                            "state": state,
                        }
                        
                        # Add reason and message if available
                        if hasattr(state_obj, 'reason'):
                            status["reason"] = state_obj.reason
                        if hasattr(state_obj, 'message'):
                            status["message"] = state_obj.message
                            
                        container_statuses.append(status)

                    unhealthy_resources["pods"].append({
                        "name": pod.metadata.name,
                        "namespace": namespace,
                        "phase": pod.status.phase,
                        "conditions": [
                            {
                                "type": condition.type,
                                "status": condition.status,
                                "reason": condition.reason,
                                "message": condition.message
                            }
                            for condition in pod.status.conditions or []
                        ],
                        "container_statuses": container_statuses,
                        "node": pod.spec.node_name,
                        "start_time": pod.status.start_time,
                        "message": pod.status.message if pod.status.message else None,
                        "reason": pod.status.reason if pod.status.reason else None
                    })

            # Check deployments
            deployments = k8s_client.apps_v1.list_namespaced_deployment(namespace)
            for dep in deployments.items:
                if (dep.status.available_replicas or 0) != dep.spec.replicas:
                    unhealthy_resources["deployments"].append({
                        "name": dep.metadata.name,
                        "namespace": namespace,
                        "replicas": {
                            "desired": dep.spec.replicas,
                            "available": dep.status.available_replicas or 0,
                            "ready": dep.status.ready_replicas or 0,
                            "updated": dep.status.updated_replicas or 0
                        },
                        "conditions": [
                            {
                                "type": condition.type,
                                "status": condition.status,
                                "reason": condition.reason,
                                "message": condition.message,
                                "last_update": condition.last_update_time,
                                "last_transition": condition.last_transition_time
                            }
                            for condition in dep.status.conditions or []
                        ],
                        "containers": [
                            {
                                "name": container.name,
                                "image": container.image,
                                "ready": False  # Since deployment is unhealthy
                            }
                            for container in dep.spec.template.spec.containers
                        ]
                    })

        # Calculate total unhealthy resources
        unhealthy_resources["total_unhealthy"] = len(unhealthy_resources["pods"]) + len(unhealthy_resources["deployments"])
        
        # Add summary
        unhealthy_resources["summary"] = {
            "unhealthy_pods": len(unhealthy_resources["pods"]),
            "unhealthy_deployments": len(unhealthy_resources["deployments"]),
            "affected_namespaces": len(set(
                [res["namespace"] for res in unhealthy_resources["pods"]] +
                [res["namespace"] for res in unhealthy_resources["deployments"]]
            ))
        }

        return unhealthy_resources

    except Exception as e:
        print(f"Error in get_unhealthy_resources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 