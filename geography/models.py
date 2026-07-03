"""Geography dimension: statistical areas and their hierarchy.

Two area types matter for this model:

* ``LAD`` — Local Authority District (ONS codes like ``E06000001``)
* ``WPC`` — Westminster Parliamentary Constituency (codes like ``E14000530``)

Higher-level areas (region, country) are represented with the same
``Geography`` model at different :class:`GeographyLevel` values so that
totals can be rolled up through ``parent``.
"""
from django.db import models


class GeographyLevel(models.Model):
    """A tier of the geography hierarchy (LAD, WPC, region, country)."""

    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=64)
    # Lower numbers are broader (country=0, region=1, LAD/WPC=2).
    rank = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["rank", "code"]

    def __str__(self):
        return self.name


class Geography(models.Model):
    """A single statistical area, identified by its ONS geography code."""

    code = models.CharField(max_length=16, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    level = models.ForeignKey(
        GeographyLevel,
        on_delete=models.PROTECT,
        related_name="areas",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    # Optional representative point (boundary centroid) for mapping.
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["level__rank", "name"]
        verbose_name = "geography"
        verbose_name_plural = "geographies"

    def __str__(self):
        return f"{self.name} ({self.code})"
