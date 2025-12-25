# 🎯 KIE.AI MODELS - ПОЛНАЯ БАЗА ДАННЫХ

## Статус проекта

**Всего моделей**: 9  
**Источник**: Официальная API документация kie.ai  
**Дата обновления**: 24.12.2024  
**Коммиты**: 7c1fa86, 5a4241b  

---

## 📊 Модели по категориям

### 💰 САМЫЕ ДЕШЕВЫЕ (до 5₽)

| Модель | Цена | Категория | Что делает |
|--------|------|-----------|------------|
| **grok-imagine/upscale** | 3.56₽ | Image | Upscale Kie-generated images (requires task_id) |
| **seedream/4.5-text-to-image** | 3.56₽ | Image | Text → Image (2K basic, 4K high quality) |

**ИТОГО: 2 модели, средняя цена 3.56₽**

---

### 🖼️ БЮДЖЕТНЫЕ IMAGE МОДЕЛИ (5-15₽)

| Модель | Цена | Что делает |
|--------|------|------------|
| **nano-banana-pro** | 12.83₽ | Google's Nano Banana Pro (1K/2K/4K, up to 8 reference images) |
| **grok-imagine/text-to-image** | 14.25₽ | Grok Text → Image (aspect ratios: 1:1, 2:3, 3:2) |

**ИТОГО: 2 модели, средняя цена 13.54₽**

---

### 🎬 БЮДЖЕТНЫЕ VIDEO МОДЕЛИ (до 50₽)

| Модель | Цена | Что делает |
|--------|------|------------|
| **grok-imagine/text-to-video** | 14.25₽ | Grok Text → Video (modes: fun, normal, spicy) |
| **grok-imagine/image-to-video** | 14.25₽ | Grok Image → Video (external URLs + Kie task_id) |
| **wan/2-6-image-to-video** | 42.75₽ | Wan 2.6 Image → Video (5s/10s/15s, 720p/1080p) |
| **wan/2-6-video-to-video** | 42.75₽ | Wan 2.6 Video → Video (5s/10s, transformations) |
| **wan/2-6-text-to-video** | 49.88₽ | Wan 2.6 Text → Video (5s/10s/15s, multi-shot) |

**ИТОГО: 5 моделей, средняя цена 32.82₽**

---

## 💰 Полная таблица цен

| # | Модель | Наша цена | KIE цена | Категория | Provider |
|---|--------|-----------|----------|-----------|----------|
| 1 | grok-imagine/upscale | 3.56₽ | 2.38₽ | Image | Grok |
| 2 | seedream/4.5-text-to-image (basic) | 3.56₽ | 2.38₽ | Image | Seedream |
| 3 | seedream/4.5-text-to-image (high) | 7.13₽ | 4.75₽ | Image | Seedream |
| 4 | nano-banana-pro (1K/2K) | 12.83₽ | 8.55₽ | Image | Google |
| 5 | grok-imagine/text-to-image | 14.25₽ | 9.50₽ | Image | Grok |
| 6 | grok-imagine/text-to-video | 14.25₽ | 9.50₽ | Video | Grok |
| 7 | grok-imagine/image-to-video | 14.25₽ | 9.50₽ | Video | Grok |
| 8 | nano-banana-pro (4K) | 17.10₽ | 11.40₽ | Image | Google |
| 9 | wan/2-6-image-to-video (5s) | 42.75₽ | 28.50₽ | Video | Wan |
| 10 | wan/2-6-video-to-video (5s) | 42.75₽ | 28.50₽ | Video | Wan |
| 11 | wan/2-6-text-to-video (5s) | 49.88₽ | 33.25₽ | Video | Wan |
| 12 | wan/2-6-image-to-video (10s) | 85.50₽ | 57.00₽ | Video | Wan |
| 13 | wan/2-6-video-to-video (10s) | 85.50₽ | 57.00₽ | Video | Wan |
| 14 | wan/2-6-text-to-video (10s) | 99.75₽ | 66.50₽ | Video | Wan |
| 15 | wan/2-6-image-to-video (15s) | 128.25₽ | 85.50₽ | Video | Wan |
| 16 | wan/2-6-text-to-video (15s) | 149.63₽ | 99.75₽ | Video | Wan |

**Наша наценка**: 50% от KIE цены  
**Курс**: 95 RUB/USD (примерно)

---

## 🧪 Тестирование

### Готовые тесты:

1. **tests/test_kie_grok_nano.py** - Grok & Nano Banana (100₽ budget)
   ```bash
   export KIE_API_KEY=sk-your-key
   python tests/test_kie_grok_nano.py
   ```
   Стоимость: ~55₽ (4 теста)

2. **tests/test_kie_wan_seedream.py** - Wan 2.6 & Seedream 4.5 (100₽ budget)
   ```bash
   python tests/test_kie_wan_seedream.py
   ```
   Стоимость: ~96₽ (3 теста)

**TOTAL**: ~151₽ для всех тестов (в рамках разумного!)

---

## 📝 Примеры использования

### 1. Самая дешевая картинка (3.56₽)

```python
from app.kie.generator import KieGenerator

generator = KieGenerator()
result = await generator.generate(
    model_id='seedream/4.5-text-to-image',
    user_inputs={
        'prompt': 'A beautiful sunset over mountains',
        'aspect_ratio': '16:9',
        'quality': 'basic'  # 2K
    },
    timeout=180
)
```

### 2. Upscale для улучшения (3.56₽)

```python
result = await generator.generate(
    model_id='grok-imagine/upscale',
    user_inputs={
        'task_id': 'previous_task_id_from_grok'
    },
    timeout=120
)
```

### 3. Wan 2.6 Video (49.88₽)

```python
result = await generator.generate(
    model_id='wan/2-6-text-to-video',
    user_inputs={
        'prompt': 'A cat playing with a ball of yarn',
        'duration': '5',  # 5s, 10s, or 15s
        'resolution': '1080p',  # 720p or 1080p
        'multi_shots': False
    },
    timeout=300
)
```

---

## 🚀 Деплой

### Текущее состояние:

- ✅ 9 моделей в коде
- ✅ Все payloads строятся правильно
- ⏳ Production показывает 22 старые модели
- ⏳ Нужен deploy новых моделей

### Чтобы задеплоить:

```bash
git push origin main
```

Render автоматически подхватит изменения и обновит production.

---

## 📊 Статистика

| Метрика | Значение |
|---------|----------|
| Всего моделей | 9 |
| Самая дешевая | 3.56₽ (2 модели) |
| Самая дорогая | 149.63₽ (wan/2-6 text 15s) |
| Средняя цена | ~32₽ |
| Image модели | 4 |
| Video модели | 5 |
| Providers | 4 (Grok, Google, Wan, Seedream) |

---

## 🎯 Следующие шаги

1. ✅ Grok модели добавлены (commit 7c1fa86)
2. ✅ Wan 2.6 + Seedream добавлены (commit 5a4241b)
3. ⏳ **Получить API ключ и протестировать**
4. ⏳ **Deploy на production**
5. ⏳ Добавить остальные ~213 моделей из kie.ai/pricing
6. ⏳ Обновить бот UI для показа всех моделей

---

## 📞 Контакты

- Repo: ferixdi-png/5656
- Branch: main
- Latest commits: 7c1fa86, 5a4241b
- Production: https://five656.onrender.com
