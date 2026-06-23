#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard Econômico - Indicadores Brasil
=========================================
Fontes:
  - Banco Central (SGS / PTAX / Expectativas / Noticias)
  - IBGE (SIDRA)

STATUS:
✅ Selic        → SGS 432
✅ IPCA 12m     → SGS 13522
✅ Poupança     → SGS 195
✅ Dólar PTAX   → Olinda PTAX
✅ Focus IPCA   → Olinda Expectativas
✅ Spread       → calculado (Focus IPCA - Selic)
✅ Desemprego   → SIDRA 6381 / var 4099
✅ PIB          → SIDRA 1621 / var 584
✅ Confiança    → SIDRA 7963 / var 7383  ⚠️ validar se agregado existe
✅ Comunicados  → BCB noticias API
"""

import json
import requests
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =====================================================
# CONFIG
# =====================================================
DATA_FILE = "data.json"

# =====================================================
# SESSION COM RETRY
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

HEADERS = {"User-Agent": "DashboardEconomico/2.0"}

# =====================================================
# LOG
# =====================================================
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# =====================================================
# HELPERS
# =====================================================
def safe_request(url, params=None):
    try:
        r = session.get(url, timeout=20, headers=HEADERS, params=params)
        r.raise_for_status()
        return r
    except Exception as e:
        log(f"ERRO REQUEST [{url[:60]}...]: {e}")
        return None

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"macro": {}, "metadata": {}, "comunicados": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_old_value(data, key):
    try:
        return data["macro"][key]["value"]
    except:
        return None

def calculate_trend(current, previous):
    try:
        if previous in [None, 0]:
            return 0.0
        return round(((current - previous) / previous) * 100, 2)
    except:
        return 0.0

def ultimo_dia_util(delta_days=0):
    """Retorna último dia útil (seg–sex) como string MM-DD-YYYY para PTAX."""
    d = datetime.today() - timedelta(days=delta_days)
    # volta até sexta se cair em fim de semana
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%m-%d-%Y")

# =====================================================
# SGS GENÉRICO — BCB
# Endpoint: /dados/serie/bcdata.sgs.{codigo}/dados/ultimos/1
# =====================================================
def fetch_sgs(series_code):
    url = (
        f"https://api.bcb.gov.br/dados/serie/"
        f"bcdata.sgs.{series_code}/dados/ultimos/1?formato=json"
    )
    try:
        r = safe_request(url)
        if not r:
            return None
        data = r.json()
        if not data:
            return None
        raw = data[0].get("valor") or data[0].get("value")
        return float(str(raw).replace(",", "."))
    except Exception as e:
        log(f"SGS {series_code}: {e}")
        return None

# =====================================================
# 1. SELIC — SGS 432 (diária, % a.a.)
# =====================================================
def fetch_selic():
    v = fetch_sgs(432)
    if v is not None:
        log(f"Selic: {v}% a.a.")
    return v

# =====================================================
# 2. IPCA 12M — SGS 13522 (acumulado 12 meses, %)
# =====================================================
def fetch_ipca():
    v = fetch_sgs(13522)
    if v is not None:
        log(f"IPCA 12m: {v}%")
    return v

# =====================================================
# 3. POUPANÇA — SGS 195 (rendimento mensal, %)
# Série 195 = poupança antiga (depósitos até maio/2012)
# Série 25 = poupança nova (TR + 70% Selic se < 8.5%)
# Usar 25 se quiser regra atual
# =====================================================
def fetch_poupanca():
    v = fetch_sgs(25)
    if v is not None:
        log(f"Poupança: {v}% a.m.")
    return v

# =====================================================
# 4. DÓLAR PTAX — Olinda PTAX
# Endpoint: CotacaoDolarDia(dataCotacao=@d)
# Tenta hoje, se não vier (fds/feriado) tenta D-1 até D-3
# =====================================================
def fetch_dolar():
    try:
        base = (
            "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
            "CotacaoDolarDia(dataCotacao=@dataCotacao)"
        )
        for delta in range(4):
            data_str = ultimo_dia_util(delta)
            params = {
                "@dataCotacao": f"'{data_str}'",
                "$format": "json",
                "$select": "cotacaoVenda,dataHoraCotacao"
            }
            r = safe_request(base, params=params)
            if not r:
                continue
            values = r.json().get("value", [])
            if values:
                v = float(values[-1]["cotacaoVenda"])
                log(f"Dólar PTAX ({data_str}): R$ {v}")
                return v
        log("Dólar: nenhuma cotação encontrada nos últimos 4 dias úteis")
        return None
    except Exception as e:
        log(f"Dólar: {e}")
        return None

# =====================================================
# 5. FOCUS — Olinda Expectativas
# Puxa expectativa mediana de IPCA para o ano corrente
# =====================================================
def fetch_focus():
    try:
        url = (
            "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
            "ExpectativaMercadoAnuais"
        )
        ano = str(datetime.today().year)
        params = {
            "$filter": f"Indicador eq 'IPCA' and DataReferencia eq '{ano}'",
            "$orderby": "Data desc",
            "$top": "1",
            "$select": "Indicador,Data,DataReferencia,Mediana",
            "$format": "json"
        }
        r = safe_request(url, params=params)
        if not r:
            return None
        values = r.json().get("value", [])
        if not values:
            return None
        v = float(values[0]["Mediana"])
        log(f"Focus IPCA {ano}: {v}%")
        return v
    except Exception as e:
        log(f"Focus: {e}")
        return None

# =====================================================
# 7. DESEMPREGO — SIDRA 6381 / variável 4099
# PNAD Contínua trimestral, Brasil (N1)
# =====================================================
def fetch_desemprego():
    try:
        url = (
            "https://servicodados.ibge.gov.br/api/v3/agregados/"
            "6381/periodos/last%201/variaveis/4099"
            "?localidades=N1[all]"
        )
        r = safe_request(url)
        if not r:
            return None
        data = r.json()
        v = float(data[0]["resultados"][0]["series"][0]["serie"].values().__iter__().__next__())
        log(f"Desemprego: {v}%")
        return v
    except Exception as e:
        log(f"Desemprego: {e}")
        return None

# =====================================================
# 8. PIB — SIDRA 1621 / variável 584
# Contas Nacionais Trimestrais, var % acum. 4 tri
# =====================================================
def fetch_pib():
    try:
        url = (
            "https://servicodados.ibge.gov.br/api/v3/agregados/"
            "1621/periodos/last%201/variaveis/584"
            "?localidades=N1[all]"
        )
        r = safe_request(url)
        if not r:
            return None
        data = r.json()
        v = float(data[0]["resultados"][0]["series"][0]["serie"].values().__iter__().__next__())
        log(f"PIB: {v}%")
        return v
    except Exception as e:
        log(f"PIB: {e}")
        return None

# =====================================================
# 9. CONFIANÇA — SIDRA 7963 / variável 7383
# ICC — Índice de Confiança do Consumidor (FGV via IBGE)
# ⚠️ Se retornar None, agregado pode ter mudado — verificar SIDRA
# =====================================================
def fetch_confianca():
    try:
        url = (
            "https://servicodados.ibge.gov.br/api/v3/agregados/"
            "7963/periodos/last%201/variaveis/7383"
            "?localidades=N1[all]"
        )
        r = safe_request(url)
        if not r:
            return None
        data = r.json()
        v = float(data[0]["resultados"][0]["series"][0]["serie"].values().__iter__().__next__())
        log(f"Confiança ICC: {v}")
        return v
    except Exception as e:
        log(f"Confiança: {e}")
        return None

# =====================================================
# 10. COMUNICADOS — BCB Notícias
# =====================================================
def fetch_comunicados():
    try:
        url = "https://www.bcb.gov.br/api/servico/sitebcb/noticias"
        params = {"quantidade": 3, "offset": 0}
        r = safe_request(url, params=params)
        if not r:
            return []
        items = r.json().get("conteudo", [])
        result = []
        for item in items:
            result.append({
                "titulo": item.get("titulo", ""),
                "data": item.get("dataPublicacao", ""),
                "url": "https://www.bcb.gov.br" + item.get("url", "")
            })
        log(f"Comunicados: {len(result)} itens")
        return result
    except Exception as e:
        log(f"Comunicados: {e}")
        return []

# =====================================================
# UPDATE INDICADOR
# =====================================================
def update_indicator(data, key, value, source, unit=""):
    old_value = get_old_value(data, key)
    api_ok = value is not None

    if value is None:
        value = old_value  # mantém último valor conhecido
    if value is None:
        value = 0.0        # fallback absoluto

    trend = calculate_trend(value, old_value)

    data["macro"][key] = {
        "value": value,
        "unit": unit,
        "trend": trend,
        "source": source,
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return api_ok

# =====================================================
# MAIN
# =====================================================
def main():
    log("INICIANDO UPDATE")
    data = load_data()

    # --------------------------------------------------
    # FETCH
    # --------------------------------------------------
    selic      = fetch_selic()
    ipca       = fetch_ipca()
    poupanca   = fetch_poupanca()
    dolar      = fetch_dolar()
    focus      = fetch_focus()
    desemprego = fetch_desemprego()
    pib        = fetch_pib()
    confianca  = fetch_confianca()
    comunicados = fetch_comunicados()

    # --------------------------------------------------
    # UPDATE INDICADORES
    # --------------------------------------------------
    api_status = {}

    api_status["selic"]      = update_indicator(data, "selic",      selic,      "Banco Central", "% a.a.")
    api_status["ipca"]       = update_indicator(data, "ipca",       ipca,       "Banco Central", "% 12m")
    api_status["poupanca"]   = update_indicator(data, "poupanca",   poupanca,   "Banco Central", "% a.m.")
    api_status["dolar"]      = update_indicator(data, "dolar",      dolar,      "Banco Central", "R$/USD")
    api_status["focus"]      = update_indicator(data, "focus",      focus,      "Banco Central", "% IPCA proj.")
    api_status["desemprego"] = update_indicator(data, "desemprego", desemprego, "IBGE",          "%")
    api_status["pib"]        = update_indicator(data, "pib",        pib,        "IBGE",          "% acum. 4tri")
    api_status["confianca"]  = update_indicator(data, "confianca",  confianca,  "FGV/IBGE",      "pontos")

    # --------------------------------------------------
    # SPREAD — calculado: Focus IPCA - Selic
    # Positivo = mercado espera inflação acima da Selic
    # Negativo = mercado espera queda de juros
    # --------------------------------------------------
    selic_val = data["macro"]["selic"]["value"]
    focus_val = data["macro"]["focus"]["value"]
    spread_pp = round(focus_val - selic_val, 2)

    data["macro"]["spread"] = {
        "value": spread_pp,
        "bps": int(spread_pp * 100),
        "interpretation": (
            "Mercado espera QUEDA de juros" if spread_pp < 0 else
            "Mercado espera ALTA de juros"  if spread_pp > 0 else
            "Mercado espera ESTABILIDADE"
        ),
        "unit": "pp",
        "source": "Calculado (Focus IPCA - Selic)",
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # --------------------------------------------------
    # COMUNICADOS
    # --------------------------------------------------
    if comunicados:
        data["comunicados"] = comunicados

    # --------------------------------------------------
    # METADATA
    # --------------------------------------------------
    success_count = sum(1 for v in api_status.values() if v)
    data["metadata"] = {
        "lastUpdate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "successRate": f"{success_count}/{len(api_status)}",
        "apiStatus": api_status
    }

    # --------------------------------------------------
    # SAVE
    # --------------------------------------------------
    save_data(data)

    # --------------------------------------------------
    # RELATÓRIO FINAL
    # --------------------------------------------------
    log("UPDATE FINALIZADO")
    print()
    print("=" * 50)
    print(f"  Taxa de sucesso: {success_count}/{len(api_status)}")
    print("=" * 50)
    for k, ok in api_status.items():
        status = "✅" if ok else "❌ (usando valor anterior)"
        val = data["macro"].get(k, {}).get("value", "-")
        unit = data["macro"].get(k, {}).get("unit", "")
        print(f"  {status}  {k:<12} → {val} {unit}")
    print("=" * 50)
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERRO CRÍTICO: {e}")
        raise
