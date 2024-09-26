from django.core.management.base import BaseCommand
from viewer.models import Sequence, Feature
import json
import os

class Command(BaseCommand):
    help = 'Load sequences and features into the database'

    def handle(self, *args, **options):
        # Load sequences
        with open('data/sequences.json', 'r') as seq_file:
            sequences = json.load(seq_file)
            for seq in sequences:
                sequence_obj, created = Sequence.objects.get_or_create(
                    contig=seq['contig'],
                    defaults={'sequence': seq['sequence']}
                )
                if created:
                    self.stdout.write(f"Created sequence {seq['contig']}.")

        # Load features
        with open('data/features.json', 'r') as feat_file:
            features = json.load(feat_file)
            for contig_data in features:
                contig_name = contig_data['contig']
                sequence_obj = Sequence.objects.get(contig=contig_name)
                for feat in contig_data['features']:
                    Feature.objects.create(
                        sequence=sequence_obj,
                        source=feat['source'],
                        type=feat['type'],
                        start=feat['start'],
                        end=feat['end'],
                        score=feat.get('score'),
                        strand=feat.get('strand'),
                        phase=feat.get('phase'),
                        attributes=feat.get('attributes', {})
                    )
                self.stdout.write(f"Added features for contig {contig_name}.")