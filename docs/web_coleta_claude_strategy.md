# Validação da estrutura atual e estratégia de coleta remota de `.claude`

## 1) Validação da estrutura atual do projeto

A estrutura atual está **coerente com a arquitetura em camadas** declarada no repositório:

- `src/backend/routes`: handlers HTTP por rota
- `src/backend/services`: regras de negócio
- `src/backend/repositories`: acesso a dados
- `src/frontend/templates`: páginas e componentes
- `src/frontend/static`: CSS/JS

Pontos positivos observados:

1. Separação backend/frontend já aplicada.
2. Rotas principais isoladas em arquivos dedicados (`dashboard`, `live_usage`).
3. Persistência local em SQLite (`~/.claude/usage.db`) reduz dependência externa.
4. Base com testes automatizados (suite passando localmente).

## 2) O que muda ao publicar em um endereço web

Quando o sistema roda em um servidor web (ex.: `https://seu-dominio.com`), o backend **não consegue ler diretamente** `~/.claude` da máquina do visitante.

Motivo técnico:

- O navegador não concede acesso arbitrário ao filesystem local do usuário.
- O servidor remoto só enxerga arquivos do próprio servidor.

Conclusão: para compor o dashboard com dados do usuário final, é necessário um mecanismo explícito de ingestão.

## 3) Formas viáveis para coletar dados do usuário

### Opção A — Upload manual (MVP recomendado)

Fluxo:

1. Usuário executa um script local (`python cli.py export --format json`).
2. Script gera um `report.json` (sem necessidade de enviar tudo de `.claude`).
3. Usuário faz upload desse arquivo no site.
4. Backend processa e renderiza dashboard por sessão de usuário.

Vantagens:

- Mais simples e seguro para primeira versão.
- Consentimento explícito via upload.
- Menor superfície de ataque.

Desvantagem:

- Processo manual para o usuário.

### Opção B — Agente local + sincronização HTTPS

Fluxo:

1. Usuário instala um pequeno agente local (CLI/daemon).
2. Agente lê `~/.claude/projects/*.jsonl` periodicamente.
3. Agente sanitiza/anonimiza conteúdo sensível.
4. Agente envia apenas métricas agregadas para API remota autenticada.

Vantagens:

- Experiência contínua (quase tempo real).
- Melhor para produto SaaS.

Desvantagens:

- Complexidade de distribuição, atualização e suporte multiplataforma.

### Opção C — App desktop (Electron/Tauri) com dashboard embutido

Fluxo:

1. App roda localmente com permissão de filesystem.
2. Dashboard é servido localmente (ou híbrido local+cloud).

Vantagens:

- Controle de permissões local claro.
- Boa UX para dados sensíveis.

Desvantagem:

- Requer ciclo de release de aplicativo.

## 4) Recomendação prática para este projeto

### Fase 1 (rápida)

- Manter arquitetura atual.
- Criar endpoint de ingestão por upload (`POST /api/import-report`).
- Reusar o formato de export já existente no CLI.
- Persistir dados importados por `user_id` em banco separado do scanner local.

### Fase 2 (escala)

- Criar `claude-usage-agent` local (instalável).
- Autenticação por token curto e rotação.
- Envio incremental (delta por `session_id` + `mtime`).
- Observabilidade (fila de retry + auditoria de eventos de ingestão).

## 5) Segurança e privacidade (essencial)

Para qualquer coleta remota:

1. **Consentimento explícito** e revogável.
2. **Minimização de dados** (preferir métricas; evitar texto bruto das conversas).
3. **Criptografia em trânsito** (TLS) e em repouso.
4. **Controles de retenção** (TTL e exclusão sob demanda).
5. **Logs de auditoria** para uploads, importações e deleções.
6. **Termos de uso + política de privacidade** com base legal aplicável (LGPD/GDPR, conforme público).

## 6) Resposta objetiva à pergunta

> "Se eu subir em um endereço web, consigo pedir para executar script no computador do usuário e obter `.claude` para compor o dashboard?"

Sim, **mas não diretamente pelo navegador**. Você precisa de uma destas abordagens:

- **Upload manual de arquivo exportado** (mais simples para começar), ou
- **Agente local instalado pelo usuário** que envia dados com consentimento.

Sem um desses mecanismos, o servidor web não acessa `~/.claude` da máquina do usuário.
