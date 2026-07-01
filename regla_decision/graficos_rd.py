"""
graficos_rd.py
==============
Gráficos VERTICALES de zonas de conformidad metrológica.
- Eje Y = valor medido (zonas horizontales)
- Un punto por columna en el comparativo
- Leyenda y etiquetas siempre fuera del área de datos
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

matplotlib.rcParams["font.family"] = "DejaVu Sans"

INF = float("inf")

# ── Paleta ────────────────────────────────────────────────────────────────────
C_VERDE_FONDO   = "#cdeeda"
C_VERDE_BORDE   = "#1e8449"
C_VERDE_PUNTO   = "#1a6b35"

C_NARANJA_FONDO = "#fde8c2"
C_NARANJA_BORDE = "#e67e22"
C_NARANJA_PUNTO = "#c0610a"

C_DURAZNO_FONDO = "#fac9a8"
C_DURAZNO_BORDE = "#cb4a1a"
C_DURAZNO_PUNTO = "#8b2500"

C_ROJO_FONDO    = "#f5b8b0"
C_ROJO_BORDE    = "#c0392b"
C_ROJO_PUNTO    = "#7b241c"

C_AL  = "#27ae60"
C_TL  = "#2c3e50"
C_TLW = "#cb4a1a"

CPUNTO = {
    "Pasa":                     C_VERDE_PUNTO,
    "Pasa condicionalmente":    C_NARANJA_PUNTO,
    "No pasa condicionalmente": C_DURAZNO_PUNTO,
    "No pasa":                  C_ROJO_PUNTO,
}


def _rango_y(LSL, USL, valores, U_vals, extras=None, pad_factor=0.30):
    """Calcula límites del eje Y con margen."""
    pts = list(valores)
    refs = [v for v in [LSL, USL] if abs(v) < 1e15]
    if extras:
        refs += [v for v in extras if v is not None and abs(v) < 1e15]
    todos = pts + refs
    if not todos:
        return -1.0, 1.0
    rng = max(todos) - min(todos) or 1.0
    u_pad = max(U_vals) * 2.8 if U_vals else 0
    pad = max(rng * pad_factor, u_pad)
    return min(todos) - pad, max(todos) + pad


def _hspan(ax, y0, y1, ylo, yhi, color, alpha=0.82):
    """Franja horizontal recortada al rango visible (todo el ancho del eje X)."""
    a, b = max(y0, ylo), min(y1, yhi)
    if b > a:
        ax.axhspan(a, b, color=color, alpha=alpha, zorder=0)


def _hspan_col(ax, x0, x1, y0, y1, ylo, yhi, color, alpha=0.82):
    """Franja horizontal recortada al rango visible, limitada a una columna
    (x0–x1). Permite que cada punto del comparativo tenga su propia zona,
    según su propio AL/w, en vez de una franja única para todo el gráfico."""
    a, b = max(y0, ylo), min(y1, yhi)
    if b > a:
        ax.add_patch(mpatches.Rectangle(
            (x0, a), x1 - x0, b - a,
            facecolor=color, edgecolor="none", alpha=alpha, zorder=0))


def _hline(ax, y, color, lw, ls, zorder=4):
    if y is not None and abs(y) < 1e15:
        ax.axhline(y, color=color, lw=lw, ls=ls, zorder=zorder)


# =============================================================================
# GRÁFICO INDIVIDUAL (vertical)
# =============================================================================

def grafico_individual(valor_medido, U, LSL, USL, resultado, unidad, titulo=""):
    """
    Gráfico de un único punto con el eje Y como valor medido.
    Las zonas se muestran como franjas horizontales.
    """
    AL_inf = getattr(resultado, "AL_inf", None)
    AL_sup = getattr(resultado, "AL_sup", None)
    w      = getattr(resultado, "w", 0) or 0
    dec    = resultado.decision
    regla  = getattr(resultado, "regla", "")   # "binaria_zona_seguridad" / "no_binaria_zona_seguridad"

    TLW_sup = (USL + w) if (USL < 1e15 and w > 0) else None
    TLW_inf = (LSL - w) if (LSL > -1e15 and w > 0) else None

    al_s = AL_sup if (AL_sup is not None and AL_sup < 1e15) else (USL if USL < 1e15 else None)
    al_i = AL_inf if (AL_inf is not None and AL_inf > -1e15) else (LSL if LSL > -1e15 else None)

    ylo, yhi = _rango_y(LSL, USL, [valor_medido], [U],
                        extras=[TLW_sup, TLW_inf, al_s, al_i])

    es_no_binaria = "no_binaria" in str(regla)

    fig, ax = plt.subplots(figsize=(7, 5.5))
    fig.patch.set_facecolor("white")

    _usl   = USL   if USL < 1e15   else yhi
    _lsl   = LSL   if LSL > -1e15  else ylo
    _al_s  = al_s  if al_s  is not None else _usl
    _al_i  = al_i  if al_i  is not None else _lsl
    _tlw_s = TLW_sup if TLW_sup is not None else _usl
    _tlw_i = TLW_inf if TLW_inf is not None else _lsl

    # ── Fondos de zona ─────────────────────────────────────────────────────
    if es_no_binaria:
        _hspan(ax, ylo,   _tlw_i, ylo, yhi, C_ROJO_FONDO)
        _hspan(ax, _tlw_i, _lsl,  ylo, yhi, C_DURAZNO_FONDO)
        _hspan(ax, _lsl,   _al_i, ylo, yhi, C_NARANJA_FONDO)
        _hspan(ax, _al_i,  _al_s, ylo, yhi, C_VERDE_FONDO)
        _hspan(ax, _al_s,  _usl,  ylo, yhi, C_NARANJA_FONDO)
        _hspan(ax, _usl,   _tlw_s,ylo, yhi, C_DURAZNO_FONDO)
        _hspan(ax, _tlw_s, yhi,   ylo, yhi, C_ROJO_FONDO)
    else:
        # binaria (simple o con zona de seguridad): 3 zonas
        _hspan(ax, ylo,  _lsl,  ylo, yhi, C_ROJO_FONDO)
        _hspan(ax, _lsl, _al_i, ylo, yhi, C_NARANJA_FONDO)
        _hspan(ax, _al_i,_al_s, ylo, yhi, C_VERDE_FONDO)
        _hspan(ax, _al_s,_usl,  ylo, yhi, C_NARANJA_FONDO)
        _hspan(ax, _usl, yhi,   ylo, yhi, C_ROJO_FONDO)

    # ── Líneas de referencia ────────────────────────────────────────────────
    _hline(ax, _usl, C_TL, 2.0, "-")
    _hline(ax, _lsl, C_TL, 2.0, "-")
    if al_s is not None and abs(_al_s - _usl) > 1e-10:
        _hline(ax, _al_s, C_AL, 1.8, "--")
    if al_i is not None and abs(_al_i - _lsl) > 1e-10:
        _hline(ax, _al_i, C_AL, 1.8, "--")
    if es_no_binaria:
        if TLW_sup is not None and abs(_tlw_s - _usl) > 1e-10:
            _hline(ax, _tlw_s, C_TLW, 1.4, ":")
        if TLW_inf is not None and abs(_tlw_i - _lsl) > 1e-10:
            _hline(ax, _tlw_i, C_TLW, 1.4, ":")

    # ── Punto con barra de incertidumbre ────────────────────────────────────
    c_p = CPUNTO.get(dec, "#7f8c8d")
    ax.errorbar(0.5, valor_medido, yerr=U, fmt="o",
                color=c_p, ecolor="#2c3e50",
                elinewidth=2.2, capsize=8, capthick=2.2,
                markersize=11, zorder=5,
                markeredgecolor="white", markeredgewidth=1.2)

    # ── Etiquetas de líneas (lado derecho, fuera del área de datos) ─────────
    x_lbl = 0.97   # coordenada axes
    def hlabel(y, texto, color):
        if y is not None and ylo < y < yhi:
            ax.text(x_lbl, y, f" {texto}",
                    transform=ax.get_yaxis_transform(),
                    ha="left", va="center", fontsize=7.5,
                    color=color, clip_on=False,
                    bbox=dict(boxstyle="round,pad=0.18", fc="white",
                              ec=color, alpha=0.85, lw=0.8))

    hlabel(_usl,   f"TL={_usl:.4g}", C_TL)
    if al_s is not None and abs(_al_s - _usl) > 1e-10:
        hlabel(_al_s, f"AL={_al_s:.4g}", C_AL)
    if es_no_binaria and TLW_sup is not None and abs(_tlw_s - _usl) > 1e-10:
        hlabel(_tlw_s, f"TL+w={_tlw_s:.4g}", C_TLW)

    # ── Estética ────────────────────────────────────────────────────────────
    ax.set_ylim(ylo, yhi)
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_ylabel(f"Valor medido ({unidad})", fontsize=9, color="#444", labelpad=6)
    ax.set_title(titulo, fontsize=9.5, fontweight="bold", color="#2c3e50", pad=9,
                 wrap=True)
    ax.tick_params(axis="y", labelsize=8.5, colors="#444")
    for sp in ["top", "bottom", "right"]:
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color("#bbb")

    # ── Leyenda debajo del gráfico ──────────────────────────────────────────
    if es_no_binaria:
        items_leyenda = [
            mpatches.Patch(color=C_VERDE_FONDO,   label="Conforme"),
            mpatches.Patch(color=C_NARANJA_FONDO, label="Pasa cond."),
            mpatches.Patch(color=C_DURAZNO_FONDO, label="No pasa cond."),
            mpatches.Patch(color=C_ROJO_FONDO,    label="No conforme"),
        ]
    else:
        items_leyenda = [
            mpatches.Patch(color=C_VERDE_FONDO,   label="Conforme"),
            mpatches.Patch(color=C_NARANJA_FONDO, label="Zona de guarda"),
            mpatches.Patch(color=C_ROJO_FONDO,    label="No conforme"),
        ]
    ax.legend(handles=items_leyenda,
              loc="upper center", bbox_to_anchor=(0.5, -0.04),
              ncol=2, fontsize=7.5, framealpha=0.95,
              edgecolor="#ccc", bbox_transform=ax.transAxes)

    fig.tight_layout(rect=[0.0, 0.12, 0.82, 1.0])
    return fig


# =============================================================================
# GRÁFICO COMPARATIVO (vertical, una columna por punto)
# =============================================================================

def grafico_comparativo(df, LSL, USL, unidad, titulo="", regla=""):
    """
    Gráfico comparativo con orientación vertical:
    - Eje Y = valor medido con franjas de zona horizontales
    - Eje X = puntos de medición (una columna por etiqueta)
    - Leyenda y etiquetas de valor fuera del área de datos
    """
    if df is None or df.empty:
        return None

    n = len(df)

    es_no_binaria = "no_binaria" in str(regla)

    _usl   = USL if USL < 1e15 else None
    _lsl   = LSL if LSL > -1e15 else None

    # ── Límites de aceptación (AL) y zona de seguridad (w) PROPIOS de cada
    #    punto: cada fila puede tener una U (y por lo tanto un w y un AL)
    #    distinta, así que se calculan y se guardan por punto, no una sola
    #    vez para todo el gráfico. ───────────────────────────────────────────
    al_sup_pts, al_inf_pts, w_pts = [], [], []
    tlw_sup_pts, tlw_inf_pts = [], []
    for _, row in df.iterrows():
        als = row.get("AL_sup")
        ali = row.get("AL_inf")
        ww  = float(row.get("w", 0) or 0)
        als = float(als) if (als is not None and abs(float(als)) < 1e15) else _usl
        ali = float(ali) if (ali is not None and abs(float(ali)) < 1e15) else _lsl
        al_sup_pts.append(als)
        al_inf_pts.append(ali)
        w_pts.append(ww)
        tlw_sup_pts.append((_usl + ww) if (_usl is not None and ww > 0) else None)
        tlw_inf_pts.append((_lsl - ww) if (_lsl is not None and ww > 0) else None)

    def _uniforme(valores, tol=1e-9):
        """True si todos los puntos comparten el mismo valor (dentro de tol)."""
        vals_validos = [v for v in valores if v is not None]
        if len(vals_validos) <= 1:
            return True
        v0 = vals_validos[0]
        return all(abs(v - v0) <= tol * max(1.0, abs(v0)) for v in vals_validos)

    w_es_uniforme = _uniforme(w_pts)

    vals = df["Valor Medido"].tolist()
    us   = df["U"].tolist()
    extras = [v for v in (al_sup_pts + al_inf_pts + tlw_sup_pts + tlw_inf_pts) if v is not None]
    ylo, yhi = _rango_y(LSL, USL, vals, us, extras=extras, pad_factor=0.25)

    # ── Figura ───────────────────────────────────────────────────────────────
    col_w  = 1.6          # ancho por columna de datos
    fig_w  = max(7, n * col_w + 4.0)   # 4 cm extra: margen izq etiquetas + leyenda der
    fig_h  = 7.5

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor("white")

    # Rango X: de -0.5 a n-0.5 (columnas centradas en 0,1,2,...)
    xlo, xhi = -0.6, n - 0.4

    # ── Fondos de zona: una franja POR COLUMNA, con el AL/w propio de cada
    #    punto, en vez de una única franja calculada con el primer dato. ─────
    _u = _usl if _usl is not None else yhi
    _l = _lsl if _lsl is not None else ylo

    for i in range(n):
        x0, x1 = i - 0.42, i + 0.42
        _as = al_sup_pts[i]  if al_sup_pts[i]  is not None else _u
        _ai = al_inf_pts[i]  if al_inf_pts[i]  is not None else _l
        _ts = tlw_sup_pts[i] if tlw_sup_pts[i] is not None else _u
        _ti = tlw_inf_pts[i] if tlw_inf_pts[i] is not None else _l

        if es_no_binaria:
            _hspan_col(ax, x0, x1, ylo, _ti,  ylo, yhi, C_ROJO_FONDO)
            _hspan_col(ax, x0, x1, _ti, _l,   ylo, yhi, C_DURAZNO_FONDO)
            _hspan_col(ax, x0, x1, _l,  _ai,  ylo, yhi, C_NARANJA_FONDO)
            _hspan_col(ax, x0, x1, _ai, _as,  ylo, yhi, C_VERDE_FONDO)
            _hspan_col(ax, x0, x1, _as, _u,   ylo, yhi, C_NARANJA_FONDO)
            _hspan_col(ax, x0, x1, _u,  _ts,  ylo, yhi, C_DURAZNO_FONDO)
            _hspan_col(ax, x0, x1, _ts, yhi,  ylo, yhi, C_ROJO_FONDO)
        else:
            _hspan_col(ax, x0, x1, ylo, _l,   ylo, yhi, C_ROJO_FONDO)
            _hspan_col(ax, x0, x1, _l,  _ai,  ylo, yhi, C_NARANJA_FONDO)
            _hspan_col(ax, x0, x1, _ai, _as,  ylo, yhi, C_VERDE_FONDO)
            _hspan_col(ax, x0, x1, _as, _u,   ylo, yhi, C_NARANJA_FONDO)
            _hspan_col(ax, x0, x1, _u,  yhi,  ylo, yhi, C_ROJO_FONDO)

        # Segmentos de AL / TL±w propios de esta columna (solo dentro de su
        # ancho, para no mezclar el límite de un punto con el de otro)
        if al_sup_pts[i] is not None and abs(_as - _u) > 1e-10:
            ax.plot([x0, x1], [_as, _as], color=C_AL, lw=1.8, ls="--", zorder=4)
        if al_inf_pts[i] is not None and abs(_ai - _l) > 1e-10:
            ax.plot([x0, x1], [_ai, _ai], color=C_AL, lw=1.8, ls="--", zorder=4)
        if es_no_binaria:
            if tlw_sup_pts[i] is not None and abs(_ts - _u) > 1e-10:
                ax.plot([x0, x1], [_ts, _ts], color=C_TLW, lw=1.4, ls=":", zorder=4)
            if tlw_inf_pts[i] is not None and abs(_ti - _l) > 1e-10:
                ax.plot([x0, x1], [_ti, _ti], color=C_TLW, lw=1.4, ls=":", zorder=4)

    # ── Líneas de referencia horizontales (TL es fijo: viene de la
    #    especificación, no del dato, así que sí abarca todo el ancho) ───────
    if _usl is not None:
        _hline(ax, _usl, C_TL, 2.0, "-")
    if _lsl is not None:
        _hline(ax, _lsl, C_TL, 2.0, "-")

    # ── Etiquetas de líneas de referencia (margen derecho) ───────────────────
    x_tag = xhi + 0.05   # justo fuera del área de datos

    def ref_label(y, texto, color):
        if y is not None and ylo < y < yhi:
            ax.text(x_tag, y, f" {texto}",
                    ha="left", va="center", fontsize=7.8,
                    color=color, clip_on=False,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white",
                              ec=color, alpha=0.9, lw=0.8))

    ref_label(_usl,  f"TL = {_usl:.4g} {unidad}",  C_TL)
    if _lsl is not None:
        ref_label(_lsl, f"TL inf = {_lsl:.4g} {unidad}", C_TL)

    if w_es_uniforme:
        # Todos los puntos comparten el mismo w -> el AL/TL±w es el mismo
        # para todas las columnas, así que sí tiene sentido una sola
        # etiqueta de referencia y la flecha de "w" en el margen derecho.
        _as0 = al_sup_pts[0] if al_sup_pts[0] is not None else _u
        _ai0 = al_inf_pts[0] if al_inf_pts[0] is not None else _l
        _ts0 = tlw_sup_pts[0] if tlw_sup_pts[0] is not None else _u
        _ti0 = tlw_inf_pts[0] if tlw_inf_pts[0] is not None else _l

        if al_sup_pts[0] is not None and abs(_as0 - _u) > 1e-10:
            ref_label(al_sup_pts[0], f"AL = {al_sup_pts[0]:.4g} {unidad}", C_AL)
        if al_inf_pts[0] is not None and abs(_ai0 - _l) > 1e-10:
            ref_label(al_inf_pts[0], f"AL inf = {al_inf_pts[0]:.4g} {unidad}", C_AL)
        if es_no_binaria:
            if tlw_sup_pts[0] is not None and abs(_ts0 - _u) > 1e-10:
                ref_label(tlw_sup_pts[0], f"TL+w = {tlw_sup_pts[0]:.4g} {unidad}", C_TLW)
            if tlw_inf_pts[0] is not None and abs(_ti0 - _l) > 1e-10:
                ref_label(tlw_inf_pts[0], f"TL−w = {tlw_inf_pts[0]:.4g} {unidad}", C_TLW)

        # ── Flecha w entre TL y AL (lado derecho, en el margen) ─────────────
        if al_sup_pts[0] is not None and abs(_as0 - _u) > 1e-10 and _usl is not None:
            x_arr = xhi + (x_tag - xhi) * 0.45
            ax.annotate("", xy=(x_arr, _usl), xytext=(x_arr, al_sup_pts[0]),
                        arrowprops=dict(arrowstyle="<->", color=C_AL, lw=1.2),
                        annotation_clip=False)
            ax.text(x_arr + 0.07, (al_sup_pts[0] + _usl) / 2,
                    f"w={w_pts[0]:.3g}", ha="left", va="center",
                    fontsize=7, color=C_AL, clip_on=False)
    # Si w varía de un punto a otro, no se muestra una única etiqueta/flecha
    # de AL ó w en el margen (sería ambigua: ¿de cuál punto?). En su lugar,
    # cada columna ya queda dibujada con su propia zona y su propia línea de
    # AL/TL±w, y el valor de w de cada punto se añade además bajo su
    # etiqueta en el eje X (ver más abajo).

    # ── Puntos de medición ───────────────────────────────────────────────────
    for i, (_, row) in enumerate(df.iterrows()):
        vm  = float(row["Valor Medido"])
        u   = float(row["U"])
        dec = row["Decisión"]
        etq = str(row["Etiqueta"])

        # Fondo de columna alternado sutil
        fc = "#f4f4f4" if i % 2 == 0 else "white"
        ax.axvspan(i - 0.4, i + 0.4, color=fc, alpha=0.35, zorder=1)

        cp = CPUNTO.get(dec, "#7f8c8d")

        ax.errorbar(i, vm, yerr=u, fmt="o",
                    color=cp, ecolor="#34495e",
                    elinewidth=2.0, capsize=7, capthick=2.0,
                    markersize=10, zorder=5,
                    markeredgecolor="white", markeredgewidth=1.0)

        # Valor numérico encima del punto
        ax.text(i, vm + u + (yhi - ylo) * 0.015,
                f"{vm:.4g}", ha="center", va="bottom",
                fontsize=7.5, color=cp, fontweight="bold",
                clip_on=False)

    # ── Eje X: etiquetas con etiqueta y decisión ─────────────────────────────
    CLABEL = {
        "Pasa":                     C_VERDE_BORDE,
        "Pasa condicionalmente":    C_NARANJA_BORDE,
        "No pasa condicionalmente": C_DURAZNO_BORDE,
        "No pasa":                  C_ROJO_BORDE,
    }
    ax.set_xticks(range(n))
    xticklabels = []
    for idx, (_, row) in enumerate(df.iterrows()):
        dec = row["Decisión"]
        etq = str(row["Etiqueta"])
        # Línea 1: etiqueta, línea 2: decisión en mayúsc abreviado
        abrev = {
            "Pasa": "PASA",
            "Pasa condicionalmente": "PASA COND.",
            "No pasa condicionalmente": "NO PASA COND.",
            "No pasa": "NO PASA",
        }.get(dec, dec.upper())
        etiqueta_txt = f"{etq}\n{abrev}"
        if not w_es_uniforme and w_pts[idx] > 0:
            # w distinto por punto: se indica explícitamente bajo cada
            # etiqueta, ya que no hay una sola flecha de margen que sirva
            # para todos los puntos.
            etiqueta_txt += f"\nw={w_pts[idx]:.3g} {unidad}"
        xticklabels.append(etiqueta_txt)

    ax.set_xticklabels(xticklabels, fontsize=8, color="#2c3e50")

    # Colorear cada etiqueta según decisión
    for tick, (_, row) in zip(ax.get_xticklabels(), df.iterrows()):
        tick.set_color(CLABEL.get(row["Decisión"], "#2c3e50"))

    # ── Leyenda — debajo del gráfico, centrada ────────────────────────────────
    if es_no_binaria:
        items_leyenda = [
            mpatches.Patch(color=C_VERDE_FONDO,   label="Conforme"),
            mpatches.Patch(color=C_NARANJA_FONDO, label="Pasa condicionalmente"),
            mpatches.Patch(color=C_DURAZNO_FONDO, label="No pasa condicionalmente"),
            mpatches.Patch(color=C_ROJO_FONDO,    label="No conforme"),
            plt.Line2D([0],[0], color=C_TL,  lw=2.0, ls="-",  label="Límite de tolerancia (TL)"),
            plt.Line2D([0],[0], color=C_AL,  lw=1.8, ls="--", label="Límite de aceptación (AL)"),
            plt.Line2D([0],[0], color=C_TLW, lw=1.4, ls=":",  label="TL ± w"),
        ]
    else:
        items_leyenda = [
            mpatches.Patch(color=C_VERDE_FONDO,   label="Conforme"),
            mpatches.Patch(color=C_NARANJA_FONDO, label="Zona de guarda"),
            mpatches.Patch(color=C_ROJO_FONDO,    label="No conforme"),
            plt.Line2D([0],[0], color=C_TL, lw=2.0, ls="-",  label="Límite de tolerancia (TL)"),
            plt.Line2D([0],[0], color=C_AL, lw=1.8, ls="--", label="Límite de aceptación (AL)"),
        ]

    ax.legend(handles=items_leyenda,
              loc="upper center",
              bbox_to_anchor=(0.5, -0.14),
              ncol=4, fontsize=8.0,
              framealpha=0.97, edgecolor="#ccc",
              bbox_transform=ax.transAxes)

    # ── Estética ──────────────────────────────────────────────────────────────
    ax.set_xlim(xlo, xhi)
    ax.set_ylim(ylo, yhi)
    ax.set_ylabel(f"Valor medido ({unidad})", fontsize=9.5, color="#444", labelpad=7)
    ax.set_title(
        f"Gráfico Comparativo de Zonas de Conformidad\n{titulo}",
        fontsize=11, fontweight="bold", color="#2c3e50", pad=10
    )
    ax.tick_params(axis="y", labelsize=8.5, colors="#555")
    ax.tick_params(axis="x", length=0, pad=6)
    for sp in ["top", "right", "bottom"]:
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color("#bbb")
    ax.grid(axis="y", color="#e0e0e0", lw=0.6, zorder=0)

    # Margen derecho para las etiquetas de referencia, inferior para la leyenda
    fig.tight_layout(rect=[0.0, 0.16, 0.78, 1.0])
    return fig
