from django.contrib import admin

from .models import Geography, GeographyLevel


@admin.register(GeographyLevel)
class GeographyLevelAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "rank")
    ordering = ("rank",)


@admin.register(Geography)
class GeographyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "level", "parent")
    list_filter = ("level",)
    search_fields = ("code", "name")
    autocomplete_fields = ("parent",)
