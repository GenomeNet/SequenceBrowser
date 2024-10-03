from django.core.management.base import BaseCommand
from viewer.models import Sequence, Feature
import json
import os
from django.conf import settings

class Command(BaseCommand):
    help = 'Load sequences and features into the database from JSON files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sequences',
            type=str,
            help='Path to the sequences JSON file',
        )
        parser.add_argument(
            '--features',
            type=str,
            help='Path to the features JSON file',
        )

    def handle(self, *args, **options):
        sequences_path = options['sequences'] or os.path.join(settings.BASE_DIR, 'static', 'data', 'sequences.json')
        features_path = options['features'] or os.path.join(settings.BASE_DIR, 'static', 'data', 'features.json')

        # Load sequences
        if not os.path.exists(sequences_path):
            self.stderr.write(self.style.ERROR(f"Sequences file not found at {sequences_path}"))
            return

        with open(sequences_path, 'r') as seq_file:
            sequences = json.load(seq_file)
            for seq in sequences:
                sequence_obj, created = Sequence.objects.get_or_create(
                    contig=seq['contig'],
                    defaults={'sequence': seq['sequence']}
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Created sequence: {seq['contig']}"))
                else:
                    self.stdout.write(f"Sequence already exists: {seq['contig']}")

        # Load features
        if not os.path.exists(features_path):
            self.stderr.write(self.style.ERROR(f"Features file not found at {features_path}"))
            return

        with open(features_path, 'r') as feat_file:
            features = json.load(feat_file)
            for contig_data in features:
                contig_name = contig_data['contig']
                try:
                    sequence_obj = Sequence.objects.get(contig=contig_name)
                except Sequence.DoesNotExist:
                    self.stderr.write(self.style.ERROR(f"Sequence not found for contig: {contig_name}"))
                    continue

                for feat in contig_data['features']:
                    # Sanitize 'score' field
                    score = feat.get('score')
                    if score == 'NA':
                        score = None
                    else:
                        try:
                            score = float(score)
                        except (ValueError, TypeError):
                            score = None

                    Feature.objects.create(
                        sequence=sequence_obj,
                        source=feat['source'],
                        type=feat['type'],
                        start=feat['start'],
                        end=feat['end'],
                        score=score,
                        strand=feat.get('strand'),
                        phase=feat.get('phase'),
                        attributes=feat.get('attributes', {})
                    )
                self.stdout.write(self.style.SUCCESS(f"Added features for contig: {contig_name}"))

        self.stdout.write(self.style.SUCCESS("Data loading complete."))