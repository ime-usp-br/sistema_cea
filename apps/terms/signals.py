from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AcademicTerm


@receiver(post_save, sender=AcademicTerm)
def migrate_pending_applications_on_new_term(sender, instance, created, **kwargs):
    """Conclui transferências pendentes ao criar um novo período letivo.

    Porta do ``SemesterController::migratePendingApplications`` do legado:
    só dispara na **criação** do período (``created=True``), garantindo que
    editar um período não remigre inscrições já transferidas.
    """
    if not created:
        return
    from applications.services import TermTransferService

    TermTransferService().migrate_pending_applications(instance)
