from django.urls import path

from .views import (
    AcademicTermCreateView,
    AcademicTermListView,
    AcademicTermUpdateView,
)

app_name = "terms"

urlpatterns = [
    path("semestres/", AcademicTermListView.as_view(), name="list"),
    path("semestres/novo/", AcademicTermCreateView.as_view(), name="create"),
    path(
        "semestres/<int:pk>/editar/",
        AcademicTermUpdateView.as_view(),
        name="update",
    ),
]
