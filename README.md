# Garmin Connect Pipeline

Pipeline automático que busca dados diários do Garmin Connect e envia um relatório pelo Telegram.

## O que faz

Todo dia às 03:00 UTC (meia-noite no horário de Brasília) o GitHub Actions executa o `main.py`, que:

1. Faz login no Garmin Connect
2. Busca estatísticas do dia anterior (passos, calorias, sono, corridas)
3. Salva os dados brutos em `dados/garmin_YYYY-MM-DD.json`
4. Envia um resumo formatado via Telegram

## Secrets necessários no GitHub

Configure em **Settings → Secrets and variables → Actions**:

| Secret | Descrição |
|---|---|
| `GARMIN_USER` | E-mail da conta Garmin Connect |
| `GARMIN_PASSWORD` | Senha da conta Garmin Connect |
| `TELEGRAM_TOKEN` | Token do bot (obtido via @BotFather) |
| `TELEGRAM_CHAT_ID` | ID do chat onde o relatório será enviado |

## Como disparar manualmente

No GitHub: **Actions → Garmin Data Pipeline → Run workflow**

## Estrutura

```
main.py           # Script principal
requirements.txt  # Dependências Python
dados/            # JSONs com os dados históricos
.github/
  workflows/
    garmin_pipeline.yml  # Definição do workflow
```
