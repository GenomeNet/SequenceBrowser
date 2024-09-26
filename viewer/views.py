from django.shortcuts import render, get_object_or_404
from .models import Sequence, Feature, NucleotideData, Interaction
import json
from django.db.models import Q

def index(request):
    sequences = Sequence.objects.all()
    return render(request, 'viewer/index.html', {'sequences': sequences})

def viewer(request, contig_name):
    sequence = get_object_or_404(Sequence, contig=contig_name)
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

    context = {
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
    }
    return render(request, 'viewer/viewer.html', context)