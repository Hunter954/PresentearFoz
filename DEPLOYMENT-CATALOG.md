# Catálogo, cores e personalização

Alteração preparada para o projeto existente em `presentearfoz.com.br`, hospedado
na VPS pelo Dokploy. O código de partida é `Hunter954/PresentearFoz`, commit
`1bbbbbc`. A versão que está na VPS ainda precisa ser comparada com essa base.
Nenhuma alteração foi aplicada à produção nesta preparação.

## Comportamento

- 56 produtos e fotos originais, em 10 categorias; nomes extraídos dos arquivos
  e categorias extraídas das pastas de `PRESENTEAR/PRODUTOS`.
- Laser ativo e sublimação desativada inicialmente. Os dois controles são
  independentes por produto no admin.
- 13 cores iniciais por produto. O admin pode editar nomes e tonalidades,
  adicionar cores ou remover todas. Alterações não são desfeitas no reinício.
- A vitrine encaminha para a página do produto quando há opções a escolher.
  A página exige cor e técnica quando aplicável. Não há alteração artificial
  da foto; uma foto por cor poderá ser associada ao campo `image_path` depois.
- Cor, técnica e observação distinguem linhas do carrinho. As escolhas ficam
  registradas no orçamento, admin e mensagem preparada para WhatsApp.
- O estoque é verificado somando as variantes do mesmo produto no carrinho.
- Novos itens ficam sob orçamento. Preços existentes são preservados.

## Aplicação na VPS

1. Identificar a aplicação e a origem de código no Dokploy; comparar eventuais
   alterações da VPS antes de substituir arquivos. Confirmar o volume persistente
   usado por `UPLOAD_FOLDER` (a imagem Docker usa `/data/uploads`).
2. Fazer backup do banco e do volume de uploads antes da implantação.
3. Implantar este código com o Dockerfile existente. `start.sh` executa
   `startup.py` antes de iniciar o Gunicorn. O bootstrap cria tabelas ausentes
   e aplica a atualização idempotente de `app/schema_updates.py`.
4. Dentro do container da aplicação, executar:

   ```sh
   python -m flask --app wsgi import-catalog --manifest catalog/products.json
   ```

   O comando valida os hashes das 56 fotos, copia para o volume de uploads e
   cadastra as associações. Ele não exclui produtos ou fotos anteriores.
   Repetir o comando não duplica produtos ou imagens. Produtos existentes são
   reconhecidos pelo SKU de importação ou pelo nome normalizado; nomes ambíguos
   interrompem a importação para revisão.
5. Verificar categorias, produtos, imagens, seletor de cores, edição no admin
   e carrinho em produção, em desktop e celular. Não enviar uma mensagem real
   de WhatsApp durante a verificação.

## Banco e recuperação

A atualização adiciona opções aos produtos e snapshots das escolhas aos itens
do carrinho. A unicidade passa de `(cart_id, product_id)` para
`(cart_id, product_id, variant_key)`, preservando itens anteriores. PostgreSQL
usa transação e advisory lock; SQLite usa alteração em lote do Alembic.

Não reinstalar o código antigo sobre dados com múltiplas variantes: ele não
compreende linhas distintas do mesmo produto. Se for necessário voltar à versão
anterior, usar o backup de banco feito imediatamente antes da implantação e
avaliar eventuais carrinhos criados depois do backup.

## Verificação realizada localmente

- 11 testes automatizados aprovados, incluindo opções inválidas, snapshots,
  estoque entre variantes, admin, importação repetida e atualização de banco
  SQLite legado sem perda do carrinho.
- Importação real: 56 produtos, 10 categorias e 56 imagens. Segunda execução:
  zero produtos, categorias ou imagens duplicados.
- Todas as 56 páginas, 56 fotos e 10 páginas de categorias retornaram HTTP 200
  via cliente Flask; fotos verificadas com Pillow.
- Sintaxe dos scripts JavaScript validada e `git diff --check` sem erros.
- Ainda pendentes: acesso e comparação com a VPS, backup real, atualização
  PostgreSQL de produção, publicação no Dokploy e inspeção visual em navegador.
  O navegador desta sessão estava indisponível; o domínio retornou HTTP 403
  para as verificações HTTP externas.
