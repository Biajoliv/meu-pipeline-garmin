import os
import json
import requests
from datetime import datetime, timedelta
from garminconnect import Garmin

# 1. Carrega as credenciais
USER = os.getenv("GARMIN_USER")
PASSWORD = os.getenv("GARMIN_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not USER or not PASSWORD:
    raise ValueError("Credenciais do Garmin não encontradas.")

# 2. Login e Extração
garmin = Garmin(USER, PASSWORD)
garmin.login()

ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

stats = garmin.get_stats(ontem)
sono = garmin.get_sleep_data(ontem)

# Puxa as últimas atividades (vamos olhar as 5 mais recentes)
atividades = garmin.get_activities(0, 5)

# 3. Salva os dados brutos localmente
dados_finais = {"data": ontem, "resumo": stats, "sono": sono, "atividades": atividades}
os.makedirs("dados", exist_ok=True)
nome_ficheiro = f"dados/garmin_{ontem}.json"
with open(nome_ficheiro, "w", encoding="utf-8") as f:
    json.dump(dados_finais, f, indent=4, ensure_ascii=False)

print(f"Dados salvos em {nome_ficheiro}!")

# Funções auxiliares de formatação
def formatar_tempo(segundos):
    if not segundos:
        return "0h 00m"
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    return f"{horas}h {minutos:02d}m"

def formatar_tempo_corrida(segundos):
    if not segundos:
        return "00:00"
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    if horas > 0:
        return f"{horas}:{minutos:02d}:{segs:02d}"
    return f"{minutos:02d}:{segs:02d}"

def formatar_pace(velocidade_ms):
    # O Garmin retorna velocidade em metros por segundo. Convertemos para min/km (Pace)
    if not speed_ms or velocidade_ms <= 0:
        return "--:--"
    pace_decimal = 16.666666667 / velocidade_ms
    minutos = int(pace_decimal)
    segundos = int((pace_decimal - minutos) * 60)
    return f"{minutos}:{segundos:02d}"

# 4. Processar se houve corrida ontem
texto_corrida = ""
for act in atividades:
    # Pega a data de início da atividade (formato 'YYYY-MM-DD HH:MM:SS')
    data_act = act.get("startTimeLocal", "")[:10]
    tipo_esporte = act.get("activityType", {}).get("typeKey", "").lower()
    
    # Se a atividade foi ontem e foi uma corrida
    if data_act == ontem and "run" in tipo_esporte:
        nome_treino = act.get("activityName", "Corrida")
        distancia_km = round(act.get("distance", 0) / 1000, 2)
        duracao = formatar_tempo_corrida(act.get("duration", 0))
        pace_medio = formatar_pace(act.get("averageSpeed", 0))
        bpm_medio = int(act.get("averageHR", 0)) if act.get("averageHR") else "N/A"
        calorias_treino = int(act.get("calories", 0))
        
        texto_corrida += (
            f"🏃‍♂️ *TREINO DE CORRIDA DETALHADO*\n"
            f"🏅 *Nome:* {nome_treino}\n"
            f"📏 *Distância:* {distancia_km} km\n"
            f"⏱️ *Tempo:* {duracao}\n"
            f"⏱️ *Pace Médio:* {pace_medio} /km\n"
            f"💓 *Frequência Cardíaca Média:* {bpm_medio} bpm\n"
            f"🔥 *Calorias do Treino:* {calorias_treino} kcal\n\n"
        )

# 5. Montar a mensagem do Telegram
if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
    passos = stats.get("steps", 0)
    calorias_ativas = stats.get("activeCalories", 0)
    calorias_bren = stats.get("bmrCalories", 0)
    calorias_totais = calorias_bren + calorias_ativas
    
    sono_total, sono_profundo, sono_leve, sono_rem = "0h 00m", "0h 00m", "0h 00m", "0h 00m"
    if sono:
        dto = sono.get("dailySleepDTO", {}) or sono
        sono_total = formatar_tempo(dto.get("sleepTimeInSeconds", 0))
        sono_profundo = formatar_tempo(dto.get("deepSleepSeconds", 0))
        sono_leve = formatar_tempo(dto.get("lightSleepSeconds", 0))
        sono_rem = formatar_tempo(dto.get("remSleepSeconds", 0))

    # Junta o resumo geral com o bloco de corrida (se houver)
    mensagem = (
        f"📊 *RELATÓRIO DIÁRIO GARMIN*\n"
        f"📅 Data: {ontem}\n\n"
        f"{texto_corrida}"  # Inserirá os dados da corrida aqui no topo se você tiver corrido!
        f"📋 *RESUMO GERAL DO DIA:*\n"
        f"🚶‍♂️ *Passos:* {passos:,}\n"
        f"🔥 *Calorias Ativas:* {calorias_ativas} kcal\n"
        f"🏅 *Calorias Totais:* {calorias_totais} kcal\n\n"
        f"😴 *Tempo de Sono Total:* {sono_total}\n"
        f"💤  └ 💎 *Profundo:* {sono_profundo}\n"
        f"💤  └ ☁️ *Leve:* {sono_leve}\n"
        f"💤  └ 🧠 *REM:* {sono_rem}\n\n"
        f"💪 _Continue focado nos treinos!_"
    )
    
    url_telegram = f"https://api.telegram.com/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    
    try:
        response = requests.post(url_telegram, json=payload)
        if response.status_code != 200:
            print(f"Erro ao enviar Telegram: {response.text}")
    except Exception as e:
        print(f"Falha na conexão com o Telegram: {e}")