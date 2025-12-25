"""
Kie.ai API client.
Strictly uses:
- POST /api/v1/jobs/createTask
- GET /api/v1/jobs/recordInfo
"""
import asyncio
import logging
import os
from typing import Dict, Any

import requests

logger = logging.getLogger(__name__)


class KieApiClient:
    """Minimal, strict Kie.ai API client."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: int = 30) -> None:
        self.api_key = api_key or os.getenv("KIE_API_KEY")
        if not self.api_key:
            raise ValueError("KIE_API_KEY environment variable is required")
        
        # Default to official Kie.ai API URL if not provided
        self.base_url = (base_url or os.getenv("KIE_BASE_URL") or "https://api.kie.ai").rstrip("/")
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"POST {url} with payload: {payload}")
        response = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
        logger.info(f"Response status: {response.status_code}, body: {response.text[:500]}")
        response.raise_for_status()
        return response.json()

    def _get(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _api_base(self) -> str:
        if self.base_url.endswith("/api/v1"):
            return self.base_url
        return f"{self.base_url}/api/v1"

    async def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create Kie.ai task with retry logic."""
        url = f"{self._api_base()}/jobs/createTask"
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await asyncio.to_thread(self._post, url, payload)
            except requests.RequestException as exc:
                logger.warning(f"Kie createTask attempt {attempt+1}/{max_retries} failed: {exc}")
                if attempt == max_retries - 1:
                    logger.error("Kie createTask failed after retries: %s", exc, exc_info=True)
                    return {"error": str(exc), "state": "fail"}
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff

    async def get_record_info(self, task_id: str) -> Dict[str, Any]:
        """Get Kie.ai task record info with retry logic."""
        url = f"{self._api_base()}/jobs/recordInfo"
        payload = {"taskId": task_id}
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await asyncio.to_thread(self._get, url, payload)
            except requests.RequestException as exc:
                logger.warning(f"Kie recordInfo attempt {attempt+1}/{max_retries} failed: {exc}")
                if attempt == max_retries - 1:
                    logger.error("Kie recordInfo failed after retries: %s", exc, exc_info=True)
                    return {"error": str(exc), "state": "fail"}
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff

    async def poll_task_until_complete(
        self,
        task_id: str,
        max_wait_seconds: int = 300,
        poll_interval: float = 3.0
    ) -> Dict[str, Any]:
        """
        Poll task status until it completes (success/fail) or timeout.
        
        Args:
            task_id: Task ID from createTask
            max_wait_seconds: Maximum time to wait (default: 5 min)
            poll_interval: Seconds between polls (default: 3s)
        
        Returns:
            Final task data with state, resultJson, etc.
        """
        start_time = asyncio.get_event_loop().time()
        attempts = 0
        
        while True:
            attempts += 1
            elapsed = asyncio.get_event_loop().time() - start_time
            
            if elapsed > max_wait_seconds:
                logger.error(f"Task {task_id} timeout after {elapsed:.1f}s")
                return {
                    "error": "timeout",
                    "state": "fail",
                    "task_id": task_id,
                    "elapsed_seconds": elapsed
                }
            
            # Get current status
            record = await self.get_record_info(task_id)
            
            if "error" in record:
                logger.error(f"Task {task_id} polling error: {record['error']}")
                return record
            
            data = record.get("data", {})
            state = data.get("state", "unknown")
            
            logger.debug(f"Poll #{attempts} for {task_id}: state={state}, elapsed={elapsed:.1f}s")
            
            # Terminal states
            if state in ("success", "fail"):
                logger.info(f"Task {task_id} completed: {state} (elapsed={elapsed:.1f}s)")
                return data
            
            # Still processing
            await asyncio.sleep(poll_interval)

    async def generate(
        self,
        model_id: str,
        input_params: Dict[str, Any],
        callback_url: str | None = None,
        max_wait: int = 300
    ) -> Dict[str, Any]:
        """
        High-level generation method: create task + poll until complete.
        
        Args:
            model_id: Kie model ID (e.g., "z-image")
            input_params: Model input parameters
            callback_url: Optional callback URL
            max_wait: Maximum wait time in seconds
        
        Returns:
            {
                "state": "success" | "fail",
                "task_id": str,
                "result_urls": List[str] | None,  # For images/videos
                "error": str | None,
                "cost_time_ms": int,
                "raw_response": Dict  # Full API response
            }
        """
        # Create task
        payload = {
            "model": model_id,
            "input": input_params
        }
        
        if callback_url:
            payload["callBackUrl"] = callback_url
        
        logger.info(f"Creating task for model: {model_id}")
        create_resp = await self.create_task(payload)
        
        if "error" in create_resp or create_resp.get("code") != 200:
            error_msg = create_resp.get("error") or create_resp.get("msg", "Unknown error")
            logger.error(f"Failed to create task: {error_msg}")
            return {
                "state": "fail",
                "error": error_msg,
                "raw_response": create_resp
            }
        
        task_id = create_resp.get("data", {}).get("taskId")
        
        if not task_id:
            logger.error("No taskId in create response")
            return {
                "state": "fail",
                "error": "No taskId returned",
                "raw_response": create_resp
            }
        
        logger.info(f"Task created: {task_id}, polling for completion...")
        
        # Poll until complete
        final_data = await self.poll_task_until_complete(task_id, max_wait_seconds=max_wait)
        
        # Parse results
        state = final_data.get("state", "fail")
        result_json = final_data.get("resultJson", "{}")
        cost_time = final_data.get("costTime", 0)
        
        result = {
            "state": state,
            "task_id": task_id,
            "cost_time_ms": cost_time,
            "raw_response": final_data
        }
        
        if state == "success":
            try:
                import json
                result_data = json.loads(result_json) if isinstance(result_json, str) else result_json
                result["result_urls"] = result_data.get("resultUrls", [])
            except Exception as e:
                logger.warning(f"Failed to parse resultJson: {e}")
                result["result_urls"] = []
        else:
            result["error"] = final_data.get("failMsg") or final_data.get("error", "Unknown error")
        
        return result
