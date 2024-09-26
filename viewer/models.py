from django.db import models

class Sequence(models.Model):
    contig = models.CharField(max_length=200, unique=True)  # Non-nullable
    sequence = models.TextField()  # Stores the genome sequence

    def __str__(self):
        return self.contig

class Feature(models.Model):
    id = models.AutoField(primary_key=True)  # Primary key
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

class NucleotideData(models.Model):
    sequence = models.ForeignKey(Sequence, on_delete=models.CASCADE, related_name='nucleotide_data')
    position = models.PositiveIntegerField()  # Position in the sequence (1-based indexing)
    data_source = models.CharField(max_length=100)  # Name of the data source
    value = models.FloatField()

    class Meta:
        unique_together = ('sequence', 'position', 'data_source')

    def __str__(self):
        return f"{self.sequence.contig} position {self.position}: {self.value} [{self.data_source}]"

class Interaction(models.Model):
    from_sequence = models.ForeignKey(Sequence, related_name='interactions_from', on_delete=models.CASCADE)
    to_sequence = models.ForeignKey(Sequence, related_name='interactions_to', on_delete=models.CASCADE)
    from_position = models.IntegerField()
    to_position = models.IntegerField()
    weight = models.FloatField()

    def __str__(self):
        return f"Interaction from {self.from_position} to {self.to_position}"