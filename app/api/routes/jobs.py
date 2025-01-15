from fastapi import APIRouter, HTTPException
from app.services.k8s_client import K8sClient

router = APIRouter()
k8s_client = K8sClient()

@router.get("/", summary="List all jobs")
async def list_jobs(namespace: str = "default"):
    """
    Get all jobs in the specified namespace
    """
    try:
        jobs = k8s_client.get_jobs(namespace)
        return {
            "jobs": [
                {
                    "name": job.metadata.name,
                    "status": job.status.conditions[-1].type if job.status.conditions else "Unknown",
                    "namespace": job.metadata.namespace
                }
                for job in jobs.items
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 