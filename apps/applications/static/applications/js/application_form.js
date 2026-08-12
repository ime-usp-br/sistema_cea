/* Validação client-side da ficha de inscrição (CEA).
 *
 * Espelha exatamente as regras de `ApplicationForm.clean()` em
 * apps/applications/forms.py para feedback imediato, sem round-trip ao
 * backend. Mensagens idênticas às validações do servidor.
 */
(function () {
    "use strict";

    var form = document.getElementById("form-inscricao");
    if (!form) return;

    var MENTOR_PURPOSES = ["undergraduate_research", "master", "doctorate"];
    var PROJECT_FIELDS = [
        "project_title",
        "context_summary",
        "general_objectives",
        "variables_and_measurements",
        "contextual_factors",
        "sampling_and_limitations",
        "data_management_plan",
        "expected_results",
        "expected_support",
    ];
    var REFUND_FIELDS = [
        "refund_receipt_details",
        "refund_account_holder_name",
        "refund_account_holder_tax_id",
        "refund_bank_name",
        "refund_branch_number",
        "refund_bank_account_number",
        "refund_bank_account_type",
    ];
    var LIVE_FIELDS = ["modality", "catalog_options", "wants_refund_receipt", "data_already_collected",
        "contact_email", "contact_email_confirmation", "catalog_other_text", "mentor_name",
        "mentor_declaration_accepted", "data_use_authorization_accepted"];

    var MESSAGES = {
        modality: "Escolha a modalidade do serviço.",
        researcher_name: "Informe o nome do pesquisador.",
        contact_email: "Informe um e-mail válido.",
        contact_email_confirmation: "Os e-mails não conferem.",
        tax_id: "Informe um CPF ou CNPJ válido.",
        data_use_authorization_accepted: "É necessário autorizar o uso dos dados.",
        catalog_options: "Selecione apenas uma opção por seção.",
        catalog_other_text: "Informe o texto complementar para a opção \u201cOutro\u201d.",
        data_already_collected: "Para solicitar assessoria em Projeto é necessário já ter coletado os dados.",
        mentor_name: "Informe o nome do orientador.",
        mentor_declaration_accepted: "A declaração de presença do orientador é obrigatória.",
        refund_field: "Este campo é obrigatório quando há recibo de reembolso.",
        project_field: "Este campo é obrigatório para projetos.",
    };

    var attempted = false;

    function $(id) {
        return document.getElementById(id);
    }

    function radioValue(name) {
        var checked = form.querySelector('input[name="' + name + '"]:checked');
        return checked ? checked.value : "";
    }

    function isChecked(name) {
        var el = form.querySelector('input[name="' + name + '"]');
        return !!el && el.checked;
    }

    function valueOf(name) {
        var el = form.querySelector('[name="' + name + '"]');
        if (!el) return "";
        return (el.value || "").trim();
    }

    function checkedCatalog() {
        return Array.prototype.slice.call(
            form.querySelectorAll('input[name="catalog_options"]:checked')
        );
    }

    function onlyDigits(value) {
        return (value || "").replace(/\D/g, "");
    }

    function isEmail(value) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    }

    function isCpfValid(digits) {
        if (/^(\d)\1{10}$/.test(digits)) return false;
        function calc(base, start) {
            var total = 0;
            for (var i = 0; i < base.length; i++) {
                total += parseInt(base.charAt(i), 10) * (start - i);
            }
            var rest = total % 11;
            return rest < 2 ? 0 : 11 - rest;
        }
        var first = calc(digits.slice(0, 9), 10);
        var second = calc(digits.slice(0, 9) + String(first), 11);
        return digits.slice(9) === String(first) + String(second);
    }

    function isCnpjValid(digits) {
        if (/^(\d)\1{13}$/.test(digits)) return false;
        var w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
        var w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
        function calc(base, weights) {
            var total = 0;
            for (var i = 0; i < base.length; i++) {
                total += parseInt(base.charAt(i), 10) * weights[i];
            }
            var rest = total % 11;
            return rest < 2 ? 0 : 11 - rest;
        }
        var first = calc(digits.slice(0, 12), w1);
        var second = calc(digits.slice(0, 12) + String(first), w2);
        return digits.slice(12) === String(first) + String(second);
    }

    function isValidTaxId(value) {
        var digits = onlyDigits(value);
        if (digits.length === 11) return isCpfValid(digits);
        if (digits.length === 14) return isCnpjValid(digits);
        return false;
    }

    function validate() {
        var errors = {};
        var modality = radioValue("modality");

        if (!modality) errors.modality = MESSAGES.modality;
        if (!valueOf("researcher_name")) errors.researcher_name = "Informe o nome do pesquisador.";
        if (!valueOf("contact_email")) {
            errors.contact_email = "Informe um e-mail de contato.";
        } else if (!isEmail(valueOf("contact_email"))) {
            errors.contact_email = MESSAGES.contact_email;
        }
        if (
            valueOf("contact_email_confirmation") &&
            valueOf("contact_email_confirmation") !== valueOf("contact_email")
        ) {
            errors.contact_email_confirmation = MESSAGES.contact_email_confirmation;
        }
        if (valueOf("tax_id") && !isValidTaxId(valueOf("tax_id"))) {
            errors.tax_id = MESSAGES.tax_id;
        }
        if (!isChecked("data_use_authorization_accepted")) {
            errors.data_use_authorization_accepted = MESSAGES.data_use_authorization_accepted;
        }

        var catalog = checkedCatalog();
        var byCategory = {};
        for (var i = 0; i < catalog.length; i++) {
            var cat = catalog[i].getAttribute("data-category");
            byCategory[cat] = (byCategory[cat] || 0) + 1;
        }
        for (var key in byCategory) {
            if (Object.prototype.hasOwnProperty.call(byCategory, key) && byCategory[key] > 1) {
                errors.catalog_options = MESSAGES.catalog_options;
                break;
            }
        }
        var hasOther = catalog.some(function (cb) {
            return cb.getAttribute("data-other") === "true";
        });
        if (hasOther && !valueOf("catalog_other_text")) {
            errors.catalog_other_text = MESSAGES.catalog_other_text;
        }

        if (modality === "project") {
            if (radioValue("data_already_collected") !== "true") {
                errors.data_already_collected = MESSAGES.data_already_collected;
            }
            PROJECT_FIELDS.forEach(function (name) {
                if (!valueOf(name)) errors[name] = MESSAGES.project_field;
            });
        }

        var requiresMentor = catalog.some(function (cb) {
            return (
                cb.getAttribute("data-category") === "project_purpose" &&
                MENTOR_PURPOSES.indexOf(cb.getAttribute("data-code")) !== -1
            );
        });
        if (requiresMentor) {
            if (!valueOf("mentor_name")) errors.mentor_name = MESSAGES.mentor_name;
            if (!isChecked("mentor_declaration_accepted")) {
                errors.mentor_declaration_accepted = MESSAGES.mentor_declaration_accepted;
            }
        }

        if (radioValue("wants_refund_receipt") === "true") {
            REFUND_FIELDS.forEach(function (name) {
                if (!valueOf(name)) errors[name] = MESSAGES.refund_field;
            });
            if (valueOf("refund_account_holder_tax_id") && !isValidTaxId(valueOf("refund_account_holder_tax_id"))) {
                errors.refund_account_holder_tax_id = MESSAGES.tax_id;
            }
        }

        return errors;
    }

    function fieldElement(name) {
        return form.querySelector('[name="' + name + '"]');
    }

    function clearErrors() {
        form.querySelectorAll(".js-error").forEach(function (node) {
            node.parentNode.removeChild(node);
        });
        form.querySelectorAll(".has-error").forEach(function (node) {
            node.classList.remove("has-error");
        });
    }

    function removeError(name) {
        form.querySelectorAll('.js-error[data-for="' + name + '"]').forEach(function (node) {
            node.parentNode.removeChild(node);
        });
        var el = fieldElement(name);
        if (!el) return;
        var row = el.closest(".form-row");
        if (row) row.classList.remove("has-error");
        var block = el.closest(".form-block");
        if (block) block.classList.remove("has-error");
    }

    function errorContainerFor(el) {
        var row = el.closest ? el.closest(".form-row") : null;
        if (row) return { container: row.querySelector(".form-row-control") || row, row: row };
        var block = el.closest ? el.closest(".form-block") : null;
        if (block) return { container: block, block: block };
        return { container: el.parentNode };
    }

    function markField(name, message) {
        var el = fieldElement(name);
        if (!el) return;
        var target = errorContainerFor(el);
        var msg = document.createElement("div");
        msg.className = "field-errors js-error";
        msg.setAttribute("data-for", name);
        msg.textContent = message;
        target.container.appendChild(msg);
        if (target.row) target.row.classList.add("has-error");
        if (target.block) target.block.classList.add("has-error");
    }

    function updateSummary(count) {
        var summary = $("form-error-summary");
        if (!summary) return;
        if (count > 0) {
            summary.style.display = "block";
            summary.textContent =
                count === 1
                    ? "Há 1 campo para corrigir antes de enviar."
                    : "Há " + count + " campos para corrigir antes de enviar.";
        } else {
            summary.style.display = "none";
            summary.textContent = "";
        }
    }

    function renderErrors(errors, scroll) {
        clearErrors();
        var keys = Object.keys(errors);
        updateSummary(keys.length);
        if (!keys.length) return;

        keys.forEach(function (name) {
            markField(name, errors[name]);
        });

        if (scroll) {
            var first = form.querySelector(".js-error");
            if (first) {
                first.scrollIntoView({ behavior: "smooth", block: "center" });
                var scope = first.closest(".form-row-control") || first.closest(".form-block");
                if (scope) {
                    var input = scope.querySelector("input,textarea,select");
                    if (input) input.focus();
                }
            }
        }
    }

    function updateFieldError(name, message) {
        removeError(name);
        if (message) markField(name, message);
    }

    form.addEventListener("submit", function (event) {
        attempted = true;
        var errors = validate();
        renderErrors(errors, true);
        var valid = Object.keys(errors).length === 0;
        form.dataset.ceaValid = String(valid);
        if (!valid) {
            event.preventDefault();
        }
    });

    function onFieldInteraction(event) {
        var el = event.target;
        if (!el || !el.name) return;
        if (attempted) {
            renderErrors(validate(), false);
            return;
        }
        if (LIVE_FIELDS.indexOf(el.name) === -1) return;
        var errors = validate();
        updateFieldError(el.name, errors[el.name]);
        if (el.name === "contact_email") {
            updateFieldError("contact_email_confirmation", errors.contact_email_confirmation);
        }
        if (el.name === "catalog_options") {
            updateFieldError("catalog_other_text", errors.catalog_other_text);
            updateFieldError("mentor_name", errors.mentor_name);
            updateFieldError("mentor_declaration_accepted", errors.mentor_declaration_accepted);
        }
        if (el.name === "wants_refund_receipt") {
            REFUND_FIELDS.forEach(function (name) {
                updateFieldError(name, errors[name]);
            });
        }
        if (el.name === "modality") {
            updateFieldError("data_already_collected", errors.data_already_collected);
            PROJECT_FIELDS.forEach(function (name) {
                updateFieldError(name, errors[name]);
            });
            updateFieldError("mentor_name", errors.mentor_name);
            updateFieldError("mentor_declaration_accepted", errors.mentor_declaration_accepted);
        }
    }

    form.addEventListener("change", onFieldInteraction);
    form.addEventListener("input", onFieldInteraction);
})();
