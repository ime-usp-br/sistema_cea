import factory

from .models import AcademicTerm


class AcademicTermFactory(factory.django.DjangoModelFactory[AcademicTerm]):
    class Meta:
        model = AcademicTerm

    year = factory.Sequence(lambda n: 2025 + n)
    period = factory.Iterator([AcademicTerm.Period.FIRST, AcademicTerm.Period.SECOND])
