from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from postal.export import export
from postal.views import (
    DatasetView,
    DistrictListView,
    OfficeListView,
    PinLookupView,
    StateListView,
    health,
)
from postal.web import change_source, default_dataset, favicon, lookup

urlpatterns = [
    path("", lookup, name="lookup"),
    path("favicon.ico", favicon),
    path("source/", change_source, name="change_source"),
    path("source/default/", default_dataset, name="default_dataset"),
    path("health/", health),
    path("api/v1/offices/", OfficeListView.as_view(), name="offices"),
    path("api/v1/pincodes/<str:pincode>/", PinLookupView.as_view(), name="pincode"),
    path("api/v1/states/", StateListView.as_view(), name="states"),
    path("api/v1/districts/", DistrictListView.as_view(), name="districts"),
    path("api/v1/dataset/", DatasetView.as_view(), name="dataset"),
    path("api/v1/export/", export, name="export"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
