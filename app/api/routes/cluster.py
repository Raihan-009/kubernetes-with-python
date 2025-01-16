from fastapi import APIRouter, HTTPException
from app.services.k8s_client import K8sClient

router = APIRouter()
k8s_client = K8sClient()

@router.get("/resources", summary="Get all workload resources")
async def get_cluster_resources():
    """
    Get all workload resources (Deployments, StatefulSets, DaemonSets, and standalone Pods)
    with their metrics and status
    """
    try:
        return k8s_client.get_workload_resources()
    except Exception as e:
        print(f"Error getting cluster resources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 