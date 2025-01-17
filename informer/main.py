from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
from typing import Any, Dict

app = FastAPI(
    title="Kubernetes Informer API",
    description="Proxy API for AI Monitoring Service",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base URL for the AI monitoring service
BASE_URL = "http://ai-monitoring-service.default.svc.cluster.local:8000"

# Create an async HTTP client
http_client = httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)

@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose()

async def proxy_request(path: str) -> Dict[str, Any]:
    try:
        response = await http_client.get(path)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code if hasattr(e, 'response') else 500,
                          detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Proxy routes
@app.get("/api/monitoring/health")
async def get_health():
    return await proxy_request("/api/monitoring/health")

@app.get("/api/cluster/resources")
async def get_cluster_resources():
    return await proxy_request("/api/cluster/resources")

@app.get("/api/namespaces")
async def list_namespaces():
    return await proxy_request("/api/namespaces")

@app.get("/api/namespaces/{namespace}/resources")
async def get_namespace_resources(namespace: str):
    return await proxy_request(f"/api/namespaces/{namespace}/resources")

@app.get("/api/services")
async def list_all_services():
    return await proxy_request("/api/services")

@app.get("/api/services/{namespace}")
async def list_namespace_services(namespace: str):
    return await proxy_request(f"/api/services/{namespace}")

@app.get("/api/pods")
async def list_all_pods():
    return await proxy_request("/api/pods")

@app.get("/api/pods/{namespace}")
async def list_namespace_pods(namespace: str):
    return await proxy_request(f"/api/pods/{namespace}")

@app.get("/api/pods/{namespace}/{pod_name}/logs")
async def get_pod_logs(namespace: str, pod_name: str):
    return await proxy_request(f"/api/pods/{namespace}/{pod_name}/logs")

@app.get("/api/pods/{namespace}/{pod_name}/events")
async def get_pod_events(namespace: str, pod_name: str):
    return await proxy_request(f"/api/pods/{namespace}/{pod_name}/events")

@app.get("/api/deployments")
async def list_all_deployments():
    return await proxy_request("/api/deployments")

@app.get("/api/deployments/{namespace}")
async def list_namespace_deployments(namespace: str):
    return await proxy_request(f"/api/deployments/{namespace}")

@app.get("/api/jobs")
async def list_jobs():
    return await proxy_request("/api/jobs")

@app.get("/")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4000) 