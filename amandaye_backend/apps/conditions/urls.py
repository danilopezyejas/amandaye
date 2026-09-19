from django.urls import path

from .views import ConditionsView, StationsView

app_name = "conditions"
urlpatterns = [
    path("", ConditionsView.as_view(), name="index"),
    path("stations/", StationsView.as_view(), name="stations"),
]
