# Checklist de publicação no Railway

## Serviço da aplicação

- [ ] Repositório conectado ao GitHub.
- [ ] Builder Nixpacks selecionado.
- [ ] PostgreSQL adicionado ao projeto.
- [ ] `DATABASE_URL` disponível no serviço da aplicação.
- [ ] Volume criado e montado em `/data`.
- [ ] `UPLOAD_FOLDER=/data/uploads`.
- [ ] `SITE_URL=https://presentearfoz.com.br`.
- [ ] `SECRET_KEY` longa e aleatória.
- [ ] `ADMIN_EMAIL` definido.
- [ ] `ADMIN_PASSWORD` forte e definido antes do primeiro deploy.
- [ ] `SESSION_COOKIE_SECURE=true`.
- [ ] Healthcheck `/health` retornando `status: ok`.

## Depois do primeiro deploy

- [ ] Acessar `/admin/login`.
- [ ] Confirmar que produtos demonstrativos carregaram.
- [ ] Cadastrar produtos reais.
- [ ] Enviar imagens e confirmar que continuam após redeploy.
- [ ] Testar carrinho em aba anônima.
- [ ] Copiar o código do carrinho e buscar no painel.
- [ ] Testar botão de WhatsApp no celular.
- [ ] Configurar domínio e DNS.
- [ ] Alterar `SEED_DEMO=false` quando o catálogo real estiver pronto.
- [ ] Revisar política de privacidade e dados da empresa.
