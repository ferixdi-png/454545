"""
Registry loader для KIE_SOURCE_OF_TRUTH.json

Предоставляет доступ к моделям из единого source of truth.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from functools import lru_cache


class KieRegistryLoader:
    """Загрузчик и кэш для registry моделей"""
    
    _instance = None
    _registry = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._registry is None:
            self._load_registry()
    
    def _load_registry(self):
        """Загружает registry из JSON"""
        registry_file = Path(__file__).parent.parent.parent / "models" / "KIE_SOURCE_OF_TRUTH.json"
        
        if not registry_file.exists():
            raise FileNotFoundError(f"Registry not found: {registry_file}")
        
        with open(registry_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self._registry = data
        self._models = data.get('models', {})
        self._pending = data.get('pending', [])
    
    @property
    def all_models(self) -> Dict:
        """Все модели"""
        return self._models
    
    @property
    def ready_models(self) -> Dict:
        """Модели с endpoint и schema"""
        return {
            model_id: data
            for model_id, data in self._models.items()
            if data.get('endpoint') and data.get('input_schema')
        }
    
    @property
    def priced_models(self) -> Dict:
        """Модели с ценами"""
        return {
            model_id: data
            for model_id, data in self._models.items()
            if data.get('pricing')
        }
    
    @property
    def free_models(self) -> Dict:
        """Бесплатные модели"""
        return {
            model_id: data
            for model_id, data in self._models.items()
            if data.get('pricing', {}).get('is_free', False)
        }
    
    def get_model(self, model_id: str) -> Optional[Dict]:
        """Получить данные модели по ID"""
        return self._models.get(model_id)
    
    def get_models_by_category(self, category: str) -> Dict:
        """Получить модели по категории"""
        return {
            model_id: data
            for model_id, data in self._models.items()
            if data.get('category') == category
        }
    
    def get_models_by_provider(self, provider: str) -> Dict:
        """Получить модели по provider"""
        return {
            model_id: data
            for model_id, data in self._models.items()
            if data.get('provider') == provider
        }
    
    def get_cheapest_models(self, limit: int = 5) -> List[Dict]:
        """Получить N самых дешевых моделей"""
        priced = []
        
        for model_id, data in self._models.items():
            pricing = data.get('pricing', {})
            if pricing:
                price = pricing.get('usd_per_gen', float('inf'))
                priced.append({
                    'model_id': model_id,
                    'price': price,
                    'data': data
                })
        
        # Сортируем по цене
        priced.sort(key=lambda x: x['price'])
        
        return [item['data'] for item in priced[:limit]]
    
    def search_models(self, query: str) -> Dict:
        """Поиск моделей по названию/описанию"""
        query = query.lower()
        
        results = {}
        for model_id, data in self._models.items():
            if (query in model_id.lower() or
                query in data.get('display_name', '').lower() or
                query in data.get('description', '').lower()):
                results[model_id] = data
        
        return results
    
    @property
    def stats(self) -> Dict:
        """Статистика registry"""
        return {
            'total_models': len(self._models),
            'ready_models': len(self.ready_models),
            'priced_models': len(self.priced_models),
            'free_models': len(self.free_models),
            'pending_models': len(self._pending),
            'categories': {
                cat: len(self.get_models_by_category(cat))
                for cat in set(m.get('category') for m in self._models.values())
            }
        }


# Singleton instance
_loader = None


def get_registry() -> KieRegistryLoader:
    """Получить singleton registry loader"""
    global _loader
    if _loader is None:
        _loader = KieRegistryLoader()
    return _loader


def load_all_models() -> Dict:
    """Загрузить все модели"""
    return get_registry().all_models


def load_ready_models() -> Dict:
    """Загрузить готовые модели (с endpoint + schema)"""
    return get_registry().ready_models


def load_free_models() -> Dict:
    """Загрузить бесплатные модели"""
    return get_registry().free_models


def get_model_by_id(model_id: str) -> Optional[Dict]:
    """Получить модель по ID"""
    return get_registry().get_model(model_id)


def get_cheapest_models(limit: int = 5) -> List[Dict]:
    """Получить N самых дешевых моделей"""
    return get_registry().get_cheapest_models(limit)


def get_model_registry() -> Dict:
    """
    LEGACY: Загрузить все модели (для обратной совместимости)
    Используйте load_all_models() вместо этого
    """
    return load_all_models()
