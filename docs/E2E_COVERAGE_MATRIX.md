# Matriz de cobertura E2E — Inscrições CEA

Data da linha de base: 2026-11-23
Escopo: suíte de navegador em `e2e/`, stack `docker-compose.e2e.yml` e catálogo de `docs/TEST_SCENARIOS.md`.

Arquivos de apoio:

- `docs/e2e_scenario_catalog.csv` — os 216 cenários `TS-*` com camada-alvo, evidência E2E e status.
- `docs/e2e_route_coverage.csv` — as 72 rotas não-admin com status de cobertura.
- `docs/E2E_REVIEW_REPORT.md` — achados de revisão, riscos e decisões pendentes.

## 1. Definição de cobertura

A suíte E2E não precisa executar os 216 cenários técnicos no navegador. Cada cenário recebe uma camada:

| Camada | Significado |
|---|---|
| `E2E-UI` | Jornada de navegador com efeito verificado na tela e/ou no estado persistido. |
| `E2E-API` | Fluxo HTTP real fora do navegador (webhook, download, exportação). |
| `E2E-CLI` | Processo operacional via management command (importação legada). |
| `Unidade` | Comportamento de contrato/integração coberto fora do E2E, com justificativa. |
| `Waiver` | Cenário inviável ou sem implementação no produto, com decisão registrada. |

Status usado no catálogo:

- `Coberto`: existe teste E2E que exercita o cenário de forma direta.
- `Parcial`: existe teste que toca o cenário, mas falta uma ramificação, asserção ou matriz de perfis.
- `Lacuna`: nenhum teste E2E exercita o cenário.
- `Divergente`: o comportamento documentado difere do produto; exige decisão antes de testar.
- `Unidade`: coberto por teste de unidade/integração, fora do escopo do navegador.

## 2. Linha de base de execução

Comando executado (stack isolada preservada entre as rodadas):

```bash
docker compose -p sistema_cea_e2e -f docker-compose.e2e.yml run --rm \
  -e E2E_BASE_URL=http://web:8000 \
  -e COMPOSE_PROJECT_NAME=sistema_cea_e2e \
  e2e pytest -q -p no:cacheprovider e2e -c e2e/pytest.ini
```

| Rodada | Banco | Resultado | Duração | Observação |
|---|---|---|---|---|
| 1 | volume novo | 55 passed | 411,49 s | Linha de base limpa. |
| 2 | mesmo volume | 54 passed, 1 failed | 401,74 s | Falha determinística por resíduo da rodada 1. |
| 3 | mesmo volume | 54 passed, 1 failed | 403,01 s | Reproduz a mesma falha. |
| 4 | reutilizado | 55 passed | 597,68 s | Fase 1: candidato e termo exclusivos. |
| 5 | mesmo banco da rodada 4 | 55 passed | 591,04 s | Idempotência validada. |
| P0 | reutilizado | 10 passed | 140,41 s | Marcador `p0`. |
| Host | reutilizado, `127.0.0.1:18000` (override host) | 55 passed | 601,03 s | Modo host do CI, incluindo Senha Única. |
| 6 | reutilizado, após correções | 55 passed | 601,29 s | Purga do namespace sem erro de teardown; namespace final = 0. |
| 7 | reutilizado, jornadas/pagamentos UI-only | 55 passed | 558,77 s | Migração parcial de D-05 validada. |
| 8 | reutilizado, suíte 100% UI-only | 55 passed | 489,61 s | `simulate_journey` removido do E2E. |
| 9 | reutilizado, com rate limiting | 56 passed | 618,25 s | TS-SEC-006 coberto; limites não afetaram os fluxos normais. |
| 10 | reutilizado, com importação E2E-CLI | 57 passed | 630,18 s | TS-IMP cobertos; namespace limpo. |
| 11 | reutilizado, com PAY/PIX P0 | 61 passed | 690,39 s | Troca de instrumento, taxa paga, Pix expirado e taxa de terceiro. |
| 12 | reutilizado, com NOT P0 | 65 passed | 753,20 s | Correção, aprovação, rejeição, Pix, boleto e manual sem e-mail. |
| 13 | reutilizado, com CSRF | 66 passed | 761,16 s | POST sem token anônimo e autenticado retorna 403. |
| 14 | reutilizado, com FILE/CLAIM | 68 passed | 792,37 s | Metadados, download negado, link externo e resgate incorreto. |
| 15 | reutilizado, P0 sem lacunas | 77 passed | 895,59 s | AUD, MOD, MEET e TRM; 15 P0 unitários. |
| 16 | reutilizado, com VAL | 84 passed | 952,69 s | Validações de formulário e mensagem de sucesso. |
| 17 | reutilizado, com AUTH-007 | 85 passed | 957,72 s | Inativo bloqueado e nightly em shards. |
| 18 | reutilizado, com NOT restantes | 89 passed | 1020,54 s | Submissão, cobrança, modalidade e BCC do CEA. |
| 19 | reutilizado, NOT completo | 91 passed | 1055,13 s | Triagem e reunião agendadas/decididas. |

Falha original (antes da Fase 1):

- Teste: `e2e/test_backoffice_e2e.py::test_E2E_TRM_001_002_003_cadastro_de_semestre_e_transferencia_pendente`.
- Ponto: `e2e/test_backoffice_e2e.py:32` — esperava “2090 - Primeiro Semestre”, mas a página exibia “2091 - Primeiro Semestre”.
- Causa: períodos criados pela suíte não eram removidos e a inscrição importada não era rastreada.
- Correção: candidato e período exclusivos por teste, namespace 9000–9999, período explícito no formulário/`simulate_journey` e protocolo importado rastreado.
- Evidência após a Fase 1: duas execuções completas no mesmo banco passaram, com 0 inscrições vivas e 0 usuários E2E ativos após o cleanup.

## 3. Métricas estruturais

| Métrica | Valor |
|---|---:|
| Cenários em `TEST_SCENARIOS.md` | 216 |
| Testes E2E | 93 |
| Módulos com criação/pagamento UI-only | 10 de 10 |
| Arquivos de teste E2E | 11 |
| Rotas não-admin | 72 |
| Rotas admin declaradas | 155 |
| Rotas não-admin com URL literal nos testes | 35 |
| Rotas não-admin alcançadas por link/botão | 28 |
| Rotas não-admin sem cobertura | 9 |
| Rotas admin exercitadas | 1 (`/admin/terms/academicterm/add/`) |
| Testes com marcador `# Cobre: TS-*` | 92 de 93 |
| Testes marcados como P0 | 10 |
| Execuções completas verdes consecutivas no mesmo banco | 3 (2 container + 1 host) |
| Namespace E2E resetado ao final | Sim (`e2e_cleanup --purge-e2e-terms`) |
| Perfis de rate limiting | login, webhook, download e POST (Redis DB 1) |

## 4. Cobertura por prioridade

| Prioridade | Total | Coberto | Parcial | Lacuna | Divergente | Unidade |
|---|---:|---:|---:|---:|---:|---:|
| P0 | 101 | 86 | 0 | 0 | 0 | 15 |
| P1 | 100 | 50 | 0 | 0 | 0 | 50 |
| P2 | 15 | 5 | 0 | 0 | 0 | 10 |
| **Total** | **216** | **141** | **0** | **0** | **0** | **75** |

Leitura: 141 cenários têm cobertura automatizada (65,3%), sendo 93 com E2E direto e o restante com unidade/integração; não restam lacunas nem parciais.

## 5. Cobertura por área

| Área | Total | Coberto | Parcial | Lacuna | Divergente | Unidade |
|---|---:|---:|---:|---:|---:|---:|
| APP | 22 | 11 | 0 | 0 | 0 | 11 |
| AUD | 18 | 14 | 0 | 0 | 0 | 4 |
| AUTH | 7 | 6 | 0 | 0 | 0 | 1 |
| BSL | 12 | 5 | 0 | 0 | 0 | 7 |
| CLAIM | 8 | 5 | 0 | 0 | 0 | 3 |
| EVT | 4 | 4 | 0 | 0 | 0 | 0 |
| FEE | 8 | 4 | 0 | 0 | 0 | 4 |
| FILE | 6 | 4 | 0 | 0 | 0 | 2 |
| IMP | 8 | 8 | 0 | 0 | 0 | 0 |
| INT | 6 | 0 | 0 | 0 | 0 | 6 |
| MAN | 4 | 2 | 0 | 0 | 0 | 2 |
| MEET | 15 | 11 | 0 | 0 | 0 | 4 |
| MOD | 7 | 4 | 0 | 0 | 0 | 3 |
| NAV | 7 | 0 | 0 | 0 | 0 | 7 |
| NFR | 6 | 2 | 0 | 0 | 0 | 4 |
| NOT | 14 | 12 | 0 | 0 | 0 | 2 |
| PAY | 18 | 16 | 0 | 0 | 0 | 2 |
| PIX | 11 | 5 | 0 | 0 | 0 | 6 |
| REF | 5 | 4 | 0 | 0 | 0 | 1 |
| REP | 7 | 5 | 0 | 0 | 0 | 2 |
| SEC | 8 | 5 | 0 | 0 | 0 | 3 |
| TRM | 7 | 6 | 0 | 0 | 0 | 1 |
| VAL | 8 | 8 | 0 | 0 | 0 | 0 |

## 6. P0 sem E2E direto

Nenhum cenário P0 está em lacuna. Restam 14 parciais (a maioria já coberta por E2E) e 15 cobertos apenas por unidade, todos com evidência no catálogo `docs/e2e_scenario_catalog.csv`.

## 7. Cobertura de rotas

Resumo das 72 rotas não-admin:

- 35 cobertas por URL literal nos testes.
- 28 alcançadas por link, botão ou formulário, sem URL literal.
- 9 sem cobertura E2E.

Rotas sem cobertura:

| Rota | Camada | Observação |
|---|---|---|
| `auth/password_change/` | E2E-UI | Troca de senha autenticada não é coberta. |
| `auth/password_change/done/` | E2E-UI | Troca de senha autenticada não é coberta. |
| `auditoria/inscricao/<protocol>/habilitar/` | E2E-UI | Habilitar auditoria após resgate. |
| `auditoria/submissao/<id>/arquivo/` | E2E-API | Download da submissão e autorização. |
| `pix/<id>/qrcode/` | E2E-API | QR Code não é baixado nem assertado. |
| `agendamentos/` | E2E-UI | Alias da fila de agendamentos. |
| `gestao/resgates/` | E2E-UI | Fila de aprovação manual de resgates. |
| `gestao/resgates/<id>/aprovar/` | E2E-UI | Aprovação manual de resgate. |
| `logout/` | E2E-UI | Logout não é exercitado. |

Admin: apenas a criação de período em `/admin/terms/academicterm/add/` é exercitada. Usuários, papéis, templates de e-mail, permissões da secretaria e demais telas do admin não têm cobertura E2E.

## 8. Divergências e pendências

1. **TS-AUTH-001**: resolvido por D-02. `TEST_SCENARIOS.md` e o catálogo descrevem landing pública + `/painel/` protegido, e `test_E2E_AUTH_001` está alinhado.
2. **`LEVANTAMENTO_PROCESSOS_E2E.md`**: afirma 7 testes, base `cea.local`, reembolso com 403 e transferência com 500. A suíte atual tem 55 testes e cobre esses fluxos; o documento está desatualizado e não serve como fonte de verdade.
3. **Rastreabilidade**: resolvido na Fase 1. O gerador lê `# Cobre: TS-*` em `e2e/**/test*.py`; a matriz tem 210 cenários cobertos e 141 entradas E2E.
4. **Suíte fora do CI**: resolvido na Fase 1 com `.github/workflows/e2e.yml` (P0 no PR, completo no nightly).
5. **Termo “mais recente”**: resolvido na Fase 1 com candidato/período exclusivos e período explícito no formulário e no `simulate_journey`.

## 9. Encerramento do plano

- 216/216 cenários classificados: 141 com cobertura automatizada (93 E2E direto + unidade complementar) e 75 por unidade/integração.
- P0: 86 cobertos e 15 de unidade; **0 lacunas e 0 parciais**.
- Suíte E2E: 93 testes, 1052,49 s; unidade: 508 testes.
- Nightly dividido em shards `core` e `flows`; PR limitado ao P0.
- Matriz de rotas, catálogo, rastreabilidade e relatório de revisão atualizados.
- Observação: `LEVANTAMENTO_PROCESSOS_E2E.md` permanece histórico e não é fonte de verdade para cobertura.

## 10. Execuções finais

| Rodada | Banco | Resultado | Duração | Observação |
|---|---|---|---|---|
| 20 | reutilizado, plano completo | 93 passed | 1052,49 s | NFR, SEC, FILE, MOD e catálogo final |
