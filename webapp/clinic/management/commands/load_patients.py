import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from features import FEATURES, load_raw

from clinic.models import Patient


def _py(v):
    return v.item() if hasattr(v, "item") else v


class Command(BaseCommand):
    help = "Load the 2,500 synthetic patients from Saudi_IBD_Synthetic.xlsx (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--demo-user", action="store_true", help="Create/reset the 'nurse' demo login.")
        parser.add_argument("--password", help="Password for the demo user (random if omitted).")

    def handle(self, *args, **opts):
        raw = load_raw()
        existing = set(Patient.objects.values_list("patient_code", flat=True))
        new = [Patient(patient_code=r["patient_id"], source="synthetic",
                       data={f: _py(r[f]) for f in FEATURES}, synthetic_label=int(r["synthetic_IBD_outcome"]))
               for _, r in raw.iterrows() if r["patient_id"] not in existing]
        with transaction.atomic():
            Patient.objects.bulk_create(new, batch_size=500)
        self.stdout.write(self.style.SUCCESS(f"Loaded {len(new)} new patients ({Patient.objects.count()} total)."))

        if opts["demo_user"]:
            pw = opts["password"] or secrets.token_urlsafe(9)
            User = get_user_model()
            u, _ = User.objects.get_or_create(username="nurse", defaults={"first_name": "Nurse"})
            u.set_password(pw)
            u.first_name = "Nurse"
            u.save()
            self.stdout.write(self.style.SUCCESS(f"Demo login → username: nurse   password: {pw}"))
