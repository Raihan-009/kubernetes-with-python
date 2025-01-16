from fastapi import APIRouter, HTTPException
from app.services.k8s_client import K8sClient
from typing import Dict, List, Any
import datetime

router = APIRouter()
k8s_client = K8sClient()

@router.get("/health", summary="Get unhealthy pods across cluster")
async def get_unhealthy_resources():
    """
    Get all unhealthy pods (Failed/Pending/CrashLoopBackOff) with their events
    """
    try:
        # Get all namespaces
        namespaces = k8s_client.core_v1.list_namespace()
        unhealthy_resources = {
            "unhealthy_pods": [],
            "total_unhealthy_pods": 0
        }

        for ns in namespaces.items:
            namespace = ns.metadata.name

            # Check pods
            pods = k8s_client.core_v1.list_namespaced_pod(namespace)
            for pod in pods.items:
                # Check if pod is unhealthy
                is_unhealthy = (
                    pod.status.phase in ["Failed", "Pending"] or 
                    any(
                        container.ready is False or 
                        (container.state.waiting and container.state.waiting.reason in ["CrashLoopBackOff", "Error", "CreateContainerError"])
                        for container in (pod.status.container_statuses or [])
                    )
                )

                if is_unhealthy:
                    # Get events for this pod
                    events = k8s_client.core_v1.list_namespaced_event(
                        namespace=namespace,
                        field_selector=f'involvedObject.name={pod.metadata.name}'
                    )

                    # Get the main error reason from container statuses
                    error_reasons = []
                    if pod.status.container_statuses:
                        for container in pod.status.container_statuses:
                            if container.state.waiting:
                                error_reasons.append(f"{container.name}: {container.state.waiting.reason}")
                            elif container.state.terminated and container.state.terminated.exit_code != 0:
                                error_reasons.append(f"{container.name}: Terminated with exit code {container.state.terminated.exit_code}")

                    unhealthy_resources["unhealthy_pods"].append({
                        "name": pod.metadata.name,
                        "namespace": namespace,
                        "status": pod.status.phase,
                        "node": pod.spec.node_name,
                        "error_reasons": error_reasons,
                        "events": [
                            {
                                "type": event.type,
                                "reason": event.reason,
                                "message": event.message,
                                "count": event.count,
                                "first_timestamp": event.first_timestamp,
                                "last_timestamp": event.last_timestamp,
                                "source": event.source.component if event.source else None
                            }
                            for event in sorted(
                                events.items,
                                key=lambda x: (
                                    x.last_timestamp.replace(tzinfo=None) if x.last_timestamp else datetime.datetime.min,
                                    x.first_timestamp.replace(tzinfo=None) if x.first_timestamp else datetime.datetime.min
                                ),
                                reverse=True
                            )
                        ]
                    })

        # Update total count
        unhealthy_resources["total_unhealthy_pods"] = len(unhealthy_resources["unhealthy_pods"])
        
        # Add summary
        unhealthy_resources["summary"] = {
            "total_unhealthy_pods": len(unhealthy_resources["unhealthy_pods"]),
            "affected_namespaces": len(set(
                pod["namespace"] for pod in unhealthy_resources["unhealthy_pods"]
            )),
            "status_breakdown": {
                status: len([
                    pod for pod in unhealthy_resources["unhealthy_pods"]
                    if pod["status"] == status
                ])
                for status in set(pod["status"] for pod in unhealthy_resources["unhealthy_pods"])
            }
        }

        return unhealthy_resources

    except Exception as e:
        print(f"Error in get_unhealthy_resources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 