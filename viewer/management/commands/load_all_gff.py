import os
from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Loads all .gff files from ../datasets/merged_gff3/ using the load_data command'

    def handle(self, *args, **options):
        # Set the directory path
        gff_directory = "../datasets/merged_gff3/"

        # Iterate through all files in the directory
        for filename in os.listdir(gff_directory):
            if filename.endswith(".gff"):
                file_path = os.path.join(gff_directory, filename)
                
                self.stdout.write(self.style.SUCCESS(f"Processing: {filename}"))
                
                # Call the load_data command
                call_command('load_data', file_path, force=True)
                
                self.stdout.write(self.style.SUCCESS(f"Finished processing: {filename}\n"))

        self.stdout.write(self.style.SUCCESS("All .gff files have been processed."))