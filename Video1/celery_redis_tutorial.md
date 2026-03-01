# Celery + Redis + Django Tasks — Повний туторіал

---

## 1. Що таке Celery і навіщо він потрібен?

**Проблема без Celery:**
```
Юзер створює замовлення
      ↓
Django відправляє email (займає 2-3 секунди)
      ↓
Юзер чекає... чекає... чекає...
      ↓
Відповідь приходить через 3 секунди ❌
```

**З Celery:**
```
Юзер створює замовлення
      ↓
Django каже Celery: "відправ email потім"
      ↓
Юзер отримує відповідь МИТТЄВО ✅
      ↓
Celery відправляє email у фоні
```

---

## 2. Архітектура

```
Django (Producer)  →  Redis (Broker)  →  Celery Worker (Consumer)
     "виконай задачу"    "черга задач"      "виконую задачу"
```

- **Django** — створює задачі і кладе їх в чергу
- **Redis** — зберігає чергу задач (як поштова скринька)
- **Celery Worker** — бере задачі з черги і виконує їх

---

## 3. Встановлення

```bash
pip install celery redis django-redis
```

**docker-compose.yml** для Redis:
```yaml
services:
  redis:
    image: redis
    ports:
      - "6379:6379"
```

```bash
docker-compose up -d
```

---

## 4. Базовий Setup

### celery.py (поруч з settings.py)
```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

app = Celery('myproject')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ⚠️ Тільки для Windows розробки
app.conf.update(worker_pool='solo')
```

### __init__.py (в папці проєкту)
```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```

### settings.py
```python
CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/0"

# ⚠️ БЕЗ коми в кінці рядка — інакше стає tuple!
```

---

## 5. Перша задача

### api/tasks.py
```python
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def send_order_confirmation_email(order_id, user_email):
    """Відправка підтвердження замовлення"""
    subject = 'Підтвердження замовлення'
    message = f'Ваше замовлення #{order_id} прийнято!'
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user_email]
    )
    return f'Email відправлено на {user_email}'
```

### Виклик задачі у ViewSet
```python
from api.tasks import send_order_confirmation_email

class OrderViewSet(viewsets.ModelViewSet):
    
    def perform_create(self, serializer):
        order = serializer.save(user=self.request.user)
        
        # .delay() — асинхронний виклик (у фоні)
        send_order_confirmation_email.delay(
            str(order.order_id),
            self.request.user.email
        )
```

### Запуск Worker
```bash
# Linux/Mac
celery -A myproject worker --loglevel=INFO

# Windows
celery -A myproject worker --loglevel=INFO --pool=solo
```

---

## 6. Різні способи виклику задач

```python
# Асинхронно — одразу в чергу
send_email.delay(order_id, email)

# З затримкою — через 30 секунд
send_email.apply_async(
    args=[order_id, email],
    countdown=30
)

# В конкретний час
from datetime import datetime, timedelta
eta = datetime.utcnow() + timedelta(hours=1)
send_email.apply_async(args=[order_id, email], eta=eta)

# Синхронно (для тестів) — НЕ використовуй в продакшені
send_email.apply(args=[order_id, email])
```

---

## 7. Реальні приклади для твого проєкту

### 7.1 Email при зміні статусу замовлення
```python
# api/tasks.py
@shared_task
def notify_order_status_change(order_id, new_status, user_email):
    """Сповіщення при зміні статусу"""
    messages = {
        'Confirmed': 'Ваше замовлення підтверджено!',
        'Cancelled': 'На жаль, ваше замовлення скасовано.',
        'Pending': 'Ваше замовлення в обробці.',
    }
    
    message = messages.get(new_status, f'Статус змінено на {new_status}')
    
    send_mail(
        f'Замовлення #{order_id} — {new_status}',
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user_email]
    )

# api/views.py — виклик при оновленні
class OrderViewSet(viewsets.ModelViewSet):
    
    def perform_update(self, serializer):
        old_status = self.get_object().status
        order = serializer.save()
        
        if old_status != order.status:
            notify_order_status_change.delay(
                str(order.order_id),
                order.status,
                order.user.email
            )
```

### 7.2 Зменшення stock товару після замовлення
```python
@shared_task
def update_product_stock(order_id):
    """Оновлення залишків товару"""
    from api.models import Order
    
    order = Order.objects.prefetch_related('items__product').get(order_id=order_id)
    
    for item in order.items.all():
        product = item.product
        product.stock = max(0, product.stock - item.quantity)
        product.save(update_fields=['stock'])
    
    return f'Stock оновлено для замовлення {order_id}'

# Виклик:
def perform_create(self, serializer):
    order = serializer.save(user=self.request.user)
    update_product_stock.delay(str(order.order_id))
```

### 7.3 Генерація звіту (важка операція)
```python
@shared_task
def generate_sales_report(date_from, date_to, admin_email):
    """Генерація звіту продажів"""
    from api.models import Order
    from django.db.models import Sum, Count
    
    orders = Order.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
        status='Confirmed'
    )
    
    report_data = orders.aggregate(
        total_orders=Count('order_id'),
        total_revenue=Sum('items__product__price')
    )
    
    # Відправка звіту адміну
    send_mail(
        'Звіт продажів',
        f'Замовлень: {report_data["total_orders"]}\n'
        f'Дохід: {report_data["total_revenue"]}',
        settings.DEFAULT_FROM_EMAIL,
        [admin_email]
    )
```

---

## 8. Periodic Tasks (Розклад)

Для задач за розкладом потрібен **Celery Beat**.

### Встановлення
```bash
pip install django-celery-beat
```

### settings.py
```python
INSTALLED_APPS = [
    ...
    'django_celery_beat',
]
```

### Міграції
```bash
python manage.py migrate
```

### Налаштування розкладу
```python
# settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Щодня о 9:00 ранку
    'daily-sales-report': {
        'task': 'api.tasks.generate_sales_report',
        'schedule': crontab(hour=9, minute=0),
        'args': ['admin@site.com'],
    },
    
    # Кожні 30 хвилин
    'check-low-stock': {
        'task': 'api.tasks.check_low_stock_products',
        'schedule': crontab(minute='*/30'),
    },
    
    # Щопонеділка о 8:00
    'weekly-report': {
        'task': 'api.tasks.weekly_report',
        'schedule': crontab(hour=8, minute=0, day_of_week=1),
    },
}
```

### Запуск Beat (окремий процес)
```bash
celery -A myproject beat --loglevel=INFO
```

---

## 9. Retry (Повторна спроба при помилці)

```python
@shared_task(
    bind=True,
    max_retries=3,          # максимум 3 спроби
    default_retry_delay=60  # чекати 60 секунд між спробами
)
def send_order_confirmation_email(self, order_id, user_email):
    try:
        send_mail(...)
    except Exception as exc:
        # Повторна спроба при помилці
        raise self.retry(exc=exc)
```

---

## 10. Django Tasks Framework (Django 5.1+)

Django Tasks — це стандартний API для опису задач. Головна перевага — можна змінити "двигун" без переписування коду.

### Встановлення
```bash
pip install django-tasks
```

### settings.py
```python
# Розробка — без Redis, виконує одразу
TASKS = {
    "default": {
        "BACKEND": "django_tasks.backends.immediate.ImmediateBackend",
    }
}

# Продакшен — Celery як двигун
TASKS = {
    "default": {
        "BACKEND": "django_tasks.backends.celery.CeleryBackend",
    }
}
```

### Визначення задачі
```python
# api/tasks.py
from django.tasks import task

@task()
def send_order_confirmation_email(order_id: str, user_email: str):
    send_mail(...)
```

### Виклик задачі
```python
# Однаково працює з будь-яким бекендом!
send_order_confirmation_email.enqueue(str(order.order_id), user.email)
```

### Порівняння з Celery
```python
# Celery
send_email.delay(order_id, email)

# Django Tasks
send_email.enqueue(order_id, email)
```

---

## 11. Моніторинг з Flower

Flower — веб-інтерфейс для моніторингу Celery задач.

```bash
pip install flower
celery -A myproject flower --port=5555
```

Відкрий: http://localhost:5555

Показує:
- Активні задачі
- Виконані задачі
- Помилки
- Стан воркерів

---

## 12. Тестування задач

```python
# tests/test_tasks.py
from django.test import TestCase
from unittest.mock import patch
from api.tasks import send_order_confirmation_email


class TestOrderTasks(TestCase):
    
    # Виконує задачу синхронно в тестах
    @patch('django.core.mail.send_mail')
    def test_send_confirmation_email(self, mock_send_mail):
        send_order_confirmation_email.apply(
            args=['order-123', 'user@test.com']
        )
        
        mock_send_mail.assert_called_once()
        call_args = mock_send_mail.call_args
        assert 'order-123' in call_args[0][1]  # перевіряємо текст
```

---

## 13. Швидка шпаргалка

```bash
# Запуск Worker
celery -A myproject worker --loglevel=INFO          # Linux/Mac
celery -A myproject worker --loglevel=INFO --pool=solo  # Windows

# Запуск Beat (розклад)
celery -A myproject beat --loglevel=INFO

# Запуск Flower (моніторинг)
celery -A myproject flower --port=5555

# Перевірити стан
celery -A myproject inspect active
celery -A myproject inspect stats
```

---

## 14. Коли що використовувати

```
Email, SMS             → Celery task (.delay())
Важкі обчислення       → Celery task (.delay())
Щоденні звіти          → Celery Beat (розклад)
Очистка старих даних   → Celery Beat (розклад)
MVP без Redis          → Django Tasks (ImmediateBackend)
Продакшен              → Django Tasks + Celery Backend
```
