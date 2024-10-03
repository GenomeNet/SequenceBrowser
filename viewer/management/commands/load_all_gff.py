import os
import random
from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Loads a subset of .gff files from ../datasets/merged_gff3/ using the load_data command'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of GFF files to process (randomly selected)'
        )

    def handle(self, *args, **options):
        # Set the directory path
        gff_directory = "../datasets/merged_gff3/"
        limit = options['limit']

        # Get all .gff files
        gff_files = [f for f in os.listdir(gff_directory) if f.endswith(".gff")]

        # If limit is set and less than total files, randomly select subset
        if limit and limit < len(gff_files):
            gff_files = random.sample(gff_files, limit)
            self.stdout.write(self.style.SUCCESS(f"Randomly selected {limit} files to process."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Processing all {len(gff_files)} files."))

        # Process the selected files
        for filename in gff_files:
            file_path = os.path.join(gff_directory, filename)
            
            self.stdout.write(self.style.SUCCESS(f"Processing: {filename}"))
            
            # Call the load_data command
            call_command('load_data', file_path, force=True)
            
            self.stdout.write(self.style.SUCCESS(f"Finished processing: {filename}\n"))

        self.stdout.write(self.style.SUCCESS("All selected .gff files have been processed."))