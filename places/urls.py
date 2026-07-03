from django.urls import path

from . import views

app_name = "places"

urlpatterns = [
    path("", views.PlaceListView.as_view(), name="list"),
    path("<str:code>/", views.PlaceDetailView.as_view(), name="detail"),
]
