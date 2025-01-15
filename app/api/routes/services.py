from fastapi import APIRouter, HTTPException
from app.services.k8s_client import K8sClient
from typing import Optional

router = APIRouter()
k8s_client = K8sClient()

@router.get("/", summary="List all services across all namespaces")
async def list_all_services(namespace: Optional[str] = None):
    """
    Get all services across all namespaces or in a specific namespace
    """
    try:
        if namespace:
            services = k8s_client.get_services(namespace)
            services_list = services.items
        else:
            services = k8s_client.core_v1.list_service_for_all_namespaces()
            services_list = services.items

        return {
            "services": [
                {
                    "kind": "Service",
                    "name": svc.metadata.name,
                    "namespace": svc.metadata.namespace,
                    "type": svc.spec.type,
                    "cluster_ip": svc.spec.cluster_ip,
                    "external_ips": svc.spec.external_ips if hasattr(svc.spec, 'external_ips') else None,
                    "ports": [
                        {
                            "port": port.port,
                            "target_port": str(port.target_port),
                            "protocol": port.protocol,
                            "node_port": port.node_port if hasattr(port, 'node_port') else None
                        }
                        for port in svc.spec.ports
                    ] if hasattr(svc.spec, 'ports') else [],
                    "selector": svc.spec.selector if hasattr(svc.spec, 'selector') else None,
                    "creation_timestamp": svc.metadata.creation_timestamp,
                    "labels": svc.metadata.labels if hasattr(svc.metadata, 'labels') and svc.metadata.labels else {},
                    "annotations": svc.metadata.annotations if hasattr(svc.metadata, 'annotations') and svc.metadata.annotations else {}
                }
                for svc in services_list
            ]
        }
    except Exception as e:
        print(f"Error in list_all_services: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{namespace}", summary="List services in namespace")
async def list_namespace_services(namespace: str):
    """
    Get all services in a specific namespace
    """
    try:
        services = k8s_client.get_services(namespace)
        return {
            "services": [
                {
                    "kind": "Service",
                    "name": svc.metadata.name,
                    "namespace": namespace,
                    "type": svc.spec.type,
                    "cluster_ip": svc.spec.cluster_ip,
                    "external_ips": svc.spec.external_ips if hasattr(svc.spec, 'external_ips') else None,
                    "ports": [
                        {
                            "port": port.port,
                            "target_port": str(port.target_port),
                            "protocol": port.protocol,
                            "node_port": port.node_port if hasattr(port, 'node_port') else None
                        }
                        for port in svc.spec.ports
                    ] if hasattr(svc.spec, 'ports') else [],
                    "selector": svc.spec.selector if hasattr(svc.spec, 'selector') else None,
                    "creation_timestamp": svc.metadata.creation_timestamp,
                    "labels": svc.metadata.labels if hasattr(svc.metadata, 'labels') and svc.metadata.labels else {},
                    "annotations": svc.metadata.annotations if hasattr(svc.metadata, 'annotations') and svc.metadata.annotations else {}
                }
                for svc in services.items
            ]
        }
    except Exception as e:
        print(f"Error in list_namespace_services: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 