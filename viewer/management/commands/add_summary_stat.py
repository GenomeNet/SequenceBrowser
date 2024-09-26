from django.core.management.base import BaseCommand
from django.db.models import Avg, StdDev, Q
from viewer.models import Feature, NucleotideData, FeatureSummaryStat

class Command(BaseCommand):
    help = 'Calculates summary statistics (mean and standard deviation) for features based on NucleotideData.'

    def handle(self, *args, **options):
        features = Feature.objects.all()
        total_features = features.count()
        self.stdout.write(f"Processing {total_features} features...")

        for i, feature in enumerate(features, 1):
            # Fetch all NucleotideData within the feature's range
            nucleotide_data_qs = NucleotideData.objects.filter(
                sequence=feature.sequence,
                position__gte=feature.start,
                position__lte=feature.end
            )

            # Get all data_sources for this feature
            data_sources = nucleotide_data_qs.values_list('data_source', flat=True).distinct()

            for data_source in data_sources:
                # Filter data for this data_source
                data_source_qs = nucleotide_data_qs.filter(data_source=data_source)

                # Calculate mean and standard deviation
                summary = data_source_qs.aggregate(
                    mean_value=Avg('value'),
                    standard_deviation=StdDev('value')
                )

                # Create or update FeatureSummaryStat
                FeatureSummaryStat.objects.update_or_create(
                    feature=feature,
                    data_source=data_source,
                    defaults={
                        'mean_value': summary['mean_value'] or 0.0,
                        'standard_deviation': summary['standard_deviation'] or 0.0
                    }
                )

            if i % 100 == 0 or i == total_features:
                self.stdout.write(f"Processed {i}/{total_features} features.")

        self.stdout.write("Summary statistics calculation completed.")