from django.apps import AppConfig


class PlaneLazyBirdConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plane_lazy_bird"
    verbose_name = "Lazy-Bird Automation"

    def ready(self) -> None:
        import plane_lazy_bird.signals  # noqa: F401
