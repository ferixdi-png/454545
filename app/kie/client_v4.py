"""
Kie.ai API Client V4 - поддержка новой category-specific архитектуры.
Работает параллельно со старым client для совместимости.
"""
import asyncio
import logging
import os
from typing import Dict, Any, Optional

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from app.kie.router import (
    get_api_category_for_model,
    get_api_endpoint_for_model,
    get_base_url_for_category,
    load_v4_source_of_truth
)

logger = logging.getLogger(__name__)


class KieApiClientV4:
    """
    API client для новой архитектуры Kie.ai (v4).
    Поддерживает category-specific endpoints.
    """
    
    def __init__(self, api_key: str | None = None, timeout: int = 30) -> None:
        self.api_key = api_key or os.getenv("KIE_API_KEY")
        if not self.api_key:
            raise ValueError("KIE_API_KEY environment variable is required")
        
        self.timeout = timeout
        self.source_v4 = load_v4_source_of_truth()
        
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def _make_request(self, url: str, payload: Dict[str, Any]) -> requests.Response:
        """
        Make HTTP request with automatic retry.
        
        Retries on:
        - ConnectionError (network issues)
        - Timeout (slow response)
        
        Does NOT retry on:
        - 4xx errors (client errors - bad request)
        - 5xx errors (server errors - will be handled by caller)
        """
        return requests.post(
            url,
            headers=self._headers(),
            json=payload,
            timeout=self.timeout
        )
    
    async def create_task(
        self, 
        model_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create task using category-specific endpoint.
        
        Args:
            model_id: Model identifier (used to route to correct API)
            payload: Request payload (already formatted for specific category)
        
        Returns:
            Task creation response with taskId
        """
        category = get_api_category_for_model(model_id, self.source_v4)
        if not category:
            return {
                "error": f"Unknown model category for {model_id}",
                "state": "fail"
            }
        
        base_url = get_base_url_for_category(category, self.source_v4)
        endpoint = get_api_endpoint_for_model(model_id, self.source_v4)
        
        # Полный URL для category-specific API
        url = f"{base_url}{endpoint}"
        
        logger.info(f"Creating task for {model_id} ({category}): POST {url}")
        logger.debug(f"Payload: {payload}")
        
        try:
            response = await asyncio.to_thread(
                self._make_request,
                url,
                payload
            )
            
            logger.info(f"Response status: {response.status_code}")
            logger.debug(f"Response body: {response.text[:500]}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as exc:
            logger.error(f"Create task failed: {exc}", exc_info=True)
            return {"error": str(exc), "state": "fail"}
    
    async def get_record_info(self, task_id: str) -> Dict[str, Any]:
        """
        Get task record info (status checking).
        Этот endpoint все еще универсальный.
        
        Args:
            task_id: Task ID from create_task
        
        Returns:
            Task status and results
        """
        url = "https://api.kie.ai/api/v1/jobs/recordInfo"
        params = {"taskId": task_id}
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    requests.get,
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                return response.json()
                
            except requests.RequestException as exc:
                logger.warning(f"recordInfo attempt {attempt+1}/{max_retries} failed: {exc}")
                if attempt == max_retries - 1:
                    logger.error(f"Get record info failed: {exc}", exc_info=True)
                    return {"error": str(exc), "state": "fail"}
                await asyncio.sleep(1 * (attempt + 1))
    
    async def poll_task_until_complete(
        self,
        task_id: str,
        max_wait_seconds: int = 300,
        poll_interval: float = 3.0
    ) -> Dict[str, Any]:
        """
        Poll task until completion.
        
        Args:
            task_id: Task ID
            max_wait_seconds: Maximum wait time
            poll_interval: Seconds between polls
        
        Returns:
            Final task data
        """
        start_time = asyncio.get_event_loop().time()
        attempts = 0
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > max_wait_seconds:
                logger.error(f"Task {task_id} timed out after {elapsed:.1f}s")
                return {
                    "error": "Task timeout",
                    "state": "timeout",
                    "taskId": task_id,
                    "elapsed_seconds": elapsed
                }
            
            attempts += 1
            record = await self.get_record_info(task_id)
            
            if 'error' in record:
                return record
            
            state = record.get('state', '').lower()
            logger.info(f"Poll #{attempts} ({elapsed:.1f}s): task {task_id} state={state}")
            
            if state in ['success', 'completed', 'done']:
                logger.info(f"Task {task_id} completed successfully after {elapsed:.1f}s")
                return record
            
            if state in ['fail', 'failed', 'error']:
                logger.error(f"Task {task_id} failed: {record}")
                return record
            
            # Still processing
            await asyncio.sleep(poll_interval)
