# Documentação funcional — Presentear Foz

## 1. Objetivo do MVP

Criar uma vitrine de produtos personalizados com aparência de e-commerce profissional, mas sem pagamento online. O principal objetivo de conversão é levar uma seleção organizada de produtos para o WhatsApp, usando um código de carrinho que o atendente consegue pesquisar no painel.

## 2. O que foi removido em relação à referência

- Bloco longo “A importância dos brindes personalizados”.
- Área de blog.
- Newsletter.
- Texto “Entregamos em todo o Brasil”.
- Checkout e pagamento online.
- Excesso de textos de SEO visíveis no meio da home.

O conteúdo institucional foi reduzido a blocos curtos, comerciais e fáceis de editar.

## 3. Fluxo do visitante

1. O visitante entra na home ou no catálogo.
2. Busca produtos por nome ou código e filtra por categoria.
3. Abre a página de um produto.
4. Define a quantidade e pode escrever uma observação de personalização.
5. Ao adicionar o primeiro item, o sistema cria:
   - um token privado e imprevisível;
   - um código curto no padrão `PFZ-XXXXXXX`;
   - um registro de carrinho no PostgreSQL.
6. O carrinho continua salvo no navegador por sessão permanente e `localStorage`.
7. Na tela do carrinho, o visitante informa dados opcionais e clica em “Continuar no WhatsApp”.
8. O carrinho passa para o status “Enviado pelo WhatsApp”.
9. O WhatsApp abre com uma mensagem pronta contendo o código e os itens.
10. O atendente busca o código no painel e continua o orçamento.

## 4. Persistência do carrinho

- Banco: PostgreSQL.
- Identificação do navegador: token aleatório de alta entropia.
- Recuperação: cookie de sessão permanente e `localStorage`.
- Validade padrão: 180 dias, editável no painel.
- O código curto não dá acesso público ao carrinho; ele serve somente para busca administrativa.
- Depois que uma seleção é enviada, novas adições criam outro carrinho para não alterar o histórico já recebido pelo atendente.

## 5. Loja pública

### Home

- Cabeçalho com logo, busca, WhatsApp, carrinho e categorias.
- Banner principal gerenciável.
- Faixa de diferenciais.
- Categorias em destaque.
- Produtos em destaque.
- Explicação curta do processo de compra/orçamento.
- Novidades.
- Logotipos de clientes.
- CTA final para WhatsApp.

### Catálogo

- Busca textual.
- Busca instantânea no cabeçalho.
- Filtro por categoria.
- Ordenação por destaque, recentes, nome e preço.
- Paginação.
- Cards com SKU, preço opcional e botão de carrinho.

### Produto

- Galeria com várias imagens.
- Nome, SKU, categoria e prazo.
- Preço de referência opcional.
- Quantidade mínima.
- Controle de estoque opcional.
- Orientação e observação de personalização.
- Produtos relacionados.

### Carrinho

- Código visível e copiável.
- Alteração de quantidade.
- Remoção de itens.
- Observações de personalização.
- Total apenas quando todos os produtos mostram preço.
- Formulário opcional de identificação.
- Botão de continuação para WhatsApp.

## 6. Painel administrativo

### Dashboard

- Total de produtos.
- Produtos ativos.
- Carrinhos em andamento.
- Envios para WhatsApp nos últimos 30 dias.
- Carrinhos fechados nos últimos 30 dias.
- Visualizações.
- Últimos carrinhos.
- Funil por status.
- Produtos mais adicionados ao carrinho.

### Produtos

- Criar, editar e arquivar.
- SKU único.
- Categoria.
- Descrição curta e completa.
- Preço e preço anterior.
- Mostrar ou ocultar preço.
- Quantidade mínima.
- Prazo de produção.
- Estoque opcional.
- Destaque e novidade.
- SEO.
- Várias imagens.
- Definição de imagem principal.
- Importação e exportação CSV.

### Categorias

- Nome, slug, descrição e imagem.
- Ordem de exibição.
- Ativação.
- Destaque na home.

### Banners

- Chamada, título, subtítulo e botão.
- Imagem desktop e mobile.
- Controle de sobreposição.
- Ordem e ativação.

### Clientes

- Nome.
- Logomarca.
- Link opcional.
- Ordem e ativação.

### Carrinhos e atendimento

- Busca por código, nome, empresa ou telefone.
- Filtros de status.
- Visualização dos itens e personalizações.
- Dados do cliente.
- Mensagem que foi enviada ao WhatsApp.
- Notas internas.
- Histórico de alterações.
- Status de atendimento:
  - aberto;
  - enviado pelo WhatsApp;
  - em atendimento;
  - orçamento enviado;
  - fechado;
  - não convertido;
  - abandonado.

### Configurações

- Nome da empresa.
- WhatsApp e Instagram.
- Localização e e-mail.
- Cores principais.
- Textos da home e rodapé.
- Exibição de clientes.
- Validade dos carrinhos.

### Gestão

- Usuários administrativos com perfis de gerente, administrador e super administrador.
- Biblioteca de mídia com bloqueio de exclusão quando o arquivo está em uso.
- Registro de auditoria.

## 7. Dados principais

- `users`: administradores.
- `categories`: categorias.
- `products`: produtos.
- `product_images`: imagens dos produtos.
- `banners`: banners da home.
- `client_logos`: clientes.
- `carts`: carrinhos e dados do atendimento.
- `cart_items`: itens com snapshots de nome, SKU e preço.
- `cart_history`: histórico do funil.
- `site_settings`: configurações editáveis.
- `media_assets`: arquivos enviados.
- `analytics_events`: eventos básicos de navegação e conversão.
- `audit_logs`: ações administrativas.

## 8. Segurança aplicada

- Hash seguro de senhas pelo Werkzeug.
- Proteção CSRF em formulários e API.
- Cookies `HttpOnly`, `SameSite=Lax` e `Secure` em produção.
- Token de carrinho aleatório e não sequencial.
- Código público sem acesso direto aos dados.
- Validação real de imagens com Pillow.
- Redimensionamento de imagens grandes.
- Extensões permitidas limitadas.
- Nomes de upload aleatórios.
- Limite de upload por requisição.
- Cabeçalhos de segurança HTTP.
- Correção de proxy para HTTPS no Railway.
- Registro de auditoria.

## 9. Infraestrutura no Railway

- Aplicação Flask com Gunicorn.
- PostgreSQL gerenciado pelo Railway.
- Volume montado em `/data`.
- Uploads em `/data/uploads`.
- Healthcheck em `/health` com verificação do PostgreSQL.
- Criação inicial pelo comando `python manage.py bootstrap`.
- Domínio esperado: `presentearfoz.com.br`.

## 10. Critérios de aceite

- Um produto pode ser cadastrado e aparecer na loja.
- O visitante consegue adicionar itens sem criar conta.
- O carrinho recebe código único.
- O carrinho continua disponível após fechar e abrir o navegador.
- O checkout abre o WhatsApp com o código.
- O administrador encontra o carrinho pelo código.
- O administrador consegue alterar o status e registrar notas.
- Uploads continuam disponíveis após novo deploy quando o volume está montado.
- O site funciona em desktop e celular.
