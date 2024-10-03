from django.core.management.base import BaseCommand
from viewer.models import Genome, Sequence, Feature
import os
import json
from django.conf import settings
import gffutils
from Bio import SeqIO
import tempfile
from pathlib import Path

class Command(BaseCommand):
    help = 'Load sequences and features into the database from a GFF file, including FASTA sequences and genome metadata'

    def add_arguments(self, parser):
        parser.add_argument(
            'gff_file',
            type=str,
            help='Path to the GFF file to be loaded',
        )
        parser.add_argument(
            '--strain_name',
            type=str,
            default='',
            help='Name of the strain (optional)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update by removing existing entries before loading new ones',
        )

    def handle(self, *args, **options):
        gff_path = options['gff_file']
        strain_name = options['strain_name'].strip()
        force_update = options['force']

        if not os.path.exists(gff_path):
            self.stderr.write(self.style.ERROR(f"GFF file not found at {gff_path}"))
            return

        self.stdout.write(self.style.NOTICE("Parsing the GFF file..."))

        sequences_data = []
        features_data = []

        # Extract genome name from the file name (without extension)
        genome_name = Path(gff_path).stem
        self.stdout.write(f"Derived genome name: {genome_name}")

        # Create or get the Genome object
        genome_obj, genome_created = Genome.objects.get_or_create(
            name=genome_name,
            defaults={'strain_name': strain_name if strain_name else None}
        )

        if not genome_created and force_update:
            self.stdout.write(f"Forcing update for Genome: {genome_obj.name}")
            Sequence.objects.filter(genome=genome_obj).delete()
            Feature.objects.filter(sequence__genome=genome_obj).delete()
        elif not genome_created and not force_update:
            self.stdout.write(f"Genome {genome_obj.name} already exists. Skipping...")
            return

        sequences_loaded = 0
        features_loaded = 0

        try:
            # Split GFF into annotations and FASTA sections
            gff_lines = []
            fasta_lines = []
            in_fasta = False

            with open(gff_path, 'r') as f:
                for line in f:
                    if line.startswith('##FASTA'):
                        in_fasta = True
                        self.stdout.write("Found ##FASTA section. Parsing sequences from FASTA.")
                        continue
                    if in_fasta:
                        fasta_lines.append(line)
                    else:
                        gff_lines.append(line)

            # Create a temporary GFF file without the FASTA section for gffutils
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_gff:
                temp_gff.writelines(gff_lines)
                temp_gff_path = temp_gff.name

            # Create a gffutils database
            db = gffutils.create_db(temp_gff_path, dbfn=':memory:', force=True, keep_order=True, merge_strategy='merge', sort_attribute_values=True)

            # Process FASTA sequences if available
            if fasta_lines:
                fasta_content = ''.join(fasta_lines)
                fasta_handle = tempfile.NamedTemporaryFile(mode='w+', delete=False)
                fasta_handle.write(fasta_content)
                fasta_handle.close()

                for record in SeqIO.parse(fasta_handle.name, 'fasta'):
                    contig_name = record.id
                    sequence_str = str(record.seq)
                    sequence_obj, created = Sequence.objects.get_or_create(
                        genome=genome_obj,
                        contig=contig_name,
                        defaults={'sequence': sequence_str}
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f"Created Sequence: {contig_name}"))
                        sequences_loaded += 1
                    else:
                        self.stdout.write(f"Sequence already exists: {contig_name}")

                # Remove temporary FASTA file
                os.unlink(fasta_handle.name)

            # Remove temporary GFF file
            os.unlink(temp_gff_path)

            # Process features
            self.stdout.write("Processing all feature types...")
            for feature in db.all_features():
                contig = feature.seqid
                try:
                    sequence_obj = Sequence.objects.get(genome=genome_obj, contig=contig)
                except Sequence.DoesNotExist:
                    self.stderr.write(
                        self.style.ERROR(f"Sequence '{contig}' not found for feature '{feature.id}'. Skipping feature.")
                    )
                    continue

                # Sanitize 'score' field
                score = feature.attributes.get('score', [None])[0]
                if score == 'NA' or score is None:
                    score = None
                else:
                    try:
                        score = float(score)
                    except ValueError:
                        score = None

                # Determine strand
                strand = None
                if feature.strand == 1:
                    strand = '+'
                elif feature.strand == -1:
                    strand = '-'

                feature_data = {
                    'sequence': sequence_obj,
                    'source': feature.source,
                    'type': feature.featuretype,
                    'start': feature.start,
                    'end': feature.end,
                    'score': score,
                    'strand': strand,
                    'phase': feature.frame,
                    'attributes': {k: v[0] for k, v in feature.attributes.items()} if feature.attributes else {}
                }

                if force_update:
                    Feature.objects.update_or_create(
                        sequence=sequence_obj,
                        start=feature.start,
                        end=feature.end,
                        type=feature.featuretype,
                        defaults=feature_data
                    )
                    features_loaded += 1
                else:
                    _, created = Feature.objects.get_or_create(
                        sequence=sequence_obj,
                        start=feature.start,
                        end=feature.end,
                        type=feature.featuretype,
                        defaults=feature_data
                    )
                    if created:
                        features_loaded += 1
                    else:
                        self.stdout.write(f"Feature already exists: {feature.id}. Skipping...")

            # Write intermediate output to disk (optional)
            sequences_output = os.path.join(settings.BASE_DIR, 'sequences_data.json')
            features_output = os.path.join(settings.BASE_DIR, 'features_data.json')

            with open(sequences_output, 'w', encoding='utf-8') as f:
                json.dump(sequences_data, f, indent=2)

            with open(features_output, 'w', encoding='utf-8') as f:
                json.dump(features_data, f, indent=2)

            self.stdout.write(self.style.SUCCESS("Data loading complete."))
            self.stdout.write(f"Total sequences processed: {sequences_loaded}")
            self.stdout.write(f"Total features processed: {features_loaded}")

            # Verify database content after loading
            self.stdout.write("Sequences in database after loading:")
            for seq in Sequence.objects.filter(genome=genome_obj):
                self.stdout.write(f"  - {seq.contig}")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"An error occurred during data loading: {str(e)}"))
        finally:
            # Clean up any temporary files or resources if needed
            pass
            pass