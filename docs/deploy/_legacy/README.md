# Legado do deploy

Este diretório preserva, apenas para consulta/auditoria, configurações antigas
que foram retiradas do contrato de deploy.

## `docker-compose.yml.in-stack-db.bak`

Cópia do `docker-compose.yml` anterior à padronização (2026-11-25). Ele continha:

- serviço `db` (PostgreSQL) dentro da stack da aplicação;
- volume `postgres_data` com os dados locais;
- credenciais de banco com valores padrão no compose;
- `depends_on` da aplicação para o banco;
- `DATABASE_URL` apontando para o serviço Compose `db`.

Esses elementos **não fazem parte** do contrato canônico. O banco passou a ser
externo, acessado por domínio (`DB_HOST`), gerenciado pela infraestrutura de
cada ambiente. Nenhum dado foi apagado por esta mudança; o volume antigo, se
existir em algum host, deve ser migrado/descartado pela infraestrutura após
confirmação de que o banco central está disponível e migrado.

O `docker-compose.override.yml` antigo foi renomeado para
`docker-compose.local.yml` e permanece como overlay opcional de hot reload,
fora do contrato de deploy.
