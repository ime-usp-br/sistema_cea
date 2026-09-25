from django.contrib import admin

from .models import AcademicTerm


@admin.register(AcademicTerm)
class AcademicTermAdmin(admin.ModelAdmin):
    list_display = (
        "year",
        "period",
        "teaching_start_display",
        "teaching_end_display",
        "submission_start_display",
        "submission_end_display",
    )
    list_filter = ("year", "period")
    ordering = ("-year", "period")

    @admin.display(description="Data inicial")
    def teaching_start_display(self, obj: AcademicTerm):
        return obj.teaching_start_date

    @admin.display(description="Data final")
    def teaching_end_display(self, obj: AcademicTerm):
        return obj.teaching_end_date

    @admin.display(description="Data inicial das inscrições")
    def submission_start_display(self, obj: AcademicTerm):
        return obj.submission_start_date

    @admin.display(description="Data final das inscrições")
    def submission_end_display(self, obj: AcademicTerm):
        return obj.submission_end_date
