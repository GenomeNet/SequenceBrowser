import random
from django.core.management.base import BaseCommand, CommandError
from viewer.models import Sequence, NucleotideData

class Command(BaseCommand):
    help = 'Load dummy nucleotide data for a specified contig or for all contigs.'

    def add_arguments(self, parser):
        parser.add_argument(
            'contig',
            nargs='?',
            type=str,
            help='Contig name of the sequence to load data for.'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Load dummy nucleotide data for all sequences.'
        )
        parser.add_argument(
            '--seed',
            type=int,
            help='Seed for random number generator (optional).'
        )
        parser.add_argument(
            '--data_source',
            type=str,
            default='dummy',
            help='Name of the data source to assign to nucleotide data.'
        )

    def handle(self, *args, **options):
        seed = options.get('seed')
        data_source = options.get('data_source')

        if seed is not None:
            random.seed(seed)
            self.stdout.write(self.style.WARNING(f'Random seed set to {seed}'))

        sequences = []
        if options['all']:
            sequences = Sequence.objects.all()
            if not sequences.exists():
                raise CommandError('No sequences found in the database.')
            self.stdout.write(f'Loading dummy data for all {sequences.count()} sequences.')
        else:
            contig = options.get('contig')
            if not contig:
                raise CommandError('Please provide a contig name or use --all to load data for all sequences.')
            try:
                sequence = Sequence.objects.get(contig=contig)
                sequences = [sequence]
            except Sequence.DoesNotExist:
                raise CommandError(f'Sequence with contig "{contig}" does not exist.')

        for sequence in sequences:
            sequence_length = len(sequence.sequence)
            self.stdout.write(f'\nLoading dummy data for sequence "{sequence.contig}" with length {sequence_length}.')

            # Fetch existing nucleotide data to avoid duplicates
            existing_positions = set(
                NucleotideData.objects.filter(sequence=sequence).values_list('position', flat=True)
            )
            self.stdout.write(f'Found {len(existing_positions)} existing nucleotide data entries.')

            # Create dummy data for positions without existing data
            nucleotide_data_bulk = []
            for pos in range(1, sequence_length + 1):
                if pos in existing_positions:
                    continue  # Skip positions that already have data

                value = round(random.uniform(-1, 1), 4)  # Random float between -1 and 1
                nucleotide_data_bulk.append(NucleotideData(
                    sequence=sequence,
                    position=pos,
                    data_source=data_source,
                    value=value
                ))

                # Bulk create in batches to optimize performance
                if len(nucleotide_data_bulk) >= 10000:
                    NucleotideData.objects.bulk_create(nucleotide_data_bulk)
                    nucleotide_data_bulk = []
                    self.stdout.write(f'  - Loaded data up to position {pos}.')

            # Create any remaining data
            if nucleotide_data_bulk:
                NucleotideData.objects.bulk_create(nucleotide_data_bulk)
                self.stdout.write(f'  - Loaded data up to position {sequence_length}.')

            self.stdout.write(self.style.SUCCESS(f'Dummy nucleotide data loading completed for "{sequence.contig}".'))