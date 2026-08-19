from django.conf import settings


def enable_local_login(request) -> dict[str, bool]:
    """Expose the ENABLE_LOCAL_LOGIN flag to templates.

    Allows the login template to conditionally hide the local
    (username/password) form when only the Senha Única USP is desired.
    """
    return {'enable_local_login': settings.ENABLE_LOCAL_LOGIN}


def nav_context(request) -> dict:
    """Expose role flags and the active navigation section to templates.

    Allows the global navigation bar to render menus per user role and
    highlight the current section without duplicating permission checks
    inline in templates.
    """
    user = getattr(request, "user", None)
    is_authenticated = bool(user is not None and getattr(user, "is_authenticated", False))

    context = {
        "is_authenticated_user": is_authenticated,
        "is_candidate": False,
        "is_teacher": False,
        "is_secretariat": False,
        "is_admin": False,
        "nav_active": "",
    }

    if not is_authenticated:
        return context

    from users.models import User

    role = getattr(user, "role", None)
    is_admin = role == User.Role.ADMINISTRATOR or getattr(user, "is_superuser", False)

    context.update(
        {
            "is_candidate": role == User.Role.CANDIDATE,
            "is_teacher": role == User.Role.TEACHER,
            "is_secretariat": role == User.Role.SECRETARIAT,
            "is_admin": is_admin,
        }
    )

    resolver = getattr(request, "resolver_match", None)
    if resolver is not None:
        context["nav_active"] = _active_section(
            resolver.app_name or "", resolver.url_name or ""
        )
    return context


def _active_section(app_name: str, url_name: str) -> str:
    """Map a resolved route to the navigation section that should be highlighted.

    The URL name alone is ambiguous (e.g. "detail" exists in several apps), so
    the pair (app_name, url_name) is mapped to the section label.
    """
    mapping = {
        "applications.dashboard": "dashboard",
        "applications.create": "dashboard",
        "applications.detail": "dashboard",
        "applications.transfer_semester": "dashboard",
        "audits.teacher_queue": "audit_queue",
        "audits.review": "audit_queue",
        "audits.resolution_list": "audit_rejected",
        "audits.resolve": "audit_rejected",
        "meetings.queue": "meetings",
        "meetings.screening_schedule": "meetings",
        "meetings.consultation_schedule": "meetings",
        "meetings.screening_decision": "meetings",
        "meetings.consultation_decision": "meetings",
        "payments.refund_list": "refunds",
        "payments.refund_create": "refunds",
        "payments.refund_action": "refunds",
        "payments.overdue_list": "overdue",
        "payments.overdue_remind": "overdue",
        "payments.manual_confirmation": "payments",
        "imports.claim_queue": "claims",
        "imports.claim_approve": "claims",
        "reports.financial_report": "reports_financial",
        "reports.financial_csv": "reports_financial",
        "reports.financial_xlsx": "reports_financial",
        "reports.audit_report": "reports_audit",
        "pix.detail": "payments",
        "pix.generate": "payments",
        "bank_slips.detail": "payments",
        "bank_slips.generate": "payments",
        "bank_slips.admin_generate": "payments",
    }
    return mapping.get(f"{app_name}.{url_name}", "")
