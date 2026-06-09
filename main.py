import os
import json
import requests
from datetime import datetime, timedelta
from garminconnect import Garmin

USER = os.getenv("GARMIN_USER")
PASSWORD = os.getenv("GARMIN_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not USER or not PASSWORD:
    raise ValueError("Credenciais do Garmin não encontradas.")

garmin = Garmin(USER, PASSWORD)
garmin.login()

ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

stats = garmin.get_stats(ontem)
sono = garmin.get_sleep_data(ontem)
atividades = garmin.get_activities(0, 5)

dados_finais = {"data": ontem, "resumo": stats, "sono": sono, "atividades": atividades}
os.makedirs("dados", exist_ok=True)
nome_ficheiro = f"dados/garmin_{ontem}.json"
with open(nome_ficheiro, "w", encoding="utf-8") as f:
    json.dump(dados_finais, f, indent=4, ensure_ascii=False)

print(f"Dados salvos em {nome_ficheiro}!")


# --- Funções auxiliares ---

def formatar_tempo(segundos):
    if not segundos:
        return "0h 00m"
    return f"{int(segundos // 3600)}h {int((segundos % 3600) // 60):02d}m"


def formatar_tempo_corrida(segundos):
    if not segundos:
        return "00:00"
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = int(segundos % 60)
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"


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


def label_body_battery(bb):
    if bb is None:
        return "—"
    if bb >= 70:
        return "Bem recuperado ✅"
    if bb >= 40:
        return "Razoável 🟡"
    return "Baixo ⚠️"


def badge_sono(segundos):
    if not segundos:
        return "❌"
    if segundos >= 25200:
        return "✅"
    if segundos >= 21600:
        return "🟡"
    return "❌"


def label_training_effect(te):
    if not te or te < 1.0:
        return "Sem efeito"
    if te < 2.0:
        return "Menor"
    if te < 3.0:
        return "Manutenção"
    if te < 4.0:
        return "Melhora"
    if te < 5.0:
        return "Alta melhora"
    return "Sobrecarga"


def calcular_hrv_score(sono_data, historico_paths):
    if not sono_data:
        return None
    hrv_hoje = sono_data.get("avgOvernightHrv")
    hrv_status_raw = sono_data.get("hrvStatus", "")

    status_map = {
        "BALANCED": "Equilibrado ✅",
        "UNBALANCED": "Desequilibrado ⚠️",
        "POOR": "Baixo ❌",
    }
    hrv_status = status_map.get(hrv_status_raw, hrv_status_raw or "—")

    if not hrv_hoje:
        return None

    hrv_historico = []
    for path in historico_paths:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            hrv_val = data.get("sono", {}).get("avgOvernightHrv")
            if hrv_val:
                hrv_historico.append(hrv_val)
        except Exception:
            pass

    if len(hrv_historico) >= 2:
        hrv_media_7d = sum(hrv_historico) / len(hrv_historico)
        recovery_pct = round((hrv_hoje / hrv_media_7d) * 100)

        if recovery_pct >= 100:
            recovery_label, prontidao = "Ótima", "Treino intenso OK"
        elif recovery_pct >= 85:
            recovery_label, prontidao = "Boa", "Treino moderado/forte OK"
        elif recovery_pct >= 70:
            recovery_label, prontidao = "Moderada", "Prefira treino leve"
        else:
            recovery_label, prontidao = "Baixa", "Priorize recuperação hoje"

        return {
            "hrv": round(hrv_hoje),
            "status": hrv_status,
            "recovery_pct": recovery_pct,
            "recovery_label": recovery_label,
            "prontidao": prontidao,
            "has_baseline": True,
        }

    return {
        "hrv": round(hrv_hoje),
        "status": hrv_status,
        "has_baseline": False,
    }


def calcular_economia_corrida(atividade):
    cad = atividade.get("averageRunningCadenceInStepsPerMinute") or 0
    vo = atividade.get("avgVerticalOscillation") or 0
    gct = atividade.get("avgGroundContactTime") or 0

    if not (cad or vo or gct):
        return None

    scores = []

    if cad:
        cad_score = max(0.0, 100 - max(0.0, 170 - cad) * 2)
        scores.append(cad_score)
        cad_badge = "✅" if cad >= 170 else ("🟡" if cad >= 160 else "⚠️")
    else:
        cad_badge = ""

    if vo:
        vo_score = max(0.0, 100 - max(0.0, vo - 7) * 10)
        scores.append(vo_score)
        vo_badge = "✅" if vo <= 7 else ("🟡" if vo <= 9 else "⚠️")
    else:
        vo_badge = ""

    if gct:
        gct_score = max(0.0, 100 - max(0.0, gct - 220) * 0.5)
        scores.append(gct_score)
        gct_badge = "✅" if gct <= 220 else ("🟡" if gct <= 260 else "⚠️")
    else:
        gct_badge = ""

    score_final = round(sum(scores) / len(scores)) if scores else 0

    if score_final >= 85:
        label = "Excelente"
    elif score_final >= 70:
        label = "Boa"
    elif score_final >= 55:
        label = "Moderada"
    else:
        label = "Precisa melhorar"

    return {
        "cadencia": round(cad, 1) if cad else None,
        "cadencia_badge": cad_badge,
        "vo": round(vo, 1) if vo else None,
        "vo_badge": vo_badge,
        "gct": round(gct) if gct else None,
        "gct_badge": gct_badge,
        "score": score_final,
        "label": label,
    }


def verificar_alertas(stats, dto):
    alertas = []

    fc_hoje = stats.get("restingHeartRate") or 0
    fc_media_7d = stats.get("lastSevenDaysAvgRestingHeartRate") or 0
    if fc_hoje and fc_media_7d and fc_hoje > fc_media_7d * 1.10:
        alertas.append(f"❤️ FC em repouso elevada: {fc_hoje} bpm (sua média: {fc_media_7d} bpm)")

    stress = stats.get("averageStressLevel") or 0
    if stress > 65:
        alertas.append(f"🧠 Stress alto: {stress}/100")

    bb = stats.get("bodyBatteryAtWakeTime")
    if bb is not None and bb < 40:
        alertas.append(f"⚡ Body Battery baixo ao acordar: {bb}")

    if dto:
        total_sono = calcular_sono_total(dto)
        if total_sono and total_sono < 21600:
            alertas.append(f"😴 Sono insuficiente: {formatar_tempo(total_sono)} (meta: 6h+)")

        profundo = dto.get("deepSleepSeconds") or 0
        if profundo and profundo < 2700:
            alertas.append(f"💎 Sono profundo baixo: {formatar_tempo(profundo)}")

    spo2 = stats.get("lowestSpo2")
    if spo2 and spo2 < 95:
        alertas.append(f"🫁 SpO2 mínimo baixo: {spo2}%")

    return alertas


# --- Processar corridas ---
texto_corrida = ""
for act in atividades:
    data_act = act.get("startTimeLocal", "")[:10]
    tipo_esporte = act.get("activityType", {}).get("typeKey", "").lower()

    if data_act == ontem and "run" in tipo_esporte:
        nome_treino = act.get("activityName", "Corrida")
        distancia_km = round(act.get("distance", 0) / 1000, 2)
        duracao = formatar_tempo_corrida(act.get("duration", 0))
        pace_medio = formatar_pace(act.get("averageSpeed", 0))
        pace_min = formatar_pace(act.get("maxSpeed", 0))  # maior velocidade = pace mais rápido
        bpm_medio = int(act.get("averageHR", 0)) if act.get("averageHR") else "N/A"
        bpm_max = int(act.get("maxHR", 0)) if act.get("maxHR") else "N/A"
        calorias_treino = int(act.get("calories", 0))
        te_aerobico = act.get("aerobicTrainingEffect") or 0
        label_te = label_training_effect(te_aerobico)

        texto_corrida += (
            f"🏃 *TREINO DE CORRIDA*\n"
            f"🏅 {nome_treino}\n"
            f"📏 {distancia_km} km  |  ⏱️ {duracao}\n"
            f"⏱️ Pace: {pace_medio} méd  /  {pace_min} mín /km\n"
            f"💓 FC: {bpm_medio} méd  /  {bpm_max} máx bpm\n"
            f"🔥 Calorias: {calorias_treino} kcal\n"
            f"⚡ Efeito aeróbico: {te_aerobico:.1f} — {label_te}\n\n"
        )

        eco = calcular_economia_corrida(act)
        if eco:
            linhas_eco = ["📐 *ECONOMIA DE CORRIDA*"]
            if eco["cadencia"]:
                linhas_eco.append(f"Cadência: {eco['cadencia']} spm {eco['cadencia_badge']} (ideal: 170-180)")
            if eco["vo"]:
                linhas_eco.append(f"Oscilação vertical: {eco['vo']}cm {eco['vo_badge']} (ideal: menor que 7cm)")
            if eco["gct"]:
                linhas_eco.append(f"Contato com o solo: {eco['gct']}ms {eco['gct_badge']} (ideal: menor que 220ms)")
            linhas_eco.append(f"Score de eficiência: {eco['score']}/100 — {eco['label']}")
            texto_corrida += "\n".join(linhas_eco) + "\n\n"


# --- Montar a mensagem ---
if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
    passos = stats.get("totalSteps", 0)
    calorias_ativas = stats.get("activeKilocalories", 0)
    calorias_bren = stats.get("bmrKilocalories", 0)
    calorias_totais = (calorias_bren or 0) + (calorias_ativas or 0)
    stress = stats.get("averageStressLevel") or 0
    bb_acordar = stats.get("bodyBatteryAtWakeTime")

    dto = None
    sono_total_seg = 0
    if sono:
        dto = sono.get("dailySleepDTO", {}) or sono
        sono_total_seg = calcular_sono_total(dto)

    sono_profundo_seg = (dto.get("deepSleepSeconds") or 0) if dto else 0
    sono_rem_seg = (dto.get("remSleepSeconds") or 0) if dto else 0

    sono_total_fmt = formatar_tempo(sono_total_seg)
    sono_profundo_fmt = formatar_tempo(sono_profundo_seg)
    sono_leve_fmt = formatar_tempo((dto.get("lightSleepSeconds") or 0) if dto else 0)
    sono_rem_fmt = formatar_tempo(sono_rem_seg)

    pct_profundo = round(sono_profundo_seg / sono_total_seg * 100) if sono_total_seg > 0 else 0
    pct_rem = round(sono_rem_seg / sono_total_seg * 100) if sono_total_seg > 0 else 0
    badge_p = "✅" if 13 <= pct_profundo <= 23 else ("⚠️" if sono_profundo_seg > 0 else "")
    badge_r = "✅" if 20 <= pct_rem <= 25 else ("🟡" if sono_rem_seg > 0 else "")
    badge_s = badge_sono(sono_total_seg)

    # HRV: carrega histórico dos 6 dias anteriores a ontem para baseline
    hrv_historico_paths = []
    for i in range(2, 8):
        data_hist = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        path = f"dados/garmin_{data_hist}.json"
        if os.path.exists(path):
            hrv_historico_paths.append(path)

    hrv_result = calcular_hrv_score(sono, hrv_historico_paths) if sono else None

    texto_hrv = ""
    if hrv_result:
        if hrv_result["has_baseline"]:
            texto_hrv = (
                f"🫀 *HRV e RECUPERAÇÃO*\n"
                f"HRV noturno: {hrv_result['hrv']}ms  |  Status: {hrv_result['status']}\n"
                f"Recuperação: {hrv_result['recovery_pct']}% ({hrv_result['recovery_label']})  →  {hrv_result['prontidao']}\n\n"
            )
        else:
            texto_hrv = (
                f"🫀 *HRV e RECUPERAÇÃO*\n"
                f"HRV noturno: {hrv_result['hrv']}ms  |  Status: {hrv_result['status']}\n"
                f"(acumulando histórico para calcular score de recuperação)\n\n"
            )

    alertas = verificar_alertas(stats, dto)
    if alertas:
        texto_alertas = "⚠️ *ALERTAS DO DIA:*\n" + "\n".join(f"• {a}" for a in alertas) + "\n\n"
    else:
        texto_alertas = "✅ *Todos os indicadores normais*\n\n"

    mensagem = (
        f"📊 *RELATÓRIO DIÁRIO GARMIN*\n"
        f"📅 {ontem}\n\n"
        f"{texto_corrida}"
        f"📋 *RESUMO DO DIA:*\n"
        f"🚶 *Passos:* {passos:,}\n"
        f"🔥 *Calorias:* {int(calorias_ativas)} kcal ativos  /  {int(calorias_totais)} kcal totais\n\n"
        f"😴 *SONO:* {sono_total_fmt} {badge_s}\n"
        f"💎 Profundo: {sono_profundo_fmt} ({pct_profundo}%) {badge_p}  (ideal: 13-23%)\n"
        f"☁️ Leve: {sono_leve_fmt}\n"
        f"🧠 REM: {sono_rem_fmt} ({pct_rem}%) {badge_r}  (ideal: 20-25%)\n\n"
        f"{texto_hrv}"
        f"🧠 *Stress:* {stress}/100 — {label_stress(stress)}\n"
        f"⚡ *Body Battery ao acordar:* {bb_acordar if bb_acordar is not None else '—'} — {label_body_battery(bb_acordar)}\n\n"
        f"{texto_alertas}"
        f"💪 _Continue focado nos treinos!_"
    )

    url_telegram = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}

    try:
        response = requests.post(url_telegram, json=payload)
        if response.status_code != 200:
            print(f"Erro ao enviar Telegram: {response.text}")
    except Exception as e:
        print(f"Falha na conexão com o Telegram: {e}")
