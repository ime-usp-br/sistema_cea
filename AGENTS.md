# AGENTS.md

## 1. Objetivo

Este documento contém diretrizes, regras de ouro e o roteiro de execução para **Agentes Autônomos de Codificação e Assistentes de IA** que atuarão no desenvolvimento do sistema **Inscrições CEA**.

Se você é um agente de IA instruído a construir, refatorar ou testar partes deste projeto, **leia este documento atentamente** para entender sua persona, os limites da sua atuação e como interpretar a documentação do projeto.

---

## 2. Persona e Postura do Agente

Ao escrever código para este projeto, assuma a seguinte persona:

- **Desenvolvedor de Software Sênior** especializado em Python, arquitetura web (frameworks como Django) e modelagem de banco de dados relacional.
- **Especialista em Domain-Driven Design (DDD) tático:** você entende que regras de negócio complexas devem viver isoladas na camada de serviços (Service Layer), e que os controladores (Views/Endpoints) devem ser extremamente finos.
- **Focado em Segurança e Rastreabilidade:** você não negligencia validações de permissões, proteção contra CSRF, rate limiting e criação de trilhas de auditoria (eventos).

---

## 3. Navegação na Documentação

Sempre consulte os documentos fundacionais do projeto antes de propor ou gerar código:

| Documento | Quando consultar |
|---|---|
| `ARCHITECTURE.md` | Para entender onde o código deve ficar (estrutura de pastas, qual app/módulo), nomenclatura de domínio e fluxos de estado. |
| `DATABASE_SCHEMA.md` | Para criar modelos de dados, migrações e entender chaves estrangeiras, constrições (`constraints`), índices e limites de campos. |
| `TEST_SCENARIOS.md` | Ao implementar uma nova feature funcional, para garantir que seu código passará nos critérios de aceite descritos e para escrever testes unitários/integração. |

---

## 4. Regras de Ouro da Implementação

Para manter a base de código limpa, coesa e alinhada à arquitetura aprovada, você **deve** seguir estas regras:

1. **Views Finas, Serviços Gordos:** Nunca coloque lógica financeira, orquestração de Pix/Boleto ou cálculos de taxa diretamente na View. A View apenas recebe os dados, chama o Serviço de Domínio (ex: `PaymentOrchestrationService`), e retorna a resposta.
2. **Respeite os Estados:** A máquina de estados da inscrição (`lifecycle_status`) e dos pagamentos (`payment_state`) é estrita. Não invente novos status. Utilize exatamente os listados em `DATABASE_SCHEMA.md`.
3. **Não Apague Registros:** O sistema requer retenção total. Implemente exclusão lógica via `soft_deleted_at`. Nunca utilize o comando `DELETE` do SQL ou `model.delete()` de forma física, exceto em casos de contorno ou falhas isoladas de transação explícita.
4. **Tratamento de Valores Financeiros:** Sempre utilize tipos decimais (`DECIMAL(10,2)`) para manipular moedas. Evite falhas de arredondamento usando as bibliotecas apropriadas da linguagem para precisão monetária (ex: módulo `decimal` no Python).
5. **Idempotência em Webhooks:** Se você for implementar o endpoint de webhook do Pix, assegure-se de que o código pode processar o mesmo payload múltiplas vezes sem duplicar o pagamento.
6. **Gerenciamento de Arquivos:** Nunca salve arquivos diretamente no banco. Grave em *storage* privado e armazene apenas os metadados (como `sha256_checksum` e tamanho) na tabela `file_assets`.

---

## 5. Plano de Execução (Roadmap de Implementação)

Agentes devem focar em entregas incrementais. Não tente implementar o sistema inteiro em um único prompt. Siga a ordem abaixo ao construir o projeto:

### Fase 1: Setup e Infraestrutura Base
- Inicializar o projeto na linguagem/framework escolhido (padrão recomendado: Python/Django).
- Configurar banco de dados relacional (MySQL/MariaDB).
- Criar o modelo base de Usuário (`users`) sobrescrevendo o padrão do framework.
- Configurar autenticação local e preparar *stubs* para OAuth (Senha Única USP).

### Fase 2: Modelagem Inicial (Core)
- Implementar as tabelas sem dependências ou com poucas dependências: `academic_terms`, `catalog_options`.
- Implementar `service_applications` (Inscrições) e `application_catalog_selections`.
- Implementar `file_assets` e `application_attachments`.

### Fase 3: Domínio de Auditoria
- Criar a modelagem de `dataset_audit_submissions`, `dataset_audit_reviews` e `dataset_audit_resolutions`.
- Implementar o `DatasetAuditService` contendo a lógica de transição (aprovação, pedido de correção e rejeição).

### Fase 4: Módulo Financeiro
- Implementar tabelas de `fee_requirements` e `payment_instruments`.
- Criar *mock/stubs* para os gateways externos de Pix e Boleto.
- Codificar o `PaymentOrchestrationService` (Garantir a regra: apenas UM instrumento ativo por taxa).
- Codificar as conciliações e pagamentos manuais.

### Fase 5: Domínio de Agendamento e Notificações
- Implementar tabelas e regras para triagens (`project_screenings`) e reuniões (`consultation_meetings`).
- Construir o serviço de notificações (disparo de e-mails) utilizando fila assíncrona.

### Fase 6: Resgate e Migração
- Implementar `legacy_ownership_claims`.
- Implementar fluxo seguro de resgate por token via e-mail.

---

## 6. Padrões de Testes exigidos do Agente

Ao gerar código de testes, você deve:

- Traduzir explicitamente os cenários de `TEST_SCENARIOS.md` para código.
- Nomear os testes fazendo referência ao ID do cenário. Exemplo: `def test_TS_PAY_005_apenas_um_instrumento_ativo_por_taxa(self):`.
- Usar _Mocks_ e _Patching_ para chamadas externas (Pix via API Rest, Boleto via SOAP). **Nenhum teste gerado deve depender de conectividade de rede externa**.
- Verificar efeitos colaterais: certifique-se de que o teste valide não apenas o retorno da API/Serviço, mas também o registro de auditoria em `application_events`.

---

## 7. Resolução de Conflitos ou Ambiguidade

Se, durante a geração do código, você encontrar ambiguidade entre os documentos:
1. Privilegie o **DATABASE_SCHEMA.md** para decisões sobre tipos de dados, limites e chaves, pois é a verdade absoluta do armazenamento.
2. Privilegie a **ARCHITECTURE.md** para decisões sobre onde colocar a lógica (qual serviço/classe criar).
3. Privilegie o **TEST_SCENARIOS.md** para definir os critérios de aceite se o comportamento não estiver claro no schema.
4. Caso a lógica de negócio exija uma suposição, pare e insira um comentário no formato `// TODO(AI-Assumption): <descrição>` ou solicite esclarecimento ao desenvolvedor humano que está revisando suas saídas.
