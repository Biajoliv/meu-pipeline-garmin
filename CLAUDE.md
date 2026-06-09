# CLAUDE.md — Garmin Connect Pipeline

## Visão geral

Pipeline automático que busca dados de saúde e performance do Garmin Connect,
processa métricas relevantes para corredores amadores e envia relatórios via Telegram.

- **Diário** (`main.py`): executa às 03:00 UTC, envia resumo do dia anterior
- **Semanal** (`weekly_report.py`): executa toda segunda às 10:00 UTC, envia médias dos últimos 7 dias

Toda a infraestrutura roda no GitHub Actions. Os dados brutos são persistidos como
JSONs no diretório `dados/` e commitados automaticamente pelo workflow diário.

---

## Arquitetura

```
main.py              # Relatório diário — coleta dados do Garmin e envia Telegram
weekly_report.py     # Relatório semanal — lê JSONs salvos e envia Telegram
requirements.txt     # garminconnect, requests
dados/               # garmin_YYYY-MM-DD.json (um por dia, commitado pelo bot)
.github/
  workflows/
    garmin_pipeline.yml   # Workflow diário (cron 0 3 * * * + workflow_dispatch)
    weekly_report.yml     # Workflow semanal (cron 0 10 * * 1 + workflow_dispatch)
```

### Fluxo de dados (diário)
1. `garmin.get_stats(ontem)` → métricas de resumo do dia
2. `garmin.get_sleep_data(ontem)` → dados de sono e HRV
3. `garmin.get_activities(0, 5)` → últimas 5 atividades (para filtrar corridas do dia)
4. Salva tudo em `dados/garmin_{ontem}.json`
5. Monta mensagem Telegram e envia

### Fluxo de dados (semanal)
1. Lê os arquivos `dados/garmin_*.json` dos últimos 7 dias (métricas regulares)
2. Lê todos os arquivos disponíveis até 28 dias (para ACWR)
3. Monta mensagem agregada e envia

---

## Secrets (GitHub Actions)

| Secret | Uso |
|--------|-----|
| `GARMIN_USER` | E-mail da conta Garmin Connect |
| `GARMIN_PASSWORD` | Senha da conta Garmin Connect |
| `TELEGRAM_TOKEN` | Token do bot Telegram (via @BotFather) |
| `TELEGRAM_CHAT_ID` | ID do chat de destino |

Para rodar localmente, exportar essas variáveis no ambiente antes de executar.

---

## Estrutura do JSON salvo em `dados/`

```json
{
  "data": "YYYY-MM-DD",
  "resumo": { ... },   // garmin.get_stats()
  "sono":   { ... },   // garmin.get_sleep_data()
  "atividades": [ ... ] // garmin.get_activities(0, 5)
}
```

### Campos-chave de `resumo`
| Campo | Descrição |
|-------|-----------|
| `totalSteps` | Passos do dia |
| `activeKilocalories` | Calorias queimadas por atividade |
| `bmrKilocalories` | Calorias basais |
| `totalKilocalories` | Total (BMR + ativas) |
| `restingHeartRate` | FC em repouso |
| `lastSevenDaysAvgRestingHeartRate` | Média 7 dias da FC (baseline) |
| `averageStressLevel` | Stress médio (0–100) |
| `bodyBatteryAtWakeTime` | Body Battery ao acordar |
| `bodyBatteryHighestValue` | Body Battery máximo do dia |

### Campos-chave de `sono`
| Campo | Descrição |
|-------|-----------|
| `dailySleepDTO` | Sub-objeto com métricas de sono (pode ser `None`) |
| `avgOvernightHrv` | HRV médio noturno (float, em ms) |
| `hrvStatus` | `BALANCED` / `UNBALANCED` / `POOR` |

**Atenção:** `dailySleepDTO` pode estar em `sono.dailySleepDTO` ou o próprio `sono` —
use sempre o padrão `dto = sono.get("dailySleepDTO", {}) or sono`.

### Campos-chave de `dailySleepDTO`
| Campo | Descrição |
|-------|-----------|
| `sleepTimeInSeconds` | Sono total (preferencial) |
| `deepSleepSeconds` | Sono profundo |
| `lightSleepSeconds` | Sono leve |
| `remSleepSeconds` | Sono REM |

### Campos-chave por atividade de corrida
| Campo | Descrição |
|-------|-----------|
| `activityId` | ID único (usar para deduplicar) |
| `startTimeLocal` | `"YYYY-MM-DD HH:MM:SS"` — primeiros 10 chars = data |
| `activityType.typeKey` | Ex: `"running"` — filtrar com `"run" in tipo.lower()` |
| `distance` | Em metros |
| `duration` | Em segundos |
| `averageSpeed` | Em m/s — converter com `formatar_pace()` |
| `averageHR` | FC média |
| `calories` | Calorias da atividade |
| `aerobicTrainingEffect` | Float 0–5 (efeito aeróbico) |
| `averageRunningCadenceInStepsPerMinute` | Cadência |
| `avgVerticalOscillation` | Oscilação vertical em cm |
| `avgGroundContactTime` | Contato com o solo em ms |
| `avgVerticalRatio` | Razão vertical em % |
| `vO2MaxValue` | VO2 Max estimado |

---

## Funções utilitárias (reutilizar, não duplicar)

Ambos os arquivos possuem versões locais destas funções — se extrair para módulo
compartilhado no futuro, estas são as candidatas:

| Função | Arquivo | Descrição |
|--------|---------|-----------|
| `formatar_tempo(seg)` | ambos | Segundos → `"Xh MMm"` |
| `formatar_tempo_corrida(seg)` | main.py | Segundos → `"MM:SS"` ou `"H:MM:SS"` |
| `formatar_pace(m_s)` | ambos | m/s → `"M:SS /km"` |
| `calcular_sono_total(dto)` | ambos | Extrai total de sono com fallback |
| `media(lista)` | weekly_report.py | Média ignorando None e zeros |
| `label_stress(stress)` | ambos | 0-100 → label com emoji |
| `label_body_battery(bb)` | main.py | BB → label com emoji |
| `badge_sono(seg)` | main.py | Sono total → badge ✅/🟡/❌ |
| `label_training_effect(te)` | main.py | Float 0-5 → label |
| `calcular_hrv_score(sono, paths)` | main.py | HRV + histórico → score de recuperação |
| `calcular_economia_corrida(act)` | main.py | Cadência/VO/GCT → score 0-100 |
| `calcular_acwr(registros)` | weekly_report.py | Razão carga aguda/crônica |
| `label_acwr(acwr)` | weekly_report.py | Float → label de risco |
| `verificar_alertas(stats, dto)` | main.py | Retorna lista de alertas do dia |

---

## Métricas cobertas

### Relatório diário
- Passos, calorias ativas e totais
- Sono total com badge + profundo e REM com % e referências (ideal: 13-23% / 20-25%)
- HRV noturno, status Garmin, score de recuperação (% vs. baseline 7d) e prontidão para treino
- Stress com label contextual (Baixo/Moderado/Alto/Muito alto)
- Body Battery ao acordar com label
- Corrida: distância, tempo, pace, FC, calorias, efeito aeróbico
- Economia de corrida: cadência, oscilação vertical, contato com solo, score 0-100
- Alertas automáticos (FC elevada, stress, sono, SpO2, Body Battery)

### Relatório semanal
- Médias de passos, calorias, sono (com % e badges)
- FC repouso média, stress médio com label, Body Battery máximo médio
- Corridas da semana (deduplicadas por `activityId`)
- Tendência HRV 7 dias com variação vs. início da semana
- ACWR (Acute:Chronic Workload Ratio) com degradação graciosa para histórico parcial
- Alertas (FC, stress, sono, sem corridas, ACWR > 1.5)

---

## Convenções de código

- **Sem módulo compartilhado**: funções duplicadas em `main.py` e `weekly_report.py`
  por simplicidade — se o projeto crescer, extrair para `utils.py`
- **Campos corretos do Garmin**: usar `totalSteps`, `activeKilocalories`, `bmrKilocalories`
  (não `steps`, `activeCalories`, `bmrCalories` — esses não existem na API)
- **Deduplicação de atividades**: sempre usar `activityId` ao agregar atividades de múltiplos arquivos
- **Markdown Telegram**: usar `*bold*` e `_italic_` — não usar MarkdownV2 (não configurado)
- **Limite de mensagem**: 4096 chars — testar com `len(mensagem)` em mensagens densas
- **Sem comentários de código** exceto quando o comportamento é não-óbvio
- **Sem commits de co-autoria** do Claude nas mensagens de commit

---

## Direções para evolução

### Próximas funcionalidades sugeridas
- **Módulo `utils.py`**: extrair funções duplicadas para eliminar inconsistências
- **VO2 Max trend**: `vO2MaxValue` já disponível nas atividades — mostrar evolução mensal
- **SpO2 médio**: já existe alerta para mínimo, mas não exibe o valor regularmente
- **Pace por zona de FC**: usar `timeInHrZones` das atividades para análise de intensidade
- **Relatório mensal**: agregar todos os JSONs do mês — estrutura já suporta isso

### Limitações conhecidas
- `get_activities(0, 5)` captura apenas as 5 atividades mais recentes por dia —
  o ACWR de 28 dias pode estar incompleto para atletas com alto volume;
  aumentar para 20-30 melhora a cobertura
- O HRV score precisa de pelo menos 2 dias de histórico para calcular baseline;
  antes disso exibe apenas o valor absoluto
- Apenas corridas (`"run" in typeKey`) são processadas — ciclismo, natação etc. ignorados

### Evolução da arquitetura
Para projetos mais robustos, a estrutura sugerida seria:
```
garmin_connect/
  utils.py            # Funções compartilhadas
  collectors/
    daily.py          # Coleta e salva dados
    activities.py     # Processamento de atividades
  reports/
    daily_report.py   # Monta relatório diário
    weekly_report.py  # Monta relatório semanal
  metrics/
    hrv.py            # Lógica de HRV e recuperação
    economy.py        # Economia de corrida
    training_load.py  # ACWR e carga de treino
  tests/
    test_metrics.py   # Testes unitários das métricas
```
