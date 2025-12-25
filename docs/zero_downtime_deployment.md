# Zero-Downtime Deployment - Technical Implementation

## Проблема

При деплое на Render происходила ситуация race condition:

1. **Старая версия** бота работает, держит PostgreSQL advisory lock
2. **Render запускает новый контейнер** (rolling deployment)
3. **Новый контейнер** пытается захватить lock → **FAIL**
4. **Новый контейнер** переходит в passive mode (только healthcheck)
5. **Старая версия** завершается через 10-30 секунд
6. Lock освобождается, но **новый контейнер уже в passive mode**

Результат:
```
⚠️ Singleton lock NOT acquired - another instance is active
Running in passive mode (healthcheck only)
```

## Решение

### 1. Немедленное освобождение lock при SIGTERM

**Файл**: `main_render.py`

**Изменения**:
- Добавлен `singleton_lock_ref` — shared reference для доступа из signal handler
- Signal handler **сразу** вызывает `lock.release()` при получении SIGTERM
- Используется `asyncio.create_task()` для асинхронного освобождения без блокировки

**Код**:
```python
singleton_lock_ref = {"lock": None}  # Shared reference

def signal_handler(sig):
    logger.info(f"Received signal {sig}, initiating graceful shutdown...")
    shutdown_event.set()
    
    # CRITICAL: Release lock IMMEDIATELY
    if singleton_lock_ref["lock"] and singleton_lock_ref["lock"]._acquired:
        logger.info("⚡ Releasing singleton lock immediately for new instance...")
        asyncio.create_task(_emergency_lock_release(singleton_lock_ref["lock"]))

async def _emergency_lock_release(lock):
    """Emergency lock release - allows zero-downtime deployment."""
    try:
        await lock.release()
        logger.info("✅ Lock released successfully on shutdown signal")
    except Exception as e:
        logger.error(f"Error during emergency lock release: {e}", exc_info=True)
```

**Сохранение reference**:
```python
singleton_lock = SingletonLock(dsn=database_url, instance_name=instance_name)
singleton_lock_ref["lock"] = singleton_lock  # Store for signal handler
```

### 2. Улучшенное логирование в SingletonLock

**Файл**: `app/locking/single_instance.py`

**Изменения** в методе `release()`:
- Подробное логирование каждого шага
- Отображение результатов `pg_advisory_unlock()` и `DELETE`
- Явное сообщение "new instance can acquire"

**Логи при graceful shutdown**:
```
🔓 Starting lock release for bot-instance-xyz...
Heartbeat task cancelled successfully
Advisory lock released: True
Heartbeat record removed (rows affected: DELETE 1)
✅ Singleton lock fully released by bot-instance-xyz - new instance can acquire
Database connection closed
```

### 3. Конфигурация Render для graceful shutdown

**Файл**: `render.yaml`

**Добавлено**:
```yaml
# Health check для zero-downtime deployment
healthCheckPath: /health

# Graceful shutdown configuration
preDeployCommand: echo "Starting zero-downtime deployment..."

# Даем 30 секунд старому контейнеру на освобождение lock
maxShutdownDelaySeconds: 30
```

**Как это работает**:
1. Render отправляет SIGTERM старому контейнеру
2. Старый контейнер **сразу** освобождает lock (< 1 сек)
3. Render ждет до 30 секунд перед force kill
4. Новый контейнер успевает захватить lock **до** завершения старого
5. **Zero downtime** — оба контейнера работают параллельно секунды

## Timeline сравнение

### ❌ V1 (race condition - было):
```
0s   - Новый контейнер стартует
1s   - Новый пытается захватить lock → FAIL
2s   - Новый → passive mode
10s  - Render отправляет SIGTERM старому
15s  - Старый начинает shutdown
20s  - Старый освобождает lock в finally
21s  - Новый все еще в passive mode (НЕ РАБОТАЕТ)
```

### ✅ V2 (emergency release - было):
```
0s   - Новый контейнер стартует
5s   - Render отправляет SIGTERM старому
5.1s - Старый СРАЗУ освобождает lock
5.2s - Новый захватывает lock → active mode ✅
5.3s - Новый начинает polling
10s  - Старый завершает cleanup, умирает
```

**Проблема V2**: Render запускал новый контейнер **до** SIGTERM старому!

### ✅ V3 (AGGRESSIVE RETRY - текущее):
```
0s   - Новый контейнер стартует
0.5s - Попытка 1: lock NOT acquired (старый ещё работает)
2.5s - Попытка 2: Render отправил SIGTERM старому
2.6s - Старый СРАЗУ освобождает lock
2.7s - Попытка 2: lock acquired → active mode ✅
3s   - Новый начинает polling
7s   - Старый завершает cleanup
```

**Результат**: Lock захвачен на попытке 2-3, zero downtime!

## Гарантии безопасности

1. **Lock ВСЕГДА освобождается** при SIGTERM:
   - Emergency release в signal handler
   - Fallback release в finally блоке
   - Двойная защита от deadlock

2. **Heartbeat прекращается сразу**:
   - `_acquired = False` → heartbeat loop завершается
   - Task отменяется явно: `task.cancel()`

3. **Advisory lock в PostgreSQL**:
   - Автоматически освобождается при закрытии соединения
   - Не блокирует другие операции БД
   - TTL-based stale detection (60s)

4. **Idempotent operations**:
   - `release()` можно вызвать многократно
   - Проверка `if not self._acquired: return`
   - Безопасно для emergency + finally scenarios

## Проверка в production

После деплоя смотрим логи Render:

**Ожидаемые логи (успех)**:
```
[OLD] Received signal 15, initiating graceful shutdown...
[OLD] ⚡ Releasing singleton lock immediately for new instance...
[OLD] 🔓 Starting lock release for bot-instance-old...
[OLD] ✅ Singleton lock fully released - new instance can acquire

[NEW] Starting bot application...
[NEW] ✅ Singleton lock acquired by bot-instance-new
[NEW] Singleton lock acquired successfully - running in active mode
[NEW] Starting bot polling...

[OLD] Bot shutdown complete
```

**Недопустимые логи (проблема)**:
```
⚠️ Singleton lock NOT acquired - another instance is active
Running in passive mode (healthcheck only)
```

Если появляется passive mode — значит проблема с timing или конфигурацией Render.

## Rollback план

Если что-то пошло не так:

1. **Проверить ENV переменные в Render**:
   - `DATABASE_URL` установлен?
   - `DRY_RUN` НЕ установлен?

2. **Проверить логи БД**:
   ```sql
   SELECT * FROM singleton_heartbeat;
   SELECT pg_advisory_lock_held(12345);
   ```

3. **Force release lock вручную**:
   ```sql
   DELETE FROM singleton_heartbeat WHERE lock_id = 12345;
   SELECT pg_advisory_unlock_all();
   ```

4. **Restart сервиса в Render**:
   - Manual Deploy → Clear Build Cache
   - Redeploy текущей версии

## Мониторинг

**Метрики для отслеживания**:
1. Время между SIGTERM и lock release (< 1s)
2. Количество passive mode instances (должно быть 0)
3. Количество stale lock cleanups (должно быть 0)

**Алерты**:
- Если новый контейнер в passive mode > 5 минут → **CRITICAL**
- Если stale lock cleanup > 1 раз в час → **WARNING**

## Дальнейшие улучшения

1. **Metrics export**: Prometheus metrics для lock acquisition time
2. **Distributed lock**: Redis-based lock как альтернатива PostgreSQL
3. **Blue-green deployment**: Полная изоляция старой/новой версии
4. **Canary releases**: Постепенный переход трафика на новую версию

---

**Статус**: ✅ Production-ready
**Автор**: Implemented as part of zero-downtime deployment strategy
**Дата**: 2025-12-23
