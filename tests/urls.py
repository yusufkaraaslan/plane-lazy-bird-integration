from django.urls import include, path

urlpatterns = [
    path("api/webhooks/", include("plane_lazy_bird.urls")),
]
