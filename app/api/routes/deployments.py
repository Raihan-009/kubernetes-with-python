from fastapi import APIRouter, HTTPException
from app.services.k8s_client import K8sClient
from typing import Optional

router = APIRouter()
k8s_client = K8sClient()

@router.get("/", summary="List all deployments across all namespaces")
async def list_all_deployments(namespace: Optional[str] = None):
    """
    Get all deployments across all namespaces or in a specific namespace
    """
    try:
        if namespace:
            deployments = k8s_client.get_deployments(namespace)
            deployments_list = deployments.items
        else:
            deployments = k8s_client.apps_v1.list_deployment_for_all_namespaces()
            deployments_list = deployments.items

        return {
            "deployments": [
                {
                    "kind": "Deployment",
                    "name": dep.metadata.name,
                    "namespace": dep.metadata.namespace,
                    "replicas": {
                        "desired": dep.spec.replicas,
                        "available": dep.status.available_replicas or 0,
                        "ready": dep.status.ready_replicas or 0,
                        "updated": dep.status.updated_replicas or 0
                    },
                    "strategy": {
                        "type": dep.spec.strategy.type,
                        "max_surge": dep.spec.strategy.rolling_update.max_surge if dep.spec.strategy.type == "RollingUpdate" else None,
                        "max_unavailable": dep.spec.strategy.rolling_update.max_unavailable if dep.spec.strategy.type == "RollingUpdate" else None
                    },
                    "status": "Healthy" if (dep.status.available_replicas or 0) == dep.spec.replicas else "Unhealthy",
                    "containers": [
                        {
                            "name": container.name,
                            "image": container.image,
                            "ports": [
                                {
                                    "container_port": port.container_port,
                                    "protocol": port.protocol
                                }
                                for port in container.ports
                            ] if container.ports else [],
                            "resources": {
                                "requests": {
                                    "cpu": container.resources.requests.get("cpu", "N/A") if container.resources and container.resources.requests else "N/A",
                                    "memory": container.resources.requests.get("memory", "N/A") if container.resources and container.resources.requests else "N/A"
                                },
                                "limits": {
                                    "cpu": container.resources.limits.get("cpu", "N/A") if container.resources and container.resources.limits else "N/A",
                                    "memory": container.resources.limits.get("memory", "N/A") if container.resources and container.resources.limits else "N/A"
                                }
                            } if container.resources else {}
                        }
                        for container in dep.spec.template.spec.containers
                    ],
                    "conditions": [
                        {
                            "type": condition.type,
                            "status": condition.status,
                            "reason": condition.reason,
                            "message": condition.message,
                            "last_update": condition.last_update_time,
                            "last_transition": condition.last_transition_time
                        }
                        for condition in dep.status.conditions
                    ] if dep.status.conditions else [],
                    "labels": dep.metadata.labels if hasattr(dep.metadata, 'labels') and dep.metadata.labels else {},
                    "annotations": dep.metadata.annotations if hasattr(dep.metadata, 'annotations') and dep.metadata.annotations else {},
                    "creation_timestamp": dep.metadata.creation_timestamp
                }
                for dep in deployments_list
            ]
        }
    except Exception as e:
        print(f"Error in list_all_deployments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{namespace}", summary="List deployments in namespace")
async def list_namespace_deployments(namespace: str):
    """
    Get all deployments in a specific namespace
    """
    try:
        deployments = k8s_client.get_deployments(namespace)
        return {
            "deployments": [
                {
                    "kind": "Deployment",
                    "name": dep.metadata.name,
                    "namespace": namespace,
                    "replicas": {
                        "desired": dep.spec.replicas,
                        "available": dep.status.available_replicas or 0,
                        "ready": dep.status.ready_replicas or 0,
                        "updated": dep.status.updated_replicas or 0
                    },
                    "strategy": {
                        "type": dep.spec.strategy.type,
                        "max_surge": dep.spec.strategy.rolling_update.max_surge if dep.spec.strategy.type == "RollingUpdate" else None,
                        "max_unavailable": dep.spec.strategy.rolling_update.max_unavailable if dep.spec.strategy.type == "RollingUpdate" else None
                    },
                    "status": "Healthy" if (dep.status.available_replicas or 0) == dep.spec.replicas else "Unhealthy",
                    "containers": [
                        {
                            "name": container.name,
                            "image": container.image,
                            "ports": [
                                {
                                    "container_port": port.container_port,
                                    "protocol": port.protocol
                                }
                                for port in container.ports
                            ] if container.ports else [],
                            "resources": {
                                "requests": {
                                    "cpu": container.resources.requests.get("cpu", "N/A") if container.resources and container.resources.requests else "N/A",
                                    "memory": container.resources.requests.get("memory", "N/A") if container.resources and container.resources.requests else "N/A"
                                },
                                "limits": {
                                    "cpu": container.resources.limits.get("cpu", "N/A") if container.resources and container.resources.limits else "N/A",
                                    "memory": container.resources.limits.get("memory", "N/A") if container.resources and container.resources.limits else "N/A"
                                }
                            } if container.resources else {}
                        }
                        for container in dep.spec.template.spec.containers
                    ],
                    "conditions": [
                        {
                            "type": condition.type,
                            "status": condition.status,
                            "reason": condition.reason,
                            "message": condition.message,
                            "last_update": condition.last_update_time,
                            "last_transition": condition.last_transition_time
                        }
                        for condition in dep.status.conditions
                    ] if dep.status.conditions else [],
                    "labels": dep.metadata.labels if hasattr(dep.metadata, 'labels') and dep.metadata.labels else {},
                    "annotations": dep.metadata.annotations if hasattr(dep.metadata, 'annotations') and dep.metadata.annotations else {},
                    "creation_timestamp": dep.metadata.creation_timestamp
                }
                for dep in deployments.items
            ]
        }
    except Exception as e:
        print(f"Error in list_namespace_deployments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 