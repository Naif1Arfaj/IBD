"""Initialise an ephemeral hosted demo without printing login secrets."""
import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Migrate, seed synthetic patients and provision the hosted nurse login."

    def handle(self, *args, **options):
        password = os.environ.get("DEMO_NURSE_PASSWORD", "")
        if len(password) < 12:
            raise CommandError("Set DEMO_NURSE_PASSWORD to at least 12 characters.")
        call_command("migrate", interactive=False, verbosity=0)
        call_command("load_patients")
        user, _ = get_user_model().objects.get_or_create(
            username="nurse", defaults={"first_name": "Nurse"})
        if not user.check_password(password):
            user.set_password(password)
            user.save(update_fields=["password"])
        self.stdout.write(self.style.SUCCESS("Synthetic demo ready. Nurse login configured."))
