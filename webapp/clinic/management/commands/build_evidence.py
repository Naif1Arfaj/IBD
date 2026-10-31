from django.core.management.base import BaseCommand

from features import FEATURES, NO_NARRATE
from rag import llm

from clinic.services import cached_feature_evidence


class Command(BaseCommand):
    help = ("Pre-generate the literature summary for every narratable variable (both directions). "
            "With an API key this calls Claude once per item (~$0.03 each); without one it caches passages.")

    def add_arguments(self, parser):
        parser.add_argument("--features", nargs="*", help="Only these variables.")

    def handle(self, *args, **opts):
        feats = [f for f in (opts["features"] or FEATURES) if f not in NO_NARRATE]
        mode = "Claude" if llm.available() else "offline passages"
        self.stdout.write(f"Building evidence for {len(feats)} variables × 2 directions ({mode}) …")
        for f in feats:
            for d in ("raises", "lowers"):
                r = cached_feature_evidence(f, d)
                self.stdout.write(f"  {f:40s} {d:7s} {'LLM' if r['llm_used'] else 'passages'} · {len(r['references'])} refs")
        self.stdout.write(self.style.SUCCESS("Done."))
