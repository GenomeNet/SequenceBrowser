from django.core.management.base import BaseCommand, CommandError
from viewer.models import Sequence, Interaction
import random

class Command(BaseCommand):
    help = 'Generate refined dummy interactions between nucleotides for sequences.'

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
            help='Generate dummy interactions for all sequences.'
        )
        parser.add_argument(
            '--seed',
            type=int,
            help='Seed for random number generator (optional).'
        )
        parser.add_argument(
            '--min_step',
            type=int,
            default=100,
            help='Minimum step size in nucleotides between interaction sites.'
        )
        parser.add_argument(
            '--max_step',
            type=int,
            default=500,
            help='Maximum step size in nucleotides between interaction sites.'
        )
        parser.add_argument(
            '--num_interactions_per_site',
            type=int,
            default=5,
            help='Number of dummy interactions per selected nucleotide site.'
        )
        parser.add_argument(
            '--range',
            type=int,
            default=50,
            help='Range in nucleotides (+/-) for potential interaction partners.'
        )
        parser.add_argument(
            '--intensity_distribution',
            type=str,
            choices=['uniform', 'weighted'],
            default='weighted',
            help='Distribution type for interaction weights.'
        )

    def handle(self, *args, **options):
        seed = options.get('seed')
        min_step = options.get('min_step')
        max_step = options.get('max_step')
        num_interactions_per_site = options.get('num_interactions_per_site')
        interaction_range = options.get('range')
        intensity_distribution = options.get('intensity_distribution')

        if seed is not None:
            random.seed(seed)
            self.stdout.write(self.style.WARNING(f'Random seed set to {seed}'))

        sequences = []
        if options['all']:
            sequences = Sequence.objects.all()
            if not sequences.exists():
                raise CommandError('No sequences found in the database.')
            self.stdout.write(f'Generating dummy interactions for all {sequences.count()} sequences.')
        else:
            contig = options.get('contig')
            if not contig:
                raise CommandError('Please provide a contig name or use --all to generate data for all sequences.')
            try:
                sequence = Sequence.objects.get(contig=contig)
                sequences = [sequence]
            except Sequence.DoesNotExist:
                raise CommandError(f'Sequence with contig "{contig}" does not exist.')

        for sequence in sequences:
            sequence_length = len(sequence.sequence)
            self.stdout.write(f'\nGenerating dummy interactions for sequence "{sequence.contig}" with length {sequence_length}.')

            interactions_bulk = []

            # Initialize the first site
            current_site = random.randint(1, max_step)

            while current_site <= sequence_length:
                # Define the range for potential interaction partners
                min_pos = max(1, current_site - interaction_range)
                max_pos = min(sequence_length, current_site + interaction_range)

                # Exclude the current site to prevent self-interaction
                potential_partners = list(range(min_pos, current_site)) + list(range(current_site + 1, max_pos + 1))

                if not potential_partners:
                    # No potential partners available; skip interaction generation for this site
                    self.stdout.write(self.style.WARNING(f'  - No potential partners for site {current_site}. Skipping.'))
                else:
                    # Select 'num_interactions_per_site' unique partners randomly
                    selected_partners = random.sample(
                        potential_partners,
                        min(num_interactions_per_site, len(potential_partners))
                    )

                    for partner in selected_partners:
                        # Define weight based on intensity distribution
                        if intensity_distribution == 'uniform':
                            weight = round(random.uniform(0.1, 1.0), 4)
                        elif intensity_distribution == 'weighted':
                            # Example: 80% interactions with lower weights, 20% with higher weights
                            weight = round(random.choices(
                                population=[round(random.uniform(0.1, 0.5), 4), round(random.uniform(0.6, 1.0), 4)],
                                weights=[80, 20],
                                k=1
                            )[0], 4)

                        interaction = Interaction(
                            from_sequence=sequence,
                            to_sequence=sequence,
                            from_position=current_site,
                            to_position=partner,
                            weight=weight
                        )
                        interactions_bulk.append(interaction)

                        # To ensure no too much memory usage, bulk create in batches
                        if len(interactions_bulk) >= 10000:
                            Interaction.objects.bulk_create(interactions_bulk)
                            self.stdout.write(f'  - Generated interactions up to position {current_site}.')
                            interactions_bulk = []

                # Determine the next site using a random step between min_step and max_step
                step = random.randint(min_step, max_step)
                current_site += step

            if interactions_bulk:
                Interaction.objects.bulk_create(interactions_bulk)
                self.stdout.write(f'  - Generated all interactions for "{sequence.contig}".')

            self.stdout.write(self.style.SUCCESS(f'Dummy interactions generation completed for "{sequence.contig}".'))