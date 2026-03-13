from celery import shared_task

from django.core.cache import cache
from django.db.models import F

from .models import Story


@shared_task()
def persist_story_views():
    keys = cache.iter_keys("story:*:views")

    for key in keys:
        guid = key.split(":")[1]
        count = cache.get(key)
        if not count:  # if  skip
            continue

        story = Story.objects.filter(guid=guid).update(
            views=F("views") + int(count),
        )

        if story:
            cache.delete(key)
