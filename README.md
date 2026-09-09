# IGAutoCon

Este projeto monitora a conexão de internet e, quando ela cai, tenta restaurá-la automaticamente por meio de um portal de autenticação captive usando Playwright.

## Visão geral

O script em [scr/AutoConnect.py](scr/AutoConnect.py) executa um monitor contínuo que:

- verifica periodicamente se a internet está funcionando;
- detecta falhas consecutivas de acesso;
- dispara uma tentativa de autenticação no portal de rede;
- confirma se a conexão foi restaurada;
- repete o processo até que a internet volte.

A ideia é lidar com ambientes em que o acesso à internet fica bloqueado por um captive portal, como em redes corporativas, universidades ou locais públicos.

## Como funciona

### 1. Verificação da internet

O monitor usa pequenas requisições HTTP para testar se a rede está acessível. As URLs de teste estão em:

- http://example.com
- http://neverssl.com

A função `internet_is_up()` tenta essas URLs em paralelo e considera a internet disponível se pelo menos uma delas responder com HTTP 200.

### 2. Detecção de falhas

A cada ciclo, o monitor faz uma checagem. Se a internet estiver fora:

- incrementa o contador de falhas;
- quando atinge o limite configurado, inicia a recuperação;
- só reinicia a contagem quando o acesso volta.

### 3. Recuperação via portal

Quando o limite de falhas é alcançado, o script dispara `execute_trigger()`, que executa uma autenticação no portal:

- abre o navegador com Playwright;
- acessa o portal em `http://10.125.128.1/status`;
- marca a opção de política (`#policy`);
- clica em "Próximo";
- espera o redirecionamento para `**irmaosgoncalves.com.br**`;
- confirma se a internet já está disponível.

Se a autenticação falhar, o processo repete em intervalos configurados.

## Configuração

As principais variáveis de configuração estão no início do arquivo:

```python
CHECK_INTERVAL = 0.20
PROBE_TIMEOUT = 0.50
FAILURES_TO_TRIGGER = 2
SUCCESSES_TO_RECOVER = 3
TRIGGER_RETRY_DELAY = 0.5
```

### Explicação

- `CHECK_INTERVAL`: intervalo entre verificações do monitor.
- `PROBE_TIMEOUT`: timeout para as requisições HTTP de teste.
- `FAILURES_TO_TRIGGER`: quantidade de falhas consecutivas para iniciar a recuperação.
- `SUCCESSES_TO_RECOVER`: quantidade de sucessos consecutivos para considerar que a internet voltou.
- `TRIGGER_RETRY_DELAY`: tempo entre tentativas de autenticação do Playwright.

## Portal e URLs

```python
PORTAL_URL = "http://10.125.128.1/status"
SUCCESS_URL = "**irmaosgoncalves.com.br**"
```

Essas constantes definem a página de login do captive portal e o destino esperado após a autenticação bem-sucedida.

## Dependências

O projeto depende de:

- Python 3
- Playwright

Para instalar o browser necessário do Playwright:

```bash
pip install playwright
playwright install chromium
```

## Como executar

Na raiz do projeto:

```bash
python scr/AutoConnect.py
```

O script roda em loop e registra eventos no console com `logging`.

## Observações importantes

- O script usa `playwright.sync_api` em modo headless desabilitado (`headless=False`), então ele abre uma janela real do Chromium.
- A navegação e ações do Playwright têm timeout desabilitado para evitar interrupções durante a autenticação do portal.
- O código bloqueia recursos desnecessários como imagens, fontes e CSS para acelerar o processo.
- O monitor ignora novas verificações enquanto a recuperação via Playwright está em andamento.

## Objetivo

Este script foi pensado para manter a rede conectada automaticamente em cenários onde a internet só volta após a aprovação de uma página de autenticação do provedor ou captive portal.
