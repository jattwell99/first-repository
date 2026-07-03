from django.contrib import admin

from .models import (
    GvaPerHead,
    GvaValue,
    Industry,
    PopulationValue,
    PopulationVintage,
    PriceBasis,
)


@admin.register(Industry)
class IndustryAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(PriceBasis)
class PriceBasisAdmin(admin.ModelAdmin):
    list_display = ("code", "name")


@admin.register(GvaValue)
class GvaValueAdmin(admin.ModelAdmin):
    list_display = ("geography", "industry", "price_basis", "year", "value_gbp_million")
    list_filter = ("price_basis", "industry", "year")
    search_fields = ("geography__code", "geography__name")


@admin.register(PopulationVintage)
class PopulationVintageAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "reference_date")


@admin.register(PopulationValue)
class PopulationValueAdmin(admin.ModelAdmin):
    list_display = ("geography", "vintage", "year", "population")
    list_filter = ("vintage", "year")
    search_fields = ("geography__code", "geography__name")


@admin.register(GvaPerHead)
class GvaPerHeadAdmin(admin.ModelAdmin):
    list_display = ("geography", "year", "gva_per_head_gbp", "population", "vintage")
    list_filter = ("year", "vintage")
    search_fields = ("geography__code", "geography__name")
