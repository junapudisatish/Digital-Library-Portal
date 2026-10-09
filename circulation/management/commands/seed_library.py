from django.core.management.base import BaseCommand
from circulation.seed_data import populate_sample_data

class Command(BaseCommand):
    help = 'Seeds sample authors, books, members, and circulation records'

    def handle(self, *args, **options):
        count = populate_sample_data()
        self.stdout.write(self.style.SUCCESS(f'Successfully populated {count} books with circulation records!'))
