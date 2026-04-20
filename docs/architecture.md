# Architecture Guidelines

## Convenções de diretórios

- **Frontend**
  - `src/frontend/templates/pages`
  - `src/frontend/templates/components`
  - `src/frontend/static/{css,js,images}`
- **Backend**
  - `src/backend/routes`
  - `src/backend/services`
  - `src/backend/repositories`
  - `src/backend/config.py`
  - `src/backend/app.py`

## Regra obrigatória

- **Sem HTML/CSS/JS inline em módulos Python.**
  - HTML deve ir para `templates/pages` ou `templates/components`.
  - CSS e JS devem ir para `static/css` e `static/js`.

## Organização de rotas

- Cada rota principal em arquivo próprio dentro de `src/backend/routes`.
  - Ex.: `dashboard.py`, `live_usage.py`.

## Ownership

- Backend (`routes/services/repositories`) mantém fluxo de dados e regras.
- Frontend (`templates/static`) mantém marcação e comportamento de interface.
