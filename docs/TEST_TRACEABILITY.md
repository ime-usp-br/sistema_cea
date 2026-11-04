# Matriz de rastreabilidade — cenários × testes

Gerada a partir de `docs/TEST_SCENARIOS.md` e dos arquivos `apps/**/test*.py`.
Atualize-a com `python scripts/gen_test_traceability.py` (ou manualmente) ao mover/renomear testes.

| ID | Cenário | Arquivo::teste | Status |
|---|---|---|---|
| TS-AUTH-001 | Página inicial exige login | — | Sem teste |
| TS-AUTH-002 | Cadastro de candidato externo | `apps/users/test_signup_verification.py::test_TS_AUTH_002_cadastro_bloqueia_login_ate_confirmar`<br>`apps/users/test_signup_verification.py::test_TS_AUTH_002_token_invalido_e_expirado`<br>`apps/users/test_signup_verification.py::test_TS_AUTH_002_email_duplicado_rejeitado`<br>`apps/users/test_signup_verification.py::test_TS_AUTH_002_token_uso_unico`<br>`apps/users/test_signup_verification.py::test_TS_AUTH_002_reenvio_nao_revela_email` | Coberto |
| TS-AUTH-003 | Login com e-mail e senha | — | Sem teste |
| TS-AUTH-004 | Login via Senha Única | — | Sem teste |
| TS-AUTH-005 | Vinculação de identidade existente | `apps/users/tests.py::test_TS_AUTH_005_vincula_identidade_a_usuario_existente_sem_duplicar` | Coberto |
| TS-AUTH-006 | Recuperação de senha | `apps/users/test_signup_verification.py::test_TS_AUTH_006_recuperacao_de_senha_templates_resolvem` | Coberto |
| TS-AUTH-007 | Usuário inativo | — | Sem teste |
| TS-APP-001 | Painel mostra apenas inscrições próprias | `apps/applications/tests.py::test_TS_APP_001_painel_mostra_apenas_inscricoes_proprias` | Coberto |
| TS-APP-002 | Criação de Projeto por candidato | `apps/applications/tests.py::test_TS_APP_002_criacao_projeto_por_candidato` | Coberto |
| TS-APP-003 | Criação de Consulta por candidato | `apps/applications/tests.py::test_TS_APP_003_criacao_consulta_por_candidato` | Coberto |
| TS-APP-004 | Protocolo único | `apps/applications/tests.py::test_TS_APP_004_protocolo_unico_com_9_digitos` | Coberto |
| TS-APP-005 | Campos obrigatórios | `apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_005_maximo_uma_opcao_por_secao_falha`<br>`apps/applications/tests.py::test_TS_APP_005_campos_obrigatorios` | Coberto |
| TS-APP-006 | Validação de CPF/CNPJ | `apps/applications/tests.py::test_TS_APP_006_validacao_de_cpf_cnpj` | Coberto |
| TS-APP-007 | Opções de catálogo com “Outro” | `apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_007_outro_exige_texto_complementar_falha`<br>`apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_007_outro_com_texto_complementar_passa`<br>`apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_007_sem_opcao_outro_nao_exige_texto_passa`<br>`apps/applications/tests.py::test_TS_APP_007_opcoes_de_catalogo_com_outro` | Coberto |
| TS-APP-008 | Anexos de inscrição | `apps/applications/tests.py::test_TS_APP_008_anexos_de_inscricao` | Coberto |
| TS-APP-009 | Anexos acima do limite | `apps/applications/tests/test_application_form.py::test_TS_APP_009b_soma_de_multiplos_anexos_excede_limite`<br>`apps/applications/tests/test_application_form.py::test_TS_APP_009c_soma_de_multiplos_anexos_dentro_do_limite`<br>`apps/applications/tests/test_application_form.py::test_TS_APP_009d_anexo_exatamente_no_limite_e_aceito`<br>`apps/applications/tests.py::test_TS_APP_009_anexos_acima_do_limite` | Coberto |
| TS-APP-010 | Exclusão lógica | `apps/applications/tests.py::test_TS_APP_010_exclusao_logica` | Coberto |
| TS-APP-011 | Listagem global e payload válido | `apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_011_projeto_valido_completo_passa`<br>`apps/applications/tests.py::test_TS_APP_011_lista_todas_inscricoes_requer_secretaria` | Coberto |
| TS-APP-012 | Projeto com dados não coletados | `apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_012_projeto_dados_nao_coletados_falha` | Coberto |
| TS-APP-013 | Projeto sem campo descritivo | `apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_013_projeto_falta_campo_descritivo_falha` | Coberto |
| TS-APP-014 | Orientador e declaração | `apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_014_projeto_sem_nome_orientador_falha`<br>`apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_014_projeto_sem_declaracao_orientador_falha`<br>`apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_014_sem_finalidade_academica_nao_exige_mentor_passa` | Coberto |
| TS-APP-015 | Consulta válida completa | `apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_015_consulta_valida_completa_passa` | Coberto |
| TS-APP-016 | Consulta sem autorização de dados | `apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_016_consulta_sem_autorizacao_dados_falha` | Coberto |
| TS-APP-017 | Reembolso completo | `apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_017_reembolso_completo_passa` | Coberto |
| TS-APP-018 | Reembolso com dados incompletos | `apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_018_reembolso_omitindo_campo_bancario_falha`<br>`apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_018_reembolso_omitindo_detalhes_recibo_falha` | Coberto |
| TS-APP-019 | CPF bancário inválido | `apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_019_cpf_bancario_invalido_falha` | Coberto |
| TS-APP-020 | Sem reembolso e dados bancários vazios | `apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_020_sem_reembolso_dados_bancarios_vazios_passa` | Coberto |
| TS-APP-022 | Regressão de payload representativo | `apps/applications/tests/test_massive_application_combinations.py::test_TS_APP_022_regressao_payload_representativo_aceito` | Coberto |
| TS-APP-024 | Inscrição fora do período | `apps/applications/tests/test_application_form.py::test_TS_APP_024_bloqueio_inscricao_projeto_fora_do_periodo`<br>`apps/applications/tests/test_application_form.py::test_TS_APP_024_consulta_nao_e_bloqueada_fora_do_periodo` | Coberto |
| TS-AUD-001 | Projeto com dono exige auditoria | `apps/audits/tests.py::test_TS_AUD_001_projeto_com_dono_exige_auditoria` | Coberto |
| TS-AUD-002 | Projeto importado sem dono não entra em auditoria | `apps/audits/tests.py::test_TS_AUD_002_projeto_importado_sem_dono_nao_entra_em_auditoria` | Coberto |
| TS-AUD-003 | Envio de arquivo válido | `apps/applications/tests/test_journey_pagamento_auditoria.py::test_TS_AUD_003_jornada_envio_por_arquivo_e_fila_docente`<br>`apps/audits/tests.py::test_TS_AUD_003_envio_de_arquivo_valido` | Coberto |
| TS-AUD-004 | Envio de arquivo acima de 10 MB | `apps/audits/tests.py::test_TS_AUD_004_envio_de_arquivo_acima_de_10mb` | Coberto |
| TS-AUD-005 | Envio de link externo | `apps/applications/tests/test_journey_pagamento_auditoria.py::test_TS_AUD_005_jornada_envio_por_link_externo`<br>`apps/audits/tests.py::test_TS_AUD_005_envio_de_link_externo` | Coberto |
| TS-AUD-006 | Link externo inválido | `apps/audits/tests.py::test_TS_AUD_006_link_externo_invalido` | Coberto |
| TS-AUD-007 | Link sem declaração de acesso | `apps/audits/tests.py::test_TS_AUD_007_link_sem_declaracao_de_acesso` | Coberto |
| TS-AUD-008 | Submissão não aceita arquivo e link simultâneos | `apps/audits/tests.py::test_TS_AUD_008_submissao_nao_aceita_arquivo_e_link_simultaneos` | Coberto |
| TS-AUD-009 | Docente solicita correção | `apps/applications/tests/test_journey_pagamento_auditoria.py::test_TS_AUD_009_jornada_docente_solicita_correcao`<br>`apps/audits/tests.py::test_TS_AUD_009_docente_solicita_correcao` | Coberto |
| TS-AUD-010 | Candidato corrige e reenvia | `apps/audits/tests.py::test_TS_AUD_010_candidato_corrige_e_reenvia` | Coberto |
| TS-AUD-011 | Docente aprova auditoria | `apps/applications/tests/test_journey_pagamento_auditoria.py::test_TS_AUD_011_jornada_docente_aprova_cria_taxa_80`<br>`apps/audits/tests.py::test_TS_AUD_011_docente_aprova_auditoria` | Coberto |
| TS-AUD-012 | Docente rejeita auditoria | `apps/applications/tests/test_journey_pagamento_auditoria.py::test_TS_AUD_012_jornada_docente_rejeita_para_secretaria`<br>`apps/audits/tests.py::test_TS_AUD_012_docente_rejeita_auditoria` | Coberto |
| TS-AUD-013 | Secretaria converte em Consulta | `apps/audits/tests.py::test_TS_AUD_013_secretaria_converte_em_consulta` | Coberto |
| TS-AUD-014 | Secretaria rejeita inscrição | `apps/audits/tests.py::test_TS_AUD_014_secretaria_rejeita_inscricao` | Coberto |
| TS-AUD-015 | Secretaria transfere de período | `apps/audits/tests.py::test_TS_AUD_015_secretaria_transfere_de_periodo` | Coberto |
| TS-AUD-016 | Auditoria habilitada após resgate | `apps/audits/test_enable_audit.py::test_TS_AUD_016_habilitar_auditoria_pela_ficha`<br>`apps/audits/test_enable_audit.py::test_TS_AUD_016_candidato_nao_pode_habilitar`<br>`apps/audits/tests.py::test_TS_AUD_016_auditoria_habilitada_apos_resgate` | Coberto |
| TS-AUD-017 | Link inacessível | `apps/audits/tests.py::test_TS_AUD_017_link_inacessivel_docente_solicita_correcao`<br>`apps/audits/tests.py::test_TS_AUD_017b_link_inacessivel_docente_rejeita` | Coberto |
| TS-AUD-018 | Download de arquivo de auditoria | `apps/audits/tests.py::test_TS_AUD_018_docente_baixa_arquivo_da_submissao`<br>`apps/audits/tests.py::test_TS_AUD_018b_secretaria_tambem_baixa_arquivo`<br>`apps/audits/tests.py::test_TS_AUD_018c_candidato_nao_pode_baixar_arquivo`<br>`apps/audits/tests.py::test_TS_AUD_018d_submissao_sem_arquivo_retorna_404` | Coberto |
| TS-FEE-001 | Taxa de inscrição de Projeto | `apps/payments/tests.py::test_TS_FEE_001_taxa_de_projeto_apos_auditoria_aprovada` | Coberto |
| TS-FEE-002 | Taxa de Consulta na submissão | `apps/payments/tests.py::test_TS_FEE_002_taxa_de_consulta_na_submissao` | Coberto |
| TS-FEE-003 | Taxa de projeto sem crédito | `apps/payments/tests.py::test_TS_FEE_003_taxa_de_projeto_sem_credito` | Coberto |
| TS-FEE-004 | Taxa de projeto com crédito de Consulta paga | `apps/payments/tests.py::test_TS_FEE_004_taxa_de_projeto_com_credito_de_consulta` | Coberto |
| TS-FEE-005 | Projeto pago aprovado como Consulta | `apps/payments/tests.py::test_TS_FEE_005_projeto_pago_aprovado_como_consulta` | Coberto |
| TS-FEE-006 | Projeto não pago aprovado como Consulta | `apps/payments/tests.py::test_TS_FEE_006_projeto_nao_pago_convertido_em_consulta` | Coberto |
| TS-FEE-007 | Valor final consistente | `apps/payments/tests.py::test_TS_FEE_007_valor_final_consistente` | Coberto |
| TS-FEE-008 | Isenção de taxa | `apps/payments/tests.py::test_TS_FEE_008_isencao_de_taxa` | Coberto |
| TS-PAY-001 | Candidato escolhe Pix | `apps/applications/tests/test_journey_pagamento_auditoria.py::test_TS_PAY_001_pagina_de_pagamento_exibe_taxa_e_aceita_pix`<br>`apps/payments/tests.py::test_TS_PAY_001_candidato_escolhe_pix` | Coberto |
| TS-PAY-002 | Candidato escolhe boleto | `apps/applications/tests/test_journey_pagamento_auditoria.py::test_TS_PAY_002_pagina_de_pagamento_aceita_boleto`<br>`apps/payments/tests.py::test_TS_PAY_002_candidato_escolhe_boleto` | Coberto |
| TS-PAY-003 | Troca de Pix para boleto | `apps/payments/tests.py::test_TS_PAY_003_troca_de_pix_para_boleto` | Coberto |
| TS-PAY-004 | Troca de boleto para Pix | `apps/payments/tests.py::test_TS_PAY_004_troca_de_boleto_para_pix` | Coberto |
| TS-PAY-005 | Um instrumento ativo por taxa | `apps/payments/tests.py::test_TS_PAY_005_um_instrumento_ativo_por_taxa` | Coberto |
| TS-PAY-006 | Instrumento pago não pode ser substituído | `apps/payments/tests.py::test_TS_PAY_006_instrumento_pago_nao_pode_ser_substituido` | Coberto |
| TS-PAY-007 | Pix expirado permite nova geração | `apps/payments/tests.py::test_TS_PAY_007_pix_expirado_permite_nova_geracao` | Coberto |
| TS-PAY-008 | Pagamento confirmado libera fluxo | `apps/payments/tests.py::test_TS_PAY_008_pagamento_confirmado_libera_fluxo` | Coberto |
| TS-PAY-009 | Candidato paga Taxa de Projeto/Complemento pela UI | `apps/payments/test_fee_selection_ui.py::test_TS_PAY_009_projeto_paga_taxa_de_projeto_pela_ui`<br>`apps/payments/test_fee_selection_ui.py::test_TS_PAY_009_taxa_pendente_e_a_selecionada_por_padrao`<br>`apps/payments/test_fee_selection_ui.py::test_TS_PAY_009_paga_complemento_de_taxa_na_consulta` | Coberto |
| TS-PAY-010 | Taxa já paga não reabre | `apps/payments/test_fee_selection_ui.py::test_TS_PAY_010_taxa_paga_nao_reabre` | Coberto |
| TS-PAY-011 | Taxa de outra inscrição | `apps/payments/test_fee_selection_ui.py::test_TS_PAY_011_nao_permite_pagar_taxa_de_outra_inscricao` | Coberto |
| TS-PAY-012 | Lifecycle com Taxa de Projeto pendente | `apps/payments/test_fee_selection_ui.py::test_TS_PAY_012_advance_nao_aprova_com_taxa_de_projeto_pendente` | Coberto |
| TS-PAY-013 | Simulação de pagamento em desenvolvimento | `apps/payments/test_simulate_payment_view.py::test_TS_PAY_013_confirmar_pix_em_dev`<br>`apps/payments/test_simulate_payment_view.py::test_TS_PAY_013_rota_indisponivel_sem_debug`<br>`apps/payments/test_simulate_payment_view.py::test_TS_PAY_013_nao_simula_pagamento_de_terceiros`<br>`apps/payments/test_simulate_payment_view.py::test_TS_PAY_013_metodo_manual_nao_simulavel` | Coberto |
| TS-PAY-014 | Cobrança em massa de boletos vencidos | `apps/payments/test_overdue_bulk.py::test_TS_PAY_014_cobranca_envia_somente_slips_selecionados`<br>`apps/payments/test_overdue_bulk.py::test_TS_PAY_014_view_exibe_checkbox_e_historico`<br>`apps/payments/test_overdue_bulk.py::test_TS_PAY_014_post_com_slip_ids_dispara_cobranca` | Coberto |
| TS-PAY-019 | Painel de boletos vencidos | `apps/applications/tests/test_legacy_parity.py::test_TS_PAY_019_secretaria_acessa_painel_de_boletos_vencidos` | Coberto |
| TS-PAY-020 | Seleção de boletos vencidos | `apps/payments/tests.py::test_TS_PAY_020_overdue_billing_service_retorna_boletos_vencidos`<br>`apps/payments/tests.py::test_TS_PAY_020b_overdue_billing_ignora_boletos_pagos_ou_futuros` | Coberto |
| TS-PAY-021 | Permissão da tela de cobranças | `apps/payments/tests.py::test_TS_PAY_021_overdue_billing_view_requer_permissao_secretaria` | Coberto |
| TS-PAY-022 | Pagamentos pendentes | `apps/payments/tests.py::test_TS_PAY_022_pagamentos_pendentes_lista_inscricoes_com_taxa_a_pagar` | Coberto |
| TS-PIX-001 | Geração com payload correto | `apps/applications/tests/test_journey_pagamento_auditoria.py::test_TS_PIX_001_jornada_payload_respeita_contrato`<br>`apps/pix/tests.py::test_TS_PIX_001_geracao_com_payload_correto` | Coberto |
| TS-PIX-002 | Armazenamento do Pix gerado | `apps/pix/tests.py::test_TS_PIX_002_armazenamento_do_pix`<br>`apps/pix/tests.py::test_TS_PIX_002_pix_ja_gerado_e_reutilizado` | Coberto |
| TS-PIX-003 | Consulta com parâmetro verificar | `apps/pix/tests.py::test_TS_PIX_003_consulta_atualiza_pagamento` | Coberto |
| TS-PIX-004 | Webhook válido | `apps/pix/tests.py::test_TS_PIX_004_webhook_valido_confirma_pagamento` | Coberto |
| TS-PIX-005 | Webhook com token inválido | `apps/pix/tests.py::test_TS_PIX_005_token_invalido_rejeitado` | Coberto |
| TS-PIX-006 | Webhook duplicado | `apps/pix/tests.py::test_TS_PIX_006_webhook_duplicado_idempotente` | Coberto |
| TS-PIX-007 | Webhook com valor divergente | `apps/pix/tests.py::test_TS_PIX_007_valor_divergente_requer_revisao` | Coberto |
| TS-PIX-008 | Webhook de Pix desconhecido | `apps/pix/tests.py::test_TS_PIX_008_pix_desconhecido` | Coberto |
| TS-PIX-009 | Reconciliação com listarConcluidos | `apps/pix/tests.py::test_TS_PIX_009_reconciliacao_confirma_pagamentos`<br>`apps/pix/tests.py::test_TS_PIX_009_periodo_maior_que_30_dias_rejeitado`<br>`apps/pix/tests.py::test_TS_PIX_009_listarconcluidos_usa_dtaini_dtafim` | Coberto |
| TS-PIX-010 | Simulação de pagamento em desenvolvimento | `apps/applications/tests/test_journey_pagamento_auditoria.py::test_TS_PIX_010_jornada_pix_simulacao_servico_avanca_fluxo`<br>`apps/pix/tests.py::test_TS_PIX_010_simulacao_apenas_em_dev` | Coberto |
| TS-PIX-011 | PDF e QR Code | `apps/pix/tests.py::test_TS_PIX_011_qrcode_asset_criado` | Coberto |
| TS-BSL-001 | Geração de boleto registrado | `apps/applications/tests/test_journey_pagamento_auditoria.py::test_TS_BSL_001_jornada_payload_respeita_contrato`<br>`apps/bank_slips/tests.py::test_TS_BSL_001_geracao_boleto_registrado`<br>`apps/bank_slips/tests.py::test_TS_BSL_001_headers_soap` | Coberto |
| TS-BSL-002 | Dados obrigatórios do boleto | `apps/bank_slips/tests.py::test_TS_BSL_002_dados_obrigatorios`<br>`apps/bank_slips/tests.py::test_TS_BSL_002b_informacoes_boleto_sacado_no_payload` | Coberto |
| TS-BSL-003 | Consulta de situação | `apps/bank_slips/tests.py::test_TS_BSL_003_situacao_convertida` | Coberto |
| TS-BSL-004 | Status V não confirma pagamento | `apps/bank_slips/tests.py::test_TS_BSL_004_status_v_nao_confirma` | Coberto |
| TS-BSL-005 | Boleto pago atualiza fluxo | `apps/bank_slips/tests.py::test_TS_BSL_005_pago_atualiza_fluxo` | Coberto |
| TS-BSL-006 | Download de PDF | `apps/bank_slips/tests.py::test_TS_BSL_006_pdf_gerado_e_armazenado` | Coberto |
| TS-BSL-007 | Cancelamento de boleto substituído | `apps/bank_slips/tests.py::test_TS_BSL_007_cancelamento` | Coberto |
| TS-BSL-008 | Consulta em lote | `apps/bank_slips/tests.py::test_TS_BSL_008_consulta_em_lote` | Coberto |
| TS-BSL-009 | Falha SOAP | `apps/bank_slips/tests.py::test_TS_BSL_009_falha_soap_nao_grava_inconsistencia` | Coberto |
| TS-BSL-010 | Simulação de pagamento em desenvolvimento | `apps/bank_slips/tests.py::test_TS_BSL_010_simulacao_apenas_em_dev` | Coberto |
| TS-BSL-011 | Falha SOAP notifica a equipe CEA | `apps/bank_slips/tests.py::test_TS_BSL_011_falha_soap_notifica_equipe_cea`<br>`apps/bank_slips/tests.py::test_TS_BSL_011_sucesso_nao_notifica_falha` | Coberto |
| TS-BSL-012 | Regeneração automática de boletos vencidos | `apps/applications/tests/test_legacy_parity.py::test_TS_BSL_012_task_regenera_boletos_vencidos_e_notifica` | Coberto |
| TS-MAN-001 | Confirmação manual de pagamento | `apps/payments/tests.py::test_TS_MAN_001_confirmacao_manual_de_pagamento` | Coberto |
| TS-MAN-002 | Pagamento manual não altera status externo | `apps/payments/tests.py::test_TS_MAN_002_pagamento_manual_nao_altera_status_externo` | Coberto |
| TS-MAN-003 | Pagamento manual não envia e-mail ao candidato | `apps/payments/tests.py::test_TS_MAN_003_pagamento_manual_nao_envia_email` | Coberto |
| TS-MAN-004 | Confirmação manual em instrumento pago | `apps/payments/tests.py::test_TS_MAN_004_confirmacao_manual_em_instrumento_pago` | Coberto |
| TS-REF-001 | Solicitação de reembolso após rejeição paga | `apps/payments/test_fee_selection_ui.py::test_TS_REF_001_candidato_solicita_reembolso_e_volta_a_ficha`<br>`apps/payments/tests.py::test_TS_REF_001_solicitacao_de_reembolso_apos_rejeicao_paga` | Coberto |
| TS-REF-002 | Aprovação de reembolso | `apps/payments/tests.py::test_TS_REF_002_aprovacao_de_reembolso` | Coberto |
| TS-REF-003 | Execução de reembolso | `apps/payments/tests.py::test_TS_REF_003_execucao_de_reembolso` | Coberto |
| TS-REF-004 | Conversão em vez de reembolso | `apps/payments/tests.py::test_TS_REF_004_conversao_em_vez_de_reembolso` | Coberto |
| TS-REF-005 | Reembolso não pode exceder valor pago | `apps/payments/tests.py::test_TS_REF_005_reembolso_nao_pode_exceder_valor_pago` | Coberto |
| TS-MOD-001 | Projeto não pago convertido em Consulta | `apps/payments/tests.py::test_TS_MOD_001_projeto_nao_pago_convertido_em_consulta` | Coberto |
| TS-MOD-002 | Projeto pago convertido em Consulta | `apps/payments/tests.py::test_TS_MOD_002_projeto_pago_convertido_em_consulta` | Coberto |
| TS-MOD-003 | Projeto pago com valor igual ou superior a R$ 140,00 | `apps/payments/tests.py::test_TS_MOD_003_projeto_pago_igual_ou_superior_140` | Coberto |
| TS-MOD-004 | Consulta não paga convertida em Projeto | `apps/payments/tests.py::test_TS_MOD_004_consulta_nao_paga_convertida_em_projeto` | Coberto |
| TS-MOD-005 | Consulta paga convertida em Projeto | `apps/payments/tests.py::test_TS_MOD_005_consulta_paga_convertida_em_projeto` | Coberto |
| TS-MOD-006 | Conversão de Consulta para Projeto exige auditoria quando há dono | `apps/payments/tests.py::test_TS_MOD_006_projeto_com_taxa_de_projeto_paga_convertido_para_consulta_gera_excesso` | Coberto |
| TS-MOD-007 | Conversão de inscrição importada sem dono | — | Sem teste |
| TS-TRM-001 | Transferência manual com período futuro existente | — | Sem teste |
| TS-TRM-002 | Transferência pendente sem período futuro | `apps/applications/tests/test_term_transfer_pending.py::test_TS_TRM_002_sem_proximo_periodo_fica_pendente` | Coberto |
| TS-TRM-003 | Transferência automática ao criar período | `apps/applications/tests/test_term_transfer_pending.py::test_TS_TRM_003_criar_periodo_migra_e_reseta_status` | Coberto |
| TS-TRM-004 | Transferência preserva auditoria | `apps/applications/tests/test_term_transfer_pending.py::test_TS_TRM_004_005_preserva_auditoria_e_pagamentos` | Coberto |
| TS-TRM-005 | Transferência preserva pagamentos | — | Sem teste |
| TS-TRM-006 | Transferência manual pela Secretaria | `apps/applications/tests/test_legacy_parity.py::test_TS_TRM_006_secretaria_transfere_inscricao_manualmente` | Coberto |
| TS-TRM-007 | Editar período não re-migra | `apps/applications/tests/test_term_transfer_pending.py::test_TS_TRM_007_editar_periodo_nao_remigra` | Coberto |
| TS-MEET-001 | Agendar triagem para Projeto | `apps/meetings/tests.py::test_TS_MEET_001_agendar_triagem_para_projeto` | Coberto |
| TS-MEET-002 | Bloquear triagem para Consulta | `apps/meetings/tests.py::test_TS_MEET_002_bloquear_triagem_para_consulta` | Coberto |
| TS-MEET-003 | Agendar reunião para Consulta | `apps/meetings/tests.py::test_TS_MEET_003_agendar_reuniao_para_consulta` | Coberto |
| TS-MEET-004 | Bloquear reunião para Projeto | `apps/meetings/tests.py::test_TS_MEET_004_bloquear_reuniao_para_projeto` | Coberto |
| TS-MEET-005 | Reunião online exige link | `apps/meetings/tests.py::test_TS_MEET_005_reuniao_online_exige_link` | Coberto |
| TS-MEET-006 | Reunião presencial exige local | `apps/meetings/tests.py::test_TS_MEET_006_reuniao_presencial_exige_local` | Coberto |
| TS-MEET-007 | Reagendar | `apps/meetings/tests.py::test_TS_MEET_007_reagendar` | Coberto |
| TS-MEET-008 | Cancelar | `apps/meetings/tests.py::test_TS_MEET_008_cancelar` | Coberto |
| TS-MEET-009 | Decisão aprovado como Projeto | `apps/meetings/tests.py::test_TS_MEET_009b_decisao_aprovado_como_projeto_com_credito` | Coberto |
| TS-MEET-010 | Decisão aprovado como Consulta | `apps/meetings/tests.py::test_TS_MEET_010_decisao_aprovado_como_consulta` | Coberto |
| TS-MEET-011 | Decisão não aprovado | `apps/meetings/tests.py::test_TS_MEET_011_decisao_nao_aprovado`<br>`apps/meetings/tests.py::test_TS_MEET_011b_reuniao_decisao_nao_aprovado`<br>`apps/meetings/tests.py::test_TS_MEET_011c_decisao_exige_feedback_do_docente` | Coberto |
| TS-MEET-012 | Feedback docente após evento | `apps/meetings/tests.py::test_TS_MEET_012_feedback_docente_apos_evento`<br>`apps/meetings/tests.py::test_TS_MEET_012b_feedback_bloqueado_antes_do_evento`<br>`apps/meetings/tests.py::test_TS_MEET_012c_feedback_bloqueado_antes_do_evento_consulta` | Coberto |
| TS-MEET-013 | Reagendamento limpa campos do modo anterior | `apps/meetings/tests.py::test_TS_MEET_013_reagendamento_trocando_modo_limpa_campos_corretamente`<br>`apps/meetings/tests.py::test_TS_MEET_013_reagendamento_consulta_troca_para_online_limpa_local` | Coberto |
| TS-MEET-014 | Consulta aprovada como Projeto gera taxa | `apps/meetings/tests.py::test_TS_MEET_014_consulta_aprovada_como_projeto_gera_taxa_de_projeto` | Coberto |
| TS-MEET-015 | Alias da fila de agendamentos | `apps/meetings/test_screenings.py::test_TS_MEET_015_alias_queue_continua_disponivel` | Coberto |
| TS-NOT-001 | Inscrição submetida | `apps/notifications/test_triggers.py::test_TS_NOT_001_submissao_notifica_candidato_e_centro`<br>`apps/notifications/tests.py::test_TS_NOT_001_inscricao_submetida_notifica_candidato_e_equipe` | Coberto |
| TS-NOT-002 | Correção solicitada | `apps/notifications/test_triggers.py::test_TS_NOT_002_auditoria_correcao_notifica_candidato`<br>`apps/notifications/tests.py::test_TS_NOT_002_correcao_solicitada_notifica_candidato` | Coberto |
| TS-NOT-003 | Auditoria aprovada | `apps/notifications/test_triggers.py::test_TS_NOT_003_revisao_aprovada_notifica`<br>`apps/notifications/tests.py::test_TS_NOT_003_auditoria_aprovada_notifica_candidato` | Coberto |
| TS-NOT-004 | Auditoria rejeitada | `apps/notifications/test_triggers.py::test_TS_NOT_004_auditoria_rejeitada_notifica_candidato_e_centro`<br>`apps/notifications/tests.py::test_TS_NOT_004_auditoria_rejeitada_notifica_candidato_e_secretaria` | Coberto |
| TS-NOT-005 | Cobrança criada | `apps/notifications/test_triggers.py::test_TS_NOT_005_006_pagamento_notifica_criacao_e_confirmacao`<br>`apps/notifications/tests.py::test_TS_NOT_005_cobranca_criada_notifica_candidato` | Coberto |
| TS-NOT-006 | Pagamento confirmado por Pix | `apps/notifications/tests.py::test_TS_NOT_006_pagamento_pix_notifica_candidato` | Coberto |
| TS-NOT-007 | Pagamento confirmado por boleto | `apps/notifications/tests.py::test_TS_NOT_007_pagamento_boleto_notifica_candidato` | Coberto |
| TS-NOT-008 | Pagamento manual não notifica candidato | `apps/notifications/tests.py::test_TS_NOT_008_pagamento_manual_nao_notifica_candidato` | Coberto |
| TS-NOT-009 | Template inativo | `apps/notifications/tests.py::test_TS_NOT_009_template_inativo_nao_envia` | Coberto |
| TS-NOT-010 | Falha de envio | `apps/notifications/tests.py::test_TS_NOT_010_falha_de_envio_marca_failed`<br>`apps/notifications/tests.py::test_TS_NOT_010_task_sem_template_nao_cria_despacho`<br>`apps/notifications/tests.py::test_TS_NOT_010_anexo_serializado_e_json_seguro`<br>`apps/notifications/tests.py::test_TS_NOT_010_task_decodifica_anexo_base64` | Coberto |
| TS-NOT-011 | Mudança de modalidade notifica candidato | `apps/notifications/test_triggers.py::test_TS_NOT_011_mudanca_de_modalidade_notifica_candidato` | Coberto |
| TS-NOT-012 | Anexos e notificações de agendamento | `apps/notifications/test_triggers.py::test_TS_NOT_012_triagem_agendada_e_decidida_notifica`<br>`apps/notifications/tests.py::test_TS_NOT_012_anexo_de_boleto_pdf_chega_ao_email` | Coberto |
| TS-NOT-013 | Reunião de consulta agendada e decidida | `apps/notifications/test_triggers.py::test_TS_NOT_013_reuniao_agendada_e_decidida_notifica` | Coberto |
| TS-NOT-014 | Reemissão de boleto com cópia oculta ao CEA | `apps/notifications/test_triggers.py::test_TS_NOT_014_reemissao_boleto_envia_copia_oculta_ao_centro` | Coberto |
| TS-FILE-001 | Arquivo de auditoria salvo com metadados | — | Sem teste |
| TS-FILE-002 | Download autorizado | — | Sem teste |
| TS-FILE-003 | Download não autorizado | — | Sem teste |
| TS-FILE-004 | Arquivo ausente | — | Sem teste |
| TS-FILE-005 | Retenção por prazo indeterminado | — | Sem teste |
| TS-FILE-006 | Link externo não é baixado | — | Sem teste |
| TS-CLAIM-001 | Solicitação de resgate | `apps/imports/tests.py::test_TS_CLAIM_001_solicitacao_cria_claim` | Coberto |
| TS-CLAIM-002 | Código enviado para e-mail registrado | `apps/imports/tests.py::test_TS_CLAIM_002_codigo_enviado_como_hash_com_expiracao` | Coberto |
| TS-CLAIM-003 | Código correto vincula inscrição | `apps/imports/tests.py::test_TS_CLAIM_003_codigo_correto_vincula_inscricao` | Coberto |
| TS-CLAIM-004 | Código incorreto | `apps/imports/tests.py::test_TS_CLAIM_004_codigo_incorreto_nao_vincula_e_limita` | Coberto |
| TS-CLAIM-005 | Código expirado | `apps/imports/tests.py::test_TS_CLAIM_005_codigo_expirado_rejeitado` | Coberto |
| TS-CLAIM-006 | Nenhuma vinculação automática silenciosa | `apps/imports/tests.py::test_TS_CLAIM_006_sem_vinculacao_automatica_silenciosa` | Coberto |
| TS-CLAIM-007 | Aprovação manual | `apps/imports/tests.py::test_TS_CLAIM_007_aprovacao_manual_pela_secretaria` | Coberto |
| TS-CLAIM-008 | Inscrição resgatada pode entrar em auditoria | `apps/imports/tests.py::test_TS_CLAIM_008_inscricao_resgatada_pode_entrar_em_auditoria` | Coberto |
| TS-IMP-001 | Inscrições importadas sem dono | `apps/imports/tests.py::test_TS_IMP_001_inscricao_importada_sem_dono_preserva_contatos` | Coberto |
| TS-IMP-002 | Inscrições importadas não aparecem para candidatos | `apps/imports/tests.py::test_TS_IMP_002_importada_nao_aparece_no_painel_do_candidato` | Coberto |
| TS-IMP-003 | Anexos importados | `apps/imports/tests.py::test_TS_IMP_003_anexos_importados_criam_file_asset` | Coberto |
| TS-IMP-004 | Pagamentos preservados | `apps/imports/tests.py::test_TS_IMP_004_pagamentos_preservados` | Coberto |
| TS-IMP-005 | Projetos importados não entram em auditoria automaticamente | `apps/imports/tests.py::test_TS_IMP_005_projeto_importado_sem_auditoria_automatica` | Coberto |
| TS-IMP-006 | Transferência de inscrição importada | `apps/imports/tests.py::test_TS_IMP_006_transferencia_preserva_ausencia_de_dono` | Coberto |
| TS-IMP-007 | Protocolos únicos na importação | `apps/imports/tests.py::test_TS_IMP_007_protocolos_duplicados_detectados` | Coberto |
| TS-IMP-008 | Arquivos ausentes | `apps/imports/tests.py::test_TS_IMP_008_arquivos_ausentes_relatados` | Coberto |
| TS-REP-001 | Relatório financeiro | `apps/reports/tests.py::test_TS_REP_001_relatorio_financeiro_reune_taxas_e_metodos` | Coberto |
| TS-REP-002 | Sincronização Pix | `apps/reports/test_financial_sync.py::test_TS_REP_002_sincroniza_boleto_pago`<br>`apps/reports/test_financial_sync.py::test_TS_REP_002_candidato_nao_sincroniza`<br>`apps/reports/tests.py::test_TS_REP_002_sincronizacao_pix_estados` | Coberto |
| TS-REP-003 | Sincronização boleto | `apps/reports/tests.py::test_TS_REP_003_sincronizacao_boleto_estados` | Coberto |
| TS-REP-004 | Exportação CSV | `apps/reports/tests.py::test_TS_REP_004_exportacao_csv_bom_e_delimitador` | Coberto |
| TS-REP-005 | Exportação XLSX | `apps/reports/tests.py::test_TS_REP_005_exportacao_xlsx_colunas_financeiras` | Coberto |
| TS-REP-006 | Relatório de auditoria | `apps/reports/tests.py::test_TS_REP_006_relatorio_auditoria_mostra_submissoes_e_decisoes` | Coberto |
| TS-REP-007 | Relatório agrupado e export por semestre | `apps/reports/test_grouped_report.py::test_TS_REP_007_uma_linha_por_inscricao_com_tres_taxas`<br>`apps/reports/test_grouped_report.py::test_TS_REP_007_export_csv_usa_semestre_e_contem_taxas` | Coberto |
| TS-EVT-001 | Eventos de inscrição | — | Sem teste |
| TS-EVT-002 | Eventos de auditoria | — | Sem teste |
| TS-EVT-003 | Eventos financeiros | — | Sem teste |
| TS-EVT-004 | Eventos de resgate | — | Sem teste |
| TS-INT-001 | Timeout no Pix | — | Sem teste |
| TS-INT-002 | Falha SOAP no boleto | — | Sem teste |
| TS-INT-003 | Falha no provedor de login | — | Sem teste |
| TS-INT-004 | Falha de e-mail | — | Sem teste |
| TS-INT-005 | Falha de storage | — | Sem teste |
| TS-INT-006 | Segredos não logados | — | Sem teste |
| TS-SEC-001 | CSRF | — | Sem teste |
| TS-SEC-002 | Webhook Pix exige token | — | Sem teste |
| TS-SEC-003 | Acesso direto por URL | — | Sem teste |
| TS-SEC-004 | Dados sensíveis | — | Sem teste |
| TS-SEC-005 | Links externos seguros | — | Sem teste |
| TS-SEC-006 | Rate limiting | — | Sem teste |
| TS-SEC-007 | Upload malicioso | — | Sem teste |
| TS-SEC-008 | Permissões de admin da Secretaria e Administrador | `apps/users/test_admin_permissions.py::test_TS_SEC_008_secretaria_acessa_semestres_e_emails`<br>`apps/users/test_admin_permissions.py::test_TS_SEC_008_secretaria_nao_acessa_usuarios`<br>`apps/users/test_admin_permissions.py::test_TS_SEC_008_admin_acessa_tudo` | Coberto |
| TS-NFR-001 | Acessibilidade básica | — | Sem teste |
| TS-NFR-002 | Responsividade | — | Sem teste |
| TS-NFR-003 | Logs estruturados | — | Sem teste |
| TS-NFR-004 | Geração de PDF com textos longos | `apps/documents/tests.py::test_TS_NFR_004_textos_longos_quebram_linha` | Coberto |
| TS-NFR-005 | PDF com caracteres especiais | `apps/documents/tests.py::test_TS_NFR_005_caracteres_especiais_escapados` | Coberto |
| TS-NFR-006 | PDF com dados bancários e de reembolso | `apps/documents/tests.py::test_TS_NFR_006_pdf_contem_dados_bancarios_e_de_reembolso`<br>`apps/documents/tests.py::test_TS_NFR_006_sem_recibo_nao_imprime_dados_bancarios` | Coberto |
| TS-NAV-001 | Fluxo completo do candidato sem URLs manuais | `apps/applications/tests/test_navigation_flow.py::test_TS_NAV_001_fluxo_completo_candidato_sem_urls_manuais` | Coberto |
| TS-NAV-002 | Fluxo de auditoria da Secretaria sem URLs manuais | `apps/applications/tests/test_navigation_flow.py::test_TS_NAV_002_fluxo_auditoria_secretaria_sem_urls_manuais` | Coberto |
| TS-NAV-003 | Menu segmentado por papel | `apps/applications/tests/test_navigation_flow.py::test_TS_NAV_003_menu_global_segmenta_por_papel` | Coberto |
| TS-NAV-004 | Breadcrumbs em todas as páginas | `apps/applications/tests/test_navigation_flow.py::test_TS_NAV_004_todas_as_paginas_possuem_breadcrumb` | Coberto |
| TS-NAV-005 | Links de retorno consistentes | `apps/applications/tests/test_navigation_flow.py::test_TS_NAV_005_links_de_retorno_consistentes` | Coberto |
| TS-NAV-006 | Relatórios ligam às inscrições | `apps/applications/tests/test_navigation_flow.py::test_TS_NAV_006_relatorios_ligam_as_inscricoes` | Coberto |
| TS-NAV-007 | Instrumentos ligam a boleto/Pix/recibo | `apps/applications/tests/test_navigation_flow.py::test_TS_NAV_007_instrumentos_ligam_ao_boleto_pix_e_recibo` | Coberto |
