# Presentear Foz — e-commerce vitrine em Flask

MVP profissional para `presentearfoz.com.br`, construído em Python/Flask, PostgreSQL e preparado para deploy no Railway. O checkout não recebe pagamento: o visitante monta o carrinho, recebe um código aleatório e continua o atendimento pelo WhatsApp. O painel localiza a seleção pelo código e acompanha o orçamento até o fechamento.

## O que já está pronto

### Loja

- Home responsiva com banners, categorias, produtos em destaque, novidades, clientes e chamada para WhatsApp.
- Catálogo com busca, filtros por categoria, ordenação e paginação.
- Página de produto com galeria, SKU, quantidade mínima, observação de personalização, preço opcional e produtos relacionados.
- Carrinho persistente no PostgreSQL, associado a um token salvo na sessão e no `localStorage` do navegador.
- Código humano aleatório no padrão `PFZ-XXXXXXX`.
- Retomada do carrinho por até 180 dias por padrão; o prazo é editável no painel.
- Checkout de orçamento com nome, empresa, telefone e observações opcionais.
- Redirecionamento para WhatsApp com mensagem pronta, código e resumo dos itens.
- Se um carrinho já enviado receber novos produtos, o sistema cria uma nova seleção para preservar o histórico anterior.
- Sitemap, robots.txt, metadados SEO, Open Graph, páginas institucional, contato e privacidade.
- Sem blog, newsletter, pagamento online ou blocos longos de texto no meio da home.

### Painel administrativo

- Dashboard com produtos, visualizações, carrinhos em andamento, solicitações enviadas e conversões.
- Produtos: CRUD, múltiplas imagens, imagem principal, preço opcional, estoque, categoria, destaque, novidade, SEO e arquivamento.
- Importação e exportação de produtos por CSV.
- Categorias, banners e logotipos de clientes.
- Carrinhos: busca por código, nome, empresa ou telefone; filtros; itens; mensagem enviada; dados do cliente; notas internas; histórico e etapas do atendimento.
- Status: aberto, enviado, em atendimento, orçamento enviado, fechado, perdido e abandonado.
- Configurações de contatos, textos da home, cores e validade do carrinho.
- Perfis administrativos (`manager`, `admin` e `superadmin`), biblioteca de mídia com proteção contra exclusão de arquivos em uso e auditoria de ações.
- Proteção CSRF, senha com hash, controle de acesso por perfil, cookies `HttpOnly`, limite de upload e nomes de arquivo aleatórios.

## Estrutura

```text
app/
  admin/         painel administrativo
  api/           carrinho, restauração e busca instantânea
  auth/          login e logout
  main/          home, páginas, uploads, healthcheck e SEO
  services/      regras do carrinho
  shop/          catálogo, produto e checkout para WhatsApp
  static/        CSS, JavaScript, logomarca e placeholders
  templates/     loja e painel
config.py
manage.py
wsgi.py
railway.toml
requirements.txt
```

## Deploy no Railway

1. Crie um repositório no GitHub e envie todos os arquivos deste projeto.
2. No Railway, escolha **New Project → Deploy from GitHub Repo**.
3. Adicione um serviço **PostgreSQL** ao mesmo projeto. A variável `DATABASE_URL` será disponibilizada automaticamente.
4. No serviço da aplicação, adicione um **Volume** e monte em `/data`.
5. Configure as variáveis:

```env
SECRET_KEY=uma-chave-longa-e-aleatoria
SITE_URL=https://presentearfoz.com.br
UPLOAD_FOLDER=/data/uploads
ADMIN_EMAIL=seu-email@dominio.com
ADMIN_PASSWORD=uma-senha-forte
SESSION_COOKIE_SECURE=true
SESSION_DAYS=180
AUTO_CREATE_DB=true
SEED_DEMO=true
```

6. Faça o deploy. O comando configurado executa `python manage.py bootstrap` antes do Gunicorn. Ele cria as tabelas, configurações iniciais, produtos demonstrativos e o primeiro administrador.
7. Acesse `/admin/login` e troque a senha do administrador ou crie outro usuário no painel.
8. Depois de cadastrar produtos reais, pode alterar `SEED_DEMO=false`. Os registros existentes não são removidos.
9. Em **Settings → Domains**, conecte `presentearfoz.com.br` e configure o DNS conforme indicado pelo Railway.

## Volume persistente

Use obrigatoriamente:

```env
UPLOAD_FOLDER=/data/uploads
```

O PostgreSQL armazena produtos, carrinhos e configurações. O volume armazena imagens enviadas pelo painel. Sem o volume, uploads seriam perdidos em um novo deploy.

## Primeiro acesso

Com os valores padrão de desenvolvimento:

```text
E-mail: admin@presentearfoz.com.br
Senha: TroqueEstaSenha123!
```

Defina `ADMIN_EMAIL` e `ADMIN_PASSWORD` no Railway antes do primeiro deploy. O bootstrap não sobrescreve usuários ou configurações já existentes.

## CSV de produtos

No painel, abra **Produtos → Exportar CSV** para obter o modelo. As colunas aceitas são:

```text
sku,nome,categoria,status,preco,mostrar_preco,quantidade_minima,destaque,novo,descricao_curta
```

Produtos existentes são atualizados pelo SKU; novos SKUs criam novos produtos.

## Regras do carrinho

- A primeira adição cria o código e o token do carrinho.
- O token completo não aparece no WhatsApp; somente o código curto é enviado.
- O atendente pesquisa o código no painel e vê os itens, quantidades e observações.
- O navegador mantém o token em cookie de sessão permanente e `localStorage` para aumentar a chance de recuperação depois de semanas.
- O código não é sequencial e usa caracteres sem ambiguidades visuais.
- Um carrinho enviado permanece registrado e não é alterado por uma nova seleção.

## Comandos úteis

```bash
python manage.py bootstrap
flask --app wsgi:app create-admin
pytest
```

O projeto não depende de execução local para funcionar no Railway. Esses comandos servem para manutenção via Railway CLI ou shell do serviço.
