from fastapi import APIRouter, HTTPException
from app.services.k8s_client import K8sClient

router = APIRouter()
k8s_client = K8sClient()

@router.get("/resources", summary="Get all cluster resources")
async def get_cluster_resources():
    """
    Get all resources across the cluster with their status and metrics
    """
    try:
        resources = k8s_client.get_cluster_resources()
        return {
            "cluster_resources": resources,
            "summary": {
                "total_nodes": len(resources["nodes"]),
                "total_pods": len(resources["pods"]),
                "total_deployments": len(resources["deployments"]),
                "total_services": len(resources["services"]),
                "total_statefulsets": len(resources["statefulsets"]),
                "total_daemonsets": len(resources["daemonsets"]),
                "nodes_status": {
                    "ready": sum(1 for node in resources["nodes"] if node["status"] == "Ready"),
                    "not_ready": sum(1 for node in resources["nodes"] if node["status"] != "Ready")
                },
                "pods_status": {
                    "running": sum(1 for pod in resources["pods"] if pod["status"] == "Running"),
                    "pending": sum(1 for pod in resources["pods"] if pod["status"] == "Pending"),
                    "failed": sum(1 for pod in resources["pods"] if pod["status"] == "Failed"),
                    "succeeded": sum(1 for pod in resources["pods"] if pod["status"] == "Succeeded")
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 