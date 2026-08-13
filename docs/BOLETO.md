## **WS - Boleto Bancário** 



ESPECIFICAÇÃO de WEB SERVICE 

|º|Criado em|Atualizado em|
|---|---|---|
|N|05/07/2011|29/5/2020 09:52:37|



## **Nome do Componente** 

WS - Boleto Bancário 

## **Descrição** 

Este Web service é responsável pela geração, impressão e acompanhamento de Boleto Bancário integrado com o Sistema MercúrioWeb. 

## **URL Desenvolvimento (WSDL)** 

- Desenvolvimento: https://dev.uspdigital.usp.br/wsboleto/wsdl/boleto.wsdl 

- Produção: https://uspdigital.usp.br/wsboleto/wsdl/boleto.wsdl 

## **Métodos Disponíveis** 

- gerarBoleto: geração do boleto; 

- gerarBoletoRegistrado: geração do boleto registrado; 

- obterBoleto: impressão do boleto em pdf; 

- obterSituacao: informa a situação atual do boleto (emitido, pago, cancelado, etc); 

- cancelarBoleto: cancela um boleto gerado que não foi pago; 

- obterDetalhe: obtém informações do pdf do boleto gerado, tais como: linha digitável, valor cobrado, etc; 

- obterDetalheLote: Semelhante ao método obterDetalhe, mas para uma requisição em lote de um ou mais boletos; 

- obterSituacaoLote: Semelhante ao método obterSituacao, mas para uma requisição em lote de um ou mais boletos; 

- cancelarBoletoLote: Semelhante ao método cancelarBoleto, mas para uma requisição em lote de um ou mais boletos. 

- registrarBoleto: Registra um boleto em caso de falha. 

**Método: gerarBoleto (será descontinuado a partir de 01/2020)** Parâmetros de entrada: 

|**Campo**|**Descrição**|**Tipo**|**Tamanho**|**Obrig.**|**Observação**|
|---|---|---|---|---|---|
|codigoUnidadeDespesa|Código da unidade de<br>despesa.|Numérico|-|S|Verificar o código no anexo 1.|
|nomeFonte|Nome<br>da<br>fonte<br>de<br>recursos.|String|50|S|Obter esta informação com o<br>GRS do Mercúrio. Exemplo:<br>Prestação de Serviços.|
|nomeSubfonte|Nome da sub-fonte de<br>recursos.|String|50|S|Obter esta informação com o<br>GRS do Mercúrio. Exemplo:<br>Concurso Público.|
|estruturaHierarquica|Estrutura hierárquica|String|255|S|Obter esta informação com o<br>GRS do Mercúrio. Exemplo:<br>\GR\CODAGE\DRH\PROCSELET.|
|codigoConvenio|Código do convênio ao<br>qual<br>se<br>refere<br>este<br>boleto.|Numérico|-|N|Obter esta informação com o<br>GRS do Mercúrio.|
|dataVencimentoBoleto|Data de vencimento para<br>o boleto.|Data|-|N|Se não informado, o<br>vencimento será o dia atual<br>acrescido de 5 dias.<br>Formato dd/mm/aaaa|
|valorDocumento|Valor do boleto|Numérico|15,2|S|Formato 0.00 (com ponto no<br>separador decimal). Exemplo:<br>120.00|
|valorDesconto|Valor do desconto para o<br>boleto|Numérico|15,2|N|Formato 0.00 (com ponto no<br>separador decimal).|



Pág 1/17 

## **WS - Boleto Bancário** 

||ESPE|CIFICAÇÃO<br>|de WEB|SERVI<br>|CE<br>|
|---|---|---|---|---|---|
|Nº||Criado em<br>05/07/2011||<br>|tualizado em<br>29/5/2020 09:52:37|
|tipoSacado|Indica o tipo de sacado.|String|2|S|Valores:<br>PF - Pessoa Física.<br>PJ-Pessoa Jurídica.|
|cpfCnpj|Para<br>tipoSacado=PF,<br>informar<br>o<br>CPF.<br>Para<br>tipoSacado=PJ,<br>informar o CNPJ.|Numérico|14|S|Apenas números.<br>Exemplo: 04112731556|
|nomeSacado|Nome<br>de<br>quem<br>está<br>pagando o boleto.|String|60|S||
|codigoEmail|Email<br>de<br>quem<br>está<br>pagando o boleto|String|80|N||
|informacoesBoletoSacado|Informações gerais para<br>sacado,<br>impresso<br>na<br>parte de cima do boleto|String|2730|N||
|instrucoesObjetoCobranca|Informações<br>gerais<br>colocadas<br>no<br>campo<br>"Instruções"do boleto.|String|255|S|Exemplo: Não receber após o<br>vencimento.|



## <u>Resultado:</u> 

|**Campo**<br>**Descriç**|**ão**||**Tipo**<br>**T**|**amanho**|**Obrig.**<br>**Observação**|
|---|---|---|---|---|---|
|codigoIDBoleto<br>Código de identifica<br>bancário gerado. Es<br>ser<br>armazenado<br>outros métodos com<br>e obterSituacao.<br>**Método: gerarBoletoRegistrado**<br>Parâmetros de entrada:|ção d<br>te códi<br>para<br>o obt|o boleto<br>go deve<br>realizar<br>erBoleto|String|60|S|
|**Campo**<br>**Descriç**|**ão**|**Tipo**|**Tamanho**|<br>**Obrig.**|**Observação**|
|codigoUnidadeDespesa<br>Código<br>unidade<br>despesa.|da<br>de|Numérico|-|S|Verificar o código no anexo 1.|
|**(*) codigoFonteRecurso**<br>Código<br>fonte<br>recursos.|da<br>de|Numérico|-|N(1)|Irá substituir os campos<br>nomeFonte e nomeSubFonte.<br>Obter esta informação no<br>financeiro da unidade. Será<br>obrigatório a partir de 01/2020|
|nomeFonte<br>Nome da<br>de recurso|fonte<br>s.|String|50|S|Obter esta informação com o<br>GRS do Mercúrio. Exemplo:<br>Prestação de Serviços.|
|nomeSubfonte<br>Nome da<br>fonte<br>recursos.|sub-<br>de|String|50|S|Obter esta informação com o<br>GRS do Mercúrio. Exemplo:<br>Concurso Público.|
|estruturaHierarquica<br>Estrutura<br>hierárquic|a|String|255|S|Obter esta informação com o<br>GRS do Mercúrio. Exemplo:<br>\GR\CODAGE\DRH\PROCSELET.|
|codigoConvenio<br>Código<br>convênio<br>qual se r<br>este bolet|do<br>ao<br>efere<br>o.|Numérico|-|N|Obter esta informação com o<br>GRS do Mercúrio.|
|dataVencimentoBoleto<br>Data<br>venciment<br>para o bol|de<br>o<br>eto.|Data|-|N|Se não informado, o<br>vencimento será o dia atual<br>acrescido de 5 dias.<br>Formato dd/mm/aaaa|
|valorDocumento<br>Valor do b|oleto|Numérico|15,2|S|<br>Formato 0.00 (com ponto no<br>separador decimal). Exemplo:<br>120.00|
|valorDesconto<br>Valor<br>desconto<br>o boleto|do<br>para|Numérico|15,2|N|Formato 0.00 (com ponto no<br>separador decimal).|



Pág 2/17 

## **WS - Boleto Bancário** 

|<br>Nº|ESPE<br> <br>|CIFICAÇÃO<br>Criado em<br>05/07/2011|de WEB|SERVI<br> <br>2|CE<br>Atualizado em<br>9/5/2020 09:52:37|
|---|---|---|---|---|---|
|**(*)numeroUspSacado**|Número<br>USP<br>do Sacado|Numérico|-|N|Se informado, os seguintes<br>dados são obtidos<br>automaticamente:<br>tipoSacado(PF), cpfCnPj,<br>nomeSacado, cepSacado,<br>numeroEnderecoSacado,<br>complementoEnderecoSacado,<br>codigoEmail|
|**(*)codigoOrganizacaoSacado**|Código<br>da<br>Organização do<br>Sacado|Numérico|-|N|<br>Se informado, os seguintes<br>dados são obtidos<br>automaticamente:<br>tipoSacado(PJ), cpfCnPj,<br>nomeSacado, cepSacado,<br>codigoEmail|
|tipoSacado|Indica o tipo de<br>sacado.|String|2|S|<br>Valores:<br>PF - Pessoa Física.<br>PJ-Pessoa Jurídica|
|cpfCnpj|Para<br>tipoSacado=PF,<br>informar o CPF.<br>Para<br>tipoSacado=PJ,<br>informar<br>o<br>CNPJ.|Numérico|14|S|.<br>Apenas números.<br>Exemplo: 04112731556|
|nomeSacado|<br>Nome de quem<br>está pagando o<br>boleto|String|60|S||
|**(*)cepSacado**|.<br>Código<br>de<br>endereçamento<br>postal (CEP) do<br>sacado|String|9|N|Apenas números. Deve ser um<br>CEP válido. O WS faz a<br>verificação pela base dos<br>correios.|
|**(*)numeroEnderecoSacado**|<br>Número<br>referente<br>ao<br>endereço<br>do<br>d|String|8|N||
|**(*)complementoEnderecoSacado**|sacao<br>Complemento<br>do<br>endereço:<br>bloco,<br>andar,<br>etc|String|80|N||
|codigoEmail|...<br>Email de quem<br>está pagando o<br>boleto|String|80|N||
|informacoesBoletoSacado|<br>Informações<br>gerais<br>para<br>sacado,<br>impresso<br>na<br>parte de cima<br>do boleto|String|2730|N||
|instrucoesObjetoCobranca|<br>Informações<br>gerais<br>colocadas<br>no<br>campo<br>"Instruções" do<br>blt|String|255|S|Exemplo: Não receber após o<br>vencimento.|
|**(*) numeroUspUsuario**<br>Resultado:<br>|oeo.<br>Número<br>USP<br>do<br>usuário<br>autenticado no<br>sistema<br>que<br>gerou o boleto<br>|Numérico<br>|-<br> <br>|N<br>|<br> <br>|
|**Campo**<br>codigoIDBoleto<br>Código d<br>bancário|**Descrição**<br>e identificação d<br>gerado. Este códi|<br>o boleto<br>go deve<br>S|**Tipo**<br>**T**<br>tring|**amanho**<br>60|<br>**Obrig.**<br>**Observação**<br>S|



Pág 3/17 

## **WS - Boleto Bancário** 



ESPECIFICAÇÃO de WEB SERVICE 

Criado em Atualizado em Nº 05/07/2011 29/5/2020 09:52:37 ser armazenado para realizar outros métodos como obterBoleto <u>e obterSituacao.</u> 

## (*) Campos adicionados 

- (1) O campo passa a ser obrigatório a partir de 02/01/2020 

## **Método: obterBoleto** <u>Parâmetros de entrada:</u> 

|**Campo**|**Descrição**<br>|**Tipo**|**Tamanho**|**Obrig.**|**Observação**|
|---|---|---|---|---|---|
|codigoIDBoleto|Código de identificação do boleto<br>bancário<br>gerado<br>através<br>do<br>método gerarBoleto.|String|60|S||
|Resultado:<br>**Campo**|**Descrição**|**Tipo**|**Tamanho**|**Obrig.**|**Observação**|
|boletoPDF|Boleto em PDF no formato binário<br>codificado para Base64.|Binário<br>Base64|-|S|Este  método suporta<br>o envio eficiente de<br>dados binários<br>através de MTOM em<br>webservices.|



## **Método: obterSituacao** <u>Parâmetros de entrada:</u> 

|**Campo**|**Descrição**|**Tipo**|**Tamanho**|**Obrig.**|**Observação**|
|---|---|---|---|---|---|
|<br>codigoIDBoleto<br>Resultado:|<br>Código de identificação do boleto<br>bancário<br>gerado<br>através<br>do<br>método gerarBoleto.|<br>String|60|<br>S||
|**Campo**|**Descrição**|**Tipo**|**Tamanho**|**Obrig.**|**Observação**|
|statusBoletoBancario|Indica<br>a<br>situação<br>do<br>Boleto<br>Bancário.|String|1|N|Valores para o status<br>do boleto:|
||||||E –Emitido<br>P – Pago<br>V – Verificar<br>C–Cancelado|
|valorCobrado|Valor final a ser pago.|Númerico|-|S|Formato 0.00 (com<br>ponto no separador<br>decimal).|
|valorEfetivamentePago|Valor<br>efetivamente<br>pago<br>do<br>boleto,<br>retornado<br>pelo<br>Banco.<br>Pode ser eventualmente, maior ou<br>menor que o valor a ser pago.|Númerico|-|S|Formato 0.00 (com<br>ponto no separador<br>decimal).|
|dataVencimentoBoleto|Data de vencimento para o boleto.|Data|-|S|Formato<br>dd/mm/aaaa.|
|dataEfetivaPagamento|Data que o valor foi contabilizado<br>para a USP (retorno financeiro do<br>Banco pra a USP).|Data|-|N|Formato<br>dd/mm/aaaa.|
|dataRegistro|Data que o boleto foi registrado no<br>banco e que portanto já está<br>disponível pagamento.|Data|-|N|Formato<br>dd/mm/aaaa.|
|dataCancelamentoRegistro|Data que o boleto foi cancelado no<br>banco.|Data|-|N|Formato<br>dd/mm/aaaa.|



Pág 4/17 

## **WS - Boleto Bancário** 



ESPECIFICAÇÃO de WEB SERVICE 

|º|Criado em|Atualizado em|
|---|---|---|
|N|05/07/2011|29/5/2020 09:52:37|



## **Método: cancelarBoleto** <u>Parâmetros de entrada:</u> 

|**Campo**|**Descrição**|**Tipo**|**Tamanho**|**Obrig.**|**Observação**|
|---|---|---|---|---|---|
|codigoIDBoleto|Código de identificação do boleto<br>bancário<br>gerado<br>através<br>do<br>método gerarBoleto.|String|60|S||
|Resultado:<br>**Campo**|**Descrição**|**Tipo**|**Tamanho**|**Obrig.**|**Observação**|
|statusBoletoBancario|Indica<br>a<br>situação<br>do<br>Boleto<br>Bancário.|String|1|N|Valores para o status<br>do boleto:<br>E –Emitido<br>C–Cancelado|
|valorCobrado|Valor final a ser pago.|Númerico|-|S|Formato 0.00 (com<br>ponto no separador<br>decimal).|
|valorEfetivamentePago|Valor<br>efetivamente<br>pago<br>do<br>boleto,<br>retornado<br>pelo<br>Banco.<br>Pode ser eventualmente, maior ou<br>menor que o valor a ser pago.|Númerico|-|S|Formato 0.00 (com<br>ponto no separador<br>decimal).|
|dataVencimentoBoleto|Data de vencimento para o boleto.|Data|-|S|Formato<br>dd/mm/aaaa.|
|dataEfetivaPagamento|Data que o valor foi contabilizado<br>para a USP (retorno financeiro do<br>Banco pra a USP) .|Data|-|N|Formato<br>dd/mm/aaaa.|



## **Método: obterDetalhe** <u>Parâmetros de entrada:</u> 

|**Campo**|**Descrição**|**Tipo**|**Tamanho**|**Obrig.**|**Observação**|
|---|---|---|---|---|---|
|codigoIDBoleto|Código de identificação do boleto<br>bancário<br>gerado<br>através<br>do<br>método gerarBoleto.|String|60|S||



## – <u>Resultado: Principais campos do par chave valor utilizado na geração do pdf.</u> 

|**Campo**|<br>**Descrição**<br>|<br>**Tipo**|
|---|---|---|
|codunddsp|Código unidade de despesa<br>|String|
|smbmda|Símbolo moeda utilizada|String|
|ctucodbar|Contéudo pra o código de barra|String|
|nomsac<br>|Nome do pagador<br>|String|
|nomsubfte|Nome subfonte|String|
|istobtcob|Informações adicionais no boleto|String|
|nomfte|Nome fonte|String|
|numbco|Número banco<br>|String|
|nssnumcoo|Nosso número|String|
|nomcdt|Nome do beneficiário|String|
|endund|Endereço unidade|String|
|sglcendsp|Sigla centro de despesa|String|
|lnhdgv|Linha digitável|String|
|ifmbtosac|Informações adicionais para o pagador|String|
|coddot|Código dotação|String|
|cpfcpj|CPF ou CNPJ do pagador|String|
|dtavenbto|Data vencimento do boleto<br>|String|
|anomesref|Ano e mês de referência|String|
|tipsac|Tipo de pagador (PF ou PJ)|String|
|nomunddsp|Nome unidade de despesa|String|
|vlrcob|Valor cobrado|String|
|codema|Email informado pelo pagador|String|



Pág 5/17 

## **WS - Boleto Bancário** 



<!-- Start of picture text -->
ESPECIFICAÇÃO de WEB SERVICE<br>Criado em   Atualizado em<br>Nº<br>05/07/2011  29/5/2020 09:52:37<br>cpjcdt  CNPJ do beneficiário  String<br>vlrdoc  Valor do documento  String<br>locpag  Local de pagamento preferencial  String<br>endund  Endereço da Unidade  String<br>endsac  Endereço do Sacado  String<br><!-- End of picture text -->

|**Método: obterDe**<br>Parâmetros de ent|**talheLote**<br>rada: Um lote com um ou mais cod|igoIDBo|leto|||
|---|---|---|---|---|---|
|**Campo**|**Descrição**|**Tipo**|**Tamanho**|**Obrig.**|**Observação**|
|codigoIDBoleto|Código de identificação do boleto<br>bancário<br>gerado<br>através<br>do<br>método gerarBoleto.|String|60|S||



Resultado: Semelhante ao do método obterDetalhe mais o campo codigoIDBoleto para identificar o detalhe de cada boleto informado como parâmetro de entrada no lote. 

**Método: obterSituacaoLote** <u>Parâmetros de entrada: Um lote com um ou mais codigoIDBoleto</u> 

|**Campo**|**Descrição**|**Tipo**|**Tamanho**|**Obrig.**|**Observação**|
|---|---|---|---|---|---|
|codigoIDBoleto|Código de identificação do boleto<br>bancário<br>gerado<br>através<br>do<br>método gerarBoleto.|String|60|S||



Resultado: Semelhante ao do método obterSituacao mais o campo codigoIDBoleto para identificar a situação de cada boleto informado como parâmetro de entrada no lote. 

## **Método: cancelarBoletoLote** 

|Parâmetros de entrada: Um lote com um ou mais codigoIDBoleto|
|---|



|**Campo**|**Descrição**|**Tipo**|**Tamanho**|**Obrig.**|**Observação**|
|---|---|---|---|---|---|
|codigoIDBoleto|Código de identificação do boleto<br>bancário<br>gerado<br>através<br>do<br>método gerarBoleto.|String|60|S||



Resultado: Semelhante ao do método cancelarBoleto mais o campo codigoIDBoleto para identificar a situação de cada boleto informado como parâmetro de entrada no lote. 

## **Método: registrarBoleto** <u>Parâmetros de entrada:</u> 

|**Campo**|**Descrição**|**Tipo**|**Tamanho**|**Obrig.**|**Observação**|
|---|---|---|---|---|---|
|<br>codigoIDBoleto|<br>Código de identificação do boleto<br>bancário<br>gerado<br>através<br>do<br>método gerarBoleto.|<br>String|60|<br>S||
|Resultado:||||||
|**Campo**|**Descrição**|**Tipo**|**Tamanho**|**Obrig.**|**Observação**|
|String|Retorna “OK” se foi regitrado com<br>sucesso|String|-|S||



Pág 6/17 



||**WS - Boleto Bancário**||
|---|---|---|
||ESPECIFICAÇÃO de WEB SER|VICE|
|Nº|Criado em<br>05/07/2011|Atualizado em<br>29/5/2020 09:52:37|



## **Autenticação** 

A autenticação no webservice é realizada através de cabeçalhos SOAP. É necessário a adição de dois cabeçalhos SOAP para usuário e senha do sistema, o nome dos cabeçalhos são case sensitive. A seguir o nome utilizado e a descrição de cada cabeçalho: 

- “username” : Username registrado no sistema para utilizar o web service. 

- “password” : Senha fornecida pelo administrador do sistema. Caso não possua uma senha, contactar o administrador do sistema. 

## **FAQ** 

- O que seria os status  ‘V’ de Verificar? 

O status Verificar(V) ocorre raramente nas ocasiões em que o 'valor efetivamente pago' pelo usuário é diferente do 'valor a pagar' que consta no boleto. Neste caso, o DF faz a verificação do que ocorreu e conforme o caso, altera manualmente para Pago(P) 

- <u>Qual status os serviço retorna para boletos emitidos não pagos e com data vencida?</u> 

Continua a voltar Emitido(E), só após um tempo de Vencido (aproximadamente 30 dias) é que volta Cancelado(C), devido ao cancelamento automático 

- <u>Como simular pagamento no ambiente de teste?</u> 

Ao gerar o boleto, enviar no campo <instrucoesObjetoCobranca> o marcador #PAGO. Após no máximo 10 minutos, o boleto será registrado como Pago(P) 

## **Responsáveis** 

- Flávio Bezerra Pereira (flavio.b.pereira@usp.br) 

- Renato Takeshi Hamatu (renatoth@usp.br) 

## **Versões** 

- 29/05/2020 – Adicionado FAQ, removido menção ao status Isento(I) e pequenas correções 

- 25/11/2019 – Alteração em gerarBoletoRegistrado: novo campo codigoFonteRecurso e numeroUspUsuario. Alteração em obterSituacao: retorno dos campos dataRegistro e dataCancelamentoRegistro 

- 17/08/2017 – Adicionado método gerarBoletoRegistrado e registrarBoleto. 

- 19/12/2016 – Adicionado métodos em lote. 

- 13/12/2016 – Adicionado o método obterDetalhe. 

- 28/01/2016 – Adicionado o método cancelarBoleto. Criado wsdl fixo para contornar o problema de HTTPS. 

- 05/07/2011 – Criação do componente. 

Pág 7/17 









<!-- Start of picture text -->
) Nevisoaplll)) Project<br>Creates a new soapUI Project in this workspace<br>ridweom: [id<br>Create Requests: Create sample requests for all operations?<br>Create TestSuite: [_] Creates a TestSuite for the imported WSDL or WADL<br>Create MockService: = [_] Creates a Web Service Simulation of the imported WSDL<br>Add REST Service: [_] Opens dialog to create REST Service<br>Relative Paths: [_] Stores all file paths in project relatively to project file (requires save)<br>Create Web TestCase: [| Creates a TestCase with a Web Recording session for functional web testing<br>LOK} | Cancel<br><!-- End of picture text -->

a Fl] boleto 

- GI. BoletoSIBPartBinding res) cancelarBoleto HS gerarBaleta eS obterBoleto @ obterSituacaa 





<!-- Start of picture text -->
Pein oa 22 @  Jhttp:inodedivws.intranet. reitoria, usp.br:80,wsboleto/boleto<br>os <soapenv: Header /><br>z tsoapenry: Body><br>c sus: obterBoleta><br>tidentificacac><br>scodigoIDBoletart</codigoIDBoleta><br>tfidentificacacg><br></uws:ohterBoleto=<br></soapeny: Body><br>+ /soapenr: Envelopes<br><!-- End of picture text -->

# eet aoao a2 WB Jhttp: 'nodediws. intranet. reitoria usp. br:80fwsboleto/boleta 

= <soapenr: Envelope umlns:soapenv="http: //schemas.xmlsoap.org/soapfenvelope/" xmli oe tsoapeny: Header> ce tpassword?testel</password> z susername? SOY S424 /username> Co =,'soapenw: Header> tsoapeny: Body> ays 1 obterBoleta> stidentificacac> tcodigolDBoletoa=?+</codigolDBoleroa> = identi ficacaqc> s' ws: obterBoleta> t/ oapeny: Body> +/so0apeny: Envelope> 

[PJ & BOO 2 @ [http:/poc 





<!-- Start of picture text -->
File Tools Desktop Help<br>AaI OS 6 KEDORa<br>=)oh Projects<br>|| =} I  Gy BOLETO NODEDIWS PeetH 33 o O “22 JatoPillYnodedi<br>SF BoletoSIBPortBindioo = napeny: Envelope xulns: soapeny="<br>i @ gerarBoleto Show Interface viewer Enter soapeny: Header><br>Ee = obterBoleto| =i(“‘(i‘(i‘i(itt&;”]”*”*é<S:;:;S;é‘(SO!” sasername> Sov? 542s fusername<br>i i ea Add JMS endpoint tpassword+testel+/password><br>ge Request B B<br>GH@ obterSituace Generate Code b JBossWS 4rtiFacts<br>Check WST Compliance Cte +All JBosswW'S J4x-WS Artifacts<br>Launch TcpMon JAx-RPC Ortifacts<br>a<br>Generate TestSuite . —<br>Generate MockService Axis 1.4 Artifacts<br>Generate Documentation Axis 2 ortifacts<br>fe) Update Definition FS Apachea  (CXF<br>72) Export Definition Cp XFire 1.% Stubs<br>Oracle Proxy Artifacts<br>Clone InterFace FS TTX€<br>;<br>Remove Exeluir JAxB 2.0 OrtiFacks<br>Interface Properties xmiBeans Classes<br>Property Online Help Fi TTWET 2.0 Artifacts X€<br>Marne BoletoSIBPortBinding GSoap artifacts<br>Description a<br>Definition URL http: /fnodediws intranet.re... Online Help Fi<br>Binding fhttp:fivws. boleto.usp/}Bole...<br>SOAP Version SOAP 1.1<br>Cached true<br>Style Document<br>WS-A version NONE<br>WiS-O, anonymous optional<br><!-- End of picture text -->





<!-- Start of picture text -->
@ JAX-WS artifacts x]<br>JAX-WSSpecify  Artifacargumen t ss for WSDP/IAS-WS wsimport JOP<br>Basic Custom Ars<br>WSDL: https Vnodediws intranet. reitoria. usp. 6r/imsboleto/boletarwsdl<br>Use cached WSDL: Use cached WSDL<br>Keep: (_] tkeep generated Files)<br><!-- End of picture text -->



<!-- Start of picture text -->
x<br>soapUI Preferences Ay<br>Set global soapUI settings ra<br>Proxy Settings<br>WSDL Settings JAX-WS WSImport: — |C: Arquivos de programas\Javaljdk1.6.0_13\bin<br>UI Settings ;<br>WS-I Settings apa kere F<br>loadUI Settings<br>Web Recording Settings ANT 1.64: L Cisd<br><!-- End of picture text -->





<!-- Start of picture text -->
x<br>JAX-WSSpecify argumenArtifac t ss for JWSDOP/IAX-W'S wrsimport joe<br>Basic Custom 4rgs<br>WSDL:<br>Use cached WSDL: [| Use cached WSDL<br>Keep: {_] tkeep generated files)<br><!-- End of picture text -->

Exesiete coeYY SBoletoTestebP echo 

- | ESS source | ERB usp. boletows i | [Fy BoletoSIBService,java P| cl [a Boletow'S, java it f+) [2) GerarBoleto.java PE #1 [J] GerarBoletoResponse.java PoE [yy Identificacao.java Po a [ ObjectFactoryjava P| cl [a ObberBoleto,java i | [J] ObterBoletotesponse.java Po HL ObterSituacao,java Ha [y ObterSituacaoResponse java 

- Po a [ package-info,java it f]-[F) Reguisicac.java Pt [J] Situacaoc.java f- fF) WiSException. java 

- EeBBA JRE System Library [jre1.6,0_07] 

## **WS - Boleto Bancário** 



||ESPECIFICAÇÃO de WEB SERVICE|
|---|---|
|Nº|Criado em<br>05/07/2011<br>Atualizado em<br>29/5/2020 09:52:37|



A partir do novo pacote, podemos criar um simples cliente para a operação de obterBoleto, coforme a classe BoletoMain. 

```
import java.io.ByteArrayOutputStream;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import javax.activation.DataHandler;
import javax.xml.namespace.QName;
import com.sun.xml.ws.api.message.Header;
import com.sun.xml.ws.api.message.Headers;
import com.sun.xml.ws.developer.WSBindingProvider;
import usp.boletows.BoletoSIBService;
import usp.boletows.BoletoWS;
import usp.boletows.Identificacao;
```

```
public class BoletoMain {
```

```
    public static void main(String[] args) throws Exception {
```

```
        //instanciando um port
        BoletoSIBService service = new BoletoSIBService();
        BoletoWS port = service.getBoletoSIBPort();
```

```
        //indicando usuario e senha em SOAP Header
        List<Header> list = new ArrayList<Header>();
        list.add(Headers.create(new QName("username"),"5377542"));
        list.add(Headers.create(new QName("password"),"teste1"));
        WSBindingProvider bp = (WSBindingProvider)port;
        bp.setOutboundHeaders(list);
```

```
        //identificacao do boleto
        Identificacao ident = new Identificacao();
        ident.setCodigoIDBoleto("eCD53whElh2W2G9NDAShjnszfL0c9GZN86444Lol8Sm1gTqiHcLykw==");
```

```
        //disparando uma operacao
        DataHandler dataHandler = port.obterBoleto(ident);
        //redirecionando os dados binarios do pdf para um arquivo em disco
        ByteArrayOutputStream buffOS= new ByteArrayOutputStream();
        dataHandler.writeTo(buffOS);
        byte[] buff = buffOS.toByteArray();
        OutputStream out = new FileOutputStream("teste.pdf");
        out.write(buff);
        out.close();
}
```

```
}
```

## **Anexo 4 – Exemplo de Implementação em PHP** 

O código a seguir é um exemplo de um cliente para obter um boleto pelo web service em PHP através da biblioteca NuSOAP obtida em <u>http://sourceforge.net/projects/nusoap/.</u> Caso o web service seja implementado com HTTPS, será necessário habilitar a extensão “extension=php_curl.dll” no arquivo php.ini. 

```
<?php
/*
 * Exemplo de um simples cliente para a operacao obterBoleto via Web service
 *
```

```
 */
```

```
//bibliotecas
require_once('lib/nusoap.php');
```

Pág 15/17 



## **WS - Boleto Bancário** 



ESPECIFICAÇÃO de WEB SERVICE 

Criado em Atualizado em Nº 05/07/2011 29/5/2020 09:52:37 

```
'valorDocumento' => $valorDocumento,
'valorDesconto' => $valorDesconto,
'tipoSacado' => $tipoSacado,
'cpfCnpj' => $cpfCnpj,
'nomeSacado' => utf8_decode($nomeSacado),
'codigoEmail' => utf8_decode($codigoEmail),
'informacoesBoletoSacado' => $informacoesBoletoSacado,
'instrucoesObjetoCobranca' => $instrucoesObjetoCobranca
);
```

```
echo '<br>';
//faz a requisição SOAP para gerar o codigo do boleto
$retorno = $clienteSoap->call('gerarBoleto', array('requisicao' => $param));
if ($clienteSoap->fault) {
 echo 'Falha no cliente - Geração Código <br>';
 print_r($retorno);
 exit;
}
if ($clienteSoap->getError()){
printf("%s", $erro);
exit;
}
$codigoIDBoleto = $retorno['identificacao']['codigoIDBoleto']; //guarda o codigo do boleto na
variavel para uso posterior
//fim do gerar boleto
```

Pág 17/17 

