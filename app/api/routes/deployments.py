from fastapi import APIRouter, HTTPException
from app.services.k8s_client import K8sClient

router = APIRouter()
k8s_client = K8sClient()

@router.get("/", summary="List all deployments")
async def list_deployments(namespace: str = "default"):
    """
    Get all deployments in the specified namespace
    """
    try:
        deployments = k8s_client.get_deployments(namespace)
        return {
            "deployments": [
                {
                    "name": dep.metadata.name,
                    "replicas": dep.spec.replicas,
                    "available_replicas": dep.status.available_replicas,
                    "namespace": dep.metadata.namespace
                }
                for dep in deployments.items
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 