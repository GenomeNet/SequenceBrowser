from django.core.management.base import BaseCommand
from viewer.models import Interaction

class Command(BaseCommand):
    help = 'Delete all Interaction records from the database.'

    def handle(self, *args, **options):
        count = Interaction.objects.count()
        if count == 0:
            self.stdout.write(self.style.WARNING('No interactions found to delete.'))
        else:
            Interaction.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} interactions.'))