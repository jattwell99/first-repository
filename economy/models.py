"""Economic measures: GVA, population, and derived GVA per head.

GVA (Gross Value Added) figures come from the ONS "Regional gross value
added (balanced) by local authority" workbooks and are stored in £ million.
Population comes from the ONS mid-year estimates. GVA per head divides one
by the other for a common geography and year.
"""
from django.db import models

from geography.models import Geography


class Industry(models.Model):
    """SIC industry grouping. ``TOTAL`` is the all-industries aggregate."""

    code = models.CharField(max_length=16, unique=True)  # e.g. TOTAL, A, C
    name = models.CharField(max_length=128)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "industries"

    def __str__(self):
        return f"{self.code} — {self.name}"


class PriceBasis(models.Model):
    """How a monetary figure is expressed (current prices, chained volume)."""

    code = models.CharField(max_length=32, unique=True)  # current, chained_volume
    name = models.CharField(max_length=64)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "price bases"

    def __str__(self):
        return self.name


class GvaValue(models.Model):
    """A single GVA figure for one area, industry, price basis and year."""

    geography = models.ForeignKey(
        Geography, on_delete=models.CASCADE, related_name="gva_values"
    )
    industry = models.ForeignKey(
        Industry, on_delete=models.PROTECT, related_name="gva_values"
    )
    price_basis = models.ForeignKey(
        PriceBasis, on_delete=models.PROTECT, related_name="gva_values"
    )
    year = models.PositiveSmallIntegerField()
    value_gbp_million = models.DecimalField(max_digits=14, decimal_places=3)
    source = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["geography", "industry", "price_basis", "year"],
                name="unique_gva_value",
            )
        ]
        indexes = [models.Index(fields=["year"])]
        ordering = ["-year", "geography__name"]

    def __str__(self):
        return f"{self.geography.code} {self.year}: £{self.value_gbp_million}m"


class PopulationVintage(models.Model):
    """A named population release, e.g. the 2020 mid-year estimates."""

    code = models.CharField(max_length=32, unique=True)  # e.g. 2020-06-mye
    label = models.CharField(max_length=128)
    reference_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-code"]

    def __str__(self):
        return self.label


class PopulationValue(models.Model):
    """Population of an area for a given year within a vintage."""

    geography = models.ForeignKey(
        Geography, on_delete=models.CASCADE, related_name="population_values"
    )
    vintage = models.ForeignKey(
        PopulationVintage, on_delete=models.CASCADE, related_name="values"
    )
    year = models.PositiveSmallIntegerField()
    population = models.BigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["geography", "vintage", "year"],
                name="unique_population_value",
            )
        ]
        ordering = ["-year", "geography__name"]

    def __str__(self):
        return f"{self.geography.code} {self.year}: {self.population:,}"


class GvaPerHead(models.Model):
    """Derived GVA per head (£) for an area and year.

    Populated by the ``derive_per_head`` management command from the
    all-industries current-price :class:`GvaValue` and the matching
    :class:`PopulationValue`.
    """

    geography = models.ForeignKey(
        Geography, on_delete=models.CASCADE, related_name="gva_per_head"
    )
    year = models.PositiveSmallIntegerField()
    gva_gbp_million = models.DecimalField(max_digits=14, decimal_places=3)
    population = models.BigIntegerField()
    gva_per_head_gbp = models.DecimalField(max_digits=12, decimal_places=2)
    vintage = models.ForeignKey(
        PopulationVintage, on_delete=models.PROTECT, related_name="per_head"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["geography", "year"],
                name="unique_gva_per_head",
            )
        ]
        indexes = [models.Index(fields=["-year"])]
        ordering = ["-year", "-gva_per_head_gbp"]
        verbose_name = "GVA per head"
        verbose_name_plural = "GVA per head"

    def __str__(self):
        return f"{self.geography.code} {self.year}: £{self.gva_per_head_gbp}/head"
