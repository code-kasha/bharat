from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from postal.views import (
    DatasetView,
    DistrictListView,
    OfficeListView,
    PinLookupView,
    StateListView,
    health,
)

urlpatterns = [
    path("health/", health),
    path("api/v1/offices/", OfficeListView.as_view(), name="offices"),
    path("api/v1/pincodes/<str:pincode>/", PinLookupView.as_view(), name="pincode"),
    path("api/v1/states/", StateListView.as_view(), name="states"),
    path("api/v1/districts/", DistrictListView.as_view(), name="districts"),
    path("api/v1/dataset/", DatasetView.as_view(), name="dataset"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
