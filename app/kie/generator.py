"""
End-to-end generator for Kie.ai models with heartbeat and error handling.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
import os

from app.kie.builder import build_payload, load_source_of_truth
from app.kie.validator import ModelContractError
from app.kie.parser import parse_record_info, get_human_readable_error
from app.kie.router import is_v4_model, build_category_payload

logger = logging.getLogger(__name__)

# Test mode flag
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'
KIE_STUB = os.getenv('KIE_STUB', 'false').lower() == 'true'
USE_V4_API = os.getenv('KIE_USE_V4', 'true').lower() == 'true'  # Default to V4

# Import at module level to avoid circular imports and for isinstance check
try:
    from app.kie.client_v4 import KieApiClientV4
except ImportError:
    KieApiClientV4 = None


class KieGenerator:
    """Universal generator for Kie.ai models."""
    
    def __init__(self, api_client: Optional[Any] = None):
        """
        Initialize generator.
        
        Args:
            api_client: Optional API client (for dependency injection in tests)
        """
        self.api_client = api_client
        self.source_of_truth = None
        self._heartbeat_interval = 12  # 10-15 seconds, use 12 as middle
        
    def _get_api_client(self):
        """Get API client (real or stub) - V4 or V3."""
        if self.api_client:
            return self.api_client

        if TEST_MODE or KIE_STUB:
            return self._get_stub_client()
        
        # Check if using V4 API (new architecture)
        if USE_V4_API:
            from app.kie.client_v4 import KieApiClientV4
            return KieApiClientV4()
        
        # Fallback to old V3 client (for compatibility)
        from app.api.kie_client import KieApiClient
        return KieApiClient()
    
    def _get_stub_client(self):
        """Get stub client for testing."""
        class StubClient:
            async def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
                """Stub create_task."""
                model = payload.get('model', 'unknown')
                return {
                    'taskId': f"stub_task_{model}",
                    'status': 'waiting'
                }
            
            async def get_record_info(self, task_id: str) -> Dict[str, Any]:
                """Stub get_record_info."""
                # Simulate different states for testing
                if 'text' in task_id or 'test_text' in task_id:
                    return {
                        'state': 'success',
                        'resultJson': json.dumps({
                            'resultUrls': ['https://example.com/result1.txt']
                        })
                    }
                elif 'image' in task_id or 'test_image' in task_id:
                    return {
                        'state': 'success',
                        'resultJson': json.dumps({
                            'resultUrls': ['https://example.com/result1.jpg']
                        })
                    }
                elif 'video' in task_id or 'test_video' in task_id:
                    return {
                        'state': 'success',
                        'resultJson': json.dumps({
                            'resultUrls': ['https://example.com/result1.mp4']
                        })
                    }
                elif 'audio' in task_id or 'test_audio' in task_id:
                    return {
                        'state': 'success',
                        'resultJson': json.dumps({
                            'resultUrls': ['https://example.com/result1.mp3']
                        })
                    }
                elif 'url' in task_id or 'test_url' in task_id:
                    return {
                        'state': 'success',
                        'resultJson': json.dumps({
                            'resultUrls': ['https://example.com/processed.jpg']
                        })
                    }
                elif 'file' in task_id or 'test_file' in task_id:
                    return {
                        'state': 'success',
                        'resultJson': json.dumps({
                            'resultUrls': ['https://example.com/processed_file.pdf']
                        })
                    }
                elif 'fail' in task_id:
                    return {
                        'state': 'fail',
                        'failCode': 'TEST_ERROR',
                        'failMsg': 'Test error message'
                    }
                else:
                    return {'state': 'waiting'}
        
        return StubClient()
    
    async def generate(
        self,
        model_id: str,
        user_inputs: Dict[str, Any],
        progress_callback: Optional[Callable[[str], None]] = None,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Generate content using Kie.ai model.
        
        Args:
            model_id: Model identifier
            user_inputs: User inputs (text, url, file, etc.)
            progress_callback: Optional callback for progress updates
            timeout: Maximum wait time in seconds
            
        Returns:
            Result dictionary with:
            - success: bool
            - message: str
            - result_urls: List[str]
            - result_object: Any
            - error_code: Optional[str]
            - error_message: Optional[str]
        """
        try:
            # Load source of truth if needed
            if not self.source_of_truth:
                self.source_of_truth = load_source_of_truth()
            
            # Check if this is a V4 model (new architecture)
            is_v4 = USE_V4_API and is_v4_model(model_id)
            
            # Build payload using appropriate builder
            if is_v4:
                logger.info(f"Using V4 API for model {model_id}")
                payload = build_category_payload(model_id, user_inputs)
            else:
                logger.info(f"Using V3 API for model {model_id}")
                payload = build_payload(model_id, user_inputs, self.source_of_truth)
            
            # Create task
            api_client = self._get_api_client()
            
            # V4 API requires model_id as first argument
            # V3 API (old KieApiClient) only takes payload
            if isinstance(api_client, KieApiClientV4):
                create_response = await api_client.create_task(model_id, payload)
            else:
                create_response = await api_client.create_task(payload)
            
            # Debug: log response
            logger.info(f"Create task response: {create_response}")
            
            # Check if response is None or has error
            if create_response is None:
                logger.error("create_task returned None")
                return {
                    'success': False,
                    'message': '❌ Ошибка API: не получен ответ от сервера',
                    'result_urls': [],
                    'result_object': None,
                    'error_code': 'NO_RESPONSE',
                    'error_message': 'API client returned None',
                    'task_id': None
                }
            
            # Check for error in response (from exception handling)
            if 'error' in create_response:
                error_msg = create_response.get('error', 'Unknown error')
                logger.error(f"API error in create_task: {error_msg}")
                return {
                    'success': False,
                    'message': f'❌ Ошибка API: {error_msg}',
                    'result_urls': [],
                    'result_object': None,
                    'error_code': 'API_CONNECTION_ERROR',
                    'error_message': error_msg,
                    'task_id': None
                }
            
            # Extract taskId from response (can be at top level or in data object)
            task_id = create_response.get('taskId')
            if not task_id and create_response.get('data'):
                # data can be dict with taskId
                data = create_response.get('data')
                if isinstance(data, dict):
                    task_id = data.get('taskId')
            
            if not task_id:
                # Check if response has error
                error_code = create_response.get('code')
                error_msg = create_response.get('msg', 'Unknown error')
                
                logger.error(f"No taskId in response. Full response: {create_response}")
                return {
                    'success': False,
                    'message': f'❌ Ошибка API: {error_msg}',
                    'result_urls': [],
                    'result_object': None,
                    'error_code': f'API_ERROR_{error_code}' if error_code else 'NO_TASK_ID',
                    'error_message': f'{error_msg}. Response: {create_response}',
                    'task_id': None
                }
            
            # Wait for completion with heartbeat
            start_time = datetime.now()
            last_heartbeat = datetime.now()
            
            while True:
                # Check timeout
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    return {
                        'success': False,
                        'message': f'⏱️ Превышено время ожидания ({timeout} сек)',
                        'result_urls': [],
                        'result_object': None,
                        'error_code': 'TIMEOUT',
                        'error_message': f'Task timeout after {timeout} seconds',
                        'task_id': task_id
                    }
                
                # Get record info
                record_info = await api_client.get_record_info(task_id)
                parsed = parse_record_info(record_info)
                
                state = parsed['state']
                
                if state == 'success':
                    return {
                        'success': True,
                        'message': parsed['message'],
                        'result_urls': parsed['result_urls'],
                        'result_object': parsed['result_object'],
                        'error_code': None,
                        'error_message': None,
                        'task_id': task_id
                    }
                
                elif state == 'fail':
                    error_msg = get_human_readable_error(
                        parsed['error_code'],
                        parsed['error_message']
                    )
                    return {
                        'success': False,
                        'message': f"❌ {error_msg}\n\nНажмите /start для возврата в меню.",
                        'result_urls': [],
                        'result_object': None,
                        'error_code': parsed['error_code'],
                        'error_message': parsed['error_message'],
                        'task_id': task_id
                    }
                
                elif state == 'waiting':
                    # Send heartbeat if needed
                    time_since_heartbeat = (datetime.now() - last_heartbeat).total_seconds()
                    if time_since_heartbeat >= self._heartbeat_interval:
                        if progress_callback:
                            # Use real progress from Kie.ai if available
                            # MASTER PROMPT: "7. Прогресс / ETA" - enhanced formatting
                            progress_percent = parsed.get('progress', 0)
                            eta_seconds = parsed.get('eta')
                            
                            if progress_percent and progress_percent > 0:
                                # Show progress bar
                                bar_length = 10
                                filled = int(progress_percent / 10)
                                bar = '█' * filled + '░' * (bar_length - filled)
                                
                                if eta_seconds:
                                    progress_callback(
                                        f"⏳ <b>Генерация</b>\n\n"
                                        f"{bar} {progress_percent}%\n"
                                        f"Осталось: ~{eta_seconds} сек"
                                    )
                                else:
                                    progress_callback(
                                        f"⏳ <b>Генерация</b>\n\n"
                                        f"{bar} {progress_percent}%"
                                    )
                            elif eta_seconds:
                                progress_callback(
                                    f"⏳ <b>Генерация...</b>\n\n"
                                    f"Осталось: ~{eta_seconds} сек"
                                )
                            else:
                                # Fallback: show elapsed time with animation
                                dots = '.' * (int(elapsed) % 4)
                                progress_callback(
                                    f"⏳ <b>Генерация{dots}</b>\n\n"
                                    f"Прошло: {int(elapsed)} сек"
                                )
                        last_heartbeat = datetime.now()
                    
                    # Wait before next check
                    await asyncio.sleep(2)  # Check every 2 seconds
                    continue
                
                else:
                    # Unknown state
                    await asyncio.sleep(2)
                    continue
        
        except (ValueError, ModelContractError) as e:
            # Payload building error
            return {
                'success': False,
                'message': f"❌ Ошибка в параметрах: {str(e)}\n\nНажмите /start для возврата в меню.",
                'result_urls': [],
                'result_object': None,
                'error_code': 'INVALID_INPUT',
                'error_message': str(e),
                'task_id': None
            }
        
        except Exception as e:
            logger.error(f"Error in generate: {e}", exc_info=True)
            # MASTER PROMPT: Logging - critical event (generation failed)
            logger.error(f"Generation failed: model={model_id}, error={str(e)}")
            return {
                'success': False,
                'message': f"❌ Произошла ошибка: {str(e)}\n\nНажмите /start для возврата в меню.",
                'result_urls': [],
                'result_object': None,
                'error_code': 'UNKNOWN_ERROR',
                'error_message': str(e),
                'task_id': None
            }


# Convenience functions
async def generate_from_text(
    model_id: str,
    text: str,
    progress_callback: Optional[Callable[[str], None]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Generate from text input."""
    generator = KieGenerator()
    user_inputs = {'text': text, 'prompt': text, **kwargs}
    return await generator.generate(model_id, user_inputs, progress_callback)


async def generate_from_url(
    model_id: str,
    url: str,
    progress_callback: Optional[Callable[[str], None]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Generate from URL input."""
    generator = KieGenerator()
    user_inputs = {'url': url, **kwargs}
    return await generator.generate(model_id, user_inputs, progress_callback)


async def generate_from_file(
    model_id: str,
    file_id: str,
    progress_callback: Optional[Callable[[str], None]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Generate from file input."""
    generator = KieGenerator()
    user_inputs = {'file': file_id, 'file_id': file_id, **kwargs}
    return await generator.generate(model_id, user_inputs, progress_callback)
