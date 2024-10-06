from django.shortcuts import render, get_object_or_404
from .models import Sequence, Feature, NucleotideData, Interaction, FeatureSummaryStat, Genome, RepeatRegionMethod, CasGene, GeneInfluence
import json
from django.db.models import Q, Avg, StdDev, F, Sum, Count
from django.db.models.functions import Cast, Abs
from django.db.models import FloatField
from django.http import JsonResponse
from django.core.paginator import Paginator
from itertools import combinations
import plotly.graph_objs as go
import plotly.figure_factory as ff
import numpy as np
from scipy.cluster import hierarchy


def index(request):
    show_crispr = request.GET.get('show_crispr', 'false').lower() == 'true'
    
    genomes = Genome.objects.all()
    
    if show_crispr:
        genomes = genomes.filter(repeat_region_count__gt=0)
    
    genomes = genomes.order_by('name')
    
    paginator = Paginator(genomes, 10)  # Show 10 genomes per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Dashboard data
    total_genomes = Genome.objects.count()
    # Count distinct methods across all genomes
    total_crispr_methods = RepeatRegionMethod.objects.values('method').distinct().count()
    total_crispr_arrays = Feature.objects.filter(type='repeat_region').count()

    context = {
        'genomes': page_obj,
        'show_crispr': show_crispr,
        'total_genomes': total_genomes,
        'total_crispr_methods': total_crispr_methods,
        'total_crispr_arrays': total_crispr_arrays,
    }
    return render(request, 'viewer/index.html', context)


def cas_interactions(request):
    TOP_N = 10  # Number of top genes to display

    # Retrieve the full equation entry
    equation_entry = GeneInfluence.objects.filter(gene_name='__equation__').first()
    full_equation = equation_entry.full_equation if equation_entry else None

    # Retrieve influence data excluding the equation entry
    influences = GeneInfluence.objects.exclude(gene_name='__equation__')

    # Get all influencers and sort them by the absolute value of their coefficients
    all_influencers = list(influences)
    all_influencers.sort(key=lambda x: abs(x.coefficient), reverse=True)

    # Get top N influencers
    top_influencers = all_influencers[:TOP_N]

    context = {
        'top_influencers': top_influencers,
        'full_equation': full_equation,
        'top_n': TOP_N,
    }
    return render(request, 'viewer/cas_interactions.html', context)

def cas_heatmap(request):
    # Get all unique Cas genes
    cas_genes = list(CasGene.objects.values_list('name', flat=True).distinct())
    
    # Get all genomes
    genomes = list(Genome.objects.all().order_by('name'))
    
    # Create a matrix of Cas gene presence
    heatmap_data = []
    for genome in genomes:
        genome_cas_genes = genome.cas_genes.values_list('name', flat=True)
        row = [1 if gene in genome_cas_genes else 0 for gene in cas_genes]
        heatmap_data.append(row)
    
    # Convert to numpy array
    heatmap_data = np.array(heatmap_data)
    
    # Perform clustering
    row_linkage = hierarchy.linkage(heatmap_data, method='ward')
    col_linkage = hierarchy.linkage(heatmap_data.T, method='ward')

    # Reorder the data based on clustering
    row_order = hierarchy.dendrogram(row_linkage, no_plot=True)['leaves']
    col_order = hierarchy.dendrogram(col_linkage, no_plot=True)['leaves']

    heatmap_data = heatmap_data[row_order, :][:, col_order]
    
    # Create heatmap
    heatmap = go.Heatmap(
        z=heatmap_data,
        x=[cas_genes[i] for i in col_order],
        y=[genomes[i].name for i in row_order],
        colorscale=[[0, 'white'], [1, 'red']],
    )
    
    layout = go.Layout(
        title='Cas Gene Heatmap',
        xaxis=dict(
            title='Cas Genes',
            tickangle=90,
            side='bottom',
            tickfont=dict(size=10),
        ),
        yaxis=dict(
            title='Genomes',
            tickfont=dict(size=10),
            automargin=True,
        ),
        height=800,
        width=1200,
        margin=dict(l=200, r=50, b=200, t=50),
    )
    
    fig = go.Figure(data=[heatmap], layout=layout)
    
    # Convert the figure to JSON
    plot_json = fig.to_json()
    
    context = {
        'plot_json': plot_json,
    }
    
    return render(request, 'viewer/cas_heatmap.html', context)


def viewer(request, contig_name):
    position = request.GET.get('position')
    start = request.GET.get('start')
    end = request.GET.get('end')
    sequence = get_object_or_404(Sequence, contig=contig_name)
    
    # Fetch all features related to this sequence
    features = sequence.features.all()

    # Get start and end positions from URL parameters
    start_param = request.GET.get('start')
    end_param = request.GET.get('end')
    highlighted_feature_start = request.GET.get('highlighted_start')
    highlighted_feature_end = request.GET.get('highlighted_end')

    # Get color scheme from URL parameters
    color_by = request.GET.get('color_by', 'nucleotide')

    sequence_length = len(sequence.sequence)

    # Validate and set default start and end positions
    try:
        start = int(start_param)
    except (TypeError, ValueError):
        start = 0

    try:
        end = int(end_param)
    except (TypeError, ValueError):
        end = min(sequence_length, start + 5000)

    start = max(start, 0)
    end = min(end, sequence_length)

    # Convert highlighted feature positions to integers if they exist
    try:
        highlighted_feature_start = int(highlighted_feature_start)
        highlighted_feature_end = int(highlighted_feature_end)
    except (TypeError, ValueError):
        highlighted_feature_start = None
        highlighted_feature_end = None

    # Fetch available data sources
    available_data_sources = list(sequence.nucleotide_data.values_list('data_source', flat=True).distinct())

    sequence_segment = sequence.sequence[start:end]

    nucleotide_data = None
    if color_by != 'nucleotide' and color_by in available_data_sources:
        # Fetch nucleotide data for the displayed segment and selected data source
        nucleotide_data_qs = sequence.nucleotide_data.filter(
            position__gte=start + 1,
            position__lte=end,
            data_source=color_by
        ).order_by('position')

        # Prepare a list of values corresponding to the sequence segment
        nucleotide_values = [None] * (end - start)
        for nd in nucleotide_data_qs:
            idx = nd.position - (start + 1)
            if 0 <= idx < len(nucleotide_values):
                nucleotide_values[idx] = nd.value

        nucleotide_data = nucleotide_values

    # Filter features that are within the displayed region
    displayed_features = features.filter(start__lte=end, end__gte=start).exclude(type='gene').order_by('start')

    # Prepare features data for JavaScript
    features_data = []
    for feature in displayed_features:
        features_data.append({
            'id': feature.id,
            'type': feature.type,  # Added type here
            'start': feature.start,
            'end': feature.end,
            'description': feature.attributes.get('product', '') if feature.attributes else '',
        })

    # Calculate navigator position percentages
    navigator_percent_start = (start / sequence_length) * 100 if sequence_length > 0 else 0
    navigator_percent_end = ((end / sequence_length) * 100) - navigator_percent_start if sequence_length > 0 else 0

    # Prepare all features data for the second table
    all_features = features.order_by('start')
    all_features_data = []
    for feature in all_features:
        description = feature.attributes.get('product', '') if feature.attributes else ''

        # Fetch related summary statistics
        summary_stats = feature.summary_stats.all()
        stats_by_source = {}
        for stat in summary_stats:
            stats_by_source[stat.data_source] = {
                'mean_value': stat.mean_value,
                'standard_deviation': stat.standard_deviation,
            }

        all_features_data.append({
            'id': feature.id,
            'type': feature.type,
            'source': feature.source,
            'start': feature.start,
            'end': feature.end,
            'score': feature.score,
            'strand': feature.strand,
            'phase': feature.phase,
            'description': description,
            'summary_stats': stats_by_source,
        })

    # Fetch interactions where either from_position or to_position is within the current range
    interactions = Interaction.objects.filter(
        from_sequence__contig=contig_name,
        to_sequence__contig=contig_name
    ).filter(
        Q(from_position__gte=start + 1, from_position__lte=end) |
        Q(to_position__gte=start + 1, to_position__lte=end)
    )

    # Prepare interactions data for JavaScript
    interactions_data = [
        {
            'from_position': interaction.from_position,
            'to_position': interaction.to_position,
            'weight': interaction.weight,
        }
        for interaction in interactions
    ]

    # Add this new section to prepare heatmap data
    heatmap_data = []
    selected_feature_id = request.GET.get('selected_feature')
    if selected_feature_id:
        try:
            selected_feature = Feature.objects.get(id=selected_feature_id)
            for data_source in available_data_sources:
                nucleotide_data = NucleotideData.objects.filter(
                    sequence=sequence,
                    position__gte=selected_feature.start,
                    position__lte=selected_feature.end,
                    data_source=data_source
                ).order_by('position')
                
                heatmap_data.append({
                    'name': data_source,
                    'values': list(nucleotide_data.values('position', 'value'))
                })
        except Feature.DoesNotExist:
            pass

    # Determine if a position is provided
    if position:
        try:
            position = int(position)
            # Find features that encompass the position
            highlighted_feature = features.filter(start__lte=position, end__gte=position).first()
        except ValueError:
            highlighted_feature = None
    else:
        highlighted_feature = None
        
    context = {
        'contig_name': contig_name,
        'position': position,
        'highlighted_feature': highlighted_feature,
        'features': features,
        'sequence': sequence,
        'sequence_segment': sequence_segment,
        'start': start,
        'end': end,
        'navigator_percent_start': navigator_percent_start,
        'navigator_percent_width': navigator_percent_end,
        'highlighted_feature_start': highlighted_feature_start,
        'highlighted_feature_end': highlighted_feature_end,
        'sequence_length': sequence_length,
        'features': json.dumps(features_data),
        'displayed_features': features_data,
        'all_features': all_features_data,
        'available_data_sources': available_data_sources,
        'color_by': color_by,
        'nucleotide_data': json.dumps(nucleotide_data) if nucleotide_data else 'null',
        'interactions_json': json.dumps(interactions_data),
        'data_sources': available_data_sources,  # Pass data sources to the template
        'heatmap_data': json.dumps(heatmap_data),
        'selected_feature_id': selected_feature_id,
    }
    return render(request, 'viewer/viewer.html', context)

def crispr_plot(request):
    genomes = Genome.objects.all().order_by('name')
    methods = RepeatRegionMethod.objects.values_list('method', flat=True).distinct()
    
    scatter_data = []
    for method1, method2 in combinations(methods, 2):
        for genome in genomes:
            count1 = Feature.objects.filter(
                type='repeat_region',
                repeat_methods__method=method1,
                sequence__genome=genome
            ).count()
            count2 = Feature.objects.filter(
                type='repeat_region',
                repeat_methods__method=method2,
                sequence__genome=genome
            ).count()
            scatter_data.append({
                'genome_name': genome.name,
                'method1': method1,
                'method2': method2,
                'count1': count1,
                'count2': count2,
            })

    context = {
        'scatter_data': json.dumps(scatter_data),
        'methods': list(methods),
    }

    return render(request, 'viewer/crispr_plot.html', context)

def evaluation(request):
    methods = list(RepeatRegionMethod.objects.values_list('method', flat=True).distinct().order_by('method'))

    repeats_by_method = {}
    counts_per_method = {}
    avg_length_per_method = {}
    std_dev_per_method = {}
    crispr_fraction_per_method = {}
    genome_lengths = {}
    total_genome_length = 0

    for genome in Genome.objects.all():
        total_length = genome.sequences.aggregate(Sum('length'))['length__sum'] or 0
        genome_lengths[genome.name] = total_length
        total_genome_length += total_length

    for method in methods:
        repeats = Feature.objects.filter(
            type='repeat_region',
            repeat_methods__method=method
        ).annotate(length=F('end') - F('start'))

        repeats_set = set((r.sequence.contig, r.start, r.end) for r in repeats)
        repeats_by_method[method] = repeats_set
        counts_per_method[method] = len(repeats_set)

        # Calculate average length and standard deviation
        avg_length = repeats.aggregate(avg=Avg('length'))['avg']
        std_dev = repeats.aggregate(std=StdDev('length'))['std']

        avg_length_per_method[method] = round(avg_length, 2) if avg_length else 0
        std_dev_per_method[method] = round(std_dev, 2) if std_dev else 0

        # Calculate fraction of genome that is CRISPR
        total_crispr_length = repeats.aggregate(Sum('length'))['length__sum'] or 0
        crispr_fraction = (total_crispr_length / total_genome_length) if total_genome_length > 0 else 0
        crispr_fraction_per_method[method] = crispr_fraction

    total_repeats = len(set.union(*repeats_by_method.values())) if repeats_by_method else 0


    def compute_overlap_matrix(min_overlap, percentage_overlap=None):
        overlap_matrix = {}
        for method1, method2 in combinations(methods, 2):
            overlaps = 0
            for repeat1 in repeats_by_method[method1]:
                for repeat2 in repeats_by_method[method2]:
                    if repeat1[0] != repeat2[0]:
                        continue  # Different contigs
                    overlap_start = max(repeat1[1], repeat2[1])
                    overlap_end = min(repeat1[2], repeat2[2])
                    overlap_length = overlap_end - overlap_start
                    if percentage_overlap:
                        repeat1_length = repeat1[2] - repeat1[1]
                        repeat2_length = repeat2[2] - repeat2[1]
                        if (overlap_length / repeat1_length >= percentage_overlap and 
                            overlap_length / repeat2_length >= percentage_overlap):
                            overlaps += 1
                    elif overlap_length >= min_overlap:
                        overlaps += 1
            key = f"{method1}__{method2}"
            overlap_matrix[key] = overlaps
        return overlap_matrix

    overlap_matrix_100nt = compute_overlap_matrix(100)
    overlap_matrix_1nt = compute_overlap_matrix(1)
    overlap_matrix_80percent = compute_overlap_matrix(1, 0.8)

    genome_lengths = {}
    for genome in Genome.objects.all():
        total_length = genome.sequences.aggregate(Sum('length'))['length__sum'] or 0
        genome_lengths[genome.name] = total_length

    crisprs_per_1000nt = {}
    for method in methods:
        total_crisprs = 0
        for genome_name, genome_length in genome_lengths.items():
            crisprs_count = Feature.objects.filter(
                type='repeat_region',
                repeat_methods__method=method,
                sequence__genome__name=genome_name
            ).count()
            total_crisprs += crisprs_count
        
        crisprs_per_1000nt[method] = (total_crisprs / total_genome_length) * 1000 if total_genome_length > 0 else 0


    overlap_matrices = [
        ('100nt', overlap_matrix_100nt, 'Overlap of Predictions between Methods (≥100 nt):'),
        ('1nt', overlap_matrix_1nt, 'Overlap of Predictions between Methods (≥1 nt):'),
        ('80percent', overlap_matrix_80percent, 'Overlap of Predictions between Methods (≥80% of sequence length):'),
    ]

    context = {
        'methods': methods,
        'counts_per_method': counts_per_method,
        'avg_length_per_method': avg_length_per_method,
        'std_dev_per_method': std_dev_per_method,
        'total_repeats': total_repeats,
        'overlap_matrices': overlap_matrices,
        'crisprs_per_1000nt': crisprs_per_1000nt,
        'crispr_fraction_per_method': crispr_fraction_per_method,
    }

    return render(request, 'viewer/evaluation.html', context)
    def compute_overlap_matrix(min_overlap, percentage_overlap=None):
        overlap_matrix = {}
        for method1, method2 in combinations(methods, 2):
            overlaps = 0
            for repeat1 in repeats_by_method[method1]:
                for repeat2 in repeats_by_method[method2]:
                    if repeat1[0] != repeat2[0]:
                        continue  # Different contigs
                    overlap_start = max(repeat1[1], repeat2[1])
                    overlap_end = min(repeat1[2], repeat2[2])
                    overlap_length = overlap_end - overlap_start
                    if percentage_overlap:
                        repeat1_length = repeat1[2] - repeat1[1]
                        repeat2_length = repeat2[2] - repeat2[1]
                        if (overlap_length / repeat1_length >= percentage_overlap and 
                            overlap_length / repeat2_length >= percentage_overlap):
                            overlaps += 1
                    elif overlap_length >= min_overlap:
                        overlaps += 1
            key = f"{method1}__{method2}"
            overlap_matrix[key] = overlaps
        return overlap_matrix

    overlap_matrix_100nt = compute_overlap_matrix(100)
    overlap_matrix_1nt = compute_overlap_matrix(1)
    overlap_matrix_80percent = compute_overlap_matrix(1, 0.8)

    overlap_matrices = [
        ('100nt', overlap_matrix_100nt, 'Overlap of Predictions between Methods (≥100 nt):'),
        ('1nt', overlap_matrix_1nt, 'Overlap of Predictions between Methods (≥1 nt):'),
        ('80percent', overlap_matrix_80percent, 'Overlap of Predictions between Methods (≥80% of sequence length):'),
    ]

    context = {
        'methods': methods,
        'counts_per_method': counts_per_method,
        'avg_length_per_method': avg_length_per_method,
        'std_dev_per_method': std_dev_per_method,
        'total_repeats': total_repeats,
        'overlap_matrices': overlap_matrices,
        'crisprs_per_1000nt': crisprs_per_1000nt,  # Add this line
    }

    return render(request, 'viewer/evaluation.html', context)

# View to handle AJAX requests for heatmap data
def get_heatmap_data(request, contig_name):
    sequence = get_object_or_404(Sequence, contig=contig_name)
    feature_id = request.GET.get('feature_id')
    
    if not feature_id:
        return JsonResponse({'error': 'No feature selected'}, status=400)
    
    try:
        feature = Feature.objects.get(id=feature_id)
    except Feature.DoesNotExist:
        return JsonResponse({'error': 'Feature not found'}, status=404)
    
    available_data_sources = list(sequence.nucleotide_data.values_list('data_source', flat=True).distinct())
    heatmap_data = []
    
    for data_source in available_data_sources:
        nucleotide_data_qs = NucleotideData.objects.filter(
            sequence=sequence,
            position__gte=feature.start,
            position__lte=feature.end,
            data_source=data_source
        ).order_by('position')
        
        nucleotide_values = list(nucleotide_data_qs.values('position', 'value'))
            
        heatmap_data.append({
            'name': data_source,
            'values': nucleotide_values
        })
    
    return JsonResponse({
        'heatmap_data': heatmap_data,
        'feature': {
            'id': feature.id,
            'start': feature.start,
            'end': feature.end,
            'type': feature.type,
            'description': feature.attributes.get('product', '') if feature.attributes else '',
        }
    })

def get_feature_data(request, contig_name):
    sequence = get_object_or_404(Sequence, contig=contig_name)
    feature_id = request.GET.get('feature_id')

    if not feature_id:
        return JsonResponse({'error': 'No feature selected'}, status=400)

    try:
        feature = Feature.objects.get(id=feature_id)
    except Feature.DoesNotExist:
        return JsonResponse({'error': 'Feature not found'}, status=404)

    available_data_sources = list(sequence.nucleotide_data.values_list('data_source', flat=True).distinct())
    feature_data = []

    for data_source in available_data_sources:
        nucleotide_data_qs = NucleotideData.objects.filter(
            sequence=sequence,
            position__gte=feature.start,
            position__lte=feature.end,
            data_source=data_source
        ).order_by('position')

        nucleotide_values = list(nucleotide_data_qs.values('position', 'value'))

        feature_data.append({
            'name': data_source,
            'values': nucleotide_values
        })

    return JsonResponse({
        'feature_data': feature_data,
        'feature': {
            'id': feature.id,
            'start': feature.start,
            'end': feature.end,
            'type': feature.type,
            'description': feature.attributes.get('product', '') if feature.attributes else '',
        }
    })


def search_features(request, contig_name):
    sequence = get_object_or_404(Sequence, contig=contig_name)
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'features': []})
    
    # Search features by type or description (attributes->'product')
    features = Feature.objects.filter(sequence=sequence).filter(
        Q(type__icontains=query) |
        Q(attributes__product__icontains=query)
    ).values('id', 'type', 'start', 'end', 'attributes')[:100]  # Limit results for performance
    
    features_list = []
    for feature in features:
        attributes = feature['attributes'] or {}
        features_list.append({
            'id': feature['id'],
            'type': feature['type'],
            'start': feature['start'],
            'end': feature['end'],
            'description': attributes.get('product', ''),
        })
    
    return JsonResponse({'features': features_list})

def feature_info(request, contig_name):
    sequence = get_object_or_404(Sequence, contig=contig_name)
    feature_id = request.GET.get('feature_id')
    
    if not feature_id:
        return JsonResponse({'error': 'No feature ID provided'}, status=400)
    
    try:
        feature = Feature.objects.get(id=feature_id, sequence=sequence)
    except Feature.DoesNotExist:
        return JsonResponse({'error': 'Feature not found'}, status=404)
    
    feature_data = {
        'id': feature.id,
        'type': feature.type,
        'start': feature.start,
        'end': feature.end,
        'description': feature.attributes.get('product', '') if feature.attributes else '',
    }
    
    return JsonResponse({'feature': feature_data})

def about(request):
    return render(request, 'viewer/about.html')

def imprint(request):
   return render(request, 'viewer/imprint.html')
    
def dataprotection(request):
   return render(request, 'viewer/dataprotection.html')