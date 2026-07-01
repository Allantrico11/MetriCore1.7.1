"""
=============================================================================
Módulo de lógica de cálculo - Regla de Decisión en Metrología
Basado en ISO/IEC 17025:2017, ILAC G8:2009/2019, ISO 14253-1:2017
=============================================================================

Este módulo implementa el motor de cálculo puro (sin UI) para:
  - Cálculo de límites de aceptación (AL) según la zona de seguridad (w)
  - Clasificación binaria y no binaria de resultados de medición
  - Cálculo de PFA (Probabilidad de Falsa Aceptación) y
    PFR (Probabilidad de Falso Rechazo) usando distribución normal real
    (no interpolación lineal arbitraria).

Convención de signos:
  - TL (límite de tolerancia): puede ser superior (USL), inferior (LSL) o ambos.
  - w (zona de seguridad / banda de guarda): w >= 0 implica un límite de
    aceptación MÁS ESTRICTO que el de tolerancia (más conservador).
    w < 0 (caso "No crítico") implica un límite de aceptación MÁS LAXO.
  - AL_superior = USL - w
  - AL_inferior = LSL + w

Modelo probabilístico:
  Se asume que el resultado medido X sigue una distribución normal con
  media = valor medido y desviación estándar sigma = U / k (por defecto k=2,
  es decir U es la incertidumbre expandida con factor de cobertura 2).

  Para un límite superior TL_sup:
    PFA = P(valor verdadero > TL_sup | medido) -> se calcula como la cola
    de la normal que queda más allá del límite de TOLERANCIA, dado que el
    resultado fue declarado "pasa".
    PFR = P(valor verdadero <= TL_sup | medido) cuando se declaró "no pasa".

  En términos prácticos y consistentes con el material del curso:
    - El riesgo siempre se expresa como la probabilidad de que el valor
      verdadero esté del lado "contrario" a la decisión tomada, evaluada
      en el límite de TOLERANCIA (no en el límite de aceptación), porque
      el riesgo que importa es respecto a la especificación real.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import math

try:
    from scipy.stats import norm
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


INF = float("inf")


def _fmt_pct(valor: float, texto: str | None = None) -> str:
    if texto:
        return texto
    if valor <= 0.0001:
        return "1 ppm"
    return f"{valor:.4g}%"


def _fmt_pct_valor(valor: float) -> str:
    if valor < 0.01:
        return f"{valor:.4g}%"
    return f"{valor:.2f}%"


def _pct_complemento(valor: float) -> float:
    return max(0.0, min(100.0, 100.0 - valor))


# =============================================================================
# UTILIDADES PROBABILÍSTICAS
# =============================================================================

def _norm_cdf(z: float) -> float:
    """CDF de la normal estándar. Usa scipy si está disponible, si no, erf."""
    if _HAS_SCIPY:
        return float(norm.cdf(z))
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def probabilidad_mas_alla(valor_medido: float, limite: float, U: float, k: float = 2.0) -> float:
    """
    Devuelve P(valor verdadero > limite), asumiendo:
        valor verdadero ~ Normal(valor_medido, sigma=U/k)

    Esta es la probabilidad de que el valor real esté POR ENCIMA del límite
    dado. Si valor_medido == limite, la probabilidad es exactamente 50%.
    Si valor_medido < limite (dentro), la probabilidad es < 50%.
    Si valor_medido > limite (fuera), la probabilidad es > 50%.

    Sirve tanto para calcular PFA (límite = límite de tolerancia superior,
    cuando el resultado pasa) como PFR (cuando el resultado no pasa).
    """
    if U <= 0:
        # Sin incertidumbre: certeza total, sin zona gris.
        return 0.0 if valor_medido <= limite else 1.0
    sigma = U / k
    z = (limite - valor_medido) / sigma
    return 1.0 - _norm_cdf(z)


def probabilidad_mas_alla_inferior(valor_medido: float, limite: float, U: float, k: float = 2.0) -> float:
    """
    Devuelve P(valor verdadero < limite) para un límite INFERIOR.
    Análogo a probabilidad_mas_alla pero para el lado inferior de la
    distribución (usado en LSL).
    """
    if U <= 0:
        return 0.0 if valor_medido >= limite else 1.0
    sigma = U / k
    z = (valor_medido - limite) / sigma
    return 1.0 - _norm_cdf(z)


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class LimitesAceptacion:
    AL_inf: float = -INF
    AL_sup: float = INF
    w: float = 0.0


@dataclass
class ResultadoEvaluacion:
    decision: str               # "Pasa" | "No pasa" | "Pasa condicionalmente" | "No pasa condicionalmente"
    icono: str                  # "✅" | "❌" | "⚠️"
    zona: str                   # descripción textual de la zona
    pfa_min: Optional[float] = None
    pfa_max: Optional[float] = None
    pfr_min: Optional[float] = None
    pfr_max: Optional[float] = None
    AL_inf: float = -INF
    AL_sup: float = INF
    w: float = 0.0
    lado: str = ""              # "superior" | "inferior" | "bilateral"
    frase: str = ""              # frase humana lista para reporte


# =============================================================================
# CÁLCULO DE LÍMITES DE ACEPTACIÓN
# =============================================================================

def calcular_AL(LSL: float, USL: float, w: float) -> LimitesAceptacion:
    """
    Calcula los límites de aceptación a partir de los límites de tolerancia
    y la zona de seguridad w (w >= 0 hace el criterio más estricto).

        AL_sup = USL - w
        AL_inf = LSL + w
    """
    AL_inf = (LSL + w) if LSL > -INF else -INF
    AL_sup = (USL - w) if USL < INF else INF
    return LimitesAceptacion(AL_inf=AL_inf, AL_sup=AL_sup, w=w)


# =============================================================================
# REGLA 1: ACEPTACIÓN SIMPLE (BINARIA, w = 0)
# =============================================================================

def evaluar_aceptacion_simple(valor_medido: float, U: float, LSL: float, USL: float,
                               k: float = 2.0) -> ResultadoEvaluacion:
    """
    Aceptación simple: AL = TL (w = 0). Riesgo compartido.
    Declaración binaria: Pasa / No pasa.
    El riesgo se reporta como PFA (si pasa) hasta 50%, o PFR (si no pasa)
    hasta 50%, evaluado siempre en el límite de tolerancia que corresponda.
    """
    dentro = True
    if LSL > -INF and valor_medido < LSL:
        dentro = False
    if USL < INF and valor_medido > USL:
        dentro = False

    if dentro:
        # PFA: probabilidad de que el valor real esté fuera de tolerancia
        riesgos = []
        if USL < INF:
            riesgos.append(probabilidad_mas_alla(valor_medido, USL, U, k) * 100)
        if LSL > -INF:
            riesgos.append(probabilidad_mas_alla_inferior(valor_medido, LSL, U, k) * 100)
        pfa = max(riesgos) if riesgos else 0.0
        pfa = min(pfa, 50.0)  # En aceptación simple, el riesgo máximo reportado es 50%
        return ResultadoEvaluacion(
            decision="Pasa", icono="✅", zona="Dentro del límite de tolerancia",
            pfa_min=0.0, pfa_max=round(pfa, 6),
            AL_inf=LSL, AL_sup=USL, w=0.0, lado="aceptación",
            frase=f"El resultado PASA, con un riesgo de falsa aceptación (PFA) de hasta {pfa:.2f}%."
        )
    else:
        riesgos = []
        if USL < INF and valor_medido > USL:
            riesgos.append(probabilidad_mas_alla_inferior(valor_medido, USL, U, k) * 100)
        if LSL > -INF and valor_medido < LSL:
            riesgos.append(probabilidad_mas_alla(valor_medido, LSL, U, k) * 100)
        pfr = max(riesgos) if riesgos else 0.0
        pfr = min(pfr, 50.0)
        return ResultadoEvaluacion(
            decision="No pasa", icono="❌", zona="Fuera del límite de tolerancia",
            pfr_min=0.0, pfr_max=round(pfr, 2),
            AL_inf=LSL, AL_sup=USL, w=0.0, lado="rechazo",
            frase=f"El resultado NO PASA, con un riesgo de falso rechazo (PFR) de hasta {pfr:.2f}%."
        )


# =============================================================================
# REGLA 2: BINARIA CON ZONA DE SEGURIDAD
# =============================================================================

def evaluar_binaria_zona_seguridad(valor_medido: float, U: float, LSL: float, USL: float,
                                    w: float, k: float = 2.0,
                                    riesgo_ref_pct: float = 2.5,
                                    riesgo_ref_text: str | None = None) -> ResultadoEvaluacion:
    """
    Regla binaria con zona de seguridad w = m·U (o cualquier otro criterio).
    AL = TL - w (más estricto). Sigue siendo binaria: Pasa / No pasa,
    pero el riesgo se reporta de forma más granular según la tabla del curso:

        Zona de aceptación        resultado <= TL - U      Pasa      PFA <= 2.5%
        Zona de rechazo conserv.  TL - U < resultado <= TL  No pasa   PFR entre 97.5% y 50%
        Zona de rechazo cerca     TL < resultado <= TL + U  No pasa   PFR entre 50% y 2.5%
        Zona de rechazo claro     resultado > TL + U        No pasa   PFR < 2.5%

    Nota: la tabla del curso usa específicamente w = U para definir estas
    cuatro sub-zonas de riesgo informativo, aun cuando la propia regla de
    decisión pueda usar un w distinto (m·U) para la frontera PASA/NO PASA.
    Aquí generalizamos: la frontera de decisión usa el w configurado;
    las sub-zonas de riesgo informativo siempre se referencian a U.
    """
    AL = calcular_AL(LSL, USL, w)

    dentro_AL = True
    if AL.AL_inf > -INF and valor_medido < AL.AL_inf:
        dentro_AL = False
    if AL.AL_sup < INF and valor_medido > AL.AL_sup:
        dentro_AL = False

    if dentro_AL:
        riesgos = []
        if USL < INF:
            riesgos.append(probabilidad_mas_alla(valor_medido, USL, U, k) * 100)
        if LSL > -INF:
            riesgos.append(probabilidad_mas_alla_inferior(valor_medido, LSL, U, k) * 100)
        pfa = max(riesgos) if riesgos else 0.0
        pfa = min(pfa, riesgo_ref_pct) if w > 0 else min(pfa, 50.0)
        return ResultadoEvaluacion(
            decision="Pasa", icono="✅",
            zona=f"Zona de aceptación (dentro de AL, w={w:.4g})",
            pfa_min=0.0, pfa_max=round(pfa, 6),
            AL_inf=AL.AL_inf, AL_sup=AL.AL_sup, w=w, lado="aceptación",
            frase=f"El resultado PASA, con un riesgo de falsa aceptación (PFA) ≤ {_fmt_pct(riesgo_ref_pct, riesgo_ref_text)} (específicamente {_fmt_pct_valor(pfa)})."
        )

    # Fuera de AL -> No pasa. Sub-clasificar la zona de riesgo según U (tabla del curso).
    lado_superior = USL < INF and valor_medido > AL.AL_sup
    TL = USL if lado_superior else LSL

    if lado_superior:
        dist = valor_medido - TL
    else:
        dist = TL - valor_medido

    if dist <= 0:
        # Entre AL y TL: "rechazo conservador" -> PFR entre 97.5% y 50%
        sub_zona = "Zona de rechazo conservador (entre AL y TL)"
        pfr_min, pfr_max = 50.0, _pct_complemento(riesgo_ref_pct)
    elif dist <= w:
        # Entre TL y TL+U: "rechazo cerca del límite" -> PFR entre 50% y 2.5%
        sub_zona = "Zona de rechazo cerca del límite (entre TL y TL+w)"
        pfr_min, pfr_max = riesgo_ref_pct, 50.0
    else:
        # Más allá de TL+U: "rechazo claro" -> PFR < 2.5%
        sub_zona = "Zona de rechazo claro (más allá de TL+w)"
        pfr_min, pfr_max = 0.0, riesgo_ref_pct

    return ResultadoEvaluacion(
        decision="No pasa", icono="❌",
        zona=sub_zona,
        pfr_min=pfr_min, pfr_max=pfr_max,
        AL_inf=AL.AL_inf, AL_sup=AL.AL_sup, w=w,
        lado="superior" if lado_superior else "inferior",
        frase=f"El resultado NO PASA ({sub_zona}), con un riesgo de falso rechazo (PFR) entre {_fmt_pct_valor(pfr_min)} y {_fmt_pct_valor(pfr_max)}."
    )


# =============================================================================
# REGLA 3: NO BINARIA CON ZONA DE SEGURIDAD (ILAC G8)
# =============================================================================

def _evaluar_no_binaria_un_lado(valor_medido: float, TL: float, U: float,
                                 es_superior: bool, k: float = 2.0,
                                 w: float | None = None,
                                 riesgo_ref_pct: float = 2.5,
                                 riesgo_ref_text: str | None = None) -> ResultadoEvaluacion:
    """
    Evalúa la regla no binaria de ILAC G8 para un único límite de tolerancia
    (superior o inferior). w = U siempre en esta regla (es su definición).

    Zonas (para límite superior; el inferior es simétrico):
        Resultado <= TL - U                  -> Pasa                    PFA <= 2.5%
        TL - U < Resultado <= TL             -> Pasa condicionado       PFA entre 2.5% y 50%
        TL < Resultado <= TL + U             -> No pasa condicionado    PFR entre 50% y 2.5%
        Resultado > TL + U                   -> No pasa                 PFR < 2.5%
    """
    w = U if w is None else w

    if es_superior:
        AL = TL - w   # límite de aceptación clara
        d = valor_medido - TL  # distancia con signo al límite de tolerancia
    else:
        AL = TL + w
        d = TL - valor_medido

    # d > 0  => más allá del límite de tolerancia (hacia fuera)
    # d <= 0 => dentro del límite de tolerancia

    if es_superior:
        riesgo_fuera = lambda vm: probabilidad_mas_alla(vm, TL, U, k) * 100
    else:
        riesgo_fuera = lambda vm: probabilidad_mas_alla_inferior(vm, TL, U, k) * 100

    if d <= -w:
        # Resultado <= TL - U -> Pasa, PFA <= 2.5%
        pfa = min(riesgo_fuera(valor_medido), riesgo_ref_pct)
        return ResultadoEvaluacion(
            decision="Pasa", icono="✅",
            zona="Zona de aceptación clara (Resultado ≤ TL − w)",
            pfa_min=0.0, pfa_max=round(pfa, 2),
            AL_inf=AL if not es_superior else -INF,
            AL_sup=AL if es_superior else INF,
            w=w, lado="superior" if es_superior else "inferior",
            frase=f"PASA, con un riesgo de falsa aceptación (PFA) ≤ {_fmt_pct(riesgo_ref_pct, riesgo_ref_text)} (específicamente {_fmt_pct_valor(pfa)})."
        )
    elif d <= 0:
        # TL - U < Resultado <= TL -> Pasa condicionado, PFA entre 2.5% y 50%
        pfa = riesgo_fuera(valor_medido)
        pfa = max(riesgo_ref_pct, min(pfa, 50.0))
        return ResultadoEvaluacion(
            decision="Pasa condicionalmente", icono="⚠️",
            zona="Zona de aceptación condicionada (TL − w < Resultado ≤ TL)",
            pfa_min=riesgo_ref_pct, pfa_max=round(pfa, 6),
            AL_inf=AL if not es_superior else -INF,
            AL_sup=AL if es_superior else INF,
            w=w, lado="superior" if es_superior else "inferior",
            frase=f"PASA CONDICIONALMENTE (zona de duda), con un riesgo de falsa aceptación (PFA) entre {_fmt_pct(riesgo_ref_pct, riesgo_ref_text)} y {_fmt_pct_valor(pfa)}."
        )
    elif d <= w:
        # TL < Resultado <= TL + U -> No pasa condicionado, PFR entre 50% y 2.5%
        # (a medida que d crece de 0 a U, el riesgo de falso rechazo baja de 50% a 2.5%)
        pfr = 100.0 - riesgo_fuera(valor_medido)
        pfr = max(riesgo_ref_pct, min(pfr, 50.0))
        return ResultadoEvaluacion(
            decision="No pasa condicionalmente", icono="⚠️",
            zona="Zona de rechazo condicionado (TL < Resultado ≤ TL + w)",
            pfr_min=riesgo_ref_pct, pfr_max=round(pfr, 6),
            AL_inf=AL if not es_superior else -INF,
            AL_sup=AL if es_superior else INF,
            w=w, lado="superior" if es_superior else "inferior",
            frase=f"NO PASA CONDICIONALMENTE (zona de duda), con un riesgo de falso rechazo (PFR) entre {_fmt_pct(riesgo_ref_pct, riesgo_ref_text)} y {_fmt_pct_valor(pfr)}."
        )
    else:
        # Resultado > TL + U -> No pasa, PFR < 2.5%
        pfr = 100.0 - riesgo_fuera(valor_medido)
        pfr = min(pfr, riesgo_ref_pct)
        return ResultadoEvaluacion(
            decision="No pasa", icono="❌",
            zona="Zona de rechazo claro (Resultado > TL + w)",
            pfr_min=0.0, pfr_max=round(pfr, 6),
            AL_inf=AL if not es_superior else -INF,
            AL_sup=AL if es_superior else INF,
            w=w, lado="superior" if es_superior else "inferior",
            frase=f"NO PASA, con un riesgo de falso rechazo (PFR) < {_fmt_pct(riesgo_ref_pct, riesgo_ref_text)} (específicamente {_fmt_pct_valor(pfr)})."
        )


def evaluar_no_binaria_zona_seguridad(valor_medido: float, U: float, LSL: float, USL: float,
                                       k: float = 2.0, w: float | None = None,
                                       riesgo_ref_pct: float = 2.5,
                                       riesgo_ref_text: str | None = None) -> ResultadoEvaluacion:
    """
    Regla no binaria con zona de seguridad (ILAC G8). w = U siempre.
    Declaración: Pasa / Pasa condicionalmente / No pasa condicionalmente / No pasa.

    Para límites bilaterales se evalúan ambos lados y se reporta el más
    restrictivo (peor caso) según la jerarquía:
        No pasa > No pasa condicionalmente > Pasa condicionalmente > Pasa
    """
    tiene_sup = USL < INF
    tiene_inf = LSL > -INF

    jerarquia = {"No pasa": 4, "No pasa condicionalmente": 3,
                 "Pasa condicionalmente": 2, "Pasa": 1}

    candidatos = []
    if tiene_sup:
        candidatos.append(_evaluar_no_binaria_un_lado(
            valor_medido, USL, U, es_superior=True, k=k, w=w,
            riesgo_ref_pct=riesgo_ref_pct, riesgo_ref_text=riesgo_ref_text,
        ))
    if tiene_inf:
        candidatos.append(_evaluar_no_binaria_un_lado(
            valor_medido, LSL, U, es_superior=False, k=k, w=w,
            riesgo_ref_pct=riesgo_ref_pct, riesgo_ref_text=riesgo_ref_text,
        ))

    if not candidatos:
        # Sin límites definidos (caso degenerado)
        return ResultadoEvaluacion(decision="Pasa", icono="✅", zona="Sin límite definido")

    candidatos.sort(key=lambda r: jerarquia[r.decision], reverse=True)
    resultado = candidatos[0]

    # Si es bilateral, anexar ambos límites de aceptación calculados para que
    # el gráfico pueda dibujar correctamente ambos lados.
    if tiene_sup and tiene_inf:
        w_final = U if w is None else w
        resultado.AL_sup = USL - w_final
        resultado.AL_inf = LSL + w_final
    return resultado


# =============================================================================
# FUNCIÓN PRINCIPAL DE EVALUACIÓN (dispatcher)
# =============================================================================

REGLAS = {
    "aceptacion_simple": "Aceptación Simple (Binaria)",
    "binaria_zona_seguridad": "Binaria con Zona de Seguridad",
    "no_binaria_zona_seguridad": "No Binaria con Zona de Seguridad (ILAC G8)",
}


def evaluar_punto(valor_medido: float, U: float, LSL: float, USL: float,
                   regla: str, w: float = 0.0, k: float = 2.0,
                   riesgo_ref_pct: float = 2.5,
                   riesgo_ref_text: str | None = None) -> ResultadoEvaluacion:
    """
    Punto único de entrada para evaluar una medición según la regla elegida.

    regla: una de las claves/valores de REGLAS.
    w: zona de seguridad (solo aplica a "binaria_zona_seguridad"); para
       "no_binaria_zona_seguridad" se fuerza w=U automáticamente.
    k: factor de cobertura de U (por defecto 2, el estándar en metrología).
    """
    if regla in ("aceptacion_simple", REGLAS["aceptacion_simple"]):
        return evaluar_aceptacion_simple(valor_medido, U, LSL, USL, k=k)
    elif regla in ("binaria_zona_seguridad", REGLAS["binaria_zona_seguridad"]):
        return evaluar_binaria_zona_seguridad(
            valor_medido, U, LSL, USL, w=w, k=k,
            riesgo_ref_pct=riesgo_ref_pct, riesgo_ref_text=riesgo_ref_text,
        )
    elif regla in ("no_binaria_zona_seguridad", REGLAS["no_binaria_zona_seguridad"]):
        return evaluar_no_binaria_zona_seguridad(
            valor_medido, U, LSL, USL, k=k, w=w or U,
            riesgo_ref_pct=riesgo_ref_pct, riesgo_ref_text=riesgo_ref_text,
        )
    else:
        raise ValueError(f"Regla de decisión no reconocida: {regla}")
