import os
import json
import requests
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("Credenciais do Telegram não encontradas.")

# Coleta os últimos 7 dias (semana passada: seg a dom)
hoje = datetime.now().date()
dias = [(hoje - timedelta(days=i)) for i in range(1, 8)]


def formatar_tempo(segundos):
    if not segundos:
        return "0h 00m"
    return f"{int(segundos // 3600)}h {int((segundos % 3600) // 60):02d}m"


def formatar_pace(velocidade_ms):
    if not velocidade_ms or velocidade_ms <= 0:
        return "--:--"
    pace_decimal = 16.666666667 / velocidade_ms
    minutos = int(pace_decimal)
    segundos = int((pace_decimal - minutos) * 60)
    return f"{minutos}:{segundos:02d}"


# Acumula os dados de cada dia
registros = []
for dia in dias:
    caminho = f"dados/garmin_{dia}.json"
    if not os.path.exists(caminho):
        continue
    with open(caminho, encoding="utf-8") as f:
        registros.append(json.load(f))

if not registros:
    print("Nenhum dado encontrado para a última semana.")
    exit(0)

n = len(registros)


def media(lista):
    valores = [v for v in lista if v is not None and v > 0]
    return round(sum(valores) / len(valores), 1) if valores else 0


# Médias do resumo diário
passos_media = media([r["resumo"].get("totalSteps", 0) for r in registros])
calorias_ativas_media = media([r["resumo"].get("activeKilocalories", 0) for r in registros])
calorias_totais_media = media([r["resumo"].get("totalKilocalories", 0) for r in registros])
fc_repouso_media = media([r["resumo"].get("restingHeartRate", 0) for r in registros])
stress_media = media([r["resumo"].get("averageStressLevel", 0) for r in registros])
body_battery_media = media([r["resumo"].get("bodyBatteryHighestValue", 0) for r in registros])

# Médias de sono
sono_total_media = 0
sono_profundo_media = 0
sono_rem_media = 0
sono_registros = []
for r in registros:
    sono = r.get("sono")
    if not sono:
        continue
    dto = sono.get("dailySleepDTO", {}) or sono
    sono_registros.append(dto)

if sono_registros:
    sono_total_media = media([d.get("sleepTimeInSeconds", 0) for d in sono_registros])
    sono_profundo_media = media([d.get("deepSleepSeconds", 0) for d in sono_registros])
    sono_rem_media = media([d.get("remSleepSeconds", 0) for d in sono_registros])

# Resumo das corridas da semana
corridas = []
for r in registros:
    for act in r.get("atividades", []):
        data_act = act.get("startTimeLocal", "")[:10]
        tipo = act.get("activityType", {}).get("typeKey", "").lower()
        # Verifica se a atividade pertence a um dos dias da semana analisada
        if data_act in [str(d) for d in dias] and "run" in tipo:
            corridas.append(act)

texto_corridas = ""
if corridas:
    total_km = round(sum(c.get("distance", 0) for c in corridas) / 1000, 2)
    pace_medio = formatar_pace(
        sum(c.get("averageSpeed", 0) for c in corridas) / len(corridas)
    )
    fc_corrida_media = int(
        media([c.get("averageHR", 0) for c in corridas])
    )
    texto_corridas = (
        f"🏃‍♂️ *CORRIDAS DA SEMANA*\n"
        f"📌 *Qtd:* {len(corridas)} corrida(s)\n"
        f"📏 *Distância total:* {total_km} km\n"
        f"⏱️ *Pace médio:* {pace_medio} /km\n"
        f"💓 *FC média:* {fc_corrida_media} bpm\n\n"
    )
else:
    texto_corridas = "🏃‍♂️ *CORRIDAS DA SEMANA*\nNenhuma corrida registrada.\n\n"

data_inicio = str(min(dias))
data_fim = str(max(dias))

mensagem = (
    f"📊 *RELATÓRIO SEMANAL GARMIN*\n"
    f"📅 {data_inicio} → {data_fim} ({n} dias com dados)\n\n"
    f"{texto_corridas}"
    f"📋 *MÉDIAS DO PERÍODO:*\n"
    f"🚶‍♂️ *Passos/dia:* {int(passos_media):,}\n"
    f"🔥 *Calorias ativas/dia:* {int(calorias_ativas_media)} kcal\n"
    f"🏅 *Calorias totais/dia:* {int(calorias_totais_media)} kcal\n\n"
    f"😴 *Sono médio:* {formatar_tempo(sono_total_media)}\n"
    f"💤  └ 💎 *Profundo:* {formatar_tempo(sono_profundo_media)}\n"
    f"💤  └ 🧠 *REM:* {formatar_tempo(sono_rem_media)}\n\n"
    f"❤️ *FC em repouso:* {int(fc_repouso_media)} bpm\n"
    f"🧠 *Stress médio:* {int(stress_media)}/100\n"
    f"⚡ *Body Battery máx. médio:* {int(body_battery_media)}\n\n"
    f"💪 _Semana analisada. Continue evoluindo!_"
)

url_telegram = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}

try:
    response = requests.post(url_telegram, json=payload)
    if response.status_code != 200:
        print(f"Erro ao enviar Telegram: {response.text}")
    else:
        print("Relatório semanal enviado com sucesso!")
except Exception as e:
    print(f"Falha na conexão com o Telegram: {e}")
