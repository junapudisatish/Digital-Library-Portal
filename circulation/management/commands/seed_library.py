from django.core.management.base import BaseCommand
from circulation.seed_data import populate_sample_data

class Command(BaseCommand):
    help = 'Safely seeds sample authors, books, members, and circulation records without duplicate or destructive wipes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Explicitly reset existing demo circulation records to fresh state'
        )

    def handle(self, *args, **options):
        force_reset = options.get('reset', False)
        count = populate_sample_data(force_reset=force_reset)
        mode = "with fresh demo circulation records" if force_reset else "safely preserving existing records"
        self.stdout.write(self.style.SUCCESS(f'Successfully populated {count} books {mode}!'))
