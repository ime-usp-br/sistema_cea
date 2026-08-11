from django.db import models


class AcademicTerm(models.Model):
    """Representa períodos letivos."""

    class Period(models.TextChoices):
        FIRST = "first", "Primeiro Semestre"
        SECOND = "second", "Segundo Semestre"

    year = models.SmallIntegerField()
    period = models.CharField(max_length=10, choices=Period.choices)
    teaching_start_date = models.DateField(null=True, blank=True)
    teaching_end_date = models.DateField(null=True, blank=True)
    submission_start_date = models.DateField(null=True, blank=True)
    submission_end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "academic_terms"
        ordering = ["-year", "period"]
        constraints = [
            models.UniqueConstraint(
                fields=["year", "period"],
                name="uq_academic_terms_year_period",
            ),
            models.CheckConstraint(
                condition=models.Q(period__in=["first", "second"]),
                name="chk_academic_terms_period",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.year} - {self.get_period_display()}"
