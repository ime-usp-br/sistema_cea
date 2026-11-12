# Importação de dados legados (dump SQL + storage)

Guia operacional para recuperar os dados do sistema legado (Laravel/MariaDB) e
importá-los no sistema novo. O legado tem o **projeto e o banco em servidores
separados**, mas ambos pertencem ao mesmo projeto.

## Visão geral

- `manage.py import_legacy_sql` lê o dump SQL do MariaDB e importa inscrições,
  catálogo, períodos, pagamentos/boletos, triagens, reuniões, eventos, anexos e
  comprovantes.
- `manage.py import_legacy_data` continua existindo para o formato JSON
  (usado pelo fluxo de resgate e pelos testes `TS-IMP-*`).
- O parser do dump está em `apps/imports/sql_dump.py`; o importador em
  `apps/imports/importers.py`; o comando em
  `apps/imports/management/commands/import_legacy_sql.py`.

## 1. Descobrir a pasta correta do storage no legado

O erro mais comum é tarizar `storage/app` do projeto, quando o disco `local`
aponta para outro lugar. No Laravel 8, o root do disco é definido em
`config/filesystems.php` (ou por variável de ambiente).

```bash
cd /var/www/inscricoes-cea

php -r "require 'vendor/autoload.php'; \$app=require 'bootstrap/app.php'; \$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap(); echo 'storage_path: '.storage_path().PHP_EOL; echo 'default disk: '.config('filesystems.default').PHP_EOL; print_r(config('filesystems.disks'));"
```

Regras:

- `storage_path()` é o caminho do diretório `storage/` do Laravel, **não
  necessariamente** o root usado pelos anexos.
- Os anexos usam o disco `local` (ou o disco configurado no model). Veja
  `config('filesystems.disks.local.root')`.
- O `path` das tabelas `attachments` e `deposit_receipts` é
  `<protocolo>/<arquivo>`, relativo a esse root.
- O disco `public` (normalmente `storage/app/public`) é para arquivos
  públicos; não confunda com o disco dos anexos.

### Caso deste projeto

No ambiente atual do legado:

| Item | Caminho |
|---|---|
| Projeto Laravel | `/var/www/inscricoes-cea` |
| `storage_path()` | `/var/www/inscricoes-cea/storage` |
| **root do disco `local`** | **`/storage/inscricoes-cea/app`** |
| `local` no `.env`/config | `FILESYSTEM_DRIVER=local` |

Portanto o archive correto contém `app/<protocolo>/<arquivo>`, e o
`--storage-root` deve apontar para a pasta `app` (o root do disco `local`).
O `storage/app` dentro de `/var/www/inscricoes-cea` era antigo/em desuso e não
continha os arquivos referenciados pelo dump.

## 2. Gerar o dump SQL

Se ainda não houver dump:

```bash
# no servidor do banco (ou com acesso ao MariaDB)
mariadb-dump -u <usuario> -p <banco> > "$HOME/cea_$(date +%Y%m%d_%H%M).sql"
```

Tabelas lidas pelo importador: `applications`, `semesters`, `bank_slips`,
`attachments`, `deposit_receipts`, `triages`, `consultation_meetings`,
`events`. Outras tabelas do dump são ignoradas.

Não versionar o dump: ele contém dados pessoais.

## 3. Empacotar o storage correto (a partir do home)

Não crie arquivos dentro do projeto no servidor de produção.

```bash
cd "$HOME"
tar -czf "$HOME/cea-storage-local-$(date +%Y%m%d).tar.gz" \
  -C /storage/inscricoes-cea app

ls -lh "$HOME"/cea-storage-local-*.tar.gz
sha256sum "$HOME"/cea-storage-local-*.tar.gz
find /storage/inscricoes-cea/app -type f | wc -l
```

Se não tiver permissão de leitura:

```bash
sudo tar -czf "$HOME/cea-storage-local-$(date +%Y%m%d).tar.gz" \
  -C /storage/inscricoes-cea app
sudo chown "$USER:$USER" "$HOME"/cea-storage-local-*.tar.gz
```

Não é preciso tarizar `storage/logs` nem `storage/framework`.

## 4. Transferir para a máquina de dev

```bash
cd "$HOME"
scp -P <porta> <usuario>@<servidor>:"$HOME"/cea-storage-local-*.tar.gz "$HOME"/
sha256sum "$HOME"/cea-storage-local-*.tar.gz
```

Alternativa com retomada:

```bash
rsync -avz --partial --progress \
  <usuario>@<servidor>:"$HOME"/cea-storage-local-*.tar.gz "$HOME"/
```

## 5. Extrair e importar no Docker

Mantenha o storage fora do repositório e monte-o apenas na execução:

```bash
mkdir -p "$HOME/cea-legacy-storage-local"
tar -xzf "$HOME"/cea-storage-local-*.tar.gz -C "$HOME/cea-legacy-storage-local"

find "$HOME/cea-legacy-storage-local/app" -type f | wc -l

cd /home/ayrtondouglas/ime/dev/sistema_cea
docker compose run --rm \
  -v /home/ayrtondouglas/cea-legacy-storage-local:/legacy-storage:ro \
  web python manage.py import_legacy_sql \
    --dump /app/tmp/cea_20260925_1000.sql \
    --storage-root /legacy-storage/app \
    --update
```

Observações:

- Use o caminho **absoluto do host** no `-v` quando o comando for executado por
  uma sessão em sandbox (o `$HOME` da sessão pode ser outro).
- Se o dump também estiver fora do projeto, monte-o:
  `-v /home/ayrtondouglas/cea-dump:/legacy-dump:ro` e use
  `--dump /legacy-dump/<arquivo>.sql`.
- O `--storage-root` deve ser o root do disco `local` (a pasta que contém
  `<protocolo>/<arquivo>`), não o `storage/` do Laravel.

## Flags do comando

| Flag | Descrição |
|---|---|
| `--dump <arquivo.sql>` | Obrigatório. Dump MariaDB. |
| `--storage-root <pasta>` | Root do disco `local`. Se omitido, anexos/comprovantes são ignorados com aviso. |
| `--update` | Reimporta/atualiza inscrições já importadas. Sem ela, protocolos duplicados geram erro (`TS-IMP-007`). |
| `--limit N` | Processa apenas as N primeiras inscrições (teste). |

## Idempotência

Com `--update`, o comando pode ser repetido:

- Inscrições são atualizadas no lugar (o `owner` e o `dataset_audit_*` são
  preservados).
- Catálogo, taxas/instrumentos, eventos `legacy.*`, anexos e comprovantes são
  apagados e recriados.
- Triagens e reuniões usam `update_or_create`.
- Os totais ficam estáveis entre execuções.

Sem `--update`, a segunda execução falha com `protocolo duplicado` para cada
registro já existente. Isso é intencional.

Atenção: a recriação de `FileAsset` não remove o arquivo físico antigo do media
volume. Reexecuções deixam arquivos órfãos no volume (os registros no banco
ficam corretos).

## Validação

```bash
docker compose exec web python manage.py shell -c "
from applications.models import ServiceApplication, ApplicationAttachment, ApplicationEvent
from meetings.models import ProjectScreening, ConsultationMeeting
from payments.models import FeeRequirement, PaymentInstrument
from bank_slips.models import BankSlipPaymentInstrument
from files.models import FileAsset
qs = ServiceApplication.all_objects.filter(origin='imported')
print('apps', qs.count())
print('anexos', ApplicationAttachment.objects.filter(application__in=qs).count())
print('comprovantes', FileAsset.objects.filter(application__in=qs, purpose='payment_receipt').count())
print('triagens', ProjectScreening.objects.filter(application__in=qs).count())
print('reuniões', ConsultationMeeting.objects.filter(application__in=qs).count())
print('eventos', ApplicationEvent.objects.filter(application__in=qs).count())
print('taxas', FeeRequirement.objects.filter(application__in=qs).count())
print('instrumentos', PaymentInstrument.objects.filter(fee_requirement__application__in=qs).count())
print('boletos', BankSlipPaymentInstrument.objects.filter(payment_instrument__fee_requirement__application__in=qs).count())
"
```

Páginas para conferir:

- `/inscricoes/?term=all` — todas as inscrições.
- `/inscricoes/<protocolo>/` — ficha com descrição, catálogo, financeiro,
  agendamentos e anexos.

## Problemas comuns

| Sintoma | Causa provável | Ação |
|---|---|---|
| Muitos `Arquivo ausente` | `--storage-root` aponta para o `storage/app` antigo ou para o lugar errado | Descubra o `local.root` com `config('filesystems.disks')` e tarize o caminho correto. |
| Só alguns protocolos têm arquivos | Dump e storage de snapshots/ambientes diferentes, ou storage parcial | Confira a interseção de protocolos; obtenha o storage do mesmo snapshot do dump. |
| Linhas de anexo não vinculadas | `attachments`/`deposit_receipts` com `applicationID` fora da tabela `applications` | São órfãs; não há inscrição para vincular. |
| Datas erradas | Fuso do dump | O dump usa `TIME_ZONE='+00:00'`; o importador grava datetimes aware. |
| `protocolo duplicado` | Rodou sem `--update` | Use `--update` para reimportar. |
| Anexo aparece na ficha mas download falha | Metadado importado sem arquivo | Verifique o `--storage-root` e o `FileAsset.storage_key` no volume. |

## Testes

```bash
docker compose exec web python -m pytest apps/imports/test_sql_dump.py -q --no-cov
docker compose exec web python -m pytest apps/imports/tests.py -q --no-cov
```

Também vale rodar a suíte completa antes de commitar:

```bash
docker compose exec web python -m pytest -q
docker compose exec web ruff check .
docker compose exec web mypy apps/imports
```

## Segurança

- Dump e storage contêm dados pessoais. Mantenha-os em `$HOME` ou `tmp/`
  (este último é ignorado pelo Git) e nunca os commite.
- Não coloque credenciais de banco/SSH neste documento nem em scripts
  versionados.
