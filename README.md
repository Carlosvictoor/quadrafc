# QuadraPro — site

**Seu time, sem boleto e sem confusão.**

Site para times de futebol e grupos de amigos organizarem o pagamento do aluguel da quadra. O administrador cria a conta, cadastra o time e os jogadores, e registra quem pagou e quem ainda deve. O site calcula sozinho o total arrecadado, o valor pendente e quanto falta para cobrir a quadra.

## Tecnologias

| Parte | Tecnologia |
|---|---|
| Telas | HTML (templates Jinja), CSS e JavaScript puro |
| Servidor | Python 3.12 + Flask |
| Banco de dados | SQLite no seu computador / PostgreSQL em produção |
| Login | Flask-Login (senhas com hash) |
| Formulários | Flask-WTF (validação + proteção CSRF) |

## Funcionalidades

- Criar conta, entrar, "lembrar de mim", recuperar senha por e-mail
- Painel com totais do mês, % de pagos, pendentes e próximo jogo
- Jogadores: adicionar, editar, desativar, remover, buscar e filtrar
- Pagamentos por mês (Pix, Dinheiro, Transferência, Outro), com opção de desfazer
- Histórico com filtros e **exportação para Excel (CSV)**
- Quadra e jogo semanal (dia, horário, valores, regras)
- Notificações (pagamentos, novos jogadores, lembrete do jogo)
- **Compartilhar resumo no WhatsApp** ou copiar o texto
- Configurações: dados da conta, trocar senha, excluir conta (LGPD)
- Funciona no computador e no celular

## Como rodar no seu computador

```bash
# 1. Criar o ambiente e instalar (só na primeira vez)
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt

# 2. (Opcional) criar uma conta de demonstração com 12 jogadores
python seed_demo.py

# 3. Iniciar o site
python run.py
```

Abra **http://127.0.0.1:5000** no navegador. A conta de demonstração está descrita no topo de `seed_demo.py`.

Em desenvolvimento, o link de "Esqueci minha senha" aparece **no terminal**. Para enviar e-mails de verdade, configure `MAIL_*` no `.env` (veja `.env.example`).

## Testes

```bash
python -m pytest
```

São 23 testes. Eles cobrem:

- o cálculo do mês (12 × R$ 20 com 8 pagos dá R$ 160 / R$ 80)
- o cadastro, o login e o fluxo de pagamento
- o isolamento entre times: um usuário nunca acessa dados de outro
- o CSRF, o CSV, a troca de senha e a exclusão de conta

## Estrutura

```
run.py                 inicia o site
seed_demo.py           dados de demonstração
app/
  __init__.py          monta o site (configuração, banco, login, segurança)
  config.py            configurações (desenvolvimento / produção)
  models.py            tabelas: User, Team, Player, Payment, Notification
  forms.py             formulários e validações
  auth.py              login, cadastro, senha
  main.py              todas as telas internas
  services/            regras: dinheiro, meses, cálculo do mês, e-mail
  templates/           páginas HTML
  static/css/style.css visual (cores, layout, celular)
  static/js/app.js     interações (menu, busca, confirmações, copiar)
tests/                 testes automáticos
```

Os valores em dinheiro são guardados em **centavos** (número inteiro) para não haver erro de arredondamento.

## Segurança

- Senhas guardadas com hash (nunca em texto)
- Proteção CSRF em todos os formulários; ações de alteração só por POST
- Toda consulta é filtrada pelo time do usuário logado (outro time = página não encontrada)
- Cookies `HttpOnly` / `SameSite`, e `Secure` em produção
- Cabeçalhos contra clickjacking e sniffing
- O site recusa iniciar em produção sem uma `SECRET_KEY` própria

## Publicar de graça (PythonAnywhere)

Site publicado: **https://victorjg10.pythonanywhere.com**

1. Gere o pacote: `python deploy/make_zip.py` → cria `dist/quadrapro.zip` (sem senhas nem banco local).
2. Crie uma conta **Beginner (grátis)** em https://www.pythonanywhere.com.
3. Aba **Files** → *Upload a file* → envie o `quadrapro.zip` para `/home/SEU_USUARIO/`.
4. Aba **Consoles** → **Bash** e rode:
   ```bash
   unzip -o quadrapro.zip -d quadrapro
   bash ~/quadrapro/deploy/pythonanywhere_setup.sh
   ```
5. Aba **Web** → *Add a new web app* → *Next* → **Manual configuration** → escolha a versão do Python que o script mostrou.
6. Ainda na aba Web, preencha:
   - **Virtualenv:** `/home/SEU_USUARIO/quadrapro/.venv`
   - **Static files:** URL `/static/` → Directory `/home/SEU_USUARIO/quadrapro/app/static`
   - **WSGI configuration file:** abra, apague tudo e cole o conteúdo de `deploy/pythonanywhere_wsgi.py`
   - **Force HTTPS:** ligado
7. Clique em **Reload**. O site fica em `https://SEU_USUARIO.pythonanywhere.com`.

**Para atualizar depois:** gere o zip de novo, envie, rode os dois comandos do passo 4 e clique em *Reload*. O banco (`instance/`) e a chave (`.env`) são mantidos.

**Plano grátis:** **uma vez por mês**, entre na aba Web e clique em *Run until 1 month from today* ("Executar até daqui a 1 mês"), ou o site é pausado — os dados não se perdem e o PythonAnywhere avisa por e-mail uma semana antes. E-mail de recuperação de senha só funciona se você configurar `MAIL_*` com o Gmail no `.env` do servidor.

## Publicar em outros lugares (ex.: Render)

Use PostgreSQL via `DATABASE_URL`, `FLASK_ENV=production`, uma `SECRET_KEY` própria e o comando `gunicorn "app:create_app()"`.

Antes de abrir para o público, revise os textos de **Termos de Uso** e **Política de Privacidade** (`app/templates/legal/`).
