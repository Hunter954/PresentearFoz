# Relatório de validação

## Verificações concluídas neste pacote

- Compilação estática de todos os arquivos Python com `compileall`.
- Análise sintática de 30 templates Jinja.
- Verificação sintática dos arquivos JavaScript com `node --check`.
- Conferência automatizada das referências `url_for` contra os endpoints declarados.
- Conferência da ausência, na loja pública, dos blocos de blog, newsletter, texto longo sobre brindes e mensagem de entrega nacional.
- Conferência da estrutura para PostgreSQL, volume `/data/uploads`, bootstrap e Gunicorn no Railway.

## Teste de execução

A suíte `pytest` está incluída em `tests/`. Ela cobre carregamento da home e catálogo, criação e persistência do carrinho, envio para WhatsApp e login administrativo. O ambiente usado para montar este pacote não possuía Flask e extensões instalados, nem acesso de rede para instalar as dependências; por isso a suíte completa não foi executada aqui. No Railway, as dependências são instaladas pelo `requirements.txt` antes da inicialização.

## Teste recomendado após o primeiro deploy

Execute no shell do Railway:

```bash
pytest -q
```

Depois valide manualmente upload persistente, carrinho em aba anônima, busca do código no painel e abertura do WhatsApp em um celular.
