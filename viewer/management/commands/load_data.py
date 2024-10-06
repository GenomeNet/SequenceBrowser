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
    help = 'Load sequences and features into the database from GFF files in a directory'

    def add_arguments(self, parser):
        parser.add_argument(
            'gff_directory',
            type=str,
            help='Path to the directory containing GFF files',
        )
        parser.add_argument(
            '--strain_name',
            type=str,
            default='NA',
            help='Name of the strain (optional, default: NA)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update by removing existing entries before loading new ones',
        )
        parser.add_argument(
            '--test',
            type=int,
            default=None,
            help='Limit the number of genomes to process (for testing)',
        )

    def handle(self, *args, **options):
        gff_directory = options['gff_directory']
        strain_name = options['strain_name'].strip()
        force_update = options['force']
        test_limit = options['test']

        if not os.path.isdir(gff_directory):
            self.stderr.write(self.style.ERROR(f"Directory not found: {gff_directory}"))
            return

        gff_files = [f for f in os.listdir(gff_directory) if f.endswith('.gff')]
        if test_limit:
            gff_files = gff_files[:test_limit]

        total_genomes_processed = 0
        total_sequences_loaded = 0
        total_features_loaded = 0

        for gff_file in gff_files:
            gff_path = os.path.join(gff_directory, gff_file)
            genome_name = Path(gff_file).stem

            # Check if genome already exists
            if Genome.objects.filter(name=genome_name).exists() and not force_update:
                self.stdout.write(f"Genome {genome_name} already exists. Skipping...")
                continue

            self.stdout.write(self.style.NOTICE(f"Processing {gff_file}..."))

            sequences_data = []
            features_data = []

            # Create or get the Genome object
            genome_obj, genome_created = Genome.objects.get_or_create(
                name=genome_name,
                defaults={'strain_name': None if strain_name == 'NA' else strain_name}
            )

            if not genome_created and force_update:
                self.stdout.write(f"Forcing update for Genome: {genome_obj.name}")
                Sequence.objects.filter(genome=genome_obj).delete()
                Feature.objects.filter(sequence__genome=genome_obj).delete()

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

                self.stdout.write(self.style.SUCCESS(f"Data loading complete for {gff_file}."))
                self.stdout.write(f"Sequences processed: {sequences_loaded}")
                self.stdout.write(f"Features processed: {features_loaded}")

                total_sequences_loaded += sequences_loaded
                total_features_loaded += features_loaded
                total_genomes_processed += 1

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"An error occurred during data loading for {gff_file}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS("All GFF files processed."))
        self.stdout.write(f"Total genomes processed: {total_genomes_processed}")
        self.stdout.write(f"Total sequences loaded: {total_sequences_loaded}")
        self.stdout.write(f"Total features loaded: {total_features_loaded}")