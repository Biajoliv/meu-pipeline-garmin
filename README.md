# Garmin Connect Pipeline

Pipeline automático que busca dados do Garmin Connect e envia relatórios pelo Telegram.

## Relatórios

### Diário — `main.py`
Executa todo dia às 03:00 UTC (meia-noite BRT) e envia um resumo do dia anterior:
- Passos, calorias ativas e totais
- Sono (total, profundo, REM)
- Detalhes da corrida, se houver (distância, tempo, pace, FC)

### Semanal — `weekly_report.py`
Executa toda segunda-feira às 10:00 UTC (07:00 BRT) com as médias dos últimos 7 dias:
- Médias de passos, calorias e sono
- FC em repouso, stress e Body Battery
- Resumo das corridas da semana (quantidade, distância total, pace médio)

## Secrets necessários no GitHub

Configure em **Settings → Secrets and variables → Actions**:

| Secret | Descrição |
|---|---|
| `GARMIN_USER` | E-mail da conta Garmin Connect |
| `GARMIN_PASSWORD` | Senha da conta Garmin Connect |
| `TELEGRAM_TOKEN` | Token do bot (obtido via @BotFather) |
| `TELEGRAM_CHAT_ID` | ID do chat onde o relatório será enviado |

## Como disparar manualmente

- Diário: **Actions → Garmin Data Pipeline → Run workflow**
- Semanal: **Actions → Garmin Weekly Report → Run workflow**

## Estrutura

```
main.py              # Relatório diário
weekly_report.py     # Relatório semanal
requirements.txt     # Dependências Python
dados/               # JSONs com os dados históricos
.github/
  workflows/
    garmin_pipeline.yml   # Workflow diário
    weekly_report.yml     # Workflow semanal
```
