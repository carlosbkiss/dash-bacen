#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard Econômico - TESTE EXECUÇÃO
OBJETIVO:
- NÃO quebrar
- Atualizar o que funcionar
- Manter último valor salvo
- APIs instáveis retornam None
- Fácil substituição futura
STATUS:
✅ Selic
✅ IPCA
⚠️ Poupança (série pode estar errada)
⚠️ Dólar (placeholder)
⚠️ Focus (placeholder)
⚠️ Desemprego (placeholder)
⚠️ PIB (placeholder)
⚠️ Confiança (placeholder)
"""
import json
import requests
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
# =====================================================
# CONFIG
# =====================================================
DATA_FILE = "data.json"
# =====================================================
# SESSION RETRY
# =====================================================
session = requests.Session()
retry = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)
# =====================================================
# LOG
# =====================================================
def log(msg):
    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    )
# =====================================================
# HELPERS
# =====================================================
def safe_request(url):
    try:
        r = session.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "DashboardEconomico/1.0"
            }
        )
        r.raise_for_status()
        return r
    except Exception as e:
        log(f"ERRO REQUEST: {e}")
        return None
def load_data():
    try:
        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)
    except:
        return {
            "macro": {},
            "metadata": {},
            "comunicados": []
        }
def save_data(data):
    with open(
        DATA_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )
def get_old_value(data, key):
    try:
        return data["macro"][key]["value"]
    except:
        return None
def calculate_trend(current, previous):
    try:
        if previous in [None, 0]:
            return 0.0
        return round(
            ((current - previous) / previous) * 100,
            2
        )
    except:
        return 0.0
# =====================================================
# SGS GENERIC
# =====================================================
def fetch_sgs_last_value(series_code):
    try:
        url = (
            f"https://api.bcb.gov.br/dados/serie/"
            f"bcdata.sgs.{series_code}/dados?formato=json"
        )
        r = safe_request(url)
        if not r:
            return None
        data = r.json()
        if not data:
            return None
        return float(
            str(data[-1]["valor"]).replace(",", ".")
        )
    except Exception as e:
        log(f"SGS {series_code}: {e}")
        return None
# =====================================================
# SELIC
# =====================================================
# VALIDADO:
# SGS 432
def fetch_selic():
    return fetch_sgs_last_value(432)
# =====================================================
# IPCA 12M
# =====================================================
# ASSUMINDO:
# SGS 13522
def fetch_ipca():
    return fetch_sgs_last_value(13522)
# =====================================================
# POUPANÇA
# =====================================================
# PREOCUPAÇÃO:
# SÉRIE PODE ESTAR ERRADA
def fetch_poupanca():
    return fetch_sgs_last_value(11)
# =====================================================
# DÓLAR
# =====================================================
# PLACEHOLDER
def fetch_dolar():
    try:
        # TODO PTAX
        return None
    except Exception as e:
        log(f"DOLAR: {e}")
        return None
# =====================================================
# FOCUS
# =====================================================
# PLACEHOLDER
def fetch_focus():
    try:
        # TODO OLINDA
        return None
    except Exception as e:
        log(f"FOCUS: {e}")
        return None
# =====================================================
# DESEMPREGO
# =====================================================
# PLACEHOLDER
def fetch_desemprego():
    try:
        # TODO SIDRA
        return None
    except Exception as e:
        log(f"DESEMPREGO: {e}")
        return None
# =====================================================
# PIB
# =====================================================
# PLACEHOLDER
def fetch_pib():
    try:
        # TODO SIDRA
        return None
    except Exception as e:
        log(f"PIB: {e}")
        return None
# =====================================================
# CONFIANÇA
# =====================================================
# PLACEHOLDER
def fetch_confianca():
    try:
        # TODO FGV
        return None
    except Exception as e:
        log(f"FGV: {e}")
        return None
# =====================================================
# UPDATE
# =====================================================
def update_indicator(
    data,
    key,
    value,
    source
):
    old_value = get_old_value(
        data,
        key
    )
    api_ok = value is not None
    # mantém valor anterior se API falhar
    if value is None:
        value = old_value
    # fallback absoluto
    if value is None:
        value = 0.0
    trend = calculate_trend(
        value,
        old_value
    )
    data["macro"][key] = {
        "value": value,
        "trend": trend,
        "source": source,
        "updatedAt":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
    }
    return api_ok
# =====================================================
# MAIN
# =====================================================
def main():
    log("INICIANDO UPDATE")
    data = load_data()
    # ==========================================
    # FETCH
    # ==========================================
    selic = fetch_selic()
    ipca = fetch_ipca()
    poupanca = fetch_poupanca()
    dolar = fetch_dolar()
    focus = fetch_focus()
    desemprego = fetch_desemprego()
    pib = fetch_pib()
    confianca = fetch_confianca()
    # ==========================================
    # UPDATE
    # ==========================================
    api_status = {}
    api_status["selic"] = update_indicator(
        data,
        "selic",
        selic,
        "Banco Central"
    )
    api_status["ipca"] = update_indicator(
        data,
        "ipca",
        ipca,
        "Banco Central"
    )
    api_status["poupanca"] = update_indicator(
        data,
        "poupanca",
        poupanca,
        "Banco Central"
    )
    api_status["dolar"] = update_indicator(
        data,
        "dolar",
        dolar,
        "Banco Central"
    )
    api_status["focus"] = update_indicator(
        data,
        "focus",
        focus,
        "Banco Central"
    )
    api_status["desemprego"] = update_indicator(
        data,
        "desemprego",
        desemprego,
        "IBGE"
    )
    api_status["pib"] = update_indicator(
        data,
        "pib",
        pib,
        "IBGE"
    )
    api_status["confianca"] = update_indicator(
        data,
        "confianca",
        confianca,
        "FGV"
    )
    # ==========================================
    # SPREAD
    # ==========================================
    selic_val = data["macro"]["selic"]["value"]
    focus_val = data["macro"]["focus"]["value"]
    spread_pp = round(
        focus_val - selic_val,
        2
    )
    data["macro"]["spread"] = {
        "value": spread_pp,
        "bps": int(spread_pp * 100),
        "interpretation":
            "Mercado espera QUEDA"
            if spread_pp < 0
            else "Mercado espera ALTA"
            if spread_pp > 0
            else "Mercado espera ESTABILIDADE",
        "updatedAt":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
    }
    # ==========================================
    # METADATA
    # ==========================================
    success_count = sum(
        1 for v in api_status.values()
        if v
    )
    data["metadata"] = {
        "lastUpdate":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        "successRate":
            f"{success_count}/{len(api_status)}",
        "apiStatus":
            api_status
    }
    # ==========================================
    # SAVE
    # ==========================================
    save_data(data)
    # ==========================================
    # LOG
    # ==========================================
    log("UPDATE FINALIZADO")
    print()
    print("=" * 50)
    for k, v in api_status.items():
        status = "✅" if v else "❌"
        print(f"{status} {k}")
    print("=" * 50)
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERRO CRÍTICO: {e}")