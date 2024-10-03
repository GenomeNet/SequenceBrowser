from django.contrib import admin
from .models import Genome, Sequence, Feature, NucleotideData, Interaction, FeatureSummaryStat, RepeatRegionMethod, CasGene

@admin.register(Genome)
class GenomeAdmin(admin.ModelAdmin):
    list_display = ('name', 'strain_name', 'total_length', 'feature_count', 'repeat_region_count', 'has_crispr_repeat', 'cas_gene_count')
    list_filter = ('has_crispr_repeat',)
    search_fields = ('name', 'strain_name')

@admin.register(Sequence)
class SequenceAdmin(admin.ModelAdmin):
    list_display = ('contig', 'genome', 'length')
    list_filter = ('genome',)
    search_fields = ('contig', 'genome__name')

@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('id', 'sequence', 'type', 'start', 'end', 'strand')
    list_filter = ('type', 'sequence__genome')
    search_fields = ('sequence__contig', 'type', 'attributes')

@admin.register(NucleotideData)
class NucleotideDataAdmin(admin.ModelAdmin):
    list_display = ('sequence', 'position', 'data_source', 'value')
    list_filter = ('data_source', 'sequence__genome')
    search_fields = ('sequence__contig', 'data_source')

@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ('from_sequence', 'to_sequence', 'from_position', 'to_position', 'weight')
    search_fields = ('from_sequence__contig', 'to_sequence__contig')

@admin.register(FeatureSummaryStat)
class FeatureSummaryStatAdmin(admin.ModelAdmin):
    list_display = ('feature', 'data_source', 'mean_value', 'standard_deviation')
    list_filter = ('data_source',)
    search_fields = ('feature__sequence__contig', 'data_source')

@admin.register(RepeatRegionMethod)
class RepeatRegionMethodAdmin(admin.ModelAdmin):
    list_display = ('genome', 'method', 'count')
    list_filter = ('genome', 'method')
    search_fields = ('genome__name', 'method')

@admin.register(CasGene)
class CasGeneAdmin(admin.ModelAdmin):
    list_display = ('genome', 'name', 'count')
    list_filter = ('genome',)
    search_fields = ('genome__name', 'name')