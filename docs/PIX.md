# **WSPIX** 

<mark>Webservice responsável pela geração, impressão e acompanhamento de Pix integrado ao Sistema MercúrioWeb.</mark> 

## **URLbase** 

<mark>[dev] https://api-dev.portalservicos.usp.br/wspix/api</mark> 

<mark>[prod] https://uspdigital.usp.br/wspix/api</mark> 

## **Autorização no Header HTTP** 

- X-Username: usar o mesmo do wsboleto 

- X-Password: usar o mesmo do wsboleto 

## **Endpoints** 

gerar - Gera um Pix 

- consultar - Consulta um Pix 

- listarConcluidos - Lista os Pix pagos de um período gerarPDF - Gera o PDF com os dados e QrCode do Pix gerarQrCode - Gera a imagem do QrCode do Pix 

- simularPag - Simula o pagamento do Pix (somente em dev) webhookConfig - Configura webhook da aplicação 

## **Gerar** 

<mark>[POST] <URL_BASE>/pix/gerar</mark> 

<mark>[BODY - application/json]</mark> 

|**Campo**|**Tipo**|**Tamanho**|**Obrig.**|**Obs:**|
|---|---|---|---|---|
|tipoPessoa|Texto|2|S|PF (pessoa física)<br>PJ (pessoa jurídica)|
|codPesOrg|Inteiro|10|N|se PF = NoUSP<br>se PJ = Código da<br>Organização|



|docPesOrg|Inteiro|14|Obrigatório<br>somente se<br>não informado<br>codPesOrg|se PF = CPF<br>se PJ = CNPJ|
|---|---|---|---|---|
|nomePesOrg|Texto|150|Obrigatório<br>somente se<br>não informado<br>codPesOrg|Nome da pessoa /<br>organização|
|valor|Decimal|9,2|S|Valor do Pix. (Formato: pt-br)|
|infoCobranca|Texto|140|N|Texto livre referente ao<br>objeto de cobrança|
|emailPesOrg|Texto|80|N|Email do interessado. Caso<br>informado, será enviado<br>email na emissão e<br>efetivação de pagamento<br>(somente no ambiente de<br>produção)|
|expiracao|Inteiro||N|Tempo de expiração em<br>segundos<br>_(default: 3600s = 1h)_|
|codigoFonteRecurso|Inteiro||S|Obter esta informação no<br>financeiro da unidade.<br>Para homologação, usar 423|
|codigoUnidadeDespesa|Inteiro||S|Obter esta informação no<br>financeiro da unidade.<br>Para homologação, usar 1|
|estruturaHierarquica|Texto||S|Obter esta informação no<br>financeiro da unidade.<br>Para homologação, usar<br>"\DISTRIBUIDOR"|



<mark>[dados retornados]</mark> 

|**Campo**|**Tipo**|**Tamanho**|**Obrig.**|**Obs:**|
|---|---|---|---|---|
|idfpix|Texto|35|S|Identificação única do Pix|
|qrCode|Texto|255|S|Pix copia e cola|
|qrCodeImgBase64|Texto||S|Imagem do QrCode em base 64|



## **Consultar** 

<mark>[GET] <URL_BASE>/pix/<idfpix></mark> 

<mark>Parâmetros (queryParam):</mark> 

verificar: se passado este parâmetro, também é verificado o status do pagamento no banco e realiza a baixa em caso de falha do webhook. Caso tenha um webhook cadastrado, este também será disparado. 

<mark>[dados retornados]</mark> 

|**Campo**|**Tipo**|**Tamanho**|**Obrig.**|**Obs:**|
|---|---|---|---|---|
|idfpix|Texto|35|S|Identificação única do Pix|
|qrCode|Texto|255|S|Pix copia e cola|
|qrCodeImgBase64|Texto|?|S|Imagem do QrCode em base 64|
|dataGeracao|Data|19|S|Data/Hora em que o Pix foi gerado|
|dataExpiracao|Data|19|S|Data/Hora em que o Pix expira|
|tipoPessoa|Texto|2|S|PF (pessoa física) / PJ (pessoa jurídica)|
|nomePesOrg|Texto|150|S|Nome da pessoa / organização|
|docPesOrg|Inteiro|14|S|Documento da pessoa / organização|
|dataPag|Data|19|N|Data/Hora do pagamento do Pix.<br>Retornado somente se status = "Concluído"|
|nomePesOrgPag|Texto||N|Nome da pessoa/organização que pagou o<br>Pix. Retornado somente se status =<br>"Concluído"|
|docPesOrgPag|Inteiro|14|N|Documento da pessoa/organização que<br>pagou o Pix. Retornado somente se status<br>= "Concluído"|
|valor|Decimal|9,2|S|Valor do Pix|



|**Campo**|**Tipo**|**Tamanho**|**Obrig.**|**Obs:**|
|---|---|---|---|---|
|status|Texto||S|Status do Pix: "Ativo", "Expirado",<br>"Concluído"|



## **<mark>Listar Concluídos</mark>** 

<mark>[GET] <URL_BASE>/pix/listarConcluidos</mark> 

<mark>Parâmetros (queryParam):</mark> 

- dtaini: Data inicial da pesquisa, formato: dd/MM/aaaa hh:mm:ss dtafim: Data final da pesquisa, formato: dd/MM/aaaa hh:mm:ss docPesOrg: CPF/CNPJ do interessado (opcional) 

- nomsissvc: Sistema/Serviço que gerou o Pix. Se não informado, considera o X-Username (opcional) 

<mark>Regra: O período da busca não pode ser maior que 30 dias</mark> 

<mark>[dados retornados]</mark> 

|**Campo**|**Tipo**|**Tamanho**|**Obrig.**|**Obs:**|
|---|---|---|---|---|
|idfpix|Texto|35|S|Identificação única do Pix|
|tipoPessoa|Texto|2|S|PF (pessoa física) / PJ (pessoa jurídica)|
|docPesOrg|Inteiro|14|S|Documento da pessoa / organização|
|nomePesOrg|Texto|150|S|Nome da pessoa / organização|
|valor|Decimal|9,2|S|Valor do Pix|
|dataGeracao|Data|19|S|Data/Hora em que o Pix foi gerado|
|dataExpiracao|Data|19|S|Data/Hora em que o Pix expira|
|dataPag|Data|19|S|Data/Hora do pagamento do Pix|
|nomePesOrgPag|Texto||S|Nome da pessoa/organização que pagou o<br>Pix.|
|docPesOrgPag|Inteiro|14|S|Documento da pessoa/organização que<br>pagou o Pix.|



## **Gerar PDF** 

<mark>[GET] <URL_BASE>/pix/<idfpix>/pdf</mark> 

## **Gerar QRcode** 

<mark>[GET] <URL_BASE>/pix/<idfpix>/qrcode</mark> 

## **SimularPag (somente em dev)** 

<mark>[PATCH] <URL_BASE>/pix/<idfpix>/simularPag</mark> 

# **Confirmação de pagamento** 

- A confirmação de pagamento ocorre de forma imediata, tendo a possibilidade da aplicação ser avisada por Webhook (detalhamento abaixo) 

- Para verificação imediata de pagamento em um pix em específico, usar o método _consultar_ com o parâmetro verificar 

## **Webhook** 

Após a confirmação do pagamento, os dados abaixos serão enviados por webhook para a URL cadastrada juntamente com o token de segurança "X-Token", enviada por header. 

**OBS:** É extremamente recomendável fazer a verificação do token de segurança para evitar chamadas não autorizadas ao webhook de seu sistema, pois abre a possibilidade de simular pagamentos não efetuados. 

<mark>[dados enviados em JSON por POST]</mark> 

|**Campo**|**Tipo**|**Tamanho**|**Obrig.**|**Obs:**|
|---|---|---|---|---|
|idfpix|Texto|35|S|Identificação única do Pix|
|status|Texto|10|S|Retorna 'Pago'|
|valor|Decimal|9,2|S|Valor do Pix|
|dataGeracao|Data|19|S|Data/Hora em que o Pix foi gerado|
|dataExpiracao|Data|19|S|Data/Hora em que o Pix expira|
|docPesOrgPag|Inteiro|14|S|Documento da pessoa/organização que<br>pagou o Pix.|
|nomePesOrgPag|Texto||S|Nome da pessoa/organização que pagou o<br>Pix.|
|dataPag|Data|19|S|Data/Hora do pagamento do Pix|
|retornoBancario|Texto|35|S|Retorno/Autenticação bancária|



## **Configurar Webhook** 

### **<mark>Cadastrar</mark>** 

<mark>[POST] <URL_BASE>/pix/webhookConfig</mark> 

<mark>[BODY - application/json]</mark> 

|**Campo**|**Tipo**|**Tamanho**|**Obrig.**|**Obs:**|
|---|---|---|---|---|
|url|Texto|800|S|A URL a ser chamada após a confirmação do pagamento|
|token|Texto|100|S|O token de segurança que será enviado no header "X-<br>Token"|



**OBS:** No ambiente de produção, pode levar até 10min para que este cadastro (que é cacheado) seja atualizado em todos servidores. 

### **<mark>Remover</mark>** 

<mark>[DELETE] <URL_BASE>/pix/webhookConfig</mark> 

