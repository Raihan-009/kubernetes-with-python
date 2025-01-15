from fastapi import APIRouter, HTTPException
from app.services.k8s_client import K8sClient

router = APIRouter()
k8s_client = K8sClient()

@router.get("/", summary="List all namespaces")
async def list_namespaces():
    """
    Get all namespaces in the cluster
    """
    try:
        namespaces = k8s_client.get_namespaces()
        return {
            "namespaces": [
                {
                    "name": ns.metadata.name,
                    "status": ns.status.phase,
                    "creation_timestamp": ns.metadata.creation_timestamp
                }
                for ns in namespaces.items
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{namespace}/resources", summary="Get all resources in namespace")
async def get_namespace_resources(namespace: str):
    """
    Get all resources in a specific namespace
    """
    try:
        resources = k8s_client.get_namespace_resources(namespace)
        return {
            "pods": [
                {
                    "name": pod.metadata.name,
                    "status": pod.status.phase
                }
                for pod in resources["pods"].items
            ],
            "services": [
                {
                    "name": svc.metadata.name,
                    "type": svc.spec.type,
                    "cluster_ip": svc.spec.cluster_ip
                }
                for svc in resources["services"].items
            ],
            "deployments": [
                {
                    "name": dep.metadata.name,
                    "replicas": dep.spec.replicas,
                    "available_replicas": dep.status.available_replicas
                }
                for dep in resources["deployments"].items
            ],
            "jobs": [
                {
                    "name": job.metadata.name,
                    "status": job.status.conditions[-1].type if job.status.conditions else "Unknown"
                }
                for job in resources["jobs"].items
            ],
            "configmaps": [
                {
                    "name": cm.metadata.name
                }
                for cm in resources["configmaps"].items
            ],
            "statefulsets": [
                {
                    "name": sts.metadata.name,
                    "replicas": sts.spec.replicas
                }
                for sts in resources["statefulsets"].items
            ],
            "ingresses": [
                {
                    "name": ing.metadata.name,
                    "hosts": [rule.host for rule in ing.spec.rules] if ing.spec.rules else []
                }
                for ing in resources["ingresses"].items
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 