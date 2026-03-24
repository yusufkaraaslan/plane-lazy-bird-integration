"""Management command to register a webhook subscription in Lazy-Bird."""

import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from plane_lazy_bird.client import LazyBirdClient


class Command(BaseCommand):
    help = "Register a webhook subscription in Lazy-Bird for receiving task events"

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            type=str,
            help="Public URL for the webhook endpoint (e.g. https://plane.example.com/api/webhooks/lazy-bird/)",
        )
        parser.add_argument(
            "--events",
            nargs="+",
            default=["task.started", "task.completed", "task.failed", "task.cancelled", "pr.created"],
            help="Event types to subscribe to",
        )

    def handle(self, *args, **options):
        webhook_url = options["url"]
        if not webhook_url:
            raise CommandError(
                "Please provide the public webhook URL with --url. "
                "Example: --url https://plane.example.com/api/webhooks/lazy-bird/"
            )

        secret = getattr(settings, "LAZY_BIRD_WEBHOOK_SECRET", "")
        if not secret:
            raise CommandError("LAZY_BIRD_WEBHOOK_SECRET is not configured in Django settings.")

        client = LazyBirdClient()
        events = options["events"]

        self.stdout.write(f"Registering webhook: {webhook_url}")
        self.stdout.write(f"Events: {', '.join(events)}")

        try:
            result = asyncio.run(
                client.register_webhook(
                    url=webhook_url,
                    secret=secret,
                    events=events,
                    description="Plane integration webhook",
                )
            )
        except Exception as e:
            raise CommandError(f"Failed to register webhook: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Webhook registered successfully! ID: {result.get('id')}"
        ))
