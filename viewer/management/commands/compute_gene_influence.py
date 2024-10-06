from django.core.management.base import BaseCommand
from django.db.models import Q
from viewer.models import Genome, Feature, GeneInfluence
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

class Command(BaseCommand):
    help = 'Computes the influence of genes on CRISPR arrays using Ridge Regression to address multicollinearity'

    def handle(self, *args, **options):
        # Gather data
        genomes = Genome.objects.all()
        data = []
        gene_set = set()

        for genome in genomes:
            num_crispr_arrays = genome.repeat_region_count or 0

            # Get all genes for the genome
            genes = Feature.objects.filter(
                sequence__genome=genome,
                type='gene'
            ).filter(Q(attributes__has_key='gene'))

            genome_gene_presence = {}
            for gene in genes:
                gene_name = gene.attributes.get('gene')
                if gene_name:
                    genome_gene_presence[gene_name] = 1
                    gene_set.add(gene_name)

            data.append({
                'genome': genome.name,
                'num_crispr_arrays': num_crispr_arrays,
                'gene_presence': genome_gene_presence
            })

        if not data:
            self.stdout.write(self.style.WARNING('No data available to compute gene influence.'))
            return

        # Prepare data for regression
        gene_list = sorted(gene_set)
        X_data = []
        y_data = []

        for entry in data:
            presence = [entry['gene_presence'].get(gene, 0) for gene in gene_list]
            X_data.append(presence)
            y_data.append(entry['num_crispr_arrays'])

        # Convert to pandas DataFrame for better handling
        X = pd.DataFrame(X_data, columns=gene_list)
        y = pd.Series(y_data)

        # Remove columns with zero variance (genes not present in any genome)
        X = X.loc[:, (X != X.iloc[0]).any()]

        if X.empty:
            self.stdout.write(self.style.ERROR('All genes have zero variance. Cannot perform regression.'))
            return

        # Fit Ridge Regression model with alpha=1.0 (regularization strength)
        model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        model.fit(X, y)
        coefficients = model.named_steps['ridge'].coef_
        intercept = model.named_steps['ridge'].intercept_

        # Clear previous GeneInfluence objects
        GeneInfluence.objects.all().delete()

        # Save coefficients, set p_value to None since Ridge does not provide p-values
        for gene_name, coef in zip(X.columns, coefficients):
            GeneInfluence.objects.create(
                gene_name=gene_name,
                coefficient=coef,
                p_value=None,  # No p-values available
                is_cas_gene=gene_name.lower().startswith('cas')
            )

        # Save the full regression equation (excluding intercept)
        equation_terms = [f"{coef:.4f}*{name}" for name, coef in zip(X.columns, coefficients)]
        full_equation = f"num_crispr_arrays = {intercept:.4f} + " + ' + '.join(equation_terms)

        GeneInfluence.objects.create(
            gene_name='__equation__',
            coefficient=0.0,
            p_value=None,  # No p-value for equation
            full_equation=full_equation
        )

        self.stdout.write(self.style.SUCCESS('Gene influence computed and saved successfully using Ridge Regression.'))