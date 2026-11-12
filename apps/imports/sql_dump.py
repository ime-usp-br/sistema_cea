"""Leitura e conversão do dump MariaDB do sistema legado.

O dump é gerado pelo ``mysqldump``/``mariadb-dump`` e contém instruções
``INSERT INTO ... VALUES (...)`` com strings escapadas por barra invertida.
Este módulo extrai as tabelas relevantes e monta os registros no formato
consumido pelo :class:`imports.importers.LegacyImporter`.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time
from typing import Any

_ESCAPES = {
    "0": "\0",
    "b": "\b",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "Z": "\x1a",
    "\\": "\\",
    "'": "'",
    '"': '"',
    "%": "%",
    "_": "_",
}

APPLICATION_COLUMNS = [
    "id",
    "semesterID",
    "transfer_pending",
    "protocol",
    "projectResponsible",
    "contactPhone",
    "CPFCNPJ",
    "email",
    "institution",
    "institutionRelationship",
    "mentor",
    "projectPurpose",
    "ppOther",
    "fundingAgency",
    "faOther",
    "knowledgeArea",
    "kaOther",
    "bdName",
    "bdCpfCnpj",
    "bdBankName",
    "bdAgency",
    "bdAccount",
    "bdType",
    "projectTitle",
    "generalAspects",
    "generalObjectives",
    "features",
    "otherFeatures",
    "limitations",
    "storage",
    "conclusions",
    "expectedHelp",
    "created_at",
    "updated_at",
    "serviceType",
    "refundReceipt",
    "refundReceiptData",
    "status",
    "course",
    "dataCollect",
    "deleted",
    "irOther",
    "whatsapp",
]

SEMESTER_COLUMNS = [
    "id",
    "year",
    "period",
    "started_at",
    "finished_at",
    "start_date_enrollments",
    "end_date_enrollments",
    "created_at",
    "updated_at",
]

BANK_SLIP_COLUMNS = [
    "id",
    "applicationID",
    "relativoA",
    "codigoIDBoleto",
    "dataVencimentoBoleto",
    "dataEfetivaPagamento",
    "valorDocumento",
    "valorDesconto",
    "valorEfetivamentePago",
    "statusBoletoBancario",
    "manual_payment_confirmed",
    "manual_payment_confirmed_at",
    "manual_payment_confirmed_by",
    "created_at",
    "updated_at",
]

ATTACHMENT_COLUMNS = [
    "id",
    "name",
    "path",
    "link",
    "applicationID",
    "created_at",
    "updated_at",
]

DEPOSIT_RECEIPT_COLUMNS = [
    "id",
    "name",
    "path",
    "link",
    "applicationID",
    "created_at",
    "updated_at",
]

TRIAGE_COLUMNS = [
    "id",
    "applicationID",
    "date",
    "hour",
    "meetingMode",
    "link",
    "local",
    "decision",
    "note",
    "created_at",
    "updated_at",
    "feedback",
]

CONSULTATION_COLUMNS = list(TRIAGE_COLUMNS)

EVENT_COLUMNS = [
    "id",
    "applicationID",
    "name",
    "description",
    "event_date",
    "created_at",
    "updated_at",
]

_STATUS_MAP = {
    "aguardando agendamento da triagem": "awaiting_screening_scheduling",
    "aguardando resultado da triagem": "awaiting_screening_result",
    "aprovado como projeto": "approved_as_project",
    "aprovado como consulta": "approved_as_consultation",
    "não aprovado": "not_approved",
    "nao aprovado": "not_approved",
    "aguardando agendamento da reunião de consulta": "awaiting_consultation_scheduling",
    "aguardando resultado da reunião de consulta": "awaiting_consultation_result",
}

_FEE_TYPE_MAP = {
    "taxa de inscrição": "application_fee",
    "taxa de inscricao": "application_fee",
    "taxa de inscrição (substituído)": "application_fee",
    "taxa de projeto": "project_fee",
    "taxa de projeto (substituído)": "project_fee",
    "complemento de taxa": "supplement_fee",
}

_BANK_STATE_MAP = {
    "P": "paid",
    "E": "created",
    "V": "requires_review",
    "C": "canceled",
}

_PURPOSE_MAP = {
    "iniciacao cientifica": "undergraduate_research",
    "mestrado": "master",
    "doutorado": "doctorate",
    "livre docencia": "livre_docencia",
    "publicacao": "publication",
    "outra": "other",
    "outro": "other",
}

_AREA_MAP = {
    "tecnologica": "technological",
    "medica ou biologica": "health_biological",
    "social ou humana": "social_human",
    "economica": "economic",
    "outra": "other",
    "outro": "other",
}

_FUNDING_MAP = {
    "fapesp": "fapesp",
    "finep": "finep",
    "cnpq": "cnpq",
    "outra": "other",
    "outro": "other",
}

_TIE_MAP = {
    "estudante": "student",
    "funcionario": "staff",
    "professor": "faculty",
    "outro": "other",
    "outra": "other",
}


def _parse_string(text: str, i: int) -> tuple[str, int]:
    out: list[str] = []
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 1
            if i >= n:
                break
            out.append(_ESCAPES.get(text[i], text[i]))
            i += 1
            continue
        if ch == "'":
            if i + 1 < n and text[i + 1] == "'":
                out.append("'")
                i += 2
                continue
            return "".join(out), i + 1
        out.append(ch)
        i += 1
    raise ValueError("string não terminada")


def _parse_tuple(text: str, i: int) -> tuple[list[Any], int]:
    values: list[Any] = []
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        if text[i] == ")":
            return values, i + 1
        if text[i] == "'":
            value, i = _parse_string(text, i + 1)
            values.append(value)
            continue
        start = i
        while i < n and text[i] not in ",)":
            i += 1
        token = text[start:i].strip()
        if token.upper() == "NULL":
            values.append(None)
        elif re.fullmatch(r"-?\d+", token):
            values.append(int(token))
        elif re.fullmatch(r"-?\d+\.\d+", token):
            values.append(float(token))
        else:
            values.append(token)
    raise ValueError("tupla não terminada")


def _parse_values(text: str) -> list[list[Any]]:
    rows: list[list[Any]] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "(":
            row, i = _parse_tuple(text, i + 1)
            rows.append(row)
        else:
            i += 1
    return rows


def extract_table(sql: str, table: str, columns: list[str]) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"INSERT INTO `" + re.escape(table) + r"` VALUES (.*?);\s*\n",
        re.DOTALL,
    )
    rows: list[dict[str, Any]] = []
    for match in pattern.finditer(sql):
        for values in _parse_values(match.group(1)):
            if len(values) != len(columns):
                raise ValueError(
                    f"{table}: esperava {len(columns)} colunas, veio {len(values)}"
                )
            rows.append(dict(zip(columns, values, strict=True)))
    return rows


def read_dump(path: str) -> dict[str, list[dict[str, Any]]]:
    with open(path, encoding="utf-8") as handle:
        sql = handle.read()
    return {
        "applications": extract_table(sql, "applications", APPLICATION_COLUMNS),
        "semesters": extract_table(sql, "semesters", SEMESTER_COLUMNS),
        "bank_slips": extract_table(sql, "bank_slips", BANK_SLIP_COLUMNS),
        "attachments": extract_table(sql, "attachments", ATTACHMENT_COLUMNS),
        "deposit_receipts": extract_table(
            sql, "deposit_receipts", DEPOSIT_RECEIPT_COLUMNS
        ),
        "triages": extract_table(sql, "triages", TRIAGE_COLUMNS),
        "consultation_meetings": extract_table(
            sql, "consultation_meetings", CONSULTATION_COLUMNS
        ),
        "events": extract_table(sql, "events", EVENT_COLUMNS),
    }


def _normalize(value: Any) -> str:
    text = str(value or "").strip().lower()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_date(value: Any, fallback_year: int | None = None) -> date | None:
    parsed = _parse_datetime(value)
    if parsed is not None:
        return parsed.date()
    text = str(value or "").strip()
    full = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
    if full:
        day, month, year = (int(part) for part in full.groups())
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None
    partial = re.fullmatch(r"(\d{1,2})/(\d{1,2})", text)
    if partial:
        day, month = (int(part) for part in partial.groups())
        try:
            return date(fallback_year or date.today().year, month, day)
        except ValueError:
            return None
    return None


def _parse_time(value: Any) -> time | None:
    text = str(value or "").strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def _bool_yes_no(value: Any) -> bool | None:
    text = _normalize(value)
    if text in {"sim", "s", "true", "1"}:
        return True
    if text in {"nao", "n", "false", "0"}:
        return False
    return None


def _bool_int(value: Any) -> bool:
    return str(value).strip() in {"1", "True", "true"}


def _period(value: Any) -> str:
    return "first" if str(value or "").strip().startswith("1") else "second"


def _modality(value: Any) -> str:
    text = _normalize(value)
    return "consultation" if text.startswith("consulta") else "project"


def _status(value: Any) -> str:
    return _STATUS_MAP.get(_normalize(value), "submitted")


def _fee_type(value: Any) -> str:
    return _FEE_TYPE_MAP.get(_normalize(value), "application_fee")


def _bank_state(value: Any) -> str:
    return _BANK_STATE_MAP.get(str(value or "").strip().upper(), "created")


def _split_csv(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _tie_code(value: str) -> str | None:
    normalized = _normalize(value)
    if normalized in _TIE_MAP:
        return _TIE_MAP[normalized]
    if any(
        token in normalized
        for token in (
            "estudante",
            "aluno",
            "aluna",
            "discente",
            "mestrand",
            "doutorand",
            "pos-gradu",
            "pos gradu",
            "graduand",
            "residente",
        )
    ):
        return "student"
    if any(token in normalized for token in ("professor", "docente", "professora")):
        return "faculty"
    if any(
        token in normalized
        for token in (
            "funcionario",
            "funcionaria",
            "servidor",
            "estatutario",
            "celetista",
            "contrato",
        )
    ):
        return "staff"
    return None


def _catalog_selections(app: dict[str, Any]) -> list[dict[str, Any]]:
    """Converte as categorias legadas em seleções de catálogo."""

    selections: list[dict[str, Any]] = []

    def add(category: str, code: str, other_text: str | None = None) -> None:
        if code and not any(
            item["category"] == category and item["code"] == code
            for item in selections
        ):
            selections.append(
                {"category": category, "code": code, "other_text": other_text}
            )

    def map_csv(
        category: str,
        raw: Any,
        mapping: dict[str, str],
        other_text: Any,
    ) -> None:
        unknown: list[str] = []
        for part in _split_csv(raw):
            code = mapping.get(_normalize(part))
            if code is None:
                unknown.append(part)
            else:
                add(category, code, (str(other_text).strip() or None) if code == "other" else None)
        if unknown:
            text = "; ".join(unknown)
            existing = next(
                (item for item in selections if item["category"] == category and item["code"] == "other"),
                None,
            )
            combined = "; ".join(filter(None, [existing["other_text"] if existing else None, text]))
            add(category, "other", combined or str(other_text).strip() or None)

    map_csv("project_purpose", app.get("projectPurpose"), _PURPOSE_MAP, app.get("ppOther"))
    map_csv("knowledge_area", app.get("knowledgeArea"), _AREA_MAP, app.get("kaOther"))
    map_csv("funding_agency", app.get("fundingAgency"), _FUNDING_MAP, app.get("faOther"))

    raw_tie = str(app.get("institutionRelationship") or "").strip()
    if raw_tie:
        parts = _split_csv(raw_tie)
        mapped = [(_tie_code(part), part) for part in parts]
        if len(parts) > 1 and all(code is not None for code, _ in mapped):
            for code, _part in mapped:
                assert code is not None
                add("institutional_tie", code, (str(app.get("irOther")).strip() or None) if code == "other" else None)
        else:
            code = _tie_code(raw_tie)
            if code is None:
                add("institutional_tie", "other", raw_tie)
            else:
                add(
                    "institutional_tie",
                    code,
                    (str(app.get("irOther")).strip() or None) if code == "other" else None,
                )

    return selections


def _build_payments(
    slips: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    payments: list[dict[str, Any]] = []
    for slip in slips:
        payments.append(
            {
                "fee_type": _fee_type(slip.get("relativoA")),
                "method": "bank_slip",
                "state": _bank_state(slip.get("statusBoletoBancario")),
                "reason": str(slip.get("relativoA") or "Taxa importada"),
                "document_amount": slip.get("valorDocumento"),
                "discount_amount": slip.get("valorDesconto"),
                "paid_amount": slip.get("valorEfetivamentePago"),
                "paid_at": _parse_date(slip.get("dataEfetivaPagamento")),
                "created_at": _parse_datetime(slip.get("created_at")),
                "updated_at": _parse_datetime(slip.get("updated_at")),
                "bank_slip": {
                    "id": slip.get("id"),
                    "reference": str(slip.get("codigoIDBoleto") or ""),
                    "due_date": _parse_date(slip.get("dataVencimentoBoleto")),
                    "bank_status": str(slip.get("statusBoletoBancario") or "E"),
                    "document_amount": slip.get("valorDocumento"),
                    "discount_amount": slip.get("valorDesconto"),
                    "paid_amount": slip.get("valorEfetivamentePago"),
                    "payment_date": _parse_date(slip.get("dataEfetivaPagamento")),
                    "manual_confirmed": _bool_int(slip.get("manual_payment_confirmed")),
                    "manual_confirmed_at": _parse_datetime(
                        slip.get("manual_payment_confirmed_at")
                    ),
                    "manual_confirmed_by": slip.get("manual_payment_confirmed_by"),
                    "created_at": _parse_datetime(slip.get("created_at")),
                    "updated_at": _parse_datetime(slip.get("updated_at")),
                },
            }
        )
    return payments


def _build_triage(row: dict[str, Any], fallback_year: int | None) -> dict[str, Any]:
    feedback = _normalize(row.get("feedback"))
    teacher_feedback = None
    if feedback.startswith("triagem realizada"):
        teacher_feedback = "screening_completed"
    elif feedback.startswith("triagem nao realizada"):
        teacher_feedback = "screening_not_completed"
    decision: str | None = _status(row.get("decision"))
    if _normalize(row.get("decision")) not in _STATUS_MAP:
        decision = None
    return {
        "scheduled_date": _parse_date(row.get("date"), fallback_year),
        "scheduled_time": _parse_time(row.get("hour")),
        "meeting_mode": "in_person" if _normalize(row.get("meetingMode")).startswith("presencial") else "online",
        "virtual_link": row.get("link") or None,
        "place": row.get("local") or None,
        "decision": decision,
        "decision_note": row.get("note") or None,
        "teacher_feedback": teacher_feedback,
        "state": "completed" if decision or teacher_feedback else "scheduled",
        "created_at": _parse_datetime(row.get("created_at")),
        "updated_at": _parse_datetime(row.get("updated_at")),
    }


def _build_consultation(row: dict[str, Any], fallback_year: int | None) -> dict[str, Any]:
    feedback = _normalize(row.get("feedback"))
    teacher_feedback = None
    if feedback.startswith("consulta realizada"):
        teacher_feedback = "consultation_completed"
    elif feedback.startswith("consulta nao realizada"):
        teacher_feedback = "consultation_not_completed"
    decision: str | None = _status(row.get("decision"))
    if _normalize(row.get("decision")) not in _STATUS_MAP:
        decision = None
    return {
        "scheduled_date": _parse_date(row.get("date"), fallback_year),
        "scheduled_time": _parse_time(row.get("hour")),
        "meeting_mode": "in_person" if _normalize(row.get("meetingMode")).startswith("presencial") else "online",
        "virtual_link": row.get("link") or None,
        "place": row.get("local") or None,
        "decision": decision,
        "decision_note": row.get("note") or None,
        "teacher_feedback": teacher_feedback,
        "state": "completed" if decision or teacher_feedback else "scheduled",
        "created_at": _parse_datetime(row.get("created_at")),
        "updated_at": _parse_datetime(row.get("updated_at")),
    }


def _build_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_code": f"legacy.{str(row.get('name') or 'evento').strip()}",
        "description": row.get("description") or row.get("name") or "",
        "occurred_at": _parse_datetime(row.get("event_date")) or _parse_datetime(row.get("created_at")),
        "metadata": {"legacy_id": row.get("id"), "legacy_name": row.get("name")},
    }


def _group(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        app_id = row.get("applicationID")
        if app_id is not None:
            grouped.setdefault(int(app_id), []).append(row)
    return grouped


def build_records(dump: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    semesters = {int(row["id"]): row for row in dump["semesters"]}
    slips = _group(dump["bank_slips"])
    attachments = _group(dump["attachments"])
    deposit_receipts = _group(dump["deposit_receipts"])
    triages = _group(dump["triages"])
    consultations = _group(dump["consultation_meetings"])
    events = _group(dump["events"])

    records: list[dict[str, Any]] = []
    for app in dump["applications"]:
        app_id = int(app["id"])
        semester = semesters.get(int(app["semesterID"])) if app.get("semesterID") else None
        term = None
        fallback_year = None
        if semester:
            fallback_year = int(semester["year"])
            term = {
                "year": semester["year"],
                "period": _period(semester.get("period")),
                "teaching_start_date": _parse_date(semester.get("started_at")),
                "teaching_end_date": _parse_date(semester.get("finished_at")),
                "submission_start_date": _parse_date(semester.get("start_date_enrollments")),
                "submission_end_date": _parse_date(semester.get("end_date_enrollments")),
            }
        if fallback_year is None:
            created = _parse_datetime(app.get("created_at"))
            fallback_year = created.year if created else None

        record: dict[str, Any] = {
            "legacy_id": app_id,
            "protocol": str(app.get("protocol") or "").strip(),
            "modality": _modality(app.get("serviceType")),
            "researcher_name": app.get("projectResponsible") or "",
            "contact_email": app.get("email") or "",
            "contact_phone": app.get("contactPhone") or None,
            "tax_id": app.get("CPFCNPJ") or None,
            "legacy_contact_email": app.get("email") or None,
            "legacy_contact_tax_id": app.get("CPFCNPJ") or None,
            "institution_name": app.get("institution") or None,
            "course_name": app.get("course") or None,
            "mentor_name": app.get("mentor") or None,
            "project_title": app.get("projectTitle") or None,
            "context_summary": app.get("generalAspects") or None,
            "general_objectives": app.get("generalObjectives") or None,
            "variables_and_measurements": app.get("features") or None,
            "contextual_factors": app.get("otherFeatures") or None,
            "sampling_and_limitations": app.get("limitations") or None,
            "data_management_plan": app.get("storage") or None,
            "expected_results": app.get("conclusions") or None,
            "expected_support": app.get("expectedHelp") or None,
            "data_already_collected": _bool_yes_no(app.get("dataCollect")),
            "has_whatsapp": _bool_int(app.get("whatsapp")),
            "wants_refund_receipt": _bool_yes_no(app.get("refundReceipt")) or False,
            "refund_receipt_details": app.get("refundReceiptData") or None,
            "refund_account_holder_name": app.get("bdName") or None,
            "refund_account_holder_tax_id": app.get("bdCpfCnpj") or None,
            "refund_bank_name": app.get("bdBankName") or None,
            "refund_branch_number": app.get("bdAgency") or None,
            "refund_bank_account_number": app.get("bdAccount") or None,
            "refund_bank_account_type": (
                "savings"
                if _normalize(app.get("bdType")).startswith("poup")
                else "checking"
                if app.get("bdType")
                else None
            ),
            "transfer_pending": _bool_int(app.get("transfer_pending")),
            "lifecycle_status": _status(app.get("status")),
            "created_at": _parse_datetime(app.get("created_at")),
            "updated_at": _parse_datetime(app.get("updated_at")),
            "soft_deleted_at": (
                _parse_datetime(app.get("updated_at")) if _bool_int(app.get("deleted")) else None
            ),
            "catalog_options": _catalog_selections(app),
            "payments": _build_payments(slips.get(app_id, [])),
            "triages": [_build_triage(row, fallback_year) for row in triages.get(app_id, [])],
            "consultation_meetings": [
                _build_consultation(row, fallback_year)
                for row in consultations.get(app_id, [])
            ],
            "events": [_build_event(row) for row in events.get(app_id, [])],
            "attachments": [
                {
                    "legacy_path": row.get("path"),
                    "original_filename": row.get("name"),
                    "created_at": _parse_datetime(row.get("created_at")),
                }
                for row in attachments.get(app_id, [])
            ],
            "deposit_receipts": [
                {
                    "legacy_path": row.get("path"),
                    "original_filename": row.get("name"),
                    "created_at": _parse_datetime(row.get("created_at")),
                }
                for row in deposit_receipts.get(app_id, [])
            ],
        }
        if term:
            record["term"] = term
        records.append(record)
    return records
