import re
import math
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)

# ==============================================================================
# PAGE CONFIG & SYMBOLIC SETUP
# ==============================================================================
st.set_page_config(
    page_title="OmniMath — Universal Algebra & Graphing Calculator",
    page_icon="🧮",
    layout="wide",
)

TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

x, y, z, t, n = sp.symbols("x y z t n")

LOCAL_DICT = {
    "x": x, "y": y, "z": z, "t": t, "n": n,
    "sqrt": sp.sqrt, "cbrt": sp.cbrt, "abs": sp.Abs,
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "log": sp.log, "ln": sp.log, "exp": sp.exp,
    "pi": sp.pi, "e": sp.E, "i": sp.I, "I": sp.I,
    "oo": sp.oo, "inf": sp.oo,
    "factorial": sp.factorial, "gcd": sp.gcd, "lcm": sp.lcm,
    "binomial": sp.binomial,
}


def clean_and_parse(expr_str: str):
    """Parses user string into an exact SymPy expression."""
    expr_str = expr_str.strip()
    # Convert standalone integer fractions like 1/3 -> Rational(1, 3)
    expr_str = re.sub(
        r"(?<![.\w])(\d+)\s*/\s*(\d+)(?![.\w])",
        r"Rational(\1, \2)",
        expr_str,
    )
    return parse_expr(expr_str, local_dict=LOCAL_DICT, transformations=TRANSFORMATIONS)


def render_plot(expressions, labels, x_min=-10.0, x_max=10.0, points=None, title="Function Graph"):
    """Renders a clean Matplotlib chart in Streamlit."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x_vals = np.linspace(x_min, x_max, 600)

    colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e"]
    for idx, (expr, label) in enumerate(zip(expressions, labels)):
        try:
            f_num = sp.lambdify(x, expr, modules=["numpy"])
            y_vals = f_num(x_vals)
            if np.ndim(y_vals) == 0:
                y_vals = np.full_like(x_vals, float(y_vals))
            y_vals = np.array(y_vals, dtype=float)
            y_vals[np.abs(y_vals) > 1e5] = np.nan
            ax.plot(x_vals, y_vals, label=label, color=colors[idx % len(colors)], linewidth=2.2)
        except Exception:
            pass

    if points:
        for px, py, plabel in points:
            ax.scatter([px], [py], color="black", zorder=5, s=60)
            ax.annotate(
                plabel,
                (px, py),
                textcoords="offset points",
                xytext=(8, 8),
                fontsize=9,
                fontweight="bold",
            )

    ax.axhline(0, color="black", linewidth=1)
    ax.axvline(0, color="black", linewidth=1)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.set_title(title)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    if labels:
        ax.legend()
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


# ==============================================================================
# UNIT CONVERSION DATABASE
# ==============================================================================
UNIT_FACTORS = {
    # Length (to meters)
    "m": ("length", 1.0), "meter": ("length", 1.0), "meters": ("length", 1.0),
    "km": ("length", 1000.0), "kilometer": ("length", 1000.0), "kilometers": ("length", 1000.0),
    "cm": ("length", 0.01), "centimeter": ("length", 0.01), "centimeters": ("length", 0.01),
    "mm": ("length", 0.001), "millimeter": ("length", 0.001), "millimeters": ("length", 0.001),
    "mi": ("length", 1609.344), "mile": ("length", 1609.344), "miles": ("length", 1609.344),
    "yd": ("length", 0.9144), "yard": ("length", 0.9144), "yards": ("length", 0.9144),
    "ft": ("length", 0.3048), "foot": ("length", 0.3048), "feet": ("length", 0.3048),
    "in": ("length", 0.0254), "inch": ("length", 0.0254), "inches": ("length", 0.0254),
    # Mass (to kg)
    "kg": ("mass", 1.0), "kilogram": ("mass", 1.0), "kilograms": ("mass", 1.0),
    "g": ("mass", 0.001), "gram": ("mass", 0.001), "grams": ("mass", 0.001),
    "mg": ("mass", 1e-6), "milligram": ("mass", 1e-6), "milligrams": ("mass", 1e-6),
    "lb": ("mass", 0.45359237), "lbs": ("mass", 0.45359237), "pound": ("mass", 0.45359237), "pounds": ("mass", 0.45359237),
    "oz": ("mass", 0.0283495231), "ounce": ("mass", 0.0283495231), "ounces": ("mass", 0.0283495231),
    # Time (to seconds)
    "s": ("time", 1.0), "sec": ("time", 1.0), "second": ("time", 1.0), "seconds": ("time", 1.0),
    "min": ("time", 60.0), "minute": ("time", 60.0), "minutes": ("time", 60.0),
    "hr": ("time", 3600.0), "hour": ("time", 3600.0), "hours": ("time", 3600.0),
    "day": ("time", 86400.0), "days": ("time", 86400.0),
    # Speed (to m/s)
    "m/s": ("speed", 1.0),
    "km/h": ("speed", 1 / 3.6), "kph": ("speed", 1 / 3.6),
    "mph": ("speed", 0.44704),
    # Angles (to radians)
    "rad": ("angle", 1.0), "radian": ("angle", 1.0), "radians": ("angle", 1.0),
    "deg": ("angle", math.pi / 180.0), "degree": ("angle", math.pi / 180.0), "degrees": ("angle", math.pi / 180.0),
}


def convert_units(val: float, u_from: str, u_to: str):
    u_from, u_to = u_from.lower(), u_to.lower()
    # Temperature special case
    temp_aliases = {"c": "c", "celsius": "c", "f": "f", "fahrenheit": "f", "k": "k", "kelvin": "k"}
    if u_from in temp_aliases and u_to in temp_aliases:
        f1, f2 = temp_aliases[u_from], temp_aliases[u_to]
        c_val = val if f1 == "c" else ((val - 32) * 5 / 9 if f1 == "f" else val - 273.15)
        res = c_val if f2 == "c" else (c_val * 9 / 5 + 32 if f2 == "f" else c_val + 273.15)
        return res

    if u_from in UNIT_FACTORS and u_to in UNIT_FACTORS:
        cat1, fac1 = UNIT_FACTORS[u_from]
        cat2, fac2 = UNIT_FACTORS[u_to]
        if cat1 == cat2:
            return val * fac1 / fac2
    return None


# ==============================================================================
# NATURAL LANGUAGE / UNIVERSAL MATH ENGINE
# ==============================================================================
def handle_universal_query(raw_query: str):
    q = raw_query.strip()
    if not q:
        return

    q_lower = q.lower()

    # 1. Unit Conversion: "convert 100 km to miles"
    conv_match = re.match(r"^(?:convert\s+)?([-+]?\d*\.?\d+)\s*([a-zA-Z/]+)\s+(?:to|in|into)\s+([a-zA-Z/]+)$", q_lower)
    if conv_match:
        val, u1, u2 = float(conv_match.group(1)), conv_match.group(2), conv_match.group(3)
        res = convert_units(val, u1, u2)
        if res is not None:
            st.success(f"**{val} {u1} = {res:.6g} {u2}**")
            return

    # 2. System of Equations separated by ';' or ',' (when '=' is present in both)
    if ";" in q and "=" in q:
        parts = [p.strip() for p in q.split(";") if p.strip()]
        eqs = []
        all_syms = set()
        for p in parts:
            lhs, rhs = p.split("=", 1)
            eq = sp.Eq(clean_and_parse(lhs), clean_and_parse(rhs))
            eqs.append(eq)
            all_syms.update(eq.free_symbols)
        sol = sp.solve(eqs, list(all_syms), dict=True)
        st.subheader("System of Equations Solution")
        if not sol:
            st.warning("No solution found (parallel or inconsistent system).")
        else:
            for idx, s in enumerate(sol, 1):
                st.latex(f"\\text{{Solution {idx}: }} " + ",\\quad ".join(f"{k} = {sp.latex(v)}" for k, v in s.items()))
            # Plot if 2 equations in x and y
            if len(eqs) == 2 and x in all_syms and y in all_syms:
                y_exprs, labels = [], []
                for idx, eq in enumerate(eqs, 1):
                    y_sol = sp.solve(eq, y)
                    if y_sol:
                        y_exprs.append(y_sol[0])
                        labels.append(f"Eq {idx}: y = {y_sol[0]}")
                pts = []
                for s in sol:
                    if x in s and y in s and s[x].is_real and s[y].is_real:
                        px, py = float(s[x].evalf()), float(s[y].evalf())
                        pts.append((px, py, f"({px:.3g}, {py:.3g})"))
                x_center = pts[0][0] if pts else 0.0
                render_plot(y_exprs, labels, x_center - 10, x_center + 10, pts, "System Intersection")
        
        return 
    # 3. Strip conversational prefixes
    cleaned = re.sub(
        r"^(what is|calculate|compute|solve|evaluate|find|simplify)\s+",
        "",
        q,
        flags=re.IGNORECASE,
    ).strip().rstrip("?")

    # 4. Graph command: "graph sin(x) from -10 to 10"
    graph_match = re.match(
        r"^(?:graph|plot)\s+(.+?)(?:\s+from\s+([-+]?\d*\.?\d+)\s+to\s+([-+]?\d*\.?\d+))?$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if graph_match:
        funcs_raw = graph_match.group(1).split(",")
        xmin = float(graph_match.group(2)) if graph_match.group(2) else -10.0
        xmax = float(graph_match.group(3)) if graph_match.group(3) else 10.0
        exprs, labels = [], []
        for f_str in funcs_raw:
            f_str = re.sub(r"^y\s*=\s*", "", f_str.strip(), flags=re.IGNORECASE)
            e = clean_and_parse(f_str)
            exprs.append(e)
            labels.append(f"y = {e}")
        render_plot(exprs, labels, xmin, xmax, title="Interactive Function Graph")
        return
        if "=" in cleaned:
        lhs_str, rhs_str = cleaned.split("=", 1)
        lhs, rhs = clean_and_parse(lhs_str), clean_and_parse(rhs_str)
        eq = sp.Eq(lhs, rhs)
        vars_in_eq = list(eq.free_symbols) or [x]
        sols = sp.solve(eq, vars_in_eq[0])
        st.subheader("Equation Solution")
        st.latex(sp.latex(eq) + r" \implies " + sp.latex(vars_in_eq[0]) + " = " + sp.latex(sols))
        return

if re.match(r"^(?:integrate|integral|antiderivative)\b", cleaned, re.I):
        target = re.sub(r"^(?:integrate|integral|antiderivative)(?:\s+of)?\s*", "", cleaned, flags=re.I)
        expr = clean_and_parse(target)
        res = sp.integrate(expr, x)
        st.subheader("Indefinite Integral")
        st.latex(r"\int \left(" + sp.latex(expr) + r"\right)\,dx = " + sp.latex(res) + " + C")
        return

lim_match = re.match(r"^limit\s+(.+?)\s+(?:as\s+)?x\s*(?:->|→|to)\s*(.+)$", cleaned, re.I)
if lim_match:
        expr = clean_and_parse(lim_match.group(1))
        pt = clean_and_parse(lim_match.group(2).replace("infinity", "oo").replace("inf", "oo"))
        res = sp.limit(expr, x, pt)
        st.subheader("Limit Result")
        st.latex(r"\lim_{x \to " + sp.latex(pt) + r"} \left(" + sp.latex(expr) + r"\right) = " + sp.latex(res))
        return

if re.match(r"^factor\b", cleaned, re.I):
        expr = clean_and_parse(re.sub(r"^factor(?:\s+of)?\s*", "", cleaned, flags=re.I))
        st.subheader("Factored Form")
        st.latex(sp.latex(expr) + " = " + sp.latex(sp.factor(expr)))
        return

if re.match(r"^expand\b", cleaned, re.I):
        expr = clean_and_parse(re.sub(r"^expand(?:\s+of)?\s*", "", cleaned, flags=re.I))
        st.subheader("Expanded Form")
        st.latex(sp.latex(expr) + " = " + sp.latex(sp.expand(expr)))
        return

    # 5. Calculus: Derivative
    deriv_match = re.match(r"^(?:derivative|differentiate|d/dx)\s+(?:of\s+)?(.+)$", cleaned, flags=re.IGNORECASE)
    if deriv_match:
        expr = clean_and_parse(deriv_match.group(1))
        d1 = sp.diff(expr, x)
        d2 = sp.diff(expr, x, 2)
        st.subheader("Derivative Results")
        st.latex(r"\frac{d}{dx}\left(" + sp.latex(expr) + r"\right) = " + sp.latex(d1))
        st.latex(r"\frac{d^2}{dx^2}\left(" + sp.latex(expr) + r"\right) = " + sp.latex(d2))
        return

    # 6. General Evaluation / Fallback
    try:
        arith_query = re.sub(r'(?<=[0-9\)])\s*[xX×]\s*(?=[0-9\(])', '*', cleaned)
        expr = clean_and_parse(arith_query)
        simplified = sp.simplify(expr)
        st.subheader("Result")
        st.latex(sp.latex(expr) + " = " + sp.latex(simplified))
        if not simplified.free_symbols:
            st.write(f"**Decimal:** `{float(simplified.evalf()):g}`")
    except Exception:
        st.warning("Could not parse that expression. Try `(5 + 6) * 5` or `derivative of x^3`.")

st.title ("OmniMath Calculator")
user_input = st.text_input("Enter a math expression or query (e.g., the derivative of x^3:")

if user_input:
    handle_universal_query(user_input)
