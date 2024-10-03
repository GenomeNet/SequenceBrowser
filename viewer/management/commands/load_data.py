from django.core.management.base import BaseCommand
from viewer.models import Sequence, Feature
import os
import json
from django.conf import settings
import gffutils
from Bio import SeqIO
import tempfile

class Command(BaseCommand):
    help = 'Load sequences and features into the database from a GFF file, including FASTA sequences'

    def add_arguments(self, parser):
        parser.add_argument(
            'gff_file',
            type=str,
            help='Path to the GFF file to be loaded',
        )

    def handle(self, *args, **options):
        gff_path = options['gff_file']

        if not os.path.exists(gff_path):
            self.stderr.write(self.style.ERROR(f"GFF file not found at {gff_path}"))
            return

        self.stdout.write(self.style.NOTICE("Parsing the GFF file..."))

        sequences_data = []
        features_data = []

        # Split GFF into annotations and FASTA sections
        gff_lines = []
        fasta_lines = []
        in_fasta = False

        with open(gff_path, 'r') as f:
            for line in f:
                if line.startswith('##FASTA'):
                    in_fasta = True
                    continue
                if in_fasta:
                    fasta_lines.append(line)
                else:
                    gff_lines.append(line)

        # Create a temporary GFF file without the FASTA section for gffutils
        temp_gff = tempfile.NamedTemporaryFile(delete=False, suffix=".gff", mode='w', encoding='utf-8')
        temp_gff.writelines(gff_lines)
        temp_gff.close()

        try:
            # Create a gffutils database
            db = gffutils.create_db(
                temp_gff.name,
                dbfn=':memory:',
                force=True,
                keep_order=True,
                merge_strategy='merge',
                sort_attribute_values=True
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error creating gffutils database: {e}"))
            os.unlink(temp_gff.name)
            return

        os.unlink(temp_gff.name)  # Remove the temporary GFF file

        # Parse sequences from FASTA
        if fasta_lines:
            temp_fasta = tempfile.NamedTemporaryFile(delete=False, suffix=".fasta", mode='w', encoding='utf-8')
            temp_fasta.writelines(fasta_lines)
            temp_fasta.close()
            fasta = SeqIO.parse(temp_fasta.name, 'fasta')
            for record in fasta:
                contig_name = record.id
                sequence = str(record.seq)
                self.stdout.write(f"Processing sequence from FASTA: {contig_name}")
                sequence_obj, created = Sequence.objects.get_or_create(
                    contig=contig_name,
                    defaults={'sequence': sequence}
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Created sequence: {contig_name}"))
                else:
                    self.stdout.write(f"Sequence already exists: {contig_name}")
                # Optionally, add to sequences_data
                sequences_data.append({
                    'contig': contig_name,
                    'sequence': sequence
                })
            os.unlink(temp_fasta.name)
        else:
            self.stdout.write("No FASTA section found in GFF file.")

        # Process features (assuming 'gene' as the feature type)
        feature_types_to_process = ['gene', 'CDS', 'exon', 'mRNA']  # Adjust as needed
        for ftype in feature_types_to_process:
            features = db.features_of_type(ftype)
            self.stdout.write(f"Processing {ftype} features...")
            for feature in features:
                contig = feature.seqid
                try:
                    sequence_obj = Sequence.objects.get(contig=contig)
                except Sequence.DoesNotExist:
                    self.stderr.write(self.style.ERROR(f"Sequence '{contig}' not found for feature '{feature.id}'. Skipping feature."))
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

                feature_data = {
                    'sequence_id': sequence_obj.id,
                    'source': feature.source,
                    'type': feature.featuretype,
                    'start': feature.start,
                    'end': feature.end,
                    'score': score,
                    'strand': feature.strand,
                    'phase': feature.frame,
                    'attributes': dict(feature.attributes)
                }
                features_data.append(feature_data)

                # Create the Feature object
                Feature.objects.create(
                    sequence=sequence_obj,
                    **{k: v for k, v in feature_data.items() if k != 'sequence_id'}
                )

        # Write intermediate output to disk (optional)
        sequences_output = os.path.join(settings.BASE_DIR, 'sequences_data.json')
        features_output = os.path.join(settings.BASE_DIR, 'features_data.json')

        with open(sequences_output, 'w', encoding='utf-8') as f:
            json.dump(sequences_data, f, indent=2)

        with open(features_output, 'w', encoding='utf-8') as f:
            json.dump(features_data, f, indent=2)

        self.stdout.write(self.style.SUCCESS("Data loading complete."))
        self.stdout.write(f"Total sequences processed: {len(sequences_data)}")
        self.stdout.write(f"Total features processed: {len(features_data)}")

        # Verify database content after loading
        self.stdout.write("Sequences in database after loading:")
        for seq in Sequence.objects.all():
            self.stdout.write(f"  - {seq.contig}")