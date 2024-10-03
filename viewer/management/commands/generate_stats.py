from django.core.management.base import BaseCommand
from django.db.models import Sum, Count, Q
from viewer.models import Genome, Sequence, Feature, RepeatRegionMethod, CasGene
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate statistics for genomes'

    def handle(self, *args, **options):
        total_genomes = Genome.objects.count()
        self.stdout.write(f"Processing {total_genomes} genomes...\n")

        # Define regex patterns
        crispr_pattern = re.compile(r'\bCRISPR\b', re.IGNORECASE)
        cas_pattern = re.compile(r'\bcas\d*[a-z]?\b', re.IGNORECASE)

        for i, genome in enumerate(Genome.objects.all(), 1):
            self.stdout.write(f"Processing genome {i}/{total_genomes}: {genome.name}")

            try:
                # Calculate total length and update sequence lengths
                total_length = 0
                for sequence in genome.sequences.all():
                    sequence.length = len(sequence.sequence)
                    sequence.save()
                    total_length += sequence.length
                genome.total_length = total_length

                # Use database aggregation for feature counts
                feature_count = Feature.objects.filter(sequence__genome=genome).count()
                repeat_region_count = Feature.objects.filter(sequence__genome=genome, type='repeat_region').count()
                genome.feature_count = feature_count
                genome.repeat_region_count = repeat_region_count

                # Initialize flags
                has_crispr_repeat = False
                cas_gene_count = 0
                cas_gene_entries = []

                # Fetch all relevant features once to minimize database queries
                features = Feature.objects.filter(sequence__genome=genome)

                # Clear existing RepeatRegionMethod associations
                RepeatRegionMethod.objects.filter(genome=genome).delete()

                # Prepare a dictionary to hold method-wise repeat features
                method_repeats = {}

                for feature in features:
                    # Check for CRISPR repeats
                    if feature.type.lower() == 'repeat_region':
                        description = self.construct_description(feature)
                        if crispr_pattern.search(description):
                            has_crispr_repeat = True

                        # Group repeats by method (source)
                        method = feature.source.strip() if feature.source else 'Unknown'
                        if not method:
                            method = 'Unknown'

                        if method not in method_repeats:
                            method_repeats[method] = []
                        method_repeats[method].append(feature)

                    # Check for Cas genes
                    if feature.type.lower() == 'cds':
                        description = self.construct_description(feature)
                        if cas_pattern.search(description):
                            cas_gene_count += 1
                            # Extract the exact Cas gene name
                            name = self.extract_cas_gene_name(feature)
                            cas_gene_entries.append(CasGene(genome=genome, name=name, count=1))

                genome.has_crispr_repeat = has_crispr_repeat
                genome.cas_gene_count = cas_gene_count

                self.stdout.write(f"Found {cas_gene_count} Cas genes for genome {genome.name}")

                # Update CasGene model
                CasGene.objects.filter(genome=genome).delete()
                if cas_gene_entries:
                    # Group CasGene entries by name
                    cas_gene_dict = {}
                    for entry in cas_gene_entries:
                        if entry.name in cas_gene_dict:
                            cas_gene_dict[entry.name].count += 1
                        else:
                            cas_gene_dict[entry.name] = CasGene(genome=genome, name=entry.name, count=1)
                    CasGene.objects.bulk_create(cas_gene_dict.values())
                    self.stdout.write(f"Created {len(cas_gene_dict)} CasGene entries for genome {genome.name}")
                else:
                    self.stdout.write(f"No CasGene entries created for genome {genome.name}")

                # Save genome statistics before associating repeats
                genome.save()

                # Update RepeatRegionMethod with associated repeats
                for method, repeat_features in method_repeats.items():
                    try:
                        method_entry, created = RepeatRegionMethod.objects.get_or_create(genome=genome, method=method)
                        method_entry.count = len(repeat_features)
                        method_entry.save()
                        method_entry.repeats.add(*repeat_features)
                        self.stdout.write(f"Associated {len(repeat_features)} repeats with method '{method}' for genome {genome.name}")
                    except Exception as e:
                        logger.error(f"Error associating repeats with method '{method}' for genome '{genome.name}': {e}")
                        self.stderr.write(f"Error associating repeats with method '{method}' for genome '{genome.name}': {e}")

                # Save genome statistics again if needed
                genome.save()

                self.stdout.write(f"Completed processing genome {i}/{total_genomes}: {genome.name}\n")

            except Exception as e:
                logger.error(f"Error processing genome '{genome.name}': {e}")
                self.stderr.write(f"Error processing genome '{genome.name}': {e}")

        self.stdout.write(self.style.SUCCESS('Successfully generated statistics'))

    def construct_description(self, feature):
        """
        Constructs the description from the feature's attributes.
        Adjust this method based on how descriptions are built in your application.
        """
        name = feature.attributes.get('Name', [''])[0] if isinstance(feature.attributes.get('Name'), list) else feature.attributes.get('Name', '')
        gene = feature.attributes.get('gene', [''])[0] if isinstance(feature.attributes.get('gene'), list) else feature.attributes.get('gene', '')
        product = feature.attributes.get('product', [''])[0] if isinstance(feature.attributes.get('product'), list) else feature.attributes.get('product', '')
        return f"{name} {gene} {product}".strip()

    def extract_cas_gene_name(self, feature):
        """
        Extracts the Cas gene name from the feature's attributes.
        Adjust this method based on how Cas gene names are stored in your attributes.
        """
        # Priority: Name > gene > product
        if 'Name' in feature.attributes and feature.attributes['Name']:
            return feature.attributes['Name'][0] if isinstance(feature.attributes['Name'], list) else feature.attributes['Name']
        elif 'gene' in feature.attributes and feature.attributes['gene']:
            return feature.attributes['gene'][0] if isinstance(feature.attributes['gene'], list) else feature.attributes['gene']
        elif 'product' in feature.attributes and feature.attributes['product']:
            return feature.attributes['product'][0] if isinstance(feature.attributes['product'], list) else feature.attributes['product']
        else:
            return 'Unknown Cas gene'