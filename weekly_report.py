import os
import json
import glob
import requests
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("Credenciais do Telegram não encontradas.")

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


def calcular_sono_total(dto):
    total = dto.get("sleepTimeInSeconds")
    if total:
        return total
    return (
        (dto.get("deepSleepSeconds") or 0) +
        (dto.get("remSleepSeconds") or 0) +
        (dto.get("lightSleepSeconds") or 0)
    )


def media(lista):
    valores = [v for v in lista if v is not None and v > 0]
    return round(sum(valores) / len(valores), 1) if valores else 0


def label_stress(stress):
    if not stress or stress <= 0:
        return "—"
    if stress < 25:
        return "Baixo ✅"
    if stress < 50:
        return "Moderado 🟡"
    if stress < 75:
        return "Alto ⚠️"
    return "Muito alto 🔴"


def calcular_acwr(todos_registros):
    """Calcula o Acute:Chronic Workload Ratio para corridas.

    ACWR < 0.8 = destreinamento | 0.8-1.3 = zona ideal | 1.3-1.5 = atenção | >1.5 = risco de lesão
    """
    todas_atividades = {}
    for r in todos_registros:
        for act in r.get("atividades", []):
            tipo = act.get("activityType", {}).get("typeKey", "").lower()
            if "run" not in tipo:
                continue
            act_id = act.get("activityId")
            if act_id and act_id not in todas_atividades:
                todas_atividades[act_id] = act

    if not todas_atividades:
        return None

    def tlu(act):
        dur_min = (act.get("duration") or 0) / 60
        hr = act.get("averageHR") or 100
        return dur_min * (hr / 100)

    carga_7d = 0.0
    cargas_semanas = [0.0, 0.0, 0.0, 0.0]

    for act in todas_atividades.values():
        data_str = act.get("startTimeLocal", "")[:10]
        if not data_str:
            continue
        try:
            data_act = datetime.strptime(data_str, "%Y-%m-%d").date()
        except Exception:
            continue

        carga = tlu(act)
        dias_atras = (hoje - data_act).days

        if 0 <= dias_atras < 7:
            carga_7d += carga

        if 0 <= dias_atras < 28:
            semana_idx = dias_atras // 7
            cargas_semanas[semana_idx] += carga

    carga_cronica = sum(cargas_semanas) / 4

    if carga_cronica <= 0:
        return {
            "carga_aguda": round(carga_7d, 1),
            "carga_cronica": 0,
            "acwr": None,
            "dias_dados": len(todos_registros),
        }

    return {
        "carga_aguda": round(carga_7d, 1),
        "carga_cronica": round(carga_cronica, 1),
        "acwr": round(carga_7d / carga_cronica, 2),
        "dias_dados": len(todos_registros),
        "completo": len(todos_registros) >= 28,
    }


def label_acwr(acwr):
    if acwr < 0.8:
        return "Destreinamento"
    if acwr <= 1.3:
        return "Zona ideal ✅"
    if acwr <= 1.5:
        return "Zona de atenção ⚠️"
    return "Risco de lesão 🔴"


# --- Carrega dados dos últimos 7 dias ---
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

# Carrega todos os arquivos disponíveis (até 28 dias) para ACWR
todos_arquivos = sorted(glob.glob("dados/garmin_*.json"), reverse=True)[:28]
todos_registros_acwr = []
for path in todos_arquivos:
    with open(path, encoding="utf-8") as f:
        todos_registros_acwr.append(json.load(f))

n = len(registros)

# --- Médias do período ---
passos_media = media([r["resumo"].get("totalSteps", 0) for r in registros])
calorias_ativas_media = media([r["resumo"].get("activeKilocalories", 0) for r in registros])
calorias_totais_media = media([r["resumo"].get("totalKilocalories", 0) for r in registros])
fc_repouso_media = media([r["resumo"].get("restingHeartRate", 0) for r in registros])
stress_media = media([r["resumo"].get("averageStressLevel", 0) for r in registros])
body_battery_media = media([r["resumo"].get("bodyBatteryHighestValue", 0) for r in registros])

# --- Médias de sono ---
sono_registros = []
for r in registros:
    sono = r.get("sono")
    if not sono:
        continue
    dto = sono.get("dailySleepDTO", {}) or sono
    sono_registros.append(dto)

sono_total_media = 0
sono_profundo_media = 0
sono_rem_media = 0
if sono_registros:
    sono_total_media = media([calcular_sono_total(d) for d in sono_registros])
    sono_profundo_media = media([d.get("deepSleepSeconds", 0) for d in sono_registros])
    sono_rem_media = media([d.get("remSleepSeconds", 0) for d in sono_registros])

pct_profundo_media = round(sono_profundo_media / sono_total_media * 100) if sono_total_media > 0 else 0
pct_rem_media = round(sono_rem_media / sono_total_media * 100) if sono_total_media > 0 else 0
badge_profundo = "✅" if 13 <= pct_profundo_media <= 23 else "🟡"
badge_rem = "✅" if 20 <= pct_rem_media <= 25 else "🟡"

# --- Corridas da semana (deduplicadas por ID) ---
corridas_vistas = set()
corridas = []
for r in registros:
    for act in r.get("atividades", []):
        data_act = act.get("startTimeLocal", "")[:10]
        tipo = act.get("activityType", {}).get("typeKey", "").lower()
        act_id = act.get("activityId")
        if data_act in [str(d) for d in dias] and "run" in tipo:
            if act_id not in corridas_vistas:
                corridas_vistas.add(act_id)
                corridas.append(act)

texto_corridas = ""
if corridas:
    total_km = round(sum(c.get("distance", 0) for c in corridas) / 1000, 2)
    pace_medio = formatar_pace(
        sum(c.get("averageSpeed", 0) for c in corridas) / len(corridas)
    )
    fc_corrida_media = int(media([c.get("averageHR", 0) for c in corridas]))
    texto_corridas = (
        f"🏃 *CORRIDAS DA SEMANA*\n"
        f"Qtd: {len(corridas)}  |  Total: {total_km} km\n"
        f"Pace médio: {pace_medio} /km  |  FC: {fc_corrida_media} bpm\n\n"
    )
else:
    texto_corridas = "🏃 *CORRIDAS DA SEMANA*\nNenhuma corrida registrada.\n\n"

# --- Tendência HRV semanal ---
DIAS_SEMANA = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}
hrv_por_dia = {}
for r in registros:
    data = r.get("data", "")
    hrv = r.get("sono", {}).get("avgOvernightHrv") if r.get("sono") else None
    if data and hrv:
        hrv_por_dia[data] = round(hrv)

hrv_linha = []
hrv_valores = []
for dia in sorted(dias):
    hrv_val = hrv_por_dia.get(str(dia))
    label_dia = DIAS_SEMANA[dia.weekday()]
    if hrv_val:
        hrv_linha.append(f"{label_dia} {hrv_val}ms")
        hrv_valores.append(hrv_val)
    else:
        hrv_linha.append(f"{label_dia} —")

texto_hrv_semanal = ""
if hrv_valores:
    hrv_media_semana = round(sum(hrv_valores) / len(hrv_valores))
    if len(hrv_valores) >= 2:
        delta = hrv_valores[-1] - hrv_valores[0]
        tendencia = f"{'↑' if delta > 0 else '↓' if delta < 0 else '→'} {abs(delta)}ms vs. início da semana"
    else:
        tendencia = ""

    texto_hrv_semanal = (
        f"🫀 *TENDÊNCIA HRV (7 DIAS)*\n"
        + "  ".join(hrv_linha) + "\n"
        + f"Média: {hrv_media_semana}ms"
        + (f"  |  {tendencia}" if tendencia else "") + "\n\n"
    )

# --- ACWR ---
acwr_result = calcular_acwr(todos_registros_acwr)
texto_acwr = ""
if acwr_result:
    if acwr_result["acwr"] is not None:
        acwr_label = label_acwr(acwr_result["acwr"])
        aviso = "  (histórico parcial)" if not acwr_result.get("completo") else ""
        texto_acwr = (
            f"⚖️ *CARGA DE TREINO (ACWR)*\n"
            f"Aguda (7d): {acwr_result['carga_aguda']} TLU  |  Crônica (28d): {acwr_result['carga_cronica']} TLU\n"
            f"Razão: {acwr_result['acwr']} — {acwr_label}{aviso}\n"
            f"(menor que 0.8=destreinamento | 0.8-1.3=ideal | 1.3-1.5=atenção | maior que 1.5=risco)\n\n"
        )
    elif acwr_result["carga_aguda"] > 0:
        texto_acwr = (
            f"⚖️ *CARGA DE TREINO*\n"
            f"Carga da semana: {acwr_result['carga_aguda']} TLU\n"
            f"(acumulando histórico de 28 dias para calcular ACWR completo)\n\n"
        )

# --- Alertas ---
fc_baseline = registros[0]["resumo"].get("lastSevenDaysAvgRestingHeartRate") or fc_repouso_media

alertas = []
if fc_repouso_media and fc_repouso_media > fc_baseline * 1.10:
    alertas.append(f"❤️ FC em repouso média elevada: {int(fc_repouso_media)} bpm (baseline: {int(fc_baseline)} bpm)")
if stress_media and stress_media > 65:
    alertas.append(f"🧠 Semana com stress alto: média {int(stress_media)}/100")
if sono_total_media and sono_total_media < 21600:
    alertas.append(f"😴 Sono médio insuficiente: {formatar_tempo(sono_total_media)} (meta: 6h+)")
if not corridas:
    alertas.append("🏃 Nenhuma corrida registrada na semana")
if acwr_result and acwr_result.get("acwr") and acwr_result["acwr"] > 1.5:
    alertas.append(f"⚖️ Carga de treino muito elevada: ACWR {acwr_result['acwr']} — reduza o volume")

if alertas:
    texto_alertas = "⚠️ *ALERTAS DA SEMANA:*\n" + "\n".join(f"• {a}" for a in alertas) + "\n\n"
else:
    texto_alertas = "✅ *Todos os indicadores normais na semana*\n\n"

# --- Mensagem final ---
data_inicio = str(min(dias))
data_fim = str(max(dias))

mensagem = (
    f"📊 *RELATÓRIO SEMANAL GARMIN*\n"
    f"📅 {data_inicio} → {data_fim}  ({n} dias com dados)\n\n"
    f"{texto_corridas}"
    f"📋 *MÉDIAS DO PERÍODO:*\n"
    f"🚶 *Passos/dia:* {int(passos_media):,}\n"
    f"🔥 *Calorias ativas/dia:* {int(calorias_ativas_media)} kcal\n\n"
    f"😴 *SONO MÉDIO:* {formatar_tempo(sono_total_media)}\n"
    f"💎 Profundo: {formatar_tempo(sono_profundo_media)} ({pct_profundo_media}%) {badge_profundo}  (ideal: 13-23%)\n"
    f"🧠 REM: {formatar_tempo(sono_rem_media)} ({pct_rem_media}%) {badge_rem}  (ideal: 20-25%)\n\n"
    f"❤️ *FC repouso:* {int(fc_repouso_media)} bpm\n"
    f"🧠 *Stress médio:* {int(stress_media)}/100 — {label_stress(stress_media)}\n"
    f"⚡ *Body Battery máx.:* {int(body_battery_media)}\n\n"
    f"{texto_hrv_semanal}"
    f"{texto_acwr}"
    f"{texto_alertas}"
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
