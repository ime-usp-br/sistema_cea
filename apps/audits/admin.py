from django.contrib import admin

from .models import (
    DatasetAuditResolution,
    DatasetAuditReview,
    DatasetAuditSubmission,
)


class DatasetAuditReviewInline(admin.StackedInline):
    model = DatasetAuditReview
    extra = 0
    readonly_fields = ("reviewed_at", "created_at")


class DatasetAuditResolutionInline(admin.StackedInline):
    model = DatasetAuditResolution
    extra = 0
    readonly_fields = ("decided_at", "created_at")


@admin.register(DatasetAuditSubmission)
class DatasetAuditSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "application",
        "submitted_by",
        "submission_channel",
        "state",
        "submitted_at",
    )
    list_filter = ("submission_channel", "state", "submitted_at")
    search_fields = ("application__protocol", "external_url", "note")
    readonly_fields = ("submitted_at", "created_at", "updated_at")
    inlines = [DatasetAuditReviewInline, DatasetAuditResolutionInline]


@admin.register(DatasetAuditReview)
class DatasetAuditReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "submission", "reviewer", "outcome", "reviewed_at")
    list_filter = ("outcome", "reviewed_at")
    readonly_fields = ("created_at",)


@admin.register(DatasetAuditResolution)
class DatasetAuditResolutionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "submission",
        "application",
        "resolution",
        "target_term",
        "decided_by",
        "decided_at",
    )
    list_filter = ("resolution", "decided_at")
    readonly_fields = ("created_at",)
