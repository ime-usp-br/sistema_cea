from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from users.mixins import RoleRequiredMixin
from users.models import User

from .forms import AcademicTermForm
from .models import AcademicTerm


class SecretariatTermMixin(RoleRequiredMixin):
    """Restringe a gestão de semestres à Secretaria e ao Administrador."""

    allowed_roles = frozenset({User.Role.SECRETARIAT, User.Role.ADMINISTRATOR})


class AcademicTermListView(SecretariatTermMixin, ListView):
    """Página dedicada da Secretaria para listar os períodos letivos."""

    model = AcademicTerm
    template_name = "terms/term_list.html"
    context_object_name = "terms"

    def get_queryset(self):
        return AcademicTerm.objects.order_by("-year", "-period")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["current_term"] = AcademicTerm.current()
        return context


class AcademicTermCreateView(SecretariatTermMixin, CreateView):
    """Cadastro de um novo semestre pela Secretaria."""

    model = AcademicTerm
    form_class = AcademicTermForm
    template_name = "terms/term_form.html"
    success_url = reverse_lazy("terms:list")

    def form_valid(self, form: AcademicTermForm):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Semestre {self.object} cadastrado com sucesso.",
        )
        return response


class AcademicTermUpdateView(SecretariatTermMixin, UpdateView):
    """Edição de um semestre existente pela Secretaria."""

    model = AcademicTerm
    form_class = AcademicTermForm
    template_name = "terms/term_form.html"
    success_url = reverse_lazy("terms:list")

    def form_valid(self, form: AcademicTermForm):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Semestre {self.object} atualizado com sucesso.",
        )
        return response
