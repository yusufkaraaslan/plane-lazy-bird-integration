from django.urls import path

from plane_lazy_bird.webhooks import lazy_bird_webhook

app_name = "plane_lazy_bird"

urlpatterns = [
    path("lazy-bird/", lazy_bird_webhook, name="lazy_bird_webhook"),
]
