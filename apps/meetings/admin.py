from django.contrib import admin

from .models import ConsultationMeeting, ProjectScreening


@admin.register(ProjectScreening)
class ProjectScreeningAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "application",
        "scheduled_date",
        "scheduled_time",
        "meeting_mode",
        "state",
        "decision",
        "teacher_feedback",
    )
    list_filter = ("meeting_mode", "state", "decision", "teacher_feedback", "scheduled_date")
    search_fields = ("application__protocol", "virtual_link", "place")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ConsultationMeeting)
class ConsultationMeetingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "application",
        "scheduled_date",
        "scheduled_time",
        "meeting_mode",
        "state",
        "decision",
        "teacher_feedback",
    )
    list_filter = ("meeting_mode", "state", "decision", "teacher_feedback", "scheduled_date")
    search_fields = ("application__protocol", "virtual_link", "place")
    readonly_fields = ("created_at", "updated_at")
