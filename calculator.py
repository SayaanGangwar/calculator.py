import re
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

# ---------------------------------------------------------------------------
# Page Setup & Styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Python Algebra & Graphing Calculator",
    page_icon="🧮",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        height: 2.8em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# SymPy Setup
# ---------------------------------------------------------------------------
TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

x, y, z = sp.symbols("x y z")
LOCAL_DICT = {
    "x": x,
    "y": y,
    "z": z,
    "sqrt": sp.sqrt,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "log": sp.log,
    "ln": sp.log,
    "pi": sp.pi,
    "e": sp.E,
}


def clean_and_parse(expr_str: str):
    """Parses string into a SymPy expression, preserving exact fractions."""
    expr_str = expr_str.strip()
    expr_str = expr_str.replace("×", "*").replace("÷", "/").replace("−", "-")
    expr_str = re.sub(r"√\(([^)]+)\)", r"sqrt(\1)", expr_str)
    expr_str = re.sub(r"√(\d+|[a-zA-Z])", r"sqrt(\1)", expr_str)
    expr_str = re.sub(
        r"(?<![.\w])(\d+)\s*/\s*(\d+)(?![.\w])", r"Rational(\1, \2)", expr_str
    )
    return parse_expr(expr_str, local_dict=LOCAL_DICT, transformations=TRANSFORMATIONS)


def strip_question_prefix(text: str) -> str:
    """Removes conversational prefixes like 'what is' or 'solve'."""
    t = text.strip()
    if t.endswith("?"):
        t = t[:-1].strip()
    patterns = [
        r"^(what is|what's|whats|calculate|compute|evaluate|find|simplify|answer)\s+",
        r"^(solve for [xyz]|solve)\s+",
        r"^(the value of)\s+",
    ]
    for pat in patterns:
        t = re.sub(pat, "", t, flags=re.IGNORECASE).strip()
    return t


def create_function_plot(exprs, labels, x_min=-10.0, x_max=10.0, points=None, title="Graph"):
    """Generates a Matplotlib figure for one or more expressions in x."""
    fig, ax = plt.subplots(figsize=(7, 4.8))
    x_vals = np.linspace(x_min, x_max, 600)
    colors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea"]

    for idx, (expr, label) in enumerate(zip(exprs, labels)):
        color = colors[idx % len(colors)]
        f_num = sp.lambdify(x, expr, modules=["numpy"])
        with np.errstate(all="ignore"):
            y_vals = f_num(x_vals)
        if np.ndim(y_vals) == 0:
            y_vals = np.full_like(x_vals, float(y_vals))
        y_vals = np.array(y_vals, dtype=complex)
        y_real = np.where(np.abs(y_vals.imag) < 1e-7, y_vals.real, np.nan)
        y_real = np.where(np.abs(y_real) > 1e5, np.nan, y_real)
        ax.plot(x_vals, y_real, label=label, color=color, linewidth=2.2)

    if points:
        for px, py, plabel in points:
            ax.scatter([px], [py], color="#f59e0b", edgecolor="black", zorder=5, s=75)
            ax.annotate(
                plabel,
                (px, py),
                textcoords="offset points",
                xytext=(8, 8),
                fontsize=9,
                fontweight="bold",
            )

    ax.axhline(0, color="#334155", linewidth=1)
    ax.axvline(0, color="#334155", linewidth=1)
    ax.grid(True, linestyle="--", alpha=0.45)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend()
    fig.tight_layout()
    return fig


def handle_query(raw_query: str, x_min: float, x_max: float):
    """Interprets natural language, equations, systems, quadratics, or expressions."""
    q = raw_query.strip()
    q_lower = q.lower()
    output_lines = []
    fig = None

    # 1. System of equations separated by ';' or 'and'
    if ";" in q or (" and " in q_lower and q.count("=") == 2):
        parts = [p.strip() for p in (q.split(";") if ";" in q else re.split(r"\s+and\s+", q, flags=re.I)) if p.strip()]
        eqs = []
        for p in parts:
            p_clean = strip_question_prefix(p)
            if "=" in p_clean:
                lhs, rhs = p_clean.split("=", 1)
                eqs.append(sp.Eq(clean_and_parse(lhs), clean_and_parse(rhs)))
            else:
                eqs.append(sp.Eq(clean_and_parse(p_clean), 0))

        syms = sorted(list(set().union(*(eq.free_symbols for eq in eqs))), key=str)
        sol = sp.solve(eqs, syms, dict=True)
        output_lines.append("**System of Equations:**")
        for eq in eqs:
            output_lines.append(f"- `{sp.pretty(eq.lhs)} = {sp.pretty(eq.rhs)}`")

        if not sol:
            output_lines.append("\n**Result:** No unique solution found (parallel or dependent lines).")
        else:
            output_lines.append("\n**Solutions:**")
            for s in sol:
                formatted = ", ".join(f"**{k} = {v}** (≈ {float(v.evalf()):.4g})" for k, v in s.items())
                output_lines.append(f"- {formatted}")

            # Plot if 2 variables x and y
            if set(syms) <= {x, y} and len(eqs) == 2:
                y_exprs, labels = [], []
                for idx, eq in enumerate(eqs, 1):
                    y_sol = sp.solve(eq, y)
                    if y_sol:
                        y_exprs.append(y_sol[0])
                        labels.append(f"Eq {idx}: y = {y_sol[0]}")
                pts = []
                if x in sol[0] and y in sol[0] and sol[0][x].is_real and sol[0][y].is_real:
                    ix, iy = float(sol[0][x].evalf()), float(sol[0][y].evalf())
                    pts.append((ix, iy, f"({ix:.3g}, {iy:.3g})"))
                if y_exprs:
                    fig = create_function_plot(y_exprs, labels, x_min, x_max, pts, "System Intersection")
        return "\n".join(output_lines), fig

    # 2. Graphing command
    if q_lower.startswith(("graph ", "plot ")):
        body = re.sub(r"^(graph|plot)\s+", "", q, flags=re.I).strip()
        body = re.sub(r"^y\s*=\s*", "", body, flags=re.I)
        expr = clean_and_parse(body)
        output_lines.append(f"**Graphing:** `y = {expr}`")
        fig = create_function_plot([expr], [f"y = {expr}"], x_min, x_max, title=f"y = {expr}")
        return "\n".join(output_lines), fig

    # 3. Quadratic analyzer command
    if q_lower.startswith("quadratic "):
        body = re.sub(r"^quadratic\s+", "", q, flags=re.I).strip()
        if "=" in body:
            lhs, rhs = body.split("=", 1)
            expr = sp.expand(clean_and_parse(lhs) - clean_and_parse(rhs))
        else:
            expr = sp.expand(clean_and_parse(body))
        poly = sp.Poly(expr, x)
        if poly.degree() != 2:
            raise ValueError("Expression is not degree 2 (quadratic).")
        a, b, c = poly.all_coeffs()
        disc = sp.simplify(b**2 - 4 * a * c)
        vx = sp.simplify(-b / (2 * a))
        vy = sp.simplify(expr.subs(x, vx))
        roots = sp.solve(expr, x)

        output_lines.extend([
            f"**Quadratic Function:** `y = {expr}`",
            f"- **Discriminant:** `{disc}`",
            f"- **Vertex:** `({vx}, {vy})`",
            f"- **Roots:** `{roots}`",
        ])
        pts = [(float(vx.evalf()), float(vy.evalf()), f"Vertex ({vx}, {vy})")]
        for r in roots:
            if r.is_real:
                rx = float(r.evalf())
                pts.append((rx, 0.0, f"Root ({r}, 0)"))
        fig = create_function_plot(
            [expr],
            [f"y = {expr}"],
            float(vx.evalf()) - 10,
            float(vx.evalf()) + 10,
            pts,
            f"Quadratic: y = {expr}",
        )
        return "\n".join(output_lines), fig

    # 4. Factor / Expand / Derivative / Integral
    if q_lower.startswith("factor "):
        expr = clean_and_parse(re.sub(r"^factor\s+", "", q, flags=re.I))
        output_lines.append(f"**Factored:** `{sp.factor(expr)}`")
        return "\n".join(output_lines), None

    if q_lower.startswith("expand "):
        expr = clean_and_parse(re.sub(r"^expand\s+", "", q, flags=re.I))
        output_lines.append(f"**Expanded:** `{sp.expand(expr)}`")
        return "\n".join(output_lines), None

    if q_lower.startswith(("derivative of ", "differentiate ", "diff ")):
        body = re.sub(r"^(derivative of|differentiate|diff)\s+", "", q, flags=re.I)
        expr = clean_and_parse(body)
        deriv = sp.diff(expr, x)
        output_lines.append(f"**Derivative with respect to x:** `{deriv}`")
        fig = create_function_plot([expr, deriv], [f"f(x) = {expr}", f"f'(x) = {deriv}"], x_min, x_max, title="Function & Derivative")
        return "\n".join(output_lines), fig

    # 5. Equation solving ('=')
    cleaned = strip_question_prefix(q)
    if "=" in cleaned:
        lhs_s, rhs_s = cleaned.split("=", 1)
        lhs = clean_and_parse(lhs_s)
        rhs = clean_and_parse(rhs_s)
        eq = sp.Eq(lhs, rhs)
        syms = sorted(list(eq.free_symbols), key=str)
        target = syms[0] if syms else x
        sols = sp.solve(eq, target)
        output_lines.append(f"**Equation:** `{lhs} = {rhs}`")
        if not sols:
            output_lines.append("**Result:** No solutions found.")
        else:
            output_lines.append(f"**Solutions for `{target}`:**")
            for idx, s in enumerate(sols, 1):
                approx = f" (≈ {complex(s.evalf()):.4g})" if s.free_symbols == set() else ""
                output_lines.append(f"- `{target}_{idx} = {s}`{approx}")
        if target == x and len(syms) == 1:
            diff_expr = sp.simplify(lhs - rhs)
            pts = [(float(s.evalf()), 0.0, f"x={s}") for s in sols if s.is_real]
            fig = create_function_plot([diff_expr], [f"y = {diff_expr}"], x_min, x_max, pts, "Zeros of Equation")
        return "\n".join(output_lines), fig

    # 6. General expression evaluation & simplification
    expr = clean_and_parse(cleaned)
    simplified = sp.simplify(expr)
    expanded = sp.expand(simplified)
    output_lines.append(f"**Input:** `{expr}`")
    output_lines.append(f"**Exact Result:** `{expanded}`")
    if not expanded.free_symbols:
        output_lines.append(f"**Decimal Approximation:** `{expanded.evalf(12)}`")
    elif expanded.free_symbols == {x}:
        fig = create_function_plot([expanded], [f"y = {expanded}"], x_min, x_max, title=f"y = {expanded}")
    return "\n".join(output_lines), fig


# ---------------------------------------------------------------------------
# Session State for Keypad & History
# ---------------------------------------------------------------------------
if "query_input" not in st.session_state:
    st.session_state.query_input = "x^2 - 5x + 6 = 0"
if "history" not in st.session_state:
    st.session_state.history = []


def append_token(tok: str):
    st.session_state.query_input += tok


def clear_input():
    st.session_state.query_input = ""


def backspace_input():
    st.session_state.query_input = st.session_state.query_input[:-1]


# ---------------------------------------------------------------------------
# UI Layout
# ---------------------------------------------------------------------------
st.title("🧮 Algebra, Quadratic & Graphing Calculator")
st.caption("Works directly in your browser inside GitHub Codespaces or locally.")

with st.sidebar:
    st.header("⚙️ Graph Range")
    x_min = st.number_input("Min x", value=-10.0, step=1.0)
    x_max = st.number_input("Max x", value=10.0, step=1.0)

    st.divider()
    st.header("💡 Try Example Queries")
    examples = [
        "what is (3/4 + 2/5) * sqrt(25)",
        "3(x + 2) = 5x - 4",
        "quadratic x^2 - 6x + 8",
        "2x + y = 10; x - y = 2",
        "factor x^2 - 9",
        "derivative of x^3 - 3x",
        "graph sin(x)",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}"):
            st.session_state.query_input = ex
            st.rerun()

col_left, col_right = st.columns([1.15, 1.0], gap="large")

with col_left:
    st.subheader("1. Enter Math, Algebra, or Question")
    query = st.text_input(
        "Type an expression, equation, system (;), or question:",
        key="query_input",
        placeholder="e.g., x^2 - 4 = 0, sqrt(50), 2x+y=7; x-y=2",
    )

    # Keypad Grid
    keypad_rows = [
        ["7", "8", "9", "/", "sqrt(", "^"],
        ["4", "5", "6", "*", "(", ")"],
        ["1", "2", "3", "-", "x", "y"],
        ["0", ".", "=", "+", ";", "pi"],
    ]
    for r_idx, row in enumerate(keypad_rows):
        cols = st.columns(len(row))
        for c_idx, label in enumerate(row):
            cols[c_idx].button(
                label,
                key=f"btn_{r_idx}_{c_idx}",
                on_click=append_token,
                args=(label,),
            )

    action_cols = st.columns(3)
    action_cols[0].button("⌫ Backspace", on_click=backspace_input)
    action_cols[1].button("🗑️ Clear", on_click=clear_input)
    solve_clicked = action_cols[2].button("🚀 Solve / Graph", type="primary")

    st.divider()
    st.subheader("2. Answer")
    if solve_clicked or query.strip():
        if query.strip():
            try:
                answer_md, chart_fig = handle_query(query, x_min, x_max)
                st.success("Calculated successfully")
                st.markdown(answer_md)
                if solve_clicked:
                    st.session_state.history.insert(0, (query, answer_md))
            except Exception as exc:
                chart_fig = None
                st.error(f"Could not parse input: {exc}")
        else:
            chart_fig = None
            st.info("Enter an expression or click an example in the sidebar.")
    else:
        chart_fig = None

with col_right:
    st.subheader("3. Interactive Graph")
    if chart_fig is not None:
        st.pyplot(chart_fig)
        plt.close(chart_fig)
    else:
        st.info("Enter an equation in `x`, a quadratic, a system of 2 equations, or `graph ...` to see its plot here.")

    if st.session_state.history:
        st.divider()
        st.subheader("🕒 Recent Calculations")
        for past_q, past_a in st.session_state.history[:5]:
            with st.expander(past_q):
                st.markdown(past_a)