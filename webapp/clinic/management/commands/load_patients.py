import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from features import FEATURES, OPTIONAL, json_value, load_raw

from clinic.models import Patient


class Command(BaseCommand):
    help = "Load the 2,500 synthetic patients from Saudi_IBD_Synthetic.xlsx (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--demo-user", action="store_true", help="Create/reset the 'nurse' demo login.")
        parser.add_argument("--password", help="Password for the demo user (random if omitted).")

    def handle(self, *args, **opts):
        raw = load_raw()
        existing = set(Patient.objects.values_list("patient_code", flat=True))
        new = [Patient(patient_code=r["patient_id"], source="synthetic",
                       data={f: json_value(r[f]) for f in FEATURES}, synthetic_label=int(r["synthetic_IBD_outcome"]))
               for _, r in raw.iterrows() if r["patient_id"] not in existing]
        # Records saved before the signs-and-symptoms update gain the dataset's new values. Only absent keys are
        # added, so nothing recorded or edited is overwritten.
        rows = raw.set_index("patient_id")
        backfilled = []
        for p in Patient.objects.filter(source="synthetic", patient_code__in=rows.index):
            absent = [f for f in OPTIONAL if f not in p.data]
            if absent:
                p.data = {**p.data, **{f: json_value(rows.at[p.patient_code, f]) for f in absent}}
                backfilled.append(p)
        with transaction.atomic():
            Patient.objects.bulk_create(new, batch_size=500)
            Patient.objects.bulk_update(backfilled, ["data"], batch_size=500)
        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(new)} new patients ({Patient.objects.count()} total); added symptoms to {len(backfilled)}."))

        if opts["demo_user"]:
            pw = opts["password"] or secrets.token_urlsafe(9)
            User = get_user_model()
            u, _ = User.objects.get_or_create(username="nurse", defaults={"first_name": "Nurse"})
            u.set_password(pw)
            u.first_name = "Nurse"
            u.save()
            self.stdout.write(self.style.SUCCESS(f"Demo login → username: nurse   password: {pw}"))
