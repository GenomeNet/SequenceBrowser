import os
import re
import pyreadr
import pandas as pd
from tqdm import tqdm
from django.core.management.base import BaseCommand, CommandError
from viewer.models import Genome, Sequence, Feature, NucleotideData

class Command(BaseCommand):
    help = 'Load nucleotide data from .rds files into the database for deepG track and detect CRISPR regions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--folder',
            type=str,
            required=True,
            help='Folder containing .rds files.'
        )
        parser.add_argument(
            '--data_source',
            type=str,
            default='deepG',
            help='Name of the data source to assign to nucleotide data.'
        )
        parser.add_argument(
            '--dry_run',
            action='store_true',
            help='Perform a dry run without modifying the database.'
        )

    def handle(self, *args, **options):
        folder = options['folder']
        data_source = options['data_source']
        dry_run = options['dry_run']

        if not os.path.isdir(folder):
            raise CommandError(f'The folder "{folder}" does not exist or is not a directory.')

        # Get list of .rds files in the folder
        rds_files = [f for f in os.listdir(folder) if f.endswith('.rds')]
        if not rds_files:
            raise CommandError(f'No .rds files found in the folder "{folder}".')

        self.stdout.write(f'Found {len(rds_files)} .rds files in the folder.')

        for filename in tqdm(rds_files, desc='Processing files'):
            file_path = os.path.join(folder, filename)

            # Extract genome name and contig index from the filename
            # Example filename: 'GCA_012932375.1_ASM1293237v1_genomic_1.rds'
            match = re.match(r'^(.*?_genomic)_(\d+)\.rds$', filename)
            if not match:
                self.stdout.write(self.style.WARNING(
                    f'Skipping file "{filename}" - filename does not match expected pattern.'
                ))
                continue

            genome_name = match.group(1)
            contig_index = int(match.group(2))

            try:
                # Fetch the Genome object based on genome_name
                genome = Genome.objects.get(name=genome_name)
            except Genome.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'No Genome found with name "{genome_name}" for file "{filename}". Skipping.'
                ))
                continue

            # Find sequences where genome matches and contig ends with '_[contig_index]'
            sequences = Sequence.objects.filter(
                genome=genome,
                contig__endswith=f'_{contig_index}'
            )
            if not sequences.exists():
                self.stdout.write(self.style.WARNING(
                    f'No sequences found for genome "{genome_name}" and contig index {contig_index} in file "{filename}".'
                ))
                continue

            if sequences.count() > 1:
                self.stdout.write(self.style.WARNING(
                    f'Multiple sequences found for genome "{genome_name}" and contig index {contig_index} in file "{filename}". Using the first one.'
                ))

            sequence = sequences.first()
            sequence_length = len(sequence.sequence)
            self.stdout.write(
                f'Processing sequence "{sequence.contig}" from file "{filename}" with length {sequence_length}.'
            )

            try:
                # Read the .rds file using pyreadr
                result = pyreadr.read_r(file_path)
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'Failed to read .rds file "{filename}": {e}'
                ))
                continue

            # Assuming the DataFrame is the first object in the R workspace
            if len(result) == 0:
                self.stdout.write(self.style.ERROR(
                    f'No DataFrame found in file "{filename}". Skipping.'
                ))
                continue

            df = next(iter(result.values()))
            if not {'position', 'pred'}.issubset(df.columns):
                self.stdout.write(self.style.ERROR(
                    f'Required columns "position" and "pred" not found in file "{filename}". Skipping.'
                ))
                continue

            # Ensure position and pred columns are numeric
            df['position'] = pd.to_numeric(df['position'], errors='coerce')
            df['pred'] = pd.to_numeric(df['pred'], errors='coerce')
            df.dropna(subset=['position', 'pred'], inplace=True)

            # Convert positions to integers
            df['position'] = df['position'].astype(int)

            # Create states_df similar to R code
            states_df = df[['position', 'pred']].copy()
            states_df.rename(columns={'pred': 'conf_CRISPR'}, inplace=True)
            states_df['conf_non_CRISPR'] = 1 - states_df['conf_CRISPR']
            states_df['seq_end'] = states_df['position']

            # Sort by seq_end
            states_df = states_df[['seq_end', 'conf_CRISPR', 'conf_non_CRISPR']].sort_values('seq_end').reset_index(drop=True)

            # Debugging: Log first few rows
            self.stdout.write(f'First 5 rows of DataFrame from "{filename}":')
            self.stdout.write(str(states_df.head()))

            # Call the filter_crispr function
            regions = self.filter_crispr(
                states_df=states_df,
                crispr_gap=10,       # Adjusted parameters based on your R function
                conf_cutoff=0.5,
                pos_rate=0.8,
                min_seq_len=120,
                maxlen=200
            )

            if regions:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Found {len(regions)} CRISPR regions in sequence "{sequence.contig}" from file "{filename}".'
                    )
                )
                for idx, region_df in enumerate(regions):
                    start_index = int(region_df['seq_end'].min())
                    end_index = int(region_df['seq_end'].max())
                    region_length = end_index - start_index + 1

                    if dry_run:
                        self.stdout.write(
                            f'  Region {idx + 1}: Start={start_index}, End={end_index}, Length={region_length}'
                        )
                    else:
                        # Create Feature object
                        Feature.objects.create(
                            sequence=sequence,
                            type='repeat_region',
                            start=start_index,
                            end=end_index,
                            strand='.',  # Use '.' if strand information is not available
                            source='deepG'
                        )
            else:
                self.stdout.write(
                    f'No CRISPR regions found in sequence "{sequence.contig}" from file "{filename}".'
                )

            # Continue with loading NucleotideData if needed
            # [The rest of your code for loading nucleotide data goes here...]

    def filter_crispr(self, states_df,
                      crispr_gap=10,
                      conf_cutoff=0.5,
                      pos_rate=0.8,
                      min_seq_len=120,
                      maxlen=200):
        """
        Filters CRISPR regions based on specified criteria.
        """
        required_columns = {'conf_CRISPR', 'conf_non_CRISPR', 'seq_end'}
        if not required_columns.issubset(states_df.columns):
            raise ValueError(f"states_df must contain columns: {required_columns}")

        if states_df['seq_end'].duplicated().any():
            raise ValueError("positions should all be unique (seq_end column in states_df)")

        # Calculate step size
        if len(states_df) >= 2:
            step = states_df['seq_end'].iloc[1] - states_df['seq_end'].iloc[0]
        else:
            step = 1  # Default step size if only one position present

        # Filter states_df to only include rows where conf_CRISPR > conf_cutoff
        states_df = states_df[states_df['conf_CRISPR'] > conf_cutoff].copy()
        states_df.sort_values('seq_end', inplace=True)
        row_num = len(states_df)

        crispr_list = []
        if row_num == 0:
            self.stdout.write("All confidence scores below conf_cutoff")
            return crispr_list

        crispr_index = 1
        crispr_start = states_df['seq_end'].iloc[0]

        if row_num > 1:
            for i in range(row_num - 1):
                current_pos = states_df['seq_end'].iloc[i]
                next_pos = states_df['seq_end'].iloc[i + 1]

                if (abs(current_pos - next_pos) > crispr_gap) and (i != row_num - 2):
                    index = (states_df['seq_end'] >= crispr_start) & (states_df['seq_end'] <= current_pos)
                    region = states_df.loc[index].copy()
                    crispr_list.append(region)
                    crispr_start = next_pos
                    crispr_index += 1

                if i == row_num - 2:
                    # Last iteration
                    if abs(current_pos - next_pos) <= crispr_gap:
                        index = states_df['seq_end'] >= crispr_start
                        region = states_df.loc[index].copy()
                        crispr_list.append(region)
                    else:
                        index = (states_df['seq_end'] >= crispr_start) & (states_df['seq_end'] <= current_pos)
                        region = states_df.loc[index].copy()
                        crispr_list.append(region)

                        # Single sample at end
                        crispr_index += 1
                        region = states_df.iloc[[row_num - 1]].copy()
                        crispr_list.append(region)
        else:
            # Only one row
            region = states_df.copy()
            crispr_list.append(region)

        # Filter by positivity rate
        filtered_crispr_list = []
        for df in crispr_list:
            seq_len = df['seq_end'].iloc[-1] - df['seq_end'].iloc[0]
            num_possible_pos_pred = ((seq_len - 1) / step) + 1
            cov_rate = len(df) / num_possible_pos_pred if num_possible_pos_pred > 0 else 0
            if cov_rate >= pos_rate:
                filtered_crispr_list.append(df)
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'    - Discarded region due to low coverage rate: '
                        f'Coverage Rate={cov_rate:.2f}'
                    )
                )

        # Filter by size
        final_crispr_list = []
        for df in filtered_crispr_list:
            seq_len = df['seq_end'].iloc[-1] - df['seq_end'].iloc[0] + 1
            if seq_len >= min_seq_len:
                final_crispr_list.append(df)
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'    - Discarded region due to insufficient length: '
                        f'Length={seq_len}'
                    )
                )

        # Optionally compute seq_middle or other attributes
        # for df in final_crispr_list:
        #     df['seq_middle'] = df['seq_end'] - (maxlen / 2)

        self.stdout.write(
            f'  - Detected {len(final_crispr_list)} potential CRISPR regions after filtering.'
        )

        return final_crispr_list