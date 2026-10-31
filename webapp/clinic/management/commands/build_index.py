from django.core.management.base import BaseCommand

from rag.index import build


class Command(BaseCommand):
    help = "Extract, chunk and embed the research PDFs in 'Full text article/' into rag_index/."

    def handle(self, *args, **opts):
        r = build(log=self.stdout.write)
        self.stdout.write(self.style.SUCCESS(f"Indexed {r['documents']} papers → {r['chunks']} passages."))
        for f in r["failed"]:
            self.stdout.write(self.style.WARNING(f"  skipped {f['file']}: {f['error']}"))
