from django.core.management.base import BaseCommand
from viewer.models import Genome, Sequence, Feature, RepeatRegionMethod

class Command(BaseCommand):
    help = 'Generate statistics for genomes'

    def handle(self, *args, **options):
        for genome in Genome.objects.all():
            total_length = 0
            feature_count = 0
            repeat_region_count = 0
            repeat_methods = {}

            for sequence in genome.sequences.all():
                sequence.length = len(sequence.sequence)
                sequence.save()
                total_length += sequence.length

                for feature in sequence.features.all():
                    feature_count += 1
                    if feature.type == 'repeat_region':
                        repeat_region_count += 1
                        repeat_methods[feature.source] = repeat_methods.get(feature.source, 0) + 1

            genome.total_length = total_length
            genome.feature_count = feature_count
            genome.repeat_region_count = repeat_region_count
            genome.save()

            RepeatRegionMethod.objects.filter(genome=genome).delete()
            for method, count in repeat_methods.items():
                RepeatRegionMethod.objects.create(genome=genome, method=method, count=count)

        self.stdout.write(self.style.SUCCESS('Successfully generated statistics'))