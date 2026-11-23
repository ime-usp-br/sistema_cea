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
| Testes E2E | 65 |
| Módulos com criação/pagamento UI-only | 10 de 10 |
| Arquivos de teste E2E | 11 |
| Rotas não-admin | 72 |
| Rotas admin declaradas | 155 |
| Rotas não-admin com URL literal nos testes | 35 |
| Rotas não-admin alcançadas por link/botão | 28 |
| Rotas não-admin sem cobertura | 9 |
| Rotas admin exercitadas | 1 (`/admin/terms/academicterm/add/`) |
| Testes com marcador `# Cobre: TS-*` | 64 de 65 |
| Testes marcados como P0 | 10 |
| Execuções completas verdes consecutivas no mesmo banco | 3 (2 container + 1 host) |
| Namespace E2E resetado ao final | Sim (`e2e_cleanup --purge-e2e-terms`) |
| Perfis de rate limiting | login, webhook, download e POST (Redis DB 1) |

## 4. Cobertura por prioridade

| Prioridade | Total | Coberto | Parcial | Lacuna | Divergente | Unidade |
|---|---:|---:|---:|---:|---:|---:|
| P0 | 101 | 56 | 14 | 27 | 0 | 4 |
| P1 | 100 | 26 | 10 | 57 | 0 | 7 |
| P2 | 15 | 2 | 1 | 11 | 0 | 1 |
| **Total** | **216** | **84** | **25** | **95** | **0** | **12** |

Leitura: 84 cenários têm cobertura E2E direta (38,9%). Mesmo entre P0, 27 estão em lacuna e 14 são parciais. Isso mostra que a suíte atual é boa em happy paths, mas ainda distante de “100% dos cenários de uso”.

## 5. Cobertura por área

| Área | Total | Coberto | Parcial | Lacuna | Divergente | Unidade |
|---|---:|---:|---:|---:|---:|---:|
| AUTH | 7 | 2 | 3 | 2 | 0 | 0 |
| APP | 22 | 6 | 5 | 11 | 0 | 0 |
| VAL | 8 | 0 | 1 | 7 | 0 | 0 |
| AUD | 18 | 9 | 2 | 7 | 0 | 0 |
| FEE | 8 | 1 | 3 | 4 | 0 | 0 |
| PAY | 18 | 14 | 2 | 2 | 0 | 0 |
| PIX | 11 | 5 | 0 | 3 | 0 | 3 |
| BSL | 12 | 4 | 1 | 7 | 0 | 0 |
| MAN | 4 | 1 | 0 | 3 | 0 | 0 |
| REF | 5 | 3 | 0 | 2 | 0 | 0 |
| MOD | 7 | 2 | 0 | 5 | 0 | 0 |
| TRM | 7 | 3 | 2 | 2 | 0 | 0 |
| MEET | 15 | 9 | 0 | 6 | 0 | 0 |
| NOT | 14 | 6 | 0 | 8 | 0 | 0 |
| FILE | 6 | 0 | 1 | 5 | 0 | 0 |
| CLAIM | 8 | 3 | 0 | 5 | 0 | 0 |
| IMP | 8 | 8 | 0 | 0 | 0 | 0 |
| REP | 7 | 5 | 0 | 2 | 0 | 0 |
| EVT | 4 | 0 | 4 | 0 | 0 | 0 |
| INT | 6 | 0 | 0 | 0 | 0 | 6 |
| SEC | 8 | 3 | 1 | 4 | 0 | 0 |
| NFR | 6 | 0 | 0 | 3 | 0 | 3 |
| NAV | 7 | 0 | 0 | 7 | 0 | 0 |

## 6. Lacunas P0 por área

| Área | Cenários P0 em lacuna |
|---|---|
| APP | `TS-APP-004` |
| AUD | `TS-AUD-002`, `TS-AUD-004`, `TS-AUD-008` |
| BSL | `TS-BSL-002`, `TS-BSL-003`, `TS-BSL-004` |
| CLAIM | `TS-CLAIM-004`, `TS-CLAIM-006` |
| FEE | `TS-FEE-003`, `TS-FEE-006`, `TS-FEE-007` |
| FILE | `TS-FILE-001`, `TS-FILE-003`, `TS-FILE-006` |
| IMP | `TS-IMP-001`, `TS-IMP-002`, `TS-IMP-003`, `TS-IMP-004`, `TS-IMP-005`, `TS-IMP-007` |
| MAN | `TS-MAN-002`, `TS-MAN-003` |
| MEET | `TS-MEET-002`, `TS-MEET-004` |
| MOD | `TS-MOD-001`, `TS-MOD-002`, `TS-MOD-006` |
| NOT | `TS-NOT-002`, `TS-NOT-003`, `TS-NOT-004`, `TS-NOT-006`, `TS-NOT-007`, `TS-NOT-008` |
| PAY | `TS-PAY-003`, `TS-PAY-004`, `TS-PAY-005`, `TS-PAY-006`, `TS-PAY-007`, `TS-PAY-011` |
| PIX | `TS-PIX-001`, `TS-PIX-002`, `TS-PIX-007` |
| REF | `TS-REF-004`, `TS-REF-005` |
| REP | `TS-REP-003` |
| SEC | `TS-SEC-001` |
| TRM | `TS-TRM-005` |

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
3. **Rastreabilidade**: resolvido na Fase 1. O gerador lê `# Cobre: TS-*` em `e2e/**/test*.py`; a matriz tem 195 cenários cobertos e 89 entradas E2E.
4. **Suíte fora do CI**: resolvido na Fase 1 com `.github/workflows/e2e.yml` (P0 no PR, completo no nightly).
5. **Termo “mais recente”**: resolvido na Fase 1 com candidato/período exclusivos e período explícito no formulário e no `simulate_journey`.

## 9. Próximos passos

1. ~~Corrigir isolamento e limpeza~~ — concluído; duas execuções completas verdes no mesmo banco.
2. ~~Colocar a suíte no CI com artefatos e limite de tempo~~ — concluído; P0 em 140,41 s.
3. ~~Vincular testes a `TS-*` e atualizar a rastreabilidade~~ — concluído.
4. Atacar as 48 lacunas P0 por área, começando por VAL, NOT, PAY/PIX e SEC.
5. Reconciliar o `LEVANTAMENTO_PROCESSOS_E2E.md` com a suíte atual e as decisões D-01..D-06.
6. Medir novamente a suíte após cada bloco de novos testes; o P0 deve permanecer abaixo de 7 min e o nightly abaixo de 20 min.
