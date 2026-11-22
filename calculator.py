import ast
import re
import math
import statistics
from collections import Counter
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


def show_steps(title: str, steps):
    with st.expander(title):
        for step in steps:
            st.write(step)


def derivative_steps(expr, derivative):
    if isinstance(expr, sp.Add):
        steps = ["Sum rule: differentiate each term, then add the results."]
        for term in expr.args:
            steps.extend(derivative_steps(term, sp.diff(term, x)))
        return steps
    elif isinstance(expr, sp.Mul) and len(expr.args) > 1:
        rule = "Product rule: differentiate one factor at a time and sum the products."
    elif isinstance(expr, sp.Pow) and expr.base.has(x):
        if expr.exp.has(x):
            rule = "Use logarithmic differentiation because both the base and exponent depend on x."
        else:
            rule = "Power rule: multiply by the exponent and reduce the exponent by one."
    elif any(arg.has(x) and arg != x for arg in expr.args):
        rule = "Chain rule: differentiate the outer function, then multiply by the inner derivative."
    elif derivative == 0:
        rule = "Constant rule: the derivative of a constant is zero."
    else:
        rule = "Apply the derivative rule for this expression."
    return [rule, f"Intermediate derivative: {sp.latex(derivative)}"]


def arithmetic_steps(expression):
    unevaluated = parse_expr(
        expression,
        local_dict=LOCAL_DICT,
        transformations=TRANSFORMATIONS,
        evaluate=False,
    )
    steps = ["Apply parentheses first, then exponents, multiplication/division, and addition/subtraction."]
    operations = []

    def collect(node):
        for child in node.args:
            collect(child)
        if isinstance(node, (sp.Add, sp.Mul, sp.Pow)) and not node.free_symbols:
            operations.append(node)

    collect(unevaluated)
    for operation in operations:
        steps.append(f"{sp.latex(operation)} = {sp.latex(sp.simplify(operation))}")
    return steps


def parse_ode_expression(text: str):
    function = sp.Function("y")
    text = re.sub(r"\by''", "__Y_SECOND_DERIVATIVE__", text)
    text = re.sub(r"\by'", "__Y_FIRST_DERIVATIVE__", text)
    text = re.sub(r"\by\b(?!\s*\()", "y(x)", text)
    text = text.replace("__Y_SECOND_DERIVATIVE__", "Derivative(y(x), (x, 2))")
    text = text.replace("__Y_FIRST_DERIVATIVE__", "Derivative(y(x), x)")
    local_dict = {**LOCAL_DICT, "y": function, "Derivative": sp.Derivative}
    return parse_expr(text, local_dict=local_dict, transformations=TRANSFORMATIONS)


def render_plot(expressions, labels, x_min=-10.0, x_max=10.0, points=None, title="Function Graph"):
    """Renders a clean Matplotlib chart in Streamlit."""
    if x_max <= x_min:
        st.warning("The plot range must have a maximum greater than its minimum.")
        return

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
    conv_match = re.match(
        r"^(?:convert\s+)?([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*([a-zA-Z/]+)\s+(?:to|in|into)\s+([a-zA-Z/]+)$",
        q_lower,
    )
    if conv_match:
        val, u1, u2 = float(conv_match.group(1)), conv_match.group(2), conv_match.group(3)
        res = convert_units(val, u1, u2)
        if res is not None:
            st.success(f"**{val} {u1} = {res:.6g} {u2}**")
            return
        st.warning("Those units are incompatible or not recognized.")
        return

    # 2. System of Equations separated by ';' or ','
    if re.search(r"[;,]", q) and "=" in q:
        parts = [p.strip() for p in re.split(r"[;,]", q) if p.strip()]
        eqs = []
        all_syms = set()
        for p in parts:
            if "=" not in p:
                eqs = []
                break
            lhs, rhs = p.split("=", 1)
            try:
                eq = sp.Eq(clean_and_parse(lhs), clean_and_parse(rhs))
                eqs.append(eq)
                all_syms.update(eq.free_symbols)
            except Exception:
                eqs = []
                break
        if not eqs:
            st.warning("Could not parse that system of equations.")
            return
        try:
            sol = sp.solve(eqs, list(all_syms), dict=True)
        except Exception:
            st.warning("Could not solve that system.")
            return
        st.subheader("System of Equations Solution")
        if not sol:
            st.warning("No solution found (parallel or inconsistent system).")
        else:
            for idx, s in enumerate(sol, 1):
                st.latex(f"\\text{{Solution {idx}: }} " + ",\\quad ".join(f"{k} = {sp.latex(v)}" for k, v in s.items()))
            show_steps(
                "Show Step-by-Step Solution",
                [
                    "Write each equation in the system and solve them simultaneously.",
                    "Substitute the solution values into the original equations to verify them.",
                ],
            )
            if len(eqs) == 2 and x in all_syms and y in all_syms:
                y_exprs, labels = [], []
                for idx, eq in enumerate(eqs, 1):
                    y_sol = sp.solve(eq, y)
                    if y_sol:
                        y_exprs.append(y_sol[0])
                        labels.append(f"Eq {idx}: y = {y_sol[0]}")
                pts = []
                for s in sol:
                    if x in s and y in s and s[x].is_real is True and s[y].is_real is True:
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

    # 4. Differential equations
    ode_text = re.sub(r"^ode\b\s*", "", cleaned, flags=re.IGNORECASE)
    if re.match(r"^ode\b", cleaned, re.IGNORECASE) or re.search(r"\by'{1,2}", cleaned):
        if "=" not in ode_text:
            st.warning("Enter an ODE as an equation, for example `ode y' = y`.")
            return
        try:
            lhs_text, rhs_text = ode_text.split("=", 1)
            eq = sp.Eq(parse_ode_expression(lhs_text), parse_ode_expression(rhs_text))
            solution = sp.dsolve(eq)
            st.subheader("Differential Equation Solution")
            st.latex(sp.latex(solution))
            show_steps(
                "Show Step-by-Step Solution",
                [
                    "Interpret y' and y'' as derivatives of y(x) with respect to x.",
                    f"Solve the differential equation {sp.latex(eq)} using SymPy's dsolve.",
                    f"General solution: {sp.latex(solution)}",
                ],
            )
        except Exception:
            st.warning("Could not solve that differential equation.")
        return

    # 5. Taylor / Maclaurin series
    series_match = re.match(
        r"^(?:series|taylor|maclaurin)\s+(.+?)(?:\s+around\s+(.+?))?(?:\s+to\s+order\s+(\d+))?$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if series_match:
        try:
            expr = clean_and_parse(series_match.group(1))
            center = clean_and_parse(series_match.group(2)) if series_match.group(2) else sp.Integer(0)
            order = int(series_match.group(3)) if series_match.group(3) else 6
            result = sp.series(expr, x, center, order)
            st.subheader("Taylor Series")
            st.latex(sp.latex(result))
            show_steps(
                "Show Step-by-Step Solution",
                [
                    f"Expand {sp.latex(expr)} around x = {sp.latex(center)} through order {order - 1}.",
                    f"Series expansion: {sp.latex(result)}",
                ],
            )
        except Exception:
            st.warning("Could not expand that expression as a series.")
        return

    # 6. Summation
    sum_match = re.match(
        r"^sum\s+(.+?)\s+from\s+(.+?)\s+to\s+(.+)$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if sum_match:
        try:
            expr = clean_and_parse(sum_match.group(1))
            index = n if n in expr.free_symbols else next(iter(expr.free_symbols), n)
            lower = clean_and_parse(sum_match.group(2))
            upper_text = re.sub(r"\b(?:infinity|inf)\b", "oo", sum_match.group(3), flags=re.IGNORECASE)
            upper = clean_and_parse(upper_text)
            result = sp.summation(expr, (index, lower, upper))
            st.subheader("Summation")
            st.latex(sp.latex(result))
            show_steps(
                "Show Step-by-Step Solution",
                [
                    f"Sum {sp.latex(expr)} over {sp.latex(index)} from {sp.latex(lower)} to {sp.latex(upper)}.",
                    f"Evaluated sum: {sp.latex(result)}",
                ],
            )
        except Exception:
            st.warning("Could not evaluate that summation.")
        return

    # 7. Partial fractions and trigonometric simplification
    for command, operation, heading in (
        ("apart", sp.apart, "Partial Fractions"),
        ("trigsimp", sp.trigsimp, "Trigonometric Simplification"),
    ):
        if re.match(rf"^{command}\b", cleaned, re.IGNORECASE):
            try:
                expr = clean_and_parse(re.sub(rf"^{command}\s*", "", cleaned, flags=re.IGNORECASE))
                result = operation(expr)
                st.subheader(heading)
                st.latex(sp.latex(expr) + " = " + sp.latex(result))
                show_steps(
                    "Show Step-by-Step Solution",
                    [f"Apply {command} to {sp.latex(expr)}.", f"Result: {sp.latex(result)}"],
                )
            except Exception:
                st.warning(f"Could not perform {command} on that expression.")
            return

    # 8. Matrix operations
    matrix_match = re.match(r"^(det|inv|eigen|rref)\s+(.+)$", cleaned, re.IGNORECASE)
    if matrix_match:
        operation, matrix_text = matrix_match.groups()
        try:
            rows = ast.literal_eval(matrix_text)
            matrix = sp.Matrix(rows)
            operation = operation.lower()
            if operation == "det":
                result = matrix.det()
                st.subheader("Matrix Determinant")
            elif operation == "inv":
                result = matrix.inv()
                st.subheader("Matrix Inverse")
            elif operation == "eigen":
                result = matrix.eigenvects()
                st.subheader("Matrix Eigenvalues and Eigenvectors")
            else:
                result = matrix.rref()
                st.subheader("Reduced Row Echelon Form")
            st.write(result)
            show_steps(
                "Show Step-by-Step Solution",
                [f"Input matrix: {sp.latex(matrix)}", f"Apply the {operation} operation to the matrix."],
            )
        except (ValueError, TypeError, SyntaxError, sp.matrices.exceptions.NonInvertibleMatrixError):
            st.warning("Could not perform that matrix operation. Check the matrix format and operation.")
        return

    # 9. Descriptive statistics
    if re.match(r"^stats\b", cleaned, re.IGNORECASE):
        try:
            values = [float(value.strip()) for value in re.sub(r"^stats\s*", "", cleaned, flags=re.IGNORECASE).split(",")]
            if not values:
                raise ValueError("At least one value is required.")
            modes = statistics.multimode(values)
            frequencies = Counter(values)
            if max(frequencies.values()) == 1:
                mode_text = "No mode"
            else:
                mode_text = ", ".join(str(value) for value in modes)
            results = {
                "Mean": statistics.mean(values),
                "Median": statistics.median(values),
                "Mode": mode_text,
                "Population variance": statistics.pvariance(values),
                "Population standard deviation": statistics.pstdev(values),
            }
            st.subheader("Statistics")
            for label, value in results.items():
                st.write(f"**{label}:** {value}")
            show_steps(
                "Show Step-by-Step Solution",
                [
                    f"Calculate the mean, median, mode, population variance, and population standard deviation for {values}.",
                    "Population variance and standard deviation use the full supplied data set.",
                ],
            )
        except (ValueError, statistics.StatisticsError):
            st.warning("Enter one or more comma-separated numbers after `stats`.")
        return

    # 10. Number theory
    if re.match(r"^prime\s+factors?\b", cleaned, re.IGNORECASE):
        try:
            parsed_value = clean_and_parse(re.sub(r"^prime\s+factors?\s*", "", cleaned, flags=re.IGNORECASE))
            if not parsed_value.is_Integer:
                raise ValueError("An integer is required.")
            value = int(parsed_value)
            result = sp.factorint(value)
            st.subheader("Prime Factorization")
            st.write(result)
            show_steps(
                "Show Step-by-Step Solution",
                [f"Factor {value} into prime powers.", f"Prime factorization: {result}"],
            )
        except (ValueError, TypeError):
            st.warning("Enter an integer to factor, for example `prime factors 360`.")
        return

    number_match = re.match(r"^(gcd|lcm)\s+(.+)$", cleaned, re.IGNORECASE)
    if number_match:
        operation, numbers_text = number_match.groups()
        try:
            parsed_numbers = [clean_and_parse(value.strip()) for value in numbers_text.split(",")]
            if any(not value.is_Integer for value in parsed_numbers):
                raise ValueError("Integers are required.")
            numbers = [int(value) for value in parsed_numbers]
            result = sp.gcd(*numbers) if operation.lower() == "gcd" else sp.lcm(*numbers)
            st.subheader(operation.upper())
            st.write(result)
            show_steps(
                "Show Step-by-Step Solution",
                [f"Apply {operation.upper()} to {numbers}.", f"Result: {result}"],
            )
        except (ValueError, TypeError):
            st.warning(f"Enter comma-separated integers after `{operation}`, for example `{operation} 12, 18`.")
        return

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
        if xmax <= xmin:
            st.warning("The plot range must have a maximum greater than its minimum.")
            return
        exprs, labels = [], []
        for f_str in funcs_raw:
            f_str = re.sub(r"^y\s*=\s*", "", f_str.strip(), flags=re.IGNORECASE)
            e = clean_and_parse(f_str)
            exprs.append(e)
            labels.append(f"y = {e}")
        render_plot(exprs, labels, xmin, xmax, title="Interactive Function Graph")
        return

    # 5. Single equation
    if "=" in cleaned:
        lhs_str, rhs_str = cleaned.split("=", 1)
        try:
            lhs, rhs = clean_and_parse(lhs_str), clean_and_parse(rhs_str)
            eq = sp.Eq(lhs, rhs)
            vars_in_eq = list(eq.free_symbols)
            preferred = [x, y, z, t, n]
            var = next((v for v in preferred if v in vars_in_eq), vars_in_eq[0] if vars_in_eq else x)
            sols = sp.solve(eq, var)
            st.subheader("Equation Solution")
            st.latex(sp.latex(eq) + r" \implies " + sp.latex(var) + " = " + sp.latex(sols))
            moved = sp.expand(lhs - rhs)
            factored = sp.factor(moved)
            with st.expander("Step-by-Step Explanation", expanded=True):
                st.write("Move all terms to the left-hand side and set the equation equal to zero.")
                st.latex(sp.latex(moved) + " = 0")
                st.write("Factor the left-hand side.")
                st.latex(sp.latex(factored) + " = 0")
                st.write("Set each factor equal to zero and solve for the variable.")
                st.latex(sp.latex(var) + " = " + sp.latex(sols))
        except Exception:
            st.warning("Could not parse that equation.")
        return

    # 6. Integral
    if re.match(r"^(?:integrate|integral|antiderivative)\b", cleaned, re.I):
        target = re.sub(r"^(?:integrate|integral|antiderivative)(?:\s+of)?\s*", "", cleaned, flags=re.I)
        try:
            expr = clean_and_parse(target)
            res = sp.integrate(expr, x)
            st.subheader("Indefinite Integral")
            st.latex(r"\int \left(" + sp.latex(expr) + r"\right)\,dx = " + sp.latex(res) + " + C")
            with st.expander("Step-by-Step Explanation", expanded=True):
                if isinstance(expr, sp.Add):
                    st.write("Use linearity to integrate each term separately.")
                elif isinstance(expr, sp.Pow) and expr.base == x:
                    st.write("Apply the power antiderivative rule: increase the exponent by one, then divide by the new exponent.")
                else:
                    st.write("Apply the corresponding standard antiderivative rule to the expression.")
                st.write("Add the constant of integration, + C.")
                st.latex(r"\frac{d}{dx}\left(" + sp.latex(res) + r"\right) = " + sp.latex(sp.diff(res, x)))
        except Exception:
            st.warning("Could not integrate that expression.")
        return

    # 7. Limit
    lim_match = re.match(
        r"^limit\s+(.+?)\s+(?:as\s+)?x\s*(?:->|→|to)\s*(.+)$",
        cleaned,
        re.I,
    )
    if lim_match:
        try:
            expr = clean_and_parse(lim_match.group(1))
            pt = clean_and_parse(lim_match.group(2).replace("infinity", "oo").replace("inf", "oo"))
            res = sp.limit(expr, x, pt)
            st.subheader("Limit Result")
            st.latex(r"\lim_{x \to " + sp.latex(pt) + r"} \left(" + sp.latex(expr) + r"\right) = " + sp.latex(res))
        except Exception:
            st.warning("Could not evaluate that limit.")
        return

    # 8. Factor
    if re.match(r"^factor\b", cleaned, re.I):
        try:
            expr = clean_and_parse(re.sub(r"^factor(?:\s+of)?\s*", "", cleaned, flags=re.I))
            st.subheader("Factored Form")
            st.latex(sp.latex(expr) + " = " + sp.latex(sp.factor(expr)))
        except Exception:
            st.warning("Could not factor that expression.")
        return

    # 9. Expand
    if re.match(r"^expand\b", cleaned, re.I):
        try:
            expr = clean_and_parse(re.sub(r"^expand(?:\s+of)?\s*", "", cleaned, flags=re.I))
            st.subheader("Expanded Form")
            st.latex(sp.latex(expr) + " = " + sp.latex(sp.expand(expr)))
        except Exception:
            st.warning("Could not expand that expression.")
        return

    # 10. Derivative
    deriv_match = re.match(r"^(?:derivative|differentiate|d/dx)\s+(?:of\s+)?(.+)$", cleaned, flags=re.IGNORECASE)
    if deriv_match:
        try:
            expr = clean_and_parse(deriv_match.group(1))
            d1 = sp.diff(expr, x)
            d2 = sp.diff(expr, x, 2)
            st.subheader("Derivative Results")
            st.latex(r"\frac{d}{dx}\left(" + sp.latex(expr) + r"\right) = " + sp.latex(d1))
            st.latex(r"\frac{d^2}{dx^2}\left(" + sp.latex(expr) + r"\right) = " + sp.latex(d2))
            with st.expander("Step-by-Step Explanation", expanded=True):
                for step in derivative_steps(expr, d1):
                    st.write(step)
        except Exception:
            st.warning("Could not differentiate that expression.")
        return

    # 11. General Evaluation / Fallback
    try:
        arith_query = re.sub(r"(?<=[0-9)])\s*[xX×]\s*(?=[0-9(])", "*", cleaned)
        expr = clean_and_parse(arith_query)
        simplified = sp.simplify(expr)
        st.subheader("Result")
        st.latex(sp.latex(expr) + " = " + sp.latex(simplified))
        if not simplified.free_symbols:
            with st.expander("Step-by-Step Explanation", expanded=True):
                for step in arithmetic_steps(arith_query):
                    st.write(step)
        if not simplified.free_symbols:
            try:
                decimal_value = complex(simplified.evalf())
                st.write(f"**Decimal:** `{decimal_value:g}`")
            except (TypeError, ValueError, OverflowError):
                st.write(f"**Exact value:** `{sp.latex(simplified)}`")
    except Exception:
        st.warning("Could not parse that expression. Try `(5 + 6) * 5` or `derivative of x^3`.")

def set_example_query(query: str):
    st.session_state["query_input"] = query


st.sidebar.title("Math Reference Guide")
reference_categories = {
    "Arithmetic & Units": [
        ("Arithmetic", "(5 + 6) * 5"),
        ("Unit conversion", "convert 100 km to miles"),
    ],
    "Algebra & Equations": [
        ("Solve an equation", "3(x + 2) = 5x - 4"),
        ("Systems of equations", "x + y = 10, x - y = 2"),
        ("Factor", "factor x^2 - 9"),
        ("Expand", "expand (x + 2)^2"),
    ],
    "Calculus": [
        ("Derivative", "derivative of x^3 + 2x"),
        ("Integral", "integrate x^2"),
        ("Limit", "limit sin(x)/x as x -> 0"),
        ("ODE", "ode y' = y"),
    ],
    "Series & Sums": [
        ("Taylor series", "series sin(x)"),
        ("Summation", "sum 1/n^2 from 1 to oo"),
    ],
    "Expression Tools": [
        ("Partial fractions", "apart (x^2 + 1)/(x*(x + 1))"),
        ("Trig simplification", "trigsimp sin(x)^2 + cos(x)^2"),
        ("Graph", "graph sin(x) from -10 to 10"),
    ],
    "Matrices, Statistics & Number Theory": [
        ("Determinant", "det [[1,2],[3,4]]"),
        ("Inverse", "inv [[1,2],[3,4]]"),
        ("Eigenvalues and vectors", "eigen [[1,2],[3,4]]"),
        ("RREF", "rref [[1,2,3],[4,5,6]]"),
        ("Statistics", "stats 10, 20, 30, 40"),
        ("Prime factors", "prime factors 360"),
        ("GCD", "gcd 48, 180"),
        ("LCM", "lcm 12, 15"),
    ],
}
for category, examples in reference_categories.items():
    with st.sidebar.expander(category):
        for label, query in examples:
            st.button(
                label,
                key=f"example_{category}_{label}",
                on_click=set_example_query,
                args=(query,),
            )

st.title("OmniMath Calculator")
user_input = st.text_input(
    "Enter a math expression or query (e.g., derivative of x^3):",
    key="query_input",
)

if user_input:
    handle_universal_query(user_input)
