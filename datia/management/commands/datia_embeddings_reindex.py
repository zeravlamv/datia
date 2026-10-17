from django.core.management.base import BaseCommand
from datia.factories import ServiceFactory

class Command(BaseCommand):
    help = 'Re-indexes the schema terms into embeddings'

    def handle(self, *args, **options):
        svc = ServiceFactory.get_embedding_service()
        svc.index_schema()
        self.stdout.write(self.style.SUCCESS('Successfully re-indexed schema embeddings'))
