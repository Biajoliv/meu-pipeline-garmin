import os
import json
from datetime import datetime, timedelta
from garminconnect import Garmin

# Tenta ler as credenciais das variáveis de ambiente do sistema
USER = os.getenv("GARMIN_USER")
PASSWORD = os.getenv("GARMIN_PASSWORD")

if not USER or not PASSWORD:
    raise ValueError("Credenciais do Garmin não encontradas nas variáveis de ambiente.")

# Inicializa e faz login
garmin = Garmin(USER, PASSWORD)
garmin.login()

# Define a data de ontem (para garantir que pegamos o dia completo já fechado)
ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

# Extrai os dados do dia
stats = garmin.get_stats(ontem)
sono = garmin.get_sleep_data(ontem)

# Estrutura o dado final
dados_finais = {
    "data": ontem,
    "resumo": stats,
    "sono": sono
}

# Cria a pasta 'dados' se não existir
os.makedirs("dados", exist_ok=True)

# Guarda num ficheiro JSON com o nome da data
nome_ficheiro = f"dados/garmin_{ontem}.json"
with open(nome_ficheiro, "w", encoding="utf-8") as f:
    json.dump(dados_finais, f, indent=4, ensure_ascii=False)

print(f"Dados de {ontem} guardados com sucesso em {nome_ficheiro}!")