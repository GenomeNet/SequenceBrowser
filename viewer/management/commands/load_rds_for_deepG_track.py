import os
import re
import pyreadr
from tqdm import tqdm
from django.core.management.base import BaseCommand, CommandError
from viewer.models import Genome, Sequence, NucleotideData

class Command(BaseCommand):
    help = 'Load nucleotide data from .rds files into the database for deepG track.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--folder',
            type=str,
            required=True,
            help='Folder containing .rds files.'
        )
        parser.add_argument(
            '--data_source',
            type=str,
            default='deepG',
            help='Name of the data source to assign to nucleotide data.'
        )
        parser.add_argument(
            '--dry_run',
            action='store_true',
            help='Perform a dry run without modifying the database.'
        )

    def handle(self, *args, **options):
        folder = options['folder']
        data_source = options['data_source']
        dry_run = options['dry_run']

        if not os.path.isdir(folder):
            raise CommandError(f'The folder "{folder}" does not exist or is not a directory.')

        # Get list of .rds files in the folder
        rds_files = [f for f in os.listdir(folder) if f.endswith('.rds')]
        if not rds_files:
            raise CommandError(f'No .rds files found in the folder "{folder}".')

        self.stdout.write(f'Found {len(rds_files)} .rds files in the folder.')

        for filename in tqdm(rds_files, desc='Processing files'):
            file_path = os.path.join(folder, filename)
            
            # Extract genome name and contig index from the filename
            # Example filename: 'GCA_012932375.1_ASM1293237v1_genomic_1.rds'
            match = re.match(r'^(.*?_genomic)_(\d+)\.rds$', filename)
            if not match:
                self.stdout.write(self.style.WARNING(
                    f'Skipping file "{filename}" - filename does not match expected pattern.'
                ))
                continue

            genome_name = match.group(1)
            contig_index = int(match.group(2))

            try:
                # Fetch the Genome object based on genome_name
                genome = Genome.objects.get(name=genome_name)
            except Genome.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'No Genome found with name "{genome_name}" for file "{filename}". Skipping.'
                ))
                continue

            # Find sequences where genome matches and contig ends with '_[contig_index]'
            sequences = Sequence.objects.filter(
                genome=genome,
                contig__endswith=f'_{contig_index}'
            )
            if not sequences.exists():
                self.stdout.write(self.style.WARNING(
                    f'No sequences found for genome "{genome_name}" and contig index {contig_index} in file "{filename}".'
                ))
                continue

            if sequences.count() > 1:
                self.stdout.write(self.style.WARNING(
                    f'Multiple sequences found for genome "{genome_name}" and contig index {contig_index} in file "{filename}". Using the first one.'
                ))

            sequence = sequences.first()
            sequence_length = len(sequence.sequence)
            self.stdout.write(
                f'Processing sequence "{sequence.contig}" from file "{filename}" with length {sequence_length}.'
            )

            # Read .rds file using pyreadr
            try:
                result = pyreadr.read_r(file_path)
                # Assuming the data frame is the first object in the .rds file
                df = next(iter(result.values()))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error reading file "{filename}": {e}'))
                continue

            # Ensure the data frame has 'position' and 'pred' columns
            if 'position' not in df.columns or 'pred' not in df.columns:
                self.stdout.write(self.style.WARNING(
                    f'File "{filename}" does not contain required columns "position" and "pred".'
                ))
                continue

            # Fetch existing nucleotide data for this sequence and data source
            existing_positions = set(
                NucleotideData.objects.filter(sequence=sequence, data_source=data_source)
                .values_list('position', flat=True)
            )
            self.stdout.write(
                f'Found {len(existing_positions)} existing nucleotide data entries for data_source "{data_source}".'
            )

            # Prepare NucleotideData objects
            nucleotide_data_bulk = []
            for _, row in df.iterrows():
                position = int(row['position'])
                value = float(row['pred'])
                if position in existing_positions:
                    continue  # Skip positions that already have data for this data_source
                if position > sequence_length:
                    self.stdout.write(self.style.WARNING(
                        f'Position {position} exceeds sequence length {sequence_length} in file "{filename}". Skipping.'
                    ))
                    continue

                nucleotide_data_bulk.append(NucleotideData(
                    sequence=sequence,
                    position=position,
                    data_source=data_source,
                    value=value
                ))

                # Bulk create in batches to optimize performance
                if len(nucleotide_data_bulk) >= 10000:
                    if not dry_run:
                        NucleotideData.objects.bulk_create(nucleotide_data_bulk)
                    nucleotide_data_bulk = []
                    self.stdout.write(
                        f'  - Loaded data up to position {position} for data_source "{data_source}".'
                    )

            # Create any remaining data
            if nucleotide_data_bulk:
                if not dry_run:
                    NucleotideData.objects.bulk_create(nucleotide_data_bulk)
                self.stdout.write(
                    f'  - Loaded data up to position {position} for data_source "{data_source}".'
                )

            self.stdout.write(self.style.SUCCESS(
                f'Data loading completed for sequence "{sequence.contig}" from file "{filename}".'
            ))