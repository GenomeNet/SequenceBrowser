from django.core.management.base import BaseCommand
from viewer.models import Genome, Sequence, Feature
from django.db import transaction

class Command(BaseCommand):
    help = 'Deletes all Genome, Sequence, and Feature entries from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force deletion without asking for confirmation',
        )

    def handle(self, *args, **options):
        force = options['force']

        if not force:
            confirm = input("Are you sure you want to delete all Genome, Sequence, and Feature entries? This action cannot be undone. (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return

        try:
            with transaction.atomic():
                feature_count = Feature.objects.count()
                sequence_count = Sequence.objects.count()
                genome_count = Genome.objects.count()

                Feature.objects.all().delete()
                Sequence.objects.all().delete()
                Genome.objects.all().delete()

                self.stdout.write(self.style.SUCCESS(f"Successfully deleted:"))
                self.stdout.write(f"  - {feature_count} Feature entries")
                self.stdout.write(f"  - {sequence_count} Sequence entries")
                self.stdout.write(f"  - {genome_count} Genome entries")

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"An error occurred while deleting entries: {str(e)}"))
