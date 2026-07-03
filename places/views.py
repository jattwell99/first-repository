"""Views for browsing places and their GVA per head."""
from django.db.models import Max, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from economy.models import GvaPerHead
from geography.models import Geography


class PlaceListView(ListView):
    """List places with their latest GVA per head, ranked high to low."""

    template_name = "places/place_list.html"
    context_object_name = "places"

    def get_queryset(self):
        level = self.request.GET.get("level", "LAD")

        # Each place's most recent year that has a per-head figure.
        latest_year = (
            GvaPerHead.objects.filter(geography=OuterRef("pk"))
            .order_by("-year")
            .values("year")[:1]
        )
        latest = (
            GvaPerHead.objects.filter(
                geography=OuterRef("pk"), year=Subquery(latest_year)
            )
            .values("gva_per_head_gbp")[:1]
        )

        qs = (
            Geography.objects.filter(level__code=level)
            .select_related("level", "parent")
            .annotate(
                latest_year=Subquery(latest_year),
                latest_per_head=Subquery(latest),
            )
        )
        # Rank places that have a figure first (descending), then the rest.
        return qs.order_by("-latest_per_head", "name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["level"] = self.request.GET.get("level", "LAD")
        ctx["levels"] = (
            Geography.objects.values_list("level__code", "level__name")
            .distinct()
            .order_by("level__rank")
        )
        return ctx


class PlaceDetailView(DetailView):
    """A single place with its full GVA-per-head time series."""

    template_name = "places/place_detail.html"
    context_object_name = "place"
    slug_field = "code"
    slug_url_kwarg = "code"

    def get_object(self, queryset=None):
        return get_object_or_404(
            Geography.objects.select_related("level", "parent"),
            code=self.kwargs["code"],
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["series"] = self.object.gva_per_head.order_by("-year")
        ctx["latest"] = ctx["series"].first()
        return ctx
