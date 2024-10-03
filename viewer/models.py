from django.db import models

class Genome(models.Model):
    name = models.CharField(max_length=255, unique=True)
    strain_name = models.CharField(max_length=255, null=True, blank=True)
    
    # New fields for statistics
    total_length = models.BigIntegerField(default=0)
    feature_count = models.IntegerField(default=0)
    repeat_region_count = models.IntegerField(default=0)
    has_crispr_repeat = models.BooleanField(default=False)
    cas_gene_count = models.IntegerField(default=0)

    def __str__(self):
        return self.name

class Sequence(models.Model):
    genome = models.ForeignKey(Genome, on_delete=models.CASCADE, related_name='sequences')
    contig = models.CharField(max_length=200)
    sequence = models.TextField()
    length = models.IntegerField(default=0)  # New field for contig length

    def __str__(self):
        return f"{self.genome.name} - {self.contig}"

    class Meta:
        unique_together = ('genome', 'contig')

class Feature(models.Model):
    id = models.AutoField(primary_key=True)
    sequence = models.ForeignKey(Sequence, on_delete=models.CASCADE, related_name='features')
    source = models.CharField(max_length=200)
    type = models.CharField(max_length=200)
    start = models.IntegerField()
    end = models.IntegerField()
    score = models.FloatField(null=True, blank=True)
    strand = models.CharField(max_length=1, null=True, blank=True)
    phase = models.CharField(max_length=1, null=True, blank=True)
    attributes = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.type} ({self.start}-{self.end}) on {self.sequence.contig}"

    class Meta:
        indexes = [
            models.Index(fields=['sequence', 'type']),
            models.Index(fields=['sequence', 'start', 'end']),
            models.Index(fields=['sequence', 'attributes'], name='feature_attributes_idx'),
        ]

class NucleotideData(models.Model):
    sequence = models.ForeignKey(Sequence, on_delete=models.CASCADE, related_name='nucleotide_data')
    position = models.PositiveIntegerField()  # Position in the sequence (1-based indexing)
    data_source = models.CharField(max_length=100)  # Name of the data source
    value = models.FloatField()

    class Meta:
        unique_together = ('sequence', 'position', 'data_source')

    def __str__(self):
        return f"{self.sequence.genome.name} - {self.sequence.contig} position {self.position}: {self.value} [{self.data_source}]"

class Interaction(models.Model):
    from_sequence = models.ForeignKey(Sequence, related_name='interactions_from', on_delete=models.CASCADE)
    to_sequence = models.ForeignKey(Sequence, related_name='interactions_to', on_delete=models.CASCADE)
    from_position = models.IntegerField()
    to_position = models.IntegerField()
    weight = models.FloatField()

    def __str__(self):
        return f"Interaction from {self.from_position} to {self.to_position} between {self.from_sequence} and {self.to_sequence}"

class FeatureSummaryStat(models.Model):
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE, related_name='summary_stats')
    data_source = models.CharField(max_length=100)
    mean_value = models.FloatField()
    standard_deviation = models.FloatField()

    class Meta:
        unique_together = ('feature', 'data_source')

    def __str__(self):
        return f"Stats for {self.feature} [{self.data_source}]"

class RepeatRegionMethod(models.Model):
    genome = models.ForeignKey(Genome, on_delete=models.CASCADE, related_name='repeat_region_methods')
    method = models.CharField(max_length=200)
    count = models.IntegerField(default=0)
    repeats = models.ManyToManyField(Feature, related_name='repeat_methods')  # Ensure this line is present and correct

    class Meta:
        unique_together = ('genome', 'method')

    def __str__(self):
        return f"{self.genome.name} - {self.method}: {self.count}"
    
class CasGene(models.Model):
    genome = models.ForeignKey(Genome, on_delete=models.CASCADE, related_name='cas_genes')
    name = models.CharField(max_length=255)
    count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('genome', 'name')

    def __str__(self):
        return f"{self.genome.name} - {self.name}: {self.count}"