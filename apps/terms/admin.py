from django.contrib import admin

from .models import AcademicTerm


@admin.register(AcademicTerm)
class AcademicTermAdmin(admin.ModelAdmin):
    list_display = (
        "year",
        "period",
        "teaching_start_date",
        "teaching_end_date",
        "submission_start_date",
        "submission_end_date",
    )
    list_filter = ("year", "period")
    ordering = ("-year", "period")
