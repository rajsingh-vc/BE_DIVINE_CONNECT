import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

# Read CELERY_* settings from Django settings.py (namespaced with CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in each installed app (picks up volunteers/tasks.py)
app.autodiscover_tasks()