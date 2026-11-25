import ast
import inspect
import json
import math
import os
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
import sympy as sp
import pytesseract
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from PIL import Image, UnidentifiedImageError
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


def clean_and_parse(expr_str: str, local_dict=None):
    """Parses user string into an exact SymPy expression."""
    expr_str = expr_str.strip()
    # Convert standalone integer fractions like 1/3 -> Rational(1, 3)
    expr_str = re.sub(
        r"(?<![.\w^])(?<!\*\*)(\d+)\s*/\s*(\d+)(?![.\w])",
        r"Rational(\1, \2)",
        expr_str,
    )
    parse_locals = {**LOCAL_DICT, **(local_dict or {})}
    return parse_expr(
        expr_str, local_dict=parse_locals, transformations=TRANSFORMATIONS
    )


def show_steps(title: str, steps):
    record_solution_steps(steps)
    with st.expander(title):
        for step in steps:
            st.write(step)


def record_solution_steps(steps):
    capture = st.session_state.get("_solution_capture")
    if capture is not None:
        capture["steps"].extend(str(step) for step in steps)


def record_solution_answer(answer):
    capture = st.session_state.get("_solution_capture")
    if capture is not None:
        capture["answer"] = str(answer)


def solution_report_text(report):
    lines = [
        "OmniMath Solution Report",
        f"Query: {report['query']}",
        "",
        "Final answer:",
        report["answer"],
        "",
        "Step-by-step breakdown:",
    ]
    if report["steps"]:
        lines.extend(
            f"{index}. {step}" for index, step in enumerate(report["steps"], 1)
        )
    else:
        lines.append("No step-by-step explanation is available for this result.")
    return "\n".join(lines)


def solution_report_markdown(report):
    answer = report["answer"]
    if "\n" in answer or (
        re.search(r"[A-Za-z]", answer)
        and not re.search(r"\\[A-Za-z]+", answer)
        and re.search(r"[A-Za-z]{3,}", answer)
    ):
        formatted_answer = f"```text\n{answer}\n```"
    else:
        formatted_answer = f"$$\n{answer}\n$$"
    lines = [
        "# OmniMath Solution Report",
        f"**Query:** {report['query']}",
        "",
        "## Final answer",
        "",
        formatted_answer,
        "",
        "## Step-by-step breakdown",
    ]
    if report["steps"]:
        lines.extend(
            f"{index}. {step}" for index, step in enumerate(report["steps"], 1)
        )
    else:
        lines.append("No step-by-step explanation is available for this result.")
    return "\n".join(lines)


def evaluate_notebook(source: str):
    """Evaluate scratchpad lines in order, preserving earlier assignments."""
    variables = {}
    results = []
    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        assignment = re.fullmatch(r"([A-Za-z_]\w*)\s*=\s*(.+)", line)
        try:
            if assignment:
                name, expression_text = assignment.groups()
                expression = clean_and_parse(expression_text, variables)
                variables[name] = expression
                result_text = f"{name} = {sp.latex(expression)}"
            else:
                expression = clean_and_parse(line, variables)
                result_text = sp.latex(expression)
            results.append(
                {"line_number": line_number, "input": line, "result": result_text}
            )
        except (SyntaxError, TypeError, ValueError, NameError, ZeroDivisionError) as exc:
            results.append(
                {
                    "line_number": line_number,
                    "input": line,
                    "error": str(exc) or "Could not parse this line.",
                }
            )
    return results


def _split_top_level_commas(text: str):
    parts = []
    start = 0
    depth = 0
    for index, character in enumerate(text):
        if character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    parts.append(text[start:].strip())
    return [part for part in parts if part]


def _parse_calculus_call(text: str):
    call = re.fullmatch(r"(diff|differentiate|derivative|integrate|integral|limit)\s*\((.*)\)", text, re.I)
    if not call:
        return None

    operation = call.group(1).lower()
    arguments = _split_top_level_commas(call.group(2))
    if not arguments:
        raise ValueError("A calculus operation needs an expression.")
    source = clean_and_parse(arguments[0])
    variable = x
    if len(arguments) > 1 and operation != "limit":
        variable = clean_and_parse(arguments[1])
        if not isinstance(variable, sp.Symbol):
            raise ValueError("The differentiation/integration variable must be a symbol.")

    if operation in {"diff", "differentiate", "derivative"}:
        return sp.diff(source, variable), "derivative", source
    if operation in {"integrate", "integral"}:
        return sp.integrate(source, variable), "integral", source
    if len(arguments) != 3:
        raise ValueError("Use limit(expression, variable, point).")
    variable = clean_and_parse(arguments[1])
    point = clean_and_parse(arguments[2])
    if not isinstance(variable, sp.Symbol):
        raise ValueError("The limit variable must be a symbol.")
    return sp.limit(source, variable, point), "limit", source


def parse_homework_expression(text: str):
    """Return the canonical result from the same SymPy operations as the solver."""
    text = re.sub(
        r"^(?:what is|calculate|compute|solve|evaluate|find|simplify)\s+",
        "",
        text.strip().rstrip("?"),
        flags=re.IGNORECASE,
    )
    call_result = _parse_calculus_call(text)
    if call_result:
        return call_result

    integration = re.match(
        r"^(?:integrate|integral|antiderivative)(?:\s+of)?\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if integration:
        source = clean_and_parse(integration.group(1))
        return sp.integrate(source, x), "integral", source

    differentiation = re.match(
        r"^(?:differentiate|derivative|d/dx)(?:\s+of)?\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if differentiation:
        source = clean_and_parse(differentiation.group(1))
        return sp.diff(source, x), "derivative", source

    limit_match = re.match(
        r"^limit\s+(.+?)\s+(?:as\s+)?([A-Za-z_]\w*)\s*(?:->|→|to)\s*(.+)$",
        text,
        re.IGNORECASE,
    )
    if limit_match:
        expression, variable_name, point_text = limit_match.groups()
        variable = sp.Symbol(variable_name)
        source = clean_and_parse(expression)
        point = clean_and_parse(point_text.replace("infinity", "oo").replace("inf", "oo"))
        return sp.limit(source, variable, point), "limit", source

    system_parts = _split_top_level_commas(text)
    if len(system_parts) > 1 and all("=" in part for part in system_parts):
        equations = []
        variables = set()
        for part in system_parts:
            lhs_text, rhs_text = part.split("=", 1)
            equation = sp.Eq(clean_and_parse(lhs_text), clean_and_parse(rhs_text))
            equations.append(equation)
            variables.update(equation.free_symbols)
        solutions = sp.solve(equations, sorted(variables, key=str), dict=True)
        return solutions, "system", None

    matrix_match = re.match(r"^(det|inv|eigen|rref)\s+(.+)$", text, re.IGNORECASE)
    if matrix_match:
        operation, matrix_text = matrix_match.groups()
        matrix = sp.Matrix(ast.literal_eval(matrix_text))
        operation = operation.lower()
        if operation == "det":
            result = matrix.det()
        elif operation == "inv":
            result = matrix.inv()
        elif operation == "eigen":
            result = matrix.eigenvects()
        else:
            result = matrix.rref()
        return result, "matrix", None

    equation_match = re.fullmatch(r"(.+?)\s*=\s*(.+)", text)
    if equation_match:
        lhs_text, rhs_text = equation_match.groups()
        equation = sp.Eq(clean_and_parse(lhs_text), clean_and_parse(rhs_text))
        variables = sorted(equation.free_symbols, key=str)
        return sp.solve(equation, variables, dict=True), "equation", None

    factor_match = re.match(r"^factor(?:\s+of)?\s+(.+)$", text, re.IGNORECASE)
    if factor_match:
        return sp.factor(clean_and_parse(factor_match.group(1))), "expression", None
    expand_match = re.match(r"^expand(?:\s+of)?\s+(.+)$", text, re.IGNORECASE)
    if expand_match:
        return sp.expand(clean_and_parse(expand_match.group(1))), "expression", None
    if text.startswith("[["):
        return sp.Matrix(ast.literal_eval(text)), "matrix", None
    return sp.simplify(clean_and_parse(text)), "expression", None


AI_AGENT_SYSTEM_PROMPT = """You are OmniMath's math tutor. Interpret the user's natural-language
math question, translate it into exact mathematics, and explain the solution in clear,
numbered steps that a student can follow. Show the actual arithmetic and algebra using
the exact numbers from the user's problem; explain each operation in plain language
instead of saying to solve with a tool. For systems, show the equations, each
elimination or substitution, the arithmetic used to find every variable, then
substitute those values into the requested expression and simplify it before stating
the answer. For example, show steps like "Add the equations: (x + y) + (x - y) =
10 + 4 -> 2x = 14", "Divide both sides by 2: x = 14 / 2 = 7", "Plug x = 7 into
x + y = 10: 7 + y = 10 -> y = 3", and "Substitute x = 7 and y = 3 into (xy)^2:
(7 × 3)^2 = 21^2 = 441". Do not show raw LaTeX solution-set notation or refer to
SymPy as the solver in the explanation. Use LaTeX delimited by $$...$$ for important
equations. End every solvable math answer with exactly one <sympy>...</sympy> tag.
The tag must contain only a SymPy-compatible expression, equation, or supported call
such as diff(x**3 + 2*x, x); never put prose or code in it. For equations, include
the equation (for example 2*x + 5 = 15), not a guessed solution. Ask a concise
follow-up question without a tag if essential information is missing. Use earlier
turns to resolve follow-up references, but do not claim SymPy verified anything
yourself."""

AGENT_FUNCTION_NAMES = {
    "sqrt", "cbrt", "abs", "sin", "cos", "tan", "asin", "acos", "atan",
    "sinh", "cosh", "tanh", "log", "ln", "exp", "factorial", "gcd", "lcm",
    "binomial", "Rational", "diff", "differentiate", "derivative", "integrate",
    "integral", "limit",
}
AGENT_ALLOWED_NAMES = set(LOCAL_DICT) | AGENT_FUNCTION_NAMES
AGENT_AST_NODES = (
    ast.Expression, ast.Constant, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.UAdd, ast.USub,
    ast.Call,
)


def _normalize_agent_expression(text: str) -> str:
    expression = text.strip().replace("^", "**")
    expression = re.sub(r"(?<=\d)\s*(?=[A-Za-z(])", "*", expression)
    expression = re.sub(r"\b([xyztn])\s*(?=\()", r"\1*", expression)
    expression = re.sub(r"(?<=\))\s*(?=\()", "*", expression)
    return expression


def _validate_agent_expression(text: str):
    """Reject Python syntax outside the calculator's small math-expression grammar."""
    expression = _normalize_agent_expression(text)
    if not expression or not re.fullmatch(r"[A-Za-z0-9_+\-*/^().,\s=]+", expression):
        raise ValueError("The math expression contains unsupported characters.")
    if "__" in expression:
        raise ValueError("The math expression contains an unsupported name.")
    if "=" in expression:
        equations = _split_top_level_commas(expression)
        if len(equations) > 1:
            if not all("=" in equation for equation in equations):
                raise ValueError("Every part of a system must be an equation.")
            for equation in equations:
                _validate_agent_expression(equation)
            return
        sides = expression.split("=")
        if len(sides) != 2:
            raise ValueError("Use one equality sign in an equation.")
        _validate_agent_expression(sides[0])
        _validate_agent_expression(sides[1])
        return

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("The SymPy expression is not valid math syntax.") from exc
    for node in ast.walk(tree):
        if not isinstance(node, AGENT_AST_NODES):
            raise ValueError("The math expression contains unsupported syntax.")
        if isinstance(node, ast.Name) and node.id not in AGENT_ALLOWED_NAMES:
            raise ValueError(f"Unsupported math name: {node.id}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError("Only numeric constants are supported.")
        if isinstance(node, ast.Call):
            if (
                not isinstance(node.func, ast.Name)
                or node.func.id not in AGENT_FUNCTION_NAMES
                or node.keywords
            ):
                raise ValueError("Only supported SymPy math functions may be called.")


def _evaluate_agent_expression(expression_text: str):
    _validate_agent_expression(expression_text)
    expression_text = _normalize_agent_expression(expression_text)
    calculus_result = _parse_calculus_call(expression_text)
    if calculus_result:
        return calculus_result[0], calculus_result[1], calculus_result[2]
    return parse_homework_expression(expression_text)


def _agent_result_latex(value) -> str:
    if isinstance(value, (list, tuple)):
        solutions = []
        for solution in value:
            if isinstance(solution, dict):
                assignments = [
                    f"{sp.latex(variable)}={sp.latex(result)}"
                    for variable, result in solution.items()
                ]
                solutions.append(r"\,".join(assignments))
            else:
                solutions.append(sp.latex(solution))
        return r"\left\{" + r";\ ".join(solutions) + r"\right\}"
    return sp.latex(value)


def _agent_sympy_result(expression_text: str):
    value, operation, source = _evaluate_agent_expression(expression_text)
    return value, operation, source


def _agent_plain_math(expression) -> str:
    return sp.sstr(expression).replace("**", "^").replace("*", " × ")


def _agent_substitute_text(expression, substitutions) -> str:
    text = expression if isinstance(expression, str) else sp.sstr(expression)
    text = re.sub(r"\s*\*\*\s*", "**", text)
    while True:
        simplified_text = re.sub(r"\(\(([^()]*)\)\)", r"(\1)", text)
        if simplified_text == text:
            break
        text = simplified_text
    for variable, replacement in substitutions.items():
        replacement_text = sp.sstr(replacement)
        if not replacement.is_Atom:
            replacement_text = f"({replacement_text})"
        text = re.sub(
            rf"\b{re.escape(str(variable))}\b",
            lambda _: replacement_text,
            text,
        )
    return text.replace("**", "^").replace("*", " × ")


def _agent_system_word_problem_steps(
    equations, solutions, expression, expression_text, results
):
    variables = sorted(
        set().union(*(equation.free_symbols for equation in equations)),
        key=str,
    )
    if (
        len(variables) != 2
        or len(equations) != 2
        or len(solutions) != 1
        or not all(variable in solutions[0] for variable in variables)
    ):
        return None

    try:
        if any(
            sp.Poly(equation.lhs - equation.rhs, *variables).total_degree() > 1
            for equation in equations
        ):
            return None
    except sp.PolynomialError:
        return None

    first_variable, second_variable = variables
    isolated_values = sp.solve(equations[0], first_variable)
    if (
        len(isolated_values) != 1
        or isolated_values[0].has(first_variable)
        or isolated_values[0].free_symbols - {second_variable}
    ):
        return None

    isolated_value = isolated_values[0]
    first_equation = equations[0]
    first_coefficient = sp.diff(
        first_equation.lhs - first_equation.rhs, first_variable
    )
    first_remainder = sp.simplify(
        first_equation.lhs - first_coefficient * first_variable
    )
    isolated_numerator = sp.simplify(first_equation.rhs - first_remainder)
    if first_remainder:
        isolation_step = (
            f"Subtract {_agent_plain_math(first_remainder)} from both sides"
        )
    else:
        isolation_step = "Isolate the variable"
    if first_coefficient != 1:
        isolation_step += (
            f", then divide both sides by {_agent_plain_math(first_coefficient)}"
        )
    isolation_step += ": "
    if first_coefficient != 1:
        isolation_step += (
            f"{first_variable} = "
            f"({_agent_plain_math(isolated_numerator)}) / "
            f"{_agent_plain_math(first_coefficient)} = "
        )
    else:
        isolation_step += f"{first_variable} = "
    isolation_step += f"{_agent_plain_math(isolated_value)}."
    steps = [
        "Start with the equations: "
        + " and ".join(
            f"{_agent_plain_math(equation.lhs)} = "
            f"{_agent_plain_math(equation.rhs)}"
            for equation in equations
        )
        + ".",
        isolation_step,
    ]

    solution = solutions[0]
    second_equation = equations[1]
    substituted_left = _agent_substitute_text(
        second_equation.lhs, {first_variable: isolated_value}
    )
    substituted_right = _agent_substitute_text(
        second_equation.rhs, {first_variable: isolated_value}
    )
    simplified_left = sp.simplify(
        second_equation.lhs.subs(first_variable, isolated_value)
    )
    simplified_right = sp.simplify(
        second_equation.rhs.subs(first_variable, isolated_value)
    )
    steps.extend(
        [
            f"Substitute {first_variable} = {_agent_plain_math(isolated_value)} "
            f"into the second equation: {substituted_left} = {substituted_right}.",
            "Simplify: "
            f"{_agent_plain_math(simplified_left)} = "
            f"{_agent_plain_math(simplified_right)}.",
        ]
    )

    reduced_equation = sp.expand(simplified_left - simplified_right)
    coefficient = sp.diff(reduced_equation, second_variable)
    constant = reduced_equation.subs(second_variable, 0)
    if coefficient and not coefficient.free_symbols:
        if constant:
            left_constant = simplified_left.subs(second_variable, 0)
            if left_constant:
                rearrangement = (
                    f"Subtract {_agent_plain_math(left_constant)} from both "
                    f"sides: {_agent_plain_math(coefficient * second_variable)} "
                    f"= {_agent_plain_math(simplified_right)} - "
                    f"{_agent_plain_math(left_constant)} = "
                    f"{_agent_plain_math(-constant)}."
                )
            else:
                rearrangement = (
                    "Rearrange to isolate the variable term: "
                    f"{_agent_plain_math(coefficient * second_variable)} = "
                    f"{_agent_plain_math(-constant)}."
                )
            steps.append(rearrangement)
            quotient = sp.simplify(-constant / coefficient)
            dividend_text = _agent_plain_math(-constant)
            divisor_text = _agent_plain_math(coefficient)
            if (-constant).is_negative:
                dividend_text = f"({dividend_text})"
            if coefficient.is_negative:
                divisor_text = f"({divisor_text})"
            steps.append(
                f"Divide both sides by {_agent_plain_math(coefficient)}: "
                f"{second_variable} = "
                f"{dividend_text} / {divisor_text} = "
                f"{_agent_plain_math(quotient)}."
            )
        else:
            steps.append(
                f"The second equation gives {second_variable} = "
                f"{_agent_plain_math(solution[second_variable])}."
            )
    first_value = sp.simplify(isolated_value.subs(solution))
    steps.append(
        f"Substitute {second_variable} = "
        f"{_agent_plain_math(solution[second_variable])} into "
        f"{first_variable} = {_agent_plain_math(isolated_value)}: "
        f"{first_variable} = "
        f"{_agent_substitute_text(isolated_value, {second_variable: solution[second_variable]})}"
        f" = {_agent_plain_math(first_value)}."
    )

    substitutions = {
        variable: solution[variable]
        for variable in variables
        if variable in solutions[0]
    }
    substitution_text = " and ".join(
        f"{variable} = {_agent_plain_math(value)}"
        for variable, value in substitutions.items()
    )
    substituted_expression = _agent_substitute_text(
        expression_text, substitutions
    )
    power_match = re.fullmatch(r"\s*\((.+)\)\s*\*\*\s*(.+)\s*", expression_text)
    if power_match:
        base_text, exponent_text = power_match.groups()
        base = clean_and_parse(base_text)
        substituted_base_text = _agent_substitute_text(
            base_text, substitutions
        )
        evaluated_base = sp.simplify(base.subs(substitutions))
        if substituted_base_text != _agent_plain_math(evaluated_base):
            evaluated_expression = sp.simplify(expression.subs(substitutions))
            exponent_display = _agent_plain_math(clean_and_parse(exponent_text))
            steps.append(
                f"Substitute {substitution_text} into "
                f"{_agent_substitute_text(expression_text, {})}: "
                f"{substituted_expression} = {_agent_plain_math(evaluated_base)}^"
                f"{exponent_display} = "
                f"{_agent_plain_math(evaluated_expression)}."
            )
            return steps
    steps.append(
        f"Substitute {substitution_text} into "
        f"{_agent_substitute_text(expression_text, {})}: "
        f"{substituted_expression} = {_agent_plain_math(results[0])}."
    )
    return steps


def _agent_solution_steps(expression_text: str, value, operation: str, source):
    if operation == "derivative":
        return [
            f"Start with \\(f(x) = {sp.latex(source)}\\).",
            "Apply the appropriate differentiation rule term by term.",
            f"Differentiate with SymPy: \\(f'(x) = {sp.latex(value)}\\).",
        ]
    if operation == "integral":
        return [
            f"Integrate \\({sp.latex(source)}\\) with respect to \\(x\\).",
            f"SymPy returns the antiderivative \\({sp.latex(value)}\\); add a constant \\(C\\).",
        ]
    if operation == "equation":
        match = re.fullmatch(r"(.+?)\s*=\s*(.+)", expression_text)
        if match:
            left = clean_and_parse(_normalize_agent_expression(match.group(1)))
            right = clean_and_parse(_normalize_agent_expression(match.group(2)))
            equation = sp.expand(left - right)
            variables = sorted(equation.free_symbols, key=str)
            if len(variables) == 1:
                variable = variables[0]
                try:
                    degree = sp.Poly(equation, variable).degree()
                except sp.PolynomialError:
                    degree = None
                if degree == 1:
                    coefficient = sp.diff(equation, variable)
                    constant = equation.subs(variable, 0)
                    steps = [f"Start with \\({sp.latex(left)} = {sp.latex(right)}\\)."]
                    if constant != 0:
                        steps.append(
                            f"Move the constant term: \\({sp.latex(coefficient * variable)} = "
                            f"{sp.latex(-constant)}\\)."
                        )
                    if coefficient not in (1, -1):
                        steps.append(
                            f"Divide both sides by \\({sp.latex(coefficient)}\\) to isolate "
                            f"\\({sp.latex(variable)}\\)."
                        )
                    if value:
                        steps.append(
                            f"SymPy verifies \\({sp.latex(variable)} = "
                            f"{sp.latex(value[0][variable])}\\)."
                        )
                    else:
                        steps.append("SymPy found no isolated solution for this equation.")
                    return steps
        return [f"SymPy solves the equation exactly: \\({ _agent_result_latex(value) }\\)."]
    if operation == "expression":
        return [
            f"Translate the prompt into \\({sp.latex(source) if source is not None else expression_text}\\).",
            f"Evaluate and simplify with SymPy: \\({sp.latex(value)}\\).",
        ]
    if operation == "limit":
        return [f"Evaluate the requested limit exactly: \\({sp.latex(value)}\\)."]
    return [f"SymPy evaluated the translated math exactly: \\({ _agent_result_latex(value) }\\)."]


def _configured_agent_api_key():
    for provider, name in (("gemini", "GEMINI_API_KEY"), ("openai", "OPENAI_API_KEY")):
        key = os.environ.get(name)
        if key:
            return provider, key
    try:
        for provider, name in (("gemini", "GEMINI_API_KEY"), ("openai", "OPENAI_API_KEY")):
            key = st.secrets.get(name)
            if key:
                return provider, str(key)
    except FileNotFoundError:
        pass
    return None, None


def _agent_api_configuration():
    provider, key = _configured_agent_api_key()
    if key:
        return provider, key
    user_key = st.session_state.get("ai_agent_api_key", "").strip()
    if user_key:
        return st.session_state.get("ai_agent_provider", "gemini"), user_key
    return None, None


def _request_agent_completion(provider: str, api_key: str, conversation):
    if sys.platform == "emscripten":
        raise RuntimeError(
            "Hosted AI providers are unavailable in the browser app; "
            "using the local SymPy agent."
        )

    if provider == "gemini":
        import httpx
        from google import genai
        from google.genai import types
        from google.genai.errors import APIError

        def stream_response():
            try:
                with genai.Client(
                    api_key=api_key,
                    http_options=types.HttpOptions(
                        timeout=4000,
                        retry_options=types.HttpRetryOptions(attempts=1),
                    ),
                ) as client:
                    contents = [
                        {
                            "role": "model" if message["role"] == "assistant" else "user",
                            "parts": [{"text": message["content"]}],
                        }
                        for message in conversation
                    ]
                    response_stream = client.models.generate_content_stream(
                        model="gemini-2.5-flash",
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=AI_AGENT_SYSTEM_PROMPT,
                            temperature=0.1,
                            automatic_continuation=False,
                        ),
                    )
                    for chunk in response_stream:
                        if chunk.text:
                            yield chunk.text
            except (APIError, httpx.TransportError) as exc:
                raise RuntimeError(f"Gemini API request failed: {exc}") from exc

        return stream_response()

    body = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": AI_AGENT_SYSTEM_PROMPT},
            *[
                {
                    "role": "assistant" if message["role"] == "assistant" else "user",
                    "content": message["content"],
                }
                for message in conversation
            ],
        ],
    }
    request = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"OpenAI API returned HTTP {exc.code}: {details}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Could not reach the OpenAI API: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("The OpenAI API returned an invalid response.") from exc

    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("The OpenAI API response did not contain a message.") from exc


def _agent_visible_response_chunks(chunks, raw_chunks):
    opening_tag = "<sympy>"
    closing_tag = "</sympy>"
    buffer = ""
    inside_tag = False

    for chunk in chunks:
        raw_chunks.append(chunk)
        buffer += chunk
        while buffer:
            lowered_buffer = buffer.lower()
            if inside_tag:
                closing_index = lowered_buffer.find(closing_tag)
                if closing_index < 0:
                    buffer = buffer[-(len(closing_tag) - 1):]
                    break
                buffer = buffer[closing_index + len(closing_tag):]
                inside_tag = False
                continue

            opening_index = lowered_buffer.find(opening_tag)
            if opening_index >= 0:
                if opening_index:
                    yield buffer[:opening_index]
                buffer = buffer[opening_index + len(opening_tag):]
                inside_tag = True
                continue

            partial_tag_length = 0
            for length in range(1, min(len(buffer), len(opening_tag) - 1) + 1):
                if opening_tag.startswith(buffer[-length:].lower()):
                    partial_tag_length = length
            ready_length = len(buffer) - partial_tag_length
            if ready_length:
                yield buffer[:ready_length]
                buffer = buffer[ready_length:]
            break

    if not inside_tag and buffer:
        yield buffer


def _translate_linear_word_problem(prompt: str):
    if not re.search(r"\b(?:number|unknown|x)\b", prompt, re.IGNORECASE):
        return None
    translated = prompt.lower().strip().rstrip("?.!")
    translated = re.sub(
        r"\b(\d+(?:\.\d+)?)\s+less than\s+(?:a|the|some)\s+number\b",
        r"x - \1",
        translated,
    )
    translated = re.sub(r"\b(?:twice|double)\s+(?:a|the|some)\s+number\b", "2*x", translated)
    translated = re.sub(r"\b(?:three times|triple)\s+(?:a|the|some)\s+number\b", "3*x", translated)
    translated = re.sub(r"\b(?:a|the|some)\s+number\b", "x", translated)
    translated = re.sub(r"\b(?:plus|added to)\b", "+", translated)
    translated = re.sub(r"\bminus\b", "-", translated)
    translated = re.sub(r"\b(?:times|multiplied by)\b", "*", translated)
    translated = re.sub(r"\bdivided by\b", "/", translated)
    translated = re.sub(r"\b(?:equals|is|was)\b", "=", translated)
    translated = re.sub(r"\b(?:find|solve|what is|the value of|when)\b", " ", translated)
    translated = re.sub(r"\s+", " ", translated).strip()
    if "=" not in translated or re.search(r"[a-wyz]", translated):
        return None
    try:
        _validate_agent_expression(translated)
    except ValueError:
        return None
    return translated


def _translate_system_word_problem(prompt: str):
    halves = re.split(
        r"\b(?:then|what\s+is|find|calculate|compute)\b",
        prompt,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    if len(halves) != 2:
        return None
    equations_text, result_text = halves
    equations_text = re.sub(r"^\s*if\s+", "", equations_text, flags=re.IGNORECASE)
    result_text = result_text.strip().rstrip("?.!")
    result_text = re.sub(
        r"^(?:what\s+is|find|calculate|compute)\s+",
        "",
        result_text,
        flags=re.IGNORECASE,
    )

    def translate_expression(text):
        translated = text.strip().lower()
        translated = re.sub(
            r"\bto the power of\s+(\d+)\b", r"**\1", translated
        )
        translated = re.sub(r"\bsquared\b", "**2", translated)
        translated = re.sub(r"\bxy\b", "(x*y)", translated)
        translated = re.sub(r"\bplus\b", "+", translated)
        translated = re.sub(r"\bminus\b", "-", translated)
        translated = re.sub(r"\bequals\b", "=", translated)
        return translated

    equation_parts = re.split(
        r"\s*,\s*(?:and\b\s*)?|\s+\band\b(?:\s+|$)",
        equations_text,
        flags=re.IGNORECASE,
    )
    equations = [
        translate_expression(part)
        for part in equation_parts
        if "=" in part
    ]
    if len(equations) < 2 or not all("=" in equation for equation in equations):
        return None

    system_text = ", ".join(equations)
    result_text = translate_expression(result_text)
    try:
        _validate_agent_expression(system_text)
        _validate_agent_expression(result_text)
    except ValueError:
        return None
    return system_text, result_text


def _local_agent_response(prompt: str, conversation):
    normalized = prompt.strip().rstrip("?")
    prior_expression = next(
        (
            message.get("graph_expression")
            for message in reversed(conversation)
            if message["role"] == "assistant" and message.get("graph_expression")
        ),
        None,
    )
    if re.search(r"\b(?:why|explain)\b", normalized, re.IGNORECASE):
        if re.search(r"\bdivide|divided\b", normalized, re.IGNORECASE):
            previous_equation = next(
                (
                    message.get("send_expression")
                    for message in reversed(conversation)
                    if message["role"] == "assistant"
                    and message.get("send_expression")
                    and "=" in message["send_expression"]
                ),
                None,
            )
            if previous_equation:
                _validate_agent_expression(previous_equation)
                left_text, right_text = previous_equation.split("=", 1)
                left = clean_and_parse(_normalize_agent_expression(left_text))
                right = clean_and_parse(_normalize_agent_expression(right_text))
                equation = sp.expand(left - right)
                variables = sorted(equation.free_symbols, key=str)
                if len(variables) == 1:
                    variable = variables[0]
                    coefficient = sp.diff(equation, variable)
                    constant = equation.subs(variable, 0)
                    if (
                        not coefficient.free_symbols
                        and coefficient not in (1, -1, 0)
                    ):
                        return (
                            f"After moving the constant term, the equation becomes "
                            f"\\({sp.latex(coefficient * variable)} = "
                            f"{sp.latex(-constant)}\\). Since \\({variable}\\) is "
                            f"multiplied by \\({sp.latex(coefficient)}\\), divide both "
                            f"sides by \\({sp.latex(coefficient)}\\) to isolate it.",
                            None,
                            None,
                        )
            return (
                "We divide by the coefficient of the variable after moving the constant "
                "term. That isolates the variable while keeping the equation balanced.",
                None,
                None,
            )
        return (
            "I used SymPy to verify the previous result. Ask about a specific step (for "
            "example, “Why did you divide by 2?”) and I can explain the rule used.",
            None,
            None,
        )

    graph_request = re.search(r"\b(?:graph|plot|grapher|graphing)\b", normalized, re.IGNORECASE)
    if graph_request:
        expression_text = prior_expression
        if not expression_text:
            expression_text = re.sub(
                r"^\s*(?:please\s+)?(?:graph|plot)\s+", "", normalized, flags=re.IGNORECASE
            )
            expression_text = re.sub(
                r"\s+from\s+.+$", "", expression_text, flags=re.IGNORECASE
            )
        if expression_text:
            value = _agent_sympy_result(expression_text)[0]
            if not isinstance(value, sp.Expr):
                value = sp.sympify(value)
            return (
                f"Using the function \\({sp.latex(value)}\\) from the conversation. "
                "SymPy parsed it successfully; use the button below to open it in the grapher.",
                "graph",
                sp.sstr(value),
            )
        return (
            "I couldn't find a function to graph. Give me an expression, for example "
            "“graph x^2 + 1,” or solve a function first.",
            None,
            None,
        )

    circle = re.search(
        r"\barea\s+of\s+(?:a\s+)?circle\s+(?:with\s+)?radius\s+([0-9.]+)\b",
        normalized,
        re.IGNORECASE,
    )
    if circle:
        radius = clean_and_parse(circle.group(1))
        value = sp.simplify(sp.pi * radius**2)
        display = (
            f"1. Use the circle area formula: \\(A = \\pi r^2\\).\n\n"
            f"2. Substitute \\(r = {sp.latex(radius)}\\): "
            f"\\(A = \\pi \\cdot {sp.latex(radius)}^2\\).\n\n"
            f"3. **SymPy-verified result:** $$A = {sp.latex(value)}$$"
        )
        return display, "solver", sp.sstr(value)

    word_problem = _translate_system_word_problem(normalized)
    if word_problem:
        system_text, result_text = word_problem
        equations = []
        equation_parts = [
            part
            for part in _split_top_level_commas(system_text)
            if "=" in part
        ]
        for equation_text in equation_parts:
            left_text, right_text = equation_text.split("=", 1)
            equations.append(
                sp.Eq(clean_and_parse(left_text), clean_and_parse(right_text))
            )
        solutions = sp.solve(
            equations,
            sorted(
                set().union(*(equation.free_symbols for equation in equations)),
                key=str,
            ),
            dict=True,
        )
        expression = clean_and_parse(result_text)
        results = [sp.simplify(expression.subs(solution)) for solution in solutions]
        if not results:
            answer_text = (
                "The equations have no solution, so the requested "
                "expression cannot be evaluated."
            )
            result_value = None
        else:
            steps = _agent_system_word_problem_steps(
                equations, solutions, expression, result_text, results
            )
            if steps is None:
                steps = [
                    "Start with the equations: "
                    + " and ".join(
                        f"{_agent_plain_math(equation.lhs)} = "
                        f"{_agent_plain_math(equation.rhs)}"
                        for equation in equations
                    )
                    + ".",
                ]
                for solution, result in zip(solutions, results):
                    substitutions = {
                        variable: solution[variable]
                        for variable in sorted(solution, key=str)
                    }
                    solution_text = " and ".join(
                        f"{variable} = {_agent_plain_math(value)}"
                        for variable, value in substitutions.items()
                    )
                    steps.append(
                        f"Solving the equations gives {solution_text}."
                    )
                    steps.append(
                        f"Substitute {solution_text} into "
                        f"{_agent_substitute_text(result_text, {})}: "
                        f"{_agent_substitute_text(result_text, substitutions)} "
                        f"= {_agent_plain_math(result)}."
                    )
            answer_text = "\n\n".join(
                f"{index}. {step}" for index, step in enumerate(steps, 1)
            )
            answer_text += (
                f"\n\n**Answer:** {', '.join(_agent_plain_math(result) for result in results)}"
            )
            result_value = results[0] if len(results) == 1 else None
        return (
            answer_text,
            "solver" if result_value is not None else None,
            sp.sstr(result_value) if result_value is not None else None,
        )

    equation_text = _translate_linear_word_problem(normalized)
    if equation_text is None:
        equation_text = normalized
        equation_text = re.sub(
            r"^\s*(?:what is|calculate|compute|find|solve|evaluate)\s+",
            "",
            equation_text,
            flags=re.IGNORECASE,
        )
        if re.search(r"\b(?:derivative|differentiate|d/dx)\b", equation_text, re.IGNORECASE):
            equation_text = re.sub(
                r"^\s*(?:the\s+)?(?:derivative|differentiate|d/dx)(?:\s+of)?\s+",
                "diff(",
                equation_text,
                flags=re.IGNORECASE,
            )
            equation_text = equation_text.rstrip(")") + ", x)"
    value, operation, source = _agent_sympy_result(equation_text)
    steps = _agent_solution_steps(equation_text, value, operation, source)
    answer_text = "\n\n".join(
        f"{index}. {step}" for index, step in enumerate(steps, 1)
    )
    answer_text += f"\n\n**SymPy-verified result:** $$ { _agent_result_latex(value) } $$"
    graph_expression = None
    if isinstance(value, sp.Expr) and value.free_symbols <= {x, y}:
        graph_expression = sp.sstr(value)
    send_expression = graph_expression or equation_text
    target = "graph" if graph_expression else "solver"
    return answer_text, target, send_expression


def _generate_agent_response(prompt: str, conversation, stream_writer=None):
    provider, api_key = _agent_api_configuration()
    if not api_key:
        answer, target, send_expression = _local_agent_response(prompt, conversation)
        return answer, target, send_expression, "Local SymPy"

    try:
        completion = _request_agent_completion(provider, api_key, conversation)
        if provider == "gemini":
            raw_chunks = []
            if stream_writer:
                stream_writer(
                    _agent_visible_response_chunks(completion, raw_chunks)
                )
            else:
                raw_chunks.extend(completion)
            raw_response = "".join(raw_chunks)
        else:
            raw_response = completion
    except RuntimeError:
        answer, target, send_expression = _local_agent_response(prompt, conversation)
        return answer, target, send_expression, "Local SymPy"
    match = re.search(r"<sympy>\s*(.*?)\s*</sympy>", raw_response, re.IGNORECASE | re.DOTALL)
    response_text = re.sub(
        r"\s*<sympy>.*?</sympy>\s*",
        "",
        raw_response,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()
    if not match:
        response_text += "\n\n*No SymPy expression was provided for verification.*"
        return response_text, None, None, provider.title()
    expression_text = match.group(1).strip()
    value = _agent_sympy_result(expression_text)[0]
    response_text += (
        f"\n\n**SymPy-verified result:** $$ { _agent_result_latex(value) } $$"
    )
    graph_expression = (
        sp.sstr(value)
        if isinstance(value, sp.Expr) and value.free_symbols <= {x, y}
        else None
    )
    target = "graph" if graph_expression else "solver"
    send_expression = graph_expression or expression_text
    return response_text, target, send_expression, provider.title()


def _send_agent_expression(expression: str, target: str):
    if target == "graph":
        st.session_state["surface_expression"] = expression
        st.session_state["active_tab"] = "3D Surface Grapher"
    else:
        st.session_state["query_input"] = expression
        st.session_state["active_tab"] = "OmniMath Solver"


def render_ai_math_agent():
    st.subheader("AI Math Agent")
    st.caption(
        "Ask a math question or word problem, then continue with follow-ups. "
        "Every parsed result is evaluated by SymPy."
    )
    conversation = st.session_state.setdefault("ai_chat", [])
    for index, message in enumerate(conversation):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("send_expression"):
                st.button(
                    "Send to Grapher / Solver",
                    key=f"ai_send_expression_{index}",
                    on_click=_send_agent_expression,
                    args=(message["send_expression"], message["target"]),
                )
    prompt = st.chat_input("Ask a math question or follow up...", key="ai_chat_input")
    if not prompt:
        return
    conversation.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    streamed_text = []
    with st.chat_message("assistant"):
        try:
            answer, target, send_expression, mode = _generate_agent_response(
                prompt,
                conversation,
                lambda chunks: streamed_text.append(st.write_stream(chunks)),
            )
        except (
            RuntimeError,
            ValueError,
            TypeError,
            SyntaxError,
            NameError,
            ZeroDivisionError,
        ) as exc:
            answer = f"I couldn't solve that request: {exc}"
            target = send_expression = None
            mode = "SymPy"
        st.session_state["ai_chat"].append(
            {
                "role": "assistant",
                "content": answer,
                "send_expression": send_expression,
                "target": target,
                "graph_expression": (
                    send_expression if target == "graph" else None
                ),
                "mode": mode,
            }
        )
        visible_response = streamed_text[0].strip() if streamed_text else ""
        if visible_response and answer.startswith(visible_response):
            st.markdown(answer[len(visible_response):])
        else:
            st.markdown(answer)
        st.caption(f"Answered with {mode}.")
        if send_expression:
            st.button(
                "Send to Grapher / Solver",
                key=f"ai_send_expression_{len(conversation) - 1}",
                on_click=_send_agent_expression,
                args=(send_expression, target),
            )


def _parse_homework_attempt(text: str):
    parse_locals = {"C": sp.Symbol("C"), "Matrix": sp.Matrix}
    parts = _split_top_level_commas(text)
    assignments = {}
    if parts and all(re.fullmatch(r"[A-Za-z_]\w*\s*=\s*.+", part) for part in parts):
        for part in parts:
            name, expression = part.split("=", 1)
            assignments[sp.Symbol(name.strip())] = clean_and_parse(expression, parse_locals)
        return assignments

    if len(parts) == 1 and text.strip().startswith("[["):
        return sp.Matrix(ast.literal_eval(text.strip()))
    parsed_parts = []
    for part in parts:
        if "=" in part:
            lhs_text, rhs_text = part.split("=", 1)
            parsed_parts.append(
                sp.Eq(
                    clean_and_parse(lhs_text, parse_locals),
                    clean_and_parse(rhs_text, parse_locals),
                )
            )
        else:
            parsed_parts.append(clean_and_parse(part, parse_locals))
    if len(parsed_parts) == 1:
        return parsed_parts[0]
    return parsed_parts


def _homework_value_text(value):
    if isinstance(value, dict):
        return ", ".join(f"{key} = {sp.sstr(result)}" for key, result in value.items())
    if isinstance(value, (list, tuple)):
        return "; ".join(_homework_value_text(item) for item in value)
    return sp.sstr(value)


def _symbolically_equal(first, second):
    if isinstance(first, (list, tuple)) and isinstance(second, (list, tuple)):
        return len(first) == len(second) and all(
            _symbolically_equal(a, b) for a, b in zip(first, second)
        )
    if isinstance(first, sp.MatrixBase) and isinstance(second, sp.MatrixBase):
        return first.shape == second.shape and all(
            sp.simplify(a - b) == 0
            for a, b in zip(first, second)
        )
    try:
        return sp.simplify(first - second) == 0
    except (TypeError, AttributeError):
        return first == second


def _solutions_match(expected, actual):
    if isinstance(actual, dict):
        if not isinstance(expected, list) or len(expected) != 1:
            return False
        return any(
            set(solution) == set(actual)
            and all(
                variable in solution and _symbolically_equal(solution[variable], value)
                for variable, value in actual.items()
            )
            for solution in expected
        )
    if isinstance(expected, list):
        if expected and all(isinstance(solution, dict) and len(solution) == 1 for solution in expected):
            values = [next(iter(solution.values())) for solution in expected]
            actual_values = actual if isinstance(actual, list) else [actual]
            return len(values) == len(actual_values) and all(
                any(_symbolically_equal(candidate, answer) for answer in actual_values)
                for candidate in values
            )
        if isinstance(actual, list):
            return len(expected) == len(actual) and all(
                any(_symbolically_equal(candidate, answer) for answer in actual)
                for candidate in expected
            )
        return len(expected) == 1 and _symbolically_equal(expected[0], actual)
    return _symbolically_equal(expected, actual)


def _homework_walkthrough(original, expected, operation, source):
    """Return display-ready steps and intermediate values useful for diagnosis."""
    steps = []
    checkpoints = []
    problem = re.sub(
        r"^(?:what is|calculate|compute|solve|evaluate|find|simplify)\s+",
        "",
        original.strip().rstrip("?"),
        flags=re.IGNORECASE,
    )

    if operation == "system":
        parts = _split_top_level_commas(problem)
        if len(parts) == 2:
            equations = []
            variables = set()
            for part in parts:
                lhs_text, rhs_text = part.split("=", 1)
                equation = sp.Eq(
                    clean_and_parse(lhs_text),
                    clean_and_parse(rhs_text),
                    evaluate=False,
                )
                equations.append(equation)
                variables.update(equation.free_symbols)
            variables = sorted(variables, key=str)
            if len(variables) == 2 and all(
                sp.Poly(eq.lhs - eq.rhs, *variables).total_degree() <= 1
                for eq in equations
            ):
                first, second = equations
                coefficients = [
                    [
                        sp.expand(eq.lhs - eq.rhs).coeff(variable)
                        for variable in variables
                    ]
                    for eq in equations
                ]
                eliminate_index = next(
                    (
                        index
                        for index in range(2)
                        if sp.simplify(
                            coefficients[0][index] + coefficients[1][index]
                        )
                        == 0
                    ),
                    None,
                )
                operation_sign, operation_text = 1, "Add"
                scale_first, scale_second = 1, 1
                if eliminate_index is None:
                    eliminate_index = next(
                        (
                            index
                            for index in range(2)
                            if sp.simplify(
                                coefficients[0][index] - coefficients[1][index]
                            )
                            == 0
                        ),
                        None,
                    )
                    operation_sign, operation_text = (
                        -1,
                        "Subtract equation 2 from equation 1",
                    )
                    scale_second = -1
                if eliminate_index is None:
                    eliminate_index = next(
                        (
                            index
                            for index in range(2)
                            if coefficients[0][index] != 0
                            and coefficients[1][index] != 0
                        ),
                        None,
                    )
                    if eliminate_index is not None:
                        scale_first = coefficients[1][eliminate_index]
                        scale_second = -coefficients[0][eliminate_index]
                        operation_sign = 0
                        operation_text = (
                            f"Multiply equation 1 by `{scale_first}` and equation "
                            f"2 by `{scale_second}`, then add"
                        )
                if eliminate_index is not None:
                    remaining_variable = variables[1 - eliminate_index]
                    eliminated_variable = variables[eliminate_index]
                    combined_lhs = sp.simplify(
                        scale_first * first.lhs + scale_second * second.lhs
                    )
                    combined_rhs = sp.simplify(
                        scale_first * first.rhs + scale_second * second.rhs
                    )
                    if operation_sign:
                        equation_combination = (
                            rf"\left({sp.latex(first.lhs)}\right)"
                            + (r" + " if operation_sign == 1 else r" - ")
                            + rf"\left({sp.latex(second.lhs)}\right)"
                            + " = "
                            + rf"\left({sp.latex(first.rhs)}\right)"
                            + (r" + " if operation_sign == 1 else r" - ")
                            + rf"\left({sp.latex(second.rhs)}\right)"
                        )
                    else:
                        equation_combination = (
                            rf"{sp.latex(scale_first)}\left({sp.latex(first.lhs)}\right)"
                            rf" + {sp.latex(scale_second)}"
                            rf"\left({sp.latex(second.lhs)}\right)"
                            " = "
                            rf"{sp.latex(scale_first)}\left({sp.latex(first.rhs)}\right)"
                            rf" + {sp.latex(scale_second)}"
                            rf"\left({sp.latex(second.rhs)}\right)"
                        )
                    steps.append(
                        (
                            f"{operation_text} to eliminate `{eliminated_variable}`.",
                            equation_combination
                            + r"\quad\Longrightarrow\quad "
                            + rf"{sp.latex(combined_lhs)} = {sp.latex(combined_rhs)}",
                        )
                    )
                    values = sp.solve(
                        sp.Eq(combined_lhs, combined_rhs), remaining_variable
                    )
                    if len(values) == 1:
                        value = values[0]
                        coefficient = sp.simplify(
                            combined_lhs.coeff(remaining_variable)
                        )
                        steps.append(
                            (
                                f"Divide both sides by `{coefficient}` to solve "
                                f"for `{remaining_variable}`.",
                                rf"{sp.latex(remaining_variable)} = "
                                rf"\frac{{{sp.latex(combined_rhs)}}}"
                                rf"{{{sp.latex(coefficient)}}}"
                                rf" = {sp.latex(value)}",
                            )
                        )
                        checkpoints.append(
                            {
                                "value": combined_rhs,
                                "equation": (
                                    f"{sp.sstr(combined_lhs)} = "
                                    f"{sp.sstr(combined_rhs)}"
                                ),
                                "step": 2,
                            }
                        )
                        if operation_sign == 1:
                            opposite_rhs_value = sp.simplify(
                                (first.rhs - second.rhs) / coefficient
                            )
                            checkpoints.append(
                                {
                                    "value": opposite_rhs_value,
                                    "kind": "sign",
                                    "variable": remaining_variable,
                                    "equation": (
                                        f"{sp.sstr(first.rhs)} - "
                                        f"({sp.sstr(second.rhs)})"
                                    ),
                                }
                            )
                        solution = expected[0] if expected else {}
                        if eliminated_variable in solution:
                            substitution_lhs = sp.simplify(
                                first.lhs.subs(remaining_variable, value)
                            )
                            substitution_rhs = sp.simplify(
                                first.rhs.subs(remaining_variable, value)
                            )
                            steps.append(
                                (
                                    f"Substitute `{remaining_variable} = {value}` "
                                    f"into equation 1 to find `{eliminated_variable}`.",
                                    rf"{sp.latex(first.lhs)} = {sp.latex(first.rhs)}"
                                    rf"\quad\Longrightarrow\quad "
                                    rf"{sp.latex(substitution_lhs)} = "
                                    rf"{sp.latex(substitution_rhs)}"
                                    rf"\quad\Longrightarrow\quad "
                                    rf"{sp.latex(eliminated_variable)} = "
                                    rf"{sp.latex(solution[eliminated_variable])}",
                                )
                            )
                        return steps, checkpoints

    if operation == "system":
        parts = _split_top_level_commas(problem)
        if len(parts) == 2:
            equations = []
            variables = set()
            for part in parts:
                lhs_text, rhs_text = part.split("=", 1)
                equation = sp.Eq(
                    clean_and_parse(lhs_text),
                    clean_and_parse(rhs_text),
                    evaluate=False,
                )
                equations.append(equation)
                variables.update(equation.free_symbols)
            variables = sorted(variables, key=str)
            substitution_steps = (
                system_substitution_steps(equations, variables)
                if len(variables) == 2
                else None
            )
            if substitution_steps:
                descriptions = [
                    "Start with the first equation.",
                    f"Isolate `{variables[0]}`.",
                    f"Substitute into the second equation.",
                    "Simplify the resulting equation.",
                    f"Solve for `{variables[1]}`.",
                    f"Substitute back to find `{variables[0]}`.",
                ]
                steps = [
                    (descriptions[index], equation)
                    for index, equation in enumerate(substitution_steps)
                ]
                return steps, checkpoints

    if operation == "equation":
        match = re.fullmatch(r"(.+?)\s*=\s*(.+)", problem)
        if match:
            lhs, rhs = (clean_and_parse(part) for part in match.groups())
            variables = sorted((lhs - rhs).free_symbols, key=str)
            if len(variables) == 1:
                variable = variables[0]
                moved = sp.expand(lhs - rhs)
                factored = sp.factor(moved)
                roots = [
                    value
                    for solution in expected
                    for value in solution.values()
                ]
                root_set = ", ".join(sp.latex(value) for value in roots)
                polynomial = sp.Poly(moved, variable)
                if polynomial.degree() == 1:
                    coefficient, constant = polynomial.all_coeffs()
                    root = sp.solve(moved, variable)[0]
                    steps.extend(
                        [
                            (
                                "Move all terms to one side and set the equation to zero.",
                                rf"{sp.latex(lhs)} - \left({sp.latex(rhs)}\right) = 0"
                                rf"\quad\Longrightarrow\quad {sp.latex(moved)} = 0",
                            ),
                            (
                                "Move the constant term to the other side.",
                                rf"{sp.latex(coefficient * variable)}"
                                rf" + {sp.latex(constant)} = 0"
                                rf"\quad\Longrightarrow\quad "
                                rf"{sp.latex(coefficient * variable)}"
                                rf" = {sp.latex(-constant)}",
                            ),
                            (
                                f"Divide both sides by `{coefficient}`.",
                                rf"{sp.latex(variable)} = "
                                rf"\frac{{{sp.latex(-constant)}}}"
                                rf"{{{sp.latex(coefficient)}}}"
                                rf" = {sp.latex(root)}",
                            ),
                        ]
                    )
                    checkpoints.append(
                        {
                            "value": -constant,
                            "equation": (
                                f"{sp.sstr(coefficient * variable)} = "
                                f"{sp.sstr(-constant)}"
                            ),
                            "step": len(steps),
                        }
                    )
                    return steps, checkpoints
                steps.extend(
                    [
                        (
                            "Move all terms to one side and set the equation to zero.",
                            rf"{sp.latex(lhs)} - \left({sp.latex(rhs)}\right) = 0"
                            rf"\quad\Longrightarrow\quad {sp.latex(moved)} = 0",
                        ),
                        (
                            "Factor and solve for the variable.",
                            rf"{sp.latex(factored)} = 0"
                            rf"\quad\Longrightarrow\quad "
                            rf"{sp.latex(variable)} \in \left\{{{root_set}\right\}}",
                        ),
                    ]
                )
                return steps, checkpoints

    if operation in {"derivative", "integral"} and isinstance(source, sp.Basic):
        variable = x
        call = re.fullmatch(
            r"(?:diff|differentiate|derivative|integrate|integral|limit)\s*\((.*)\)",
            problem,
            re.IGNORECASE,
        )
        if call:
            arguments = _split_top_level_commas(call.group(1))
            if len(arguments) > 1 and operation != "limit":
                candidate = clean_and_parse(arguments[1])
                if isinstance(candidate, sp.Symbol):
                    variable = candidate
        if operation == "derivative":
            derivative = sp.diff(source, variable)
            terms = source.args if isinstance(source, sp.Add) else (source,)
            for term in terms:
                steps.append(
                    (
                        f"Differentiate `{sp.sstr(term)}` using its derivative rule.",
                        rf"\frac{{d}}{{d{sp.latex(variable)}}}"
                        rf"\left({sp.latex(term)}\right)"
                        rf" = {sp.latex(sp.diff(term, variable))}",
                    )
                )
            steps.append(
                (
                    "Combine the differentiated terms.",
                    rf"\frac{{d}}{{d{sp.latex(variable)}}}"
                    rf"\left({sp.latex(source)}\right)"
                    rf" = {sp.latex(derivative)}",
                )
            )
        else:
            terms = source.args if isinstance(source, sp.Add) else (source,)
            for term in terms:
                steps.append(
                    (
                        f"Integrate `{sp.sstr(term)}`.",
                        rf"\int {sp.latex(term)}\,d{sp.latex(variable)}"
                        rf" = {sp.latex(sp.integrate(term, variable))}",
                    )
                )
            steps.append(
                (
                    "Add the constant of integration.",
                    rf"\int {sp.latex(source)}\,d{sp.latex(variable)}"
                    rf" = {sp.latex(expected)} + C",
                )
            )
        return steps, checkpoints

    if operation == "expression":
        command = re.match(r"^(factor|expand)\b", problem, re.IGNORECASE)
        expression_text = (
            re.sub(r"^(?:factor|expand)(?:\s+of)?\s*", "", problem, flags=re.IGNORECASE)
            if command
            else problem
        )
        expression_text = re.sub(
            r"(?<![.\w^])(?<!\*\*)(\d+)\s*/\s*(\d+)(?![.\w])",
            r"Rational(\1, \2)",
            expression_text,
        )
        expression = parse_expr(
            expression_text,
            local_dict=LOCAL_DICT,
            transformations=TRANSFORMATIONS,
            evaluate=False,
        )
        if command and command.group(1).lower() == "factor":
            result = sp.factor(expression)
            description = "Factor the expression."
            steps.append(
                (description, rf"{sp.latex(expression)} = {sp.latex(result)}")
            )
        elif command and command.group(1).lower() == "expand":
            result = sp.expand(expression)
            steps.append(
                ("Distribute products and combine terms.", rf"{sp.latex(expression)} = {sp.latex(result)}")
            )
        else:
            expanded = sp.expand(expression)
            if expanded != expression:
                steps.append(
                    (
                        "Expand products using the distributive property.",
                        rf"{sp.latex(expression)} = {sp.latex(expanded)}",
                    )
                )
            result = sp.simplify(expanded)
            steps.append(
                (
                    "Combine like terms and simplify.",
                    rf"{sp.latex(expanded)} = {sp.latex(result)}",
                )
            )
        return steps, checkpoints

    steps.append(
        (
            "Apply the appropriate rules to the given problem and compare "
            "the result with your answer.",
            rf"\text{{Canonical result: }}{sp.latex(expected)}",
        )
    )
    return steps, checkpoints


def _homework_step_diagnosis(submitted, expected, operation, checkpoints):
    if operation == "system" and isinstance(submitted, dict) and expected:
        solution = expected[0]
        missing = [variable for variable in solution if variable not in submitted]
        if missing:
            supplied = ", ".join(
                f"{variable} = {sp.sstr(value)}"
                for variable, value in submitted.items()
            )
            remaining = ", ".join(
                f"{variable} = {sp.sstr(solution[variable])}"
                for variable in missing
            )
            return (
                f"You entered `{supplied}`, which is only part of the system "
                f"solution. Substitute into the other equation to also find "
                f"`{remaining}`."
            )
    if isinstance(submitted, sp.Basic):
        for checkpoint in checkpoints:
            if _symbolically_equal(submitted, checkpoint["value"]):
                if checkpoint.get("kind") == "sign" and expected:
                    variable = checkpoint["variable"]
                    correct_value = expected[0][variable]
                    return (
                        f"You entered `{variable} = {sp.sstr(submitted)}`, which "
                        f"matches subtracting the right-hand sides "
                        f"`{checkpoint['equation']}`. To eliminate the variable "
                        f"with opposite signs, add the equations; this gives "
                        f"`{variable} = {sp.sstr(correct_value)}`."
                    )
                return (
                    f"You entered `{sp.sstr(submitted)}`, which is the right-hand "
                    f"side of `{checkpoint['equation']}`, not the solved variable. "
                    f"Check Step {checkpoint['step']}: divide both sides by the "
                    "variable's coefficient."
                )
        if isinstance(expected, sp.Basic) and sp.simplify(expected + submitted) == 0:
            return (
                f"You entered `{sp.sstr(submitted)}`, the sign-reversed form of "
                f"the expected result `{sp.sstr(expected)}`."
            )
        if operation in {"equation", "system"} and expected:
            solution = expected[0]
            if len(solution) == 1:
                variable, value = next(iter(solution.items()))
                return (
                    f"You entered `{sp.sstr(submitted)}`, but solving for "
                    f"`{variable}` gives `{sp.sstr(value)}`. Check the numbered "
                    "steps for the rearrangement and division."
                )
    if isinstance(submitted, dict) and expected:
        solution = expected[0]
        incorrect = [
            f"{variable} = {sp.sstr(value)}"
            for variable, value in submitted.items()
            if variable in solution
            and not _symbolically_equal(solution[variable], value)
        ]
        if incorrect:
            return (
                f"You entered `{', '.join(incorrect)}`; the problem gives "
                + ", ".join(
                    f"`{variable} = {sp.sstr(solution[variable])}`"
                    for variable, _ in submitted.items()
                    if variable in solution
                )
                + ". Check the walkthrough for the step where the values diverge."
            )
    return ""


def check_homework(original: str, attempt: str):
    """Compare an attempt with the solver's canonical result and explain differences."""
    expected, operation, source = parse_homework_expression(original)
    submitted = _parse_homework_attempt(attempt)
    expected_text = _homework_value_text(expected)
    submitted_text = _homework_value_text(submitted)
    walkthrough, checkpoints = _homework_walkthrough(
        original, expected, operation, source
    )

    if operation == "integral" and not isinstance(submitted, (dict, list)):
        derivative = sp.diff(submitted, x)
        if sp.simplify(derivative - source) == 0:
            if sp.Symbol("C") not in submitted.free_symbols:
                mistake = (
                    f"Your expression `{submitted_text}` differentiates to the "
                    f"integrand, but an indefinite integral also needs the "
                    "arbitrary constant `+ C`."
                )
                return {
                    "status": "almost",
                    "expected": expected_text + " + C",
                    "parsed_attempt": submitted_text,
                    "mistake": mistake,
                    "walkthrough": walkthrough,
                }
            return {
                "status": "correct",
                "expected": expected_text + " + C",
                "parsed_attempt": submitted_text,
                "mistake": "Correct antiderivative, including the constant of integration.",
                "walkthrough": walkthrough,
            }

    if _solutions_match(expected, submitted):
        return {
            "status": "correct",
            "expected": expected_text,
            "parsed_attempt": submitted_text,
            "mistake": "Equivalent to the canonical result.",
            "walkthrough": walkthrough,
        }

    if operation in {"system", "equation"} and isinstance(submitted, dict) and expected:
        if any(
            (set(solution) > set(submitted) or len(expected) > 1)
            and all(
                variable in solution and _symbolically_equal(solution[variable], value)
                for variable, value in submitted.items()
            )
            for solution in expected
        ):
            if operation == "system":
                mistake = _homework_step_diagnosis(
                    submitted, expected, operation, checkpoints
                ) or "Partial solution: include values for every variable in the system."
            else:
                missing_values = [
                    value
                    for solution in expected
                    for value in solution.values()
                    if not any(
                        _symbolically_equal(value, submitted_value)
                        for submitted_value in submitted.values()
                    )
                ]
                variable = next(iter(expected[0]))
                mistake = (
                    f"You entered `{_homework_value_text(submitted)}`, which is "
                    f"one solution, but `{variable} = "
                    f"{', '.join(sp.sstr(value) for value in missing_values)}` "
                    "is also required."
                )
        else:
            mistake = ""
    else:
        mistake = ""

    if not mistake and isinstance(expected, sp.Basic) and isinstance(submitted, sp.Basic):
        if sp.simplify(expected + submitted) == 0:
            mistake = "Sign flip: your answer is the negative of the expected result."
    if not mistake and any(
        expression.has(sp.sin, sp.cos, sp.tan)
        for expression in (expected, submitted)
        if isinstance(expression, sp.Basic)
    ):
        mistake = (
            "Possible degree/radian mismatch: SymPy uses radians for trigonometric "
            "functions; convert degree inputs to radians."
        )
    if not mistake:
        simplified_expected = sp.simplify(expected) if isinstance(expected, sp.Basic) else expected
        simplified_submitted = sp.simplify(submitted) if isinstance(submitted, sp.Basic) else submitted
        mistake = (
            f"You entered `{_homework_value_text(simplified_submitted)}`, but the "
            f"problem's result is `{_homework_value_text(simplified_expected)}`. "
            "Compare the numbered steps to find where your work differs."
        )
    step_diagnosis = _homework_step_diagnosis(
        submitted, expected, operation, checkpoints
    )
    if step_diagnosis:
        mistake = step_diagnosis
    return {
        "status": "incorrect",
        "expected": expected_text,
        "parsed_attempt": submitted_text,
        "mistake": mistake,
        "walkthrough": walkthrough,
    }


def study_sheet_markdown(reports):
    lines = ["# OmniMath Study Sheet", ""]
    for index, report in enumerate(reports, 1):
        answer = report["answer"]
        if "\n" in answer or (
            re.search(r"[A-Za-z]", answer)
            and not re.search(r"\\[A-Za-z]+", answer)
            and re.search(r"[A-Za-z]{3,}", answer)
        ):
            formatted_answer = f"```text\n{answer}\n```"
        else:
            formatted_answer = f"$$\n{answer}\n$$"
        lines.extend(
            [
                f"## Problem {index}: {report['query']}",
                "",
                "### Final answer",
                "",
                formatted_answer,
                "",
                "### Step-by-step solution",
            ]
        )
        if report["steps"]:
            lines.extend(
                f"{step_index}. {step}"
                for step_index, step in enumerate(report["steps"], 1)
            )
        else:
            lines.append("No step-by-step explanation is available for this result.")
        lines.append("")
    return "\n".join(lines)


def handle_universal_query(raw_query: str):
    query = raw_query.strip()
    if not query:
        return

    capture = {"query": query, "answer": "", "steps": []}
    st.session_state["_solution_capture"] = capture
    try:
        _handle_universal_query(raw_query)
    finally:
        st.session_state.pop("_solution_capture", None)

    if not capture["answer"]:
        st.session_state["solution_report"] = None
        return

    st.session_state["solution_report"] = capture
    history = st.session_state.setdefault("calculation_history", [])
    if not any(
        item["query"] == capture["query"] and item["answer"] == capture["answer"]
        for item in history
    ):
        history.append(dict(capture))
    st.download_button(
        "Download solution (.txt)",
        solution_report_text(capture),
        file_name="omnimath-solution.txt",
        mime="text/plain",
        key="download_solution_txt",
    )
    st.download_button(
        "Download solution (.md)",
        solution_report_markdown(capture),
        file_name="omnimath-solution.md",
        mime="text/markdown",
        key="download_solution_md",
    )


def system_substitution_steps(eqs, variables):
    first_variable, second_variable = variables
    isolated_values = sp.solve(eqs[0], first_variable)
    if len(isolated_values) != 1 or isolated_values[0].has(first_variable):
        return None

    isolated_value = isolated_values[0]
    if isolated_value.free_symbols - {second_variable}:
        return None

    def substitute_in_latex(expr, variable, replacement):
        latex_expr = sp.latex(expr)
        latex_variable = re.escape(sp.latex(variable))
        pattern = rf"(?<![A-Za-z]){latex_variable}(?![A-Za-z])"
        latex_replacement = sp.latex(replacement)
        if not (replacement.is_Atom and replacement.is_nonnegative is True):
            latex_replacement = rf"\left({latex_replacement}\right)"
        return re.sub(pattern, lambda _: latex_replacement, latex_expr)

    substituted_equation = " = ".join(
        substitute_in_latex(side, first_variable, isolated_value)
        for side in (eqs[1].lhs, eqs[1].rhs)
    )
    simplified_sides = tuple(
        sp.simplify(side.subs(first_variable, isolated_value))
        for side in (eqs[1].lhs, eqs[1].rhs)
    )
    steps = [
        rf"\text{{Equation 1: }}{sp.latex(eqs[0])}",
        rf"{sp.latex(first_variable)} = {sp.latex(isolated_value)}",
        rf"\text{{Substitute into equation 2: }}{substituted_equation}",
        r"\text{Simplify: }" + " = ".join(sp.latex(side) for side in simplified_sides),
    ]

    second_values = sp.solve(sp.Eq(*simplified_sides, evaluate=False), second_variable)
    if len(second_values) == 1 and not second_values[0].has(second_variable):
        second_value = second_values[0]
        first_value = sp.simplify(isolated_value.subs(second_variable, second_value))
        evaluated_isolation = substitute_in_latex(
            isolated_value, second_variable, second_value
        )
        steps.extend(
            [
                rf"{sp.latex(second_variable)} = {sp.latex(second_value)}",
                rf"{sp.latex(first_variable)} = {evaluated_isolation} = {sp.latex(first_value)}",
            ]
        )
    return steps


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


def _real_numeric_value(value):
    evaluated = complex(sp.N(value))
    if abs(evaluated.imag) > 1e-10 or not math.isfinite(evaluated.real):
        raise ValueError("The expression must evaluate to finite real values.")
    return float(evaluated.real)


def _evaluate_real_function(expression, values):
    function = sp.lambdify(x, expression, modules=["numpy"])
    with np.errstate(all="ignore"):
        result = np.asarray(function(values))
    if np.iscomplexobj(result):
        if np.any(np.abs(np.imag(result)) > 1e-10):
            raise ValueError("The function has non-real values in the selected range.")
        result = np.real(result)
    if result.ndim == 0:
        result = np.full_like(values, float(result), dtype=float)
    else:
        result = np.broadcast_to(result, values.shape).astype(float)
    return np.where(np.isfinite(result), result, np.nan)


def render_riemann_visualizer():
    st.subheader("Riemann Sum Visualizer")
    expression_text = st.text_input(
        "Function f(x)",
        value="x^2",
        key="riemann_expression",
    )
    columns = st.columns(2)
    with columns[0]:
        lower_text = st.text_input("Lower bound a", value="0", key="riemann_lower")
    with columns[1]:
        upper_text = st.text_input("Upper bound b", value="3", key="riemann_upper")
    method = st.selectbox(
        "Rectangle sample point",
        ["Left", "Right", "Midpoint"],
        key="riemann_method",
    )
    rectangle_count = st.slider(
        "Number of rectangles (n)",
        min_value=2,
        max_value=100,
        value=12,
        key="riemann_n",
    )

    try:
        expression = clean_and_parse(expression_text)
        if expression.free_symbols - {x}:
            raise ValueError("Use x as the only variable in f(x).")
        lower = _real_numeric_value(clean_and_parse(lower_text))
        upper = _real_numeric_value(clean_and_parse(upper_text))
        if upper <= lower:
            raise ValueError("The upper bound must be greater than the lower bound.")

        width = (upper - lower) / rectangle_count
        left_edges = lower + np.arange(rectangle_count) * width
        if method == "Left":
            samples = left_edges
            centers = left_edges + width / 2
        elif method == "Right":
            samples = left_edges + width
            centers = left_edges + width / 2
        else:
            samples = left_edges + width / 2
            centers = samples

        heights = _evaluate_real_function(expression, samples)
        if not np.all(np.isfinite(heights)):
            raise ValueError("The function is undefined at one or more rectangle sample points.")
        approximation = float(np.sum(heights) * width)
        exact_value = None
        exact_integral = sp.integrate(expression, (x, lower, upper))
        try:
            exact_value = _real_numeric_value(exact_integral)
        except (TypeError, ValueError, OverflowError):
            pass

        curve_x = np.linspace(lower, upper, 600)
        curve_y = _evaluate_real_function(expression, curve_x)
        figure = go.Figure()
        figure.add_trace(
            go.Bar(
                x=centers,
                y=heights,
                width=width,
                base=0,
                name=f"{method} rectangles",
                opacity=0.38,
                marker_line={"color": theme_colors["accent"], "width": 1},
            )
        )
        figure.add_trace(
            go.Scatter(x=curve_x, y=curve_y, mode="lines", name="f(x)")
        )
        figure.update_layout(
            title=f"{method} Riemann sum (n = {rectangle_count})",
            xaxis_title="x",
            yaxis_title="f(x)",
            barmode="overlay",
            legend={"orientation": "h"},
        )
        st.plotly_chart(figure, width="stretch", key="riemann_plot")
        metric_columns = st.columns(2)
        metric_columns[0].metric("Riemann sum", f"{approximation:.8g}")
        if exact_value is not None:
            metric_columns[1].metric("Exact definite integral", f"{exact_value:.8g}")
        else:
            metric_columns[1].metric("Exact definite integral", "Not available")
    except (SyntaxError, TypeError, ValueError, NameError, ZeroDivisionError) as exc:
        st.error(f"Could not build the Riemann sum: {exc}")


def render_taylor_visualizer():
    st.subheader("Taylor Series Approximator")
    expression_text = st.text_input(
        "Function f(x)",
        value="sin(x)",
        key="taylor_expression",
    )
    columns = st.columns(3)
    with columns[0]:
        center_text = st.text_input("Center a", value="0", key="taylor_center")
    with columns[1]:
        degree = st.slider(
            "Taylor polynomial degree",
            min_value=0,
            max_value=12,
            value=4,
            key="taylor_degree",
        )
    with columns[2]:
        span = st.slider(
            "Plot half-width",
            min_value=1.0,
            max_value=10.0,
            value=5.0,
            step=0.5,
            key="taylor_span",
        )

    try:
        expression = clean_and_parse(expression_text)
        if expression.free_symbols - {x}:
            raise ValueError("Use x as the only variable in f(x).")
        center_expr = clean_and_parse(center_text)
        if center_expr.free_symbols:
            raise ValueError("The Taylor center must be a numeric value.")
        center = _real_numeric_value(center_expr)
        polynomial = sp.series(
            expression, x, center_expr, degree + 1
        ).removeO()
        plot_x = np.linspace(center - span, center + span, 600)
        function_y = _evaluate_real_function(expression, plot_x)
        polynomial_y = _evaluate_real_function(polynomial, plot_x)
        figure = go.Figure()
        figure.add_trace(
            go.Scatter(x=plot_x, y=function_y, mode="lines", name="f(x)")
        )
        figure.add_trace(
            go.Scatter(
                x=plot_x,
                y=polynomial_y,
                mode="lines",
                name=f"Degree {degree} Taylor polynomial",
                line={"dash": "dash"},
            )
        )
        figure.add_vline(
            x=center, line_dash="dot", line_color=theme_colors["accent"]
        )
        figure.update_layout(
            title=f"Taylor approximation around x = {center:g}",
            xaxis_title="x",
            yaxis_title="y",
            legend={"orientation": "h"},
        )
        st.plotly_chart(figure, width="stretch", key="taylor_plot")
        st.latex(r"T_{" + str(degree) + r"}(x) = " + sp.latex(polynomial))
    except (SyntaxError, TypeError, ValueError, NameError, ZeroDivisionError) as exc:
        st.error(f"Could not build the Taylor approximation: {exc}")


def render_surface_grapher():
    st.subheader("Interactive 3D Surface")
    expression_text = st.text_input(
        "Enter z = f(x, y)",
        key="surface_expression",
    )
    x_range = st.slider(
        "x range",
        min_value=-10.0,
        max_value=10.0,
        step=0.5,
        key="surface_x_range",
    )
    y_range = st.slider(
        "y range",
        min_value=-10.0,
        max_value=10.0,
        step=0.5,
        key="surface_y_range",
    )
    colorscale = st.selectbox(
        "Colorscale",
        ["Viridis", "Plasma", "Inferno", "Cividis"],
        key="surface_colorscale",
    )

    try:
        expression = clean_and_parse(expression_text)
        unsupported_symbols = expression.free_symbols - {x, y}
        if unsupported_symbols:
            st.error(
                "Use only x and y as variables in the surface expression: "
                + ", ".join(sorted(str(symbol) for symbol in unsupported_symbols))
            )
            return
        x_derivative = sp.diff(expression, x)
        y_derivative = sp.diff(expression, y)
        x_values = np.linspace(x_range[0], x_range[1], 70)
        y_values = np.linspace(y_range[0], y_range[1], 70)
        x_mesh, y_mesh = np.meshgrid(x_values, y_values)
        surface_function = sp.lambdify((x, y), expression, modules=["numpy"])
        with np.errstate(all="ignore"):
            z_mesh = np.asarray(surface_function(x_mesh, y_mesh))
        if np.iscomplexobj(z_mesh):
            if np.any(np.abs(np.imag(z_mesh)) > 1e-12):
                raise ValueError("The surface expression must evaluate to real values.")
            z_mesh = np.real(z_mesh)
        if z_mesh.ndim == 0:
            z_mesh = np.full_like(x_mesh, float(z_mesh))
        else:
            z_mesh = np.broadcast_to(z_mesh, x_mesh.shape).astype(float)
        z_mesh = np.where(np.isfinite(z_mesh), z_mesh, np.nan)
    except Exception as exc:
        st.error(f"Could not evaluate this surface expression: {exc}")
        return

    figure = go.Figure(
        data=[
            go.Surface(
                x=x_mesh,
                y=y_mesh,
                z=z_mesh,
                colorscale=colorscale,
                colorbar={"title": "z"},
            )
        ]
    )
    figure.update_layout(
        title=f"z = {expression_text}",
        scene={
            "xaxis_title": "x",
            "yaxis_title": "y",
            "zaxis_title": "z",
        },
        margin={"l": 0, "r": 0, "t": 45, "b": 0},
    )
    st.plotly_chart(figure, width="stretch", key="surface_plot")
    st.latex(r"\frac{\partial z}{\partial x} = " + sp.latex(x_derivative))
    st.latex(r"\frac{\partial z}{\partial y} = " + sp.latex(y_derivative))


def projectile_trajectory(speed, angle_degrees, gravity, drag_coefficient):
    angle = math.radians(angle_degrees)
    state = np.array(
        [0.0, 0.0, speed * math.cos(angle), speed * math.sin(angle)],
        dtype=float,
    )
    time_step = 0.02
    trajectory = [state.copy()]
    flight_time = 0.0

    def derivative(current_state):
        _, _, velocity_x, velocity_y = current_state
        velocity = math.hypot(velocity_x, velocity_y)
        return np.array(
            [
                velocity_x,
                velocity_y,
                -drag_coefficient * velocity * velocity_x,
                -gravity - drag_coefficient * velocity * velocity_y,
            ]
        )

    for step in range(1, 10001):
        k1 = derivative(state)
        k2 = derivative(state + time_step * k1 / 2)
        k3 = derivative(state + time_step * k2 / 2)
        k4 = derivative(state + time_step * k3)
        next_state = state + time_step * (k1 + 2 * k2 + 2 * k3 + k4) / 6
        if next_state[1] <= 0:
            fraction = state[1] / (state[1] - next_state[1])
            state = state + fraction * (next_state - state)
            state[1] = 0.0
            flight_time = (step - 1 + fraction) * time_step
            trajectory.append(state.copy())
            break
        state = next_state
        flight_time = step * time_step
        trajectory.append(state.copy())
    return np.asarray(trajectory), flight_time


def render_projectile_simulator():
    st.subheader("Projectile Motion with Air Drag")
    velocity = st.slider(
        "Launch velocity (m/s)",
        min_value=1.0,
        max_value=100.0,
        step=1.0,
        key="projectile_velocity",
    )
    angle = st.slider(
        "Launch angle (degrees)",
        min_value=0.0,
        max_value=90.0,
        step=1.0,
        key="projectile_angle",
    )
    gravity = st.slider(
        "Gravity (m/s²)",
        min_value=1.0,
        max_value=20.0,
        step=0.1,
        key="projectile_gravity",
    )
    drag = st.slider(
        "Normalized quadratic drag coefficient (1/m)",
        min_value=0.0,
        max_value=0.2,
        step=0.005,
        key="projectile_drag",
    )

    angle_radians = math.radians(angle)
    ideal_flight_time = 2 * velocity * math.sin(angle_radians) / gravity
    ideal_time = np.linspace(0, ideal_flight_time, 300)
    ideal_x = velocity * math.cos(angle_radians) * ideal_time
    ideal_y = (
        velocity * math.sin(angle_radians) * ideal_time
        - 0.5 * gravity * ideal_time**2
    )
    drag_path, drag_flight_time = projectile_trajectory(
        velocity, angle, gravity, drag
    )
    drag_max_height = float(np.max(drag_path[:, 1]))
    drag_range = float(drag_path[-1, 0])

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(x=ideal_x, y=ideal_y, mode="lines", name="Ideal (no drag)")
    )
    figure.add_trace(
        go.Scatter(
            x=drag_path[:, 0],
            y=drag_path[:, 1],
            mode="lines",
            name="With air drag",
        )
    )
    figure.update_layout(
        title="Projectile Trajectory",
        xaxis_title="Horizontal distance (m)",
        yaxis_title="Height (m)",
        legend={"orientation": "h"},
    )
    st.plotly_chart(figure, width="stretch", key="projectile_plot")

    ideal_height = velocity**2 * math.sin(angle_radians) ** 2 / (2 * gravity)
    ideal_range = velocity**2 * math.sin(2 * angle_radians) / gravity
    metric_columns = st.columns(3)
    metric_columns[0].metric("Ideal max height", f"{ideal_height:.2f} m")
    metric_columns[1].metric("Ideal range", f"{ideal_range:.2f} m")
    metric_columns[2].metric("Ideal flight time", f"{ideal_flight_time:.2f} s")
    metric_columns = st.columns(3)
    metric_columns[0].metric("Drag max height", f"{drag_max_height:.2f} m")
    metric_columns[1].metric("Drag range", f"{drag_range:.2f} m")
    metric_columns[2].metric("Drag flight time", f"{drag_flight_time:.2f} s")


def render_oscillator_simulator():
    st.subheader("Damped Harmonic Oscillator")
    st.caption("Assumes an initial displacement of 1 m and an initial velocity of 0 m/s.")
    mass = st.slider(
        "Mass, m (kg)",
        min_value=0.1,
        max_value=10.0,
        step=0.1,
        key="oscillator_mass",
    )
    spring = st.slider(
        "Spring constant, k (N/m)",
        min_value=0.1,
        max_value=50.0,
        step=0.1,
        key="oscillator_spring",
    )
    damping = st.slider(
        "Damping coefficient, c (N·s/m)",
        min_value=0.0,
        max_value=20.0,
        step=0.1,
        key="oscillator_damping",
    )

    time = np.linspace(0, 10, 1000)
    discriminant = damping**2 - 4 * mass * spring
    tolerance = 1e-12 * max(damping**2, 4 * mass * spring, 1.0)
    if discriminant < -tolerance:
        damping_rate = -damping / (2 * mass)
        damped_frequency = math.sqrt(4 * mass * spring - damping**2) / (2 * mass)
        sine_coefficient = -damping_rate / damped_frequency
        envelope = np.exp(damping_rate * time)
        displacement = envelope * (
            np.cos(damped_frequency * time)
            + sine_coefficient * np.sin(damped_frequency * time)
        )
        velocity = (
            -envelope
            * (damping_rate**2 + damped_frequency**2)
            / damped_frequency
            * np.sin(damped_frequency * time)
        )
        system_type = "underdamped"
    elif discriminant > tolerance:
        root = math.sqrt(discriminant)
        root_1 = (-damping + root) / (2 * mass)
        root_2 = (-damping - root) / (2 * mass)
        coefficient_1 = -root_2 / (root_1 - root_2)
        coefficient_2 = root_1 / (root_1 - root_2)
        term_1 = coefficient_1 * np.exp(root_1 * time)
        term_2 = coefficient_2 * np.exp(root_2 * time)
        displacement = term_1 + term_2
        velocity = root_1 * term_1 + root_2 * term_2
        system_type = "overdamped"
    else:
        repeated_root = -damping / (2 * mass)
        envelope = np.exp(repeated_root * time)
        displacement = (1 - repeated_root * time) * envelope
        velocity = -(repeated_root**2) * time * envelope
        system_type = "critically damped"

    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Scatter(x=time, y=displacement, name="Displacement x(t)"),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(x=time, y=velocity, name="Velocity v(t)"),
        secondary_y=True,
    )
    figure.update_layout(
        title="Spring-Mass-Damper Response",
        legend={"orientation": "h"},
    )
    figure.update_xaxes(title_text="Time (s)")
    figure.update_yaxes(title_text="Displacement (m)", secondary_y=False)
    figure.update_yaxes(title_text="Velocity (m/s)", secondary_y=True)
    st.plotly_chart(figure, width="stretch", key="oscillator_plot")
    st.info(f"The system is {system_type}.")


def render_circuit_simulator():
    st.subheader("RC / RLC Circuit Transient Response")
    resistance = st.slider(
        "Resistance, R (Ω)",
        min_value=1.0,
        max_value=1000.0,
        step=1.0,
        key="circuit_resistance",
    )
    inductance = st.slider(
        "Inductance, L (H; set to 0 for an RC circuit)",
        min_value=0.0,
        max_value=5.0,
        step=0.01,
        key="circuit_inductance",
    )
    capacitance = st.slider(
        "Capacitance, C (F)",
        min_value=0.0001,
        max_value=0.01,
        step=0.0001,
        format="%.4f",
        key="circuit_capacitance",
    )
    voltage = st.slider(
        "Input voltage (V)",
        min_value=1.0,
        max_value=240.0,
        step=1.0,
        key="circuit_voltage",
    )

    if inductance == 0:
        time_constant = resistance * capacitance
        duration = max(5 * time_constant, 0.1)
        time = np.linspace(0, duration, 1000)
        capacitor_voltage = voltage * (1 - np.exp(-time / time_constant))
        current = voltage / resistance * np.exp(-time / time_constant)
        response_type = "RC response"
    else:
        natural_frequency_squared = 1 / (inductance * capacitance)
        damping_rate = resistance / (2 * inductance)
        discriminant = damping_rate**2 - natural_frequency_squared
        duration = max(
            5 * resistance * capacitance,
            10 * math.pi * math.sqrt(inductance * capacitance),
            0.1,
        )
        time = np.linspace(0, duration, 1200)
        if discriminant < -1e-12 * natural_frequency_squared:
            damped_frequency = math.sqrt(-discriminant)
            envelope = np.exp(-damping_rate * time)
            capacitor_voltage = voltage * (
                1
                - envelope
                * (
                    np.cos(damped_frequency * time)
                    + damping_rate
                    / damped_frequency
                    * np.sin(damped_frequency * time)
                )
            )
            current = (
                voltage
                / (inductance * damped_frequency)
                * envelope
                * np.sin(damped_frequency * time)
            )
            response_type = "underdamped RLC response"
        elif discriminant > 1e-12 * natural_frequency_squared:
            root = math.sqrt(discriminant)
            root_1 = -damping_rate + root
            root_2 = -damping_rate - root
            coefficient_1 = root_2 / (root_1 - root_2)
            coefficient_2 = -root_1 / (root_1 - root_2)
            exponential_1 = np.exp(root_1 * time)
            exponential_2 = np.exp(root_2 * time)
            capacitor_voltage = voltage * (
                1 + coefficient_1 * exponential_1 + coefficient_2 * exponential_2
            )
            current = voltage * capacitance * (
                coefficient_1 * root_1 * exponential_1
                + coefficient_2 * root_2 * exponential_2
            )
            response_type = "overdamped RLC response"
        else:
            envelope = np.exp(-damping_rate * time)
            capacitor_voltage = voltage * (
                1 - (1 + damping_rate * time) * envelope
            )
            current = (
                voltage
                * capacitance
                * damping_rate**2
                * time
                * envelope
            )
            response_type = "critically damped RLC response"

    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Scatter(x=time, y=capacitor_voltage, name="Capacitor voltage"),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(x=time, y=current, name="Circuit current"),
        secondary_y=True,
    )
    figure.update_layout(
        title=f"Circuit Step Response ({response_type})",
        legend={"orientation": "h"},
    )
    figure.update_xaxes(title_text="Time (s)")
    figure.update_yaxes(title_text="Capacitor voltage (V)", secondary_y=False)
    figure.update_yaxes(title_text="Current (A)", secondary_y=True)
    st.plotly_chart(figure, width="stretch", key="circuit_plot")
    st.info(response_type[0].upper() + response_type[1:] + ".")


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
def _handle_universal_query(raw_query: str):
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
            record_solution_answer(f"{val} {u1} = {res:.6g} {u2}")
            record_solution_steps([f"Convert {val} {u1} to {res:.6g} {u2}."])
            return
        st.warning("Those units are incompatible or not recognized.")
        return

    # 2. System of Equations separated by ';' or ','
    if re.search(r"[;,]", q) and "=" in q:
        system_query = re.sub(r"\bgraph\b", "", q, flags=re.IGNORECASE)
        parts = [p.strip() for p in re.split(r"[;,]", system_query) if p.strip()]
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
            record_solution_answer(
                "; ".join(
                    ", ".join(f"{key} = {sp.latex(value)}" for key, value in solution.items())
                    for solution in sol
                )
            )
            with st.expander("Show Step-by-Step Solution"):
                variables = sorted(all_syms, key=str)
                steps = (
                    system_substitution_steps(eqs, variables)
                    if len(eqs) == 2 and len(variables) == 2
                    else None
                )
                if steps:
                    record_solution_steps(steps)
                    for step in steps:
                        st.latex(step)
                else:
                    fallback_step = (
                        "Substitution steps are available when equation 1 uniquely "
                        "isolates the first variable in a two-variable system."
                    )
                    record_solution_steps([fallback_step])
                    st.write(fallback_step)
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
                if "graph" in q_lower:
                    render_plot(
                        y_exprs,
                        labels,
                        x_center - 10,
                        x_center + 10,
                        pts,
                        "System Intersection",
                    )
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
            record_solution_answer(sp.latex(solution))
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
            record_solution_answer(sp.latex(result))
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
            record_solution_answer(sp.latex(result))
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
                record_solution_answer(sp.latex(result))
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
            record_solution_answer(str(result))
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
            record_solution_answer(
                "\n".join(f"{label}: {value}" for label, value in results.items())
            )
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
            record_solution_answer(str(result))
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
            record_solution_answer(str(result))
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
        record_solution_answer(", ".join(labels))
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
            record_solution_answer(f"{sp.latex(var)} = {sp.latex(sols)}")
            moved = sp.expand(lhs - rhs)
            factored = sp.factor(moved)
            steps = [
                "Move all terms to the left-hand side and set the equation equal to zero.",
                sp.latex(moved) + " = 0",
                "Factor the left-hand side.",
                sp.latex(factored) + " = 0",
                "Set each factor equal to zero and solve for the variable.",
                sp.latex(var) + " = " + sp.latex(sols),
            ]
            record_solution_steps(steps)
            with st.expander("Step-by-Step Explanation", expanded=True):
                st.write(steps[0])
                st.latex(steps[1])
                st.write(steps[2])
                st.latex(steps[3])
                st.write(steps[4])
                st.latex(steps[5])
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
            record_solution_answer(sp.latex(res) + " + C")
            if isinstance(expr, sp.Add):
                initial_step = "Use linearity to integrate each term separately."
            elif isinstance(expr, sp.Pow) and expr.base == x:
                initial_step = "Apply the power antiderivative rule: increase the exponent by one, then divide by the new exponent."
            else:
                initial_step = "Apply the corresponding standard antiderivative rule to the expression."
            steps = [
                initial_step,
                "Add the constant of integration, + C.",
                r"\frac{d}{dx}\left(" + sp.latex(res) + r"\right) = " + sp.latex(sp.diff(res, x)),
            ]
            record_solution_steps(steps)
            with st.expander("Step-by-Step Explanation", expanded=True):
                st.write(steps[0])
                st.write(steps[1])
                st.latex(steps[2])
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
            record_solution_answer(sp.latex(res))
            record_solution_steps(
                [rf"\lim_{{x \to {sp.latex(pt)}}} \left({sp.latex(expr)}\right) = {sp.latex(res)}"]
            )
        except Exception:
            st.warning("Could not evaluate that limit.")
        return

    # 8. Factor
    if re.match(r"^factor\b", cleaned, re.I):
        try:
            expr = clean_and_parse(re.sub(r"^factor(?:\s+of)?\s*", "", cleaned, flags=re.I))
            result = sp.factor(expr)
            st.subheader("Factored Form")
            st.latex(sp.latex(expr) + " = " + sp.latex(result))
            record_solution_answer(sp.latex(result))
            record_solution_steps([sp.latex(expr) + " = " + sp.latex(result)])
        except Exception:
            st.warning("Could not factor that expression.")
        return

    # 9. Expand
    if re.match(r"^expand\b", cleaned, re.I):
        try:
            expr = clean_and_parse(re.sub(r"^expand(?:\s+of)?\s*", "", cleaned, flags=re.I))
            result = sp.expand(expr)
            st.subheader("Expanded Form")
            st.latex(sp.latex(expr) + " = " + sp.latex(result))
            record_solution_answer(sp.latex(result))
            record_solution_steps([sp.latex(expr) + " = " + sp.latex(result)])
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
            record_solution_answer(sp.latex(d1))
            steps = derivative_steps(expr, d1)
            record_solution_steps(steps)
            with st.expander("Step-by-Step Explanation", expanded=True):
                for step in steps:
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
        record_solution_answer(sp.latex(simplified))
        if not simplified.free_symbols:
            steps = arithmetic_steps(arith_query)
            record_solution_steps(steps)
            with st.expander("Step-by-Step Explanation", expanded=True):
                for step in steps:
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


def extract_math_text(image_file):
    try:
        image_file.seek(0)
        image = Image.open(image_file).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        st.error(f"Could not read the selected image: {exc}")
        return

    try:
        extracted_text = pytesseract.image_to_string(image, config="--psm 6").strip()
    except pytesseract.TesseractNotFoundError:
        st.error("Tesseract OCR is unavailable. Install the tesseract-ocr system package.")
        return
    except pytesseract.TesseractError as exc:
        st.error(f"OCR could not process this image: {exc}")
        return

    extracted_text = re.sub(r"\s+", " ", extracted_text)
    if not extracted_text:
        st.warning("No math text was detected. Try a clearer, well-lit image.")
        return

    st.session_state["query_input"] = extracted_text
    st.success("Text extracted. Review or edit it in the query box below.")


def _query_value(query_name):
    value = st.query_params.get(query_name)
    return value if isinstance(value, str) else None


def _seed_query_widget(
    state_key, query_name, parser, default, previous_query
):
    raw_value = _query_value(query_name)
    if (
        state_key in st.session_state
        and raw_value == previous_query.get(query_name)
    ):
        return None
    if raw_value is None:
        if query_name in previous_query:
            st.session_state[state_key] = default
        return None
    try:
        st.session_state[state_key] = parser(raw_value)
    except (TypeError, ValueError):
        st.session_state[state_key] = default
        return query_name
    return None


def initialize_shareable_state():
    invalid_parameters = []

    def choice_parser(choices):
        def parse(value):
            if value not in choices:
                raise ValueError(f"Expected one of {sorted(choices)}")
            return value

        return parse

    parsers = {
        "query_input": ("q", lambda value: value),
        "surface_expression": ("fx", lambda value: value),
        "surface_colorscale": (
            "cs",
            choice_parser({"Viridis", "Plasma", "Inferno", "Cividis"}),
        ),
        "physics_simulator": (
            "sim",
            choice_parser(
                {
                    "Projectile Motion with Air Drag",
                    "Damped Harmonic Oscillator",
                    "RC / RLC Circuit Transient Response",
                }
            ),
        ),
    }

    def bounded_float(minimum, maximum):
        def parse(value):
            number = float(value)
            if not minimum <= number <= maximum:
                raise ValueError("Value outside widget range")
            return number

        return parse

    def bounded_range(value):
        parts = [float(part) for part in value.split(",")]
        if (
            len(parts) != 2
            or not -10 <= parts[0] < parts[1] <= 10
        ):
            raise ValueError("Range outside widget limits")
        return tuple(parts)

    parsers.update(
        {
            "surface_x_range": ("xr", bounded_range),
            "surface_y_range": ("yr", bounded_range),
            "projectile_velocity": ("v", bounded_float(1, 100)),
            "projectile_angle": ("angle", bounded_float(0, 90)),
            "projectile_gravity": ("g", bounded_float(1, 20)),
            "projectile_drag": ("drag", bounded_float(0, 0.2)),
            "oscillator_mass": ("mass", bounded_float(0.1, 10)),
            "oscillator_spring": ("spring", bounded_float(0.1, 50)),
            "oscillator_damping": ("damping", bounded_float(0, 20)),
            "circuit_resistance": ("resistance", bounded_float(1, 1000)),
            "circuit_inductance": ("inductance", bounded_float(0, 5)),
            "circuit_capacitance": ("capacitance", bounded_float(0.0001, 0.01)),
            "circuit_voltage": ("voltage", bounded_float(1, 240)),
        }
    )
    defaults = {
        "query_input": "",
        "surface_expression": "sin(sqrt(x^2 + y^2))",
        "surface_x_range": (-5.0, 5.0),
        "surface_y_range": (-5.0, 5.0),
        "surface_colorscale": "Viridis",
        "physics_simulator": "Projectile Motion with Air Drag",
        "projectile_velocity": 50.0,
        "projectile_angle": 45.0,
        "projectile_gravity": 9.8,
        "projectile_drag": 0.02,
        "oscillator_mass": 1.0,
        "oscillator_spring": 20.0,
        "oscillator_damping": 2.0,
        "circuit_resistance": 100.0,
        "circuit_inductance": 0.1,
        "circuit_capacitance": 0.001,
        "circuit_voltage": 12.0,
    }
    previous_query = st.session_state.get("_share_query_snapshot", {})
    for state_key, (query_name, parser) in parsers.items():
        invalid = _seed_query_widget(
            state_key,
            query_name,
            parser,
            defaults[state_key],
            previous_query,
        )
        if invalid:
            invalid_parameters.append(invalid)
    for state_key, default in defaults.items():
        st.session_state.setdefault(state_key, default)
    if invalid_parameters:
        st.sidebar.warning(
            "Ignored invalid share-link parameter(s): "
            + ", ".join(sorted(invalid_parameters))
        )


SHAREABLE_STATE = {
    "q": ("query_input", str),
    "fx": ("surface_expression", str),
    "xr": ("surface_x_range", lambda value: f"{value[0]:g},{value[1]:g}"),
    "yr": ("surface_y_range", lambda value: f"{value[0]:g},{value[1]:g}"),
    "cs": ("surface_colorscale", str),
    "sim": ("physics_simulator", str),
    "v": ("projectile_velocity", str),
    "angle": ("projectile_angle", str),
    "g": ("projectile_gravity", str),
    "drag": ("projectile_drag", str),
    "mass": ("oscillator_mass", str),
    "spring": ("oscillator_spring", str),
    "damping": ("oscillator_damping", str),
    "resistance": ("circuit_resistance", str),
    "inductance": ("circuit_inductance", str),
    "capacitance": ("circuit_capacitance", str),
    "voltage": ("circuit_voltage", str),
}


def sync_shareable_state():
    for query_name, (state_key, formatter) in SHAREABLE_STATE.items():
        if state_key not in st.session_state:
            continue
        value = formatter(st.session_state[state_key])
        if query_name == "q" and not value:
            if query_name in st.query_params:
                del st.query_params[query_name]
        elif _query_value(query_name) != value:
            st.query_params[query_name] = value
    st.session_state["_share_query_snapshot"] = {
        query_name: _query_value(query_name) for query_name in SHAREABLE_STATE
    }


def _tabs_with_query_params(labels, key):
    try:
        parameters = inspect.signature(st.tabs).parameters
    except (TypeError, ValueError):
        parameters = {}
    if "key" in parameters and "bind" in parameters:
        return st.tabs(labels, key=key, bind="query-params")
    return st.tabs(labels)


def _tab_is_open(tab):
    return getattr(tab, "open", True)


def render_notebook():
    st.subheader("Notebook / Scratchpad")
    source = st.text_area(
        "Enter one expression or assignment per line",
        value="v0 = 25\nt = 3.5\nd = v0*t - 0.5*9.8*t**2",
        height=150,
        key="scratchpad_input",
    )
    results = evaluate_notebook(source)
    if not results:
        st.caption("Results will appear here as you enter expressions.")
        return
    input_column, result_column = st.columns(2)
    input_column.markdown("**Input**")
    result_column.markdown("**Evaluated result**")
    for item in results:
        with input_column:
            st.write(f"{item['line_number']}. {item['input']}")
        with result_column:
            if "error" in item:
                st.error(f"Line {item['line_number']}: {item['error']}")
            else:
                st.latex(item["result"])


def render_homework_checker():
    st.subheader("Spot the Mistake")
    with st.form("homework_checker_form"):
        original = st.text_input(
            "Original Expression/Problem",
            placeholder="e.g. integrate x^2",
            key="homework_original",
        )
        attempt = st.text_input(
            "Your Attempt/Answer",
            placeholder="e.g. x^3/3",
            key="homework_attempt",
        )
        submitted = st.form_submit_button("Check my work")
    if submitted:
        if not original.strip() or not attempt.strip():
            st.session_state["homework_result"] = {
                "original": original,
                "attempt": attempt,
                "error": "Enter both the original problem and your answer.",
            }
        else:
            try:
                result = check_homework(original, attempt)
                st.session_state["homework_result"] = {
                    "original": original,
                    "attempt": attempt,
                    **result,
                }
            except (
                SyntaxError,
                TypeError,
                ValueError,
                NameError,
                ZeroDivisionError,
                sp.SympifyError,
            ) as exc:
                st.session_state["homework_result"] = {
                    "original": original,
                    "attempt": attempt,
                    "error": f"Could not parse the problem or answer: {exc}",
                }

    result = st.session_state.get("homework_result")
    if result and (
        result["original"] == original and result["attempt"] == attempt
    ):
        if "error" in result:
            st.error(result["error"])
        elif result["status"] == "correct":
            st.success(result["mistake"])
            st.markdown(f"**Expected Result:** `{result['expected']}`")
            st.markdown(f"**Your Parsed Answer:** `{result['parsed_attempt']}`")
        elif result["status"] == "almost":
            st.warning(result["mistake"])
            st.markdown(f"**Expected Result:** `{result['expected']}`")
            st.markdown(f"**Your Parsed Answer:** `{result['parsed_attempt']}`")
            render_homework_walkthrough(result.get("walkthrough", []))
        else:
            st.error("Your answer is not equivalent to the canonical result.")
            st.markdown(f"**Expected Result:** `{result['expected']}`")
            st.markdown(f"**Your Parsed Answer:** `{result['parsed_attempt']}`")
            st.markdown(f"**Likely Mistake:** {result['mistake']}")
            render_homework_walkthrough(result.get("walkthrough", []))


def render_homework_walkthrough(steps):
    if not steps:
        return
    st.markdown("### Step-by-Step Walkthrough")
    for index, (explanation, equation) in enumerate(steps, 1):
        st.markdown(f"**Step {index}:** {explanation}")
        st.latex(equation)


def render_visual_calculus():
    riemann_tab, taylor_tab = st.tabs(["Riemann Sums", "Taylor Series"])
    with riemann_tab:
        render_riemann_visualizer()
    with taylor_tab:
        render_taylor_visualizer()


def render_study_sheet():
    st.subheader("LaTeX / Markdown Study Sheet")
    history = st.session_state.get("calculation_history", [])
    if not history:
        st.info("Solved problems will appear here for selection and export.")
        return

    st.caption("Select the solved problems to include in your worksheet.")
    selected_reports = []
    for index, report in enumerate(history):
        label = f"{index + 1}. {report['query']}"
        if st.checkbox(label, key=f"history_select_{index}"):
            selected_reports.append(report)
    if selected_reports:
        st.download_button(
            "Download selected problems (.md)",
            study_sheet_markdown(selected_reports),
            file_name="omnimath-study-sheet.md",
            mime="text/markdown",
            key="download_study_sheet",
        )
    else:
        st.caption("Choose at least one problem to enable the download.")


def offline_calculator_html():
    """Return a browser-hosted Stlite page containing this app's source."""
    source_json = json.dumps(
        Path(__file__).read_text(encoding="utf-8")
    ).replace("<", "\\u003c")
    template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OmniMath Full Offline App</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/browser@0.90.0/build/stlite.css">
<style>
html, body, #root { margin: 0; min-height: 100%; }
body { background: #071a2c; color: #d9f0ff; font-family: sans-serif; }
#loading { padding: 2rem; text-align: center; }
</style>
</head>
<body>
<div id="root"><p id="loading">Loading OmniMath in your browser. Internet access is needed to fetch Stlite and Python packages.</p></div>
<script type="module">
import { mount } from "https://cdn.jsdelivr.net/npm/@stlite/browser@0.90.0/build/stlite.js";
const calculatorSource = __OMNIMATH_SOURCE_JSON__;
mount({
  entrypoint: "calculator.py",
  files: { "calculator.py": calculatorSource },
  requirements: ["sympy", "numpy", "plotly", "pandas", "matplotlib", "pillow", "pytesseract"],
  streamlitConfig: {
    "theme.base": "dark",
    "theme.primaryColor": "#62c6f2",
    "theme.backgroundColor": "#071a2c",
    "theme.secondaryBackgroundColor": "#12304a",
    "theme.textColor": "#d9f0ff",
    "client.toolbarMode": "viewer"
  }
}, document.getElementById("root"));
</script>
</body>
</html>
"""
    return template.replace("__OMNIMATH_SOURCE_JSON__", source_json)


st.sidebar.title("Math Reference Guide")
themes = {
    "Midnight Dark": {
        "background": "#10131d",
        "foreground": "#e8ecf5",
        "surface": "#1b2232",
        "accent": "#91a7ff",
    },
    "Clean Light": {
        "background": "#f7f8fb",
        "foreground": "#202536",
        "surface": "#ffffff",
        "accent": "#3157a4",
    },
    "Matrix Green": {
        "background": "#06120b",
        "foreground": "#c7f9cc",
        "surface": "#102318",
        "accent": "#50fa7b",
    },
    "Ocean Blue": {
        "background": "#071a2c",
        "foreground": "#d9f0ff",
        "surface": "#12304a",
        "accent": "#62c6f2",
    },
}
theme_index = list(themes).index("Ocean Blue") if sys.platform == "emscripten" else 0
selected_theme = st.sidebar.selectbox("Color theme", list(themes), index=theme_index)
theme_colors = themes[selected_theme]
st.sidebar.download_button(
    "Download Full OmniMath App (.html)",
    data=offline_calculator_html(),
    file_name="OmniMath_Full_Offline.html",
    mime="text/html",
    key="download_offline_calculator",
)
st.sidebar.download_button(
    "Download Instant JS Calculator (.html)",
    data=offline_js_calculator_html(),
    file_name="OmniMath_Instant_Offline.html",
    mime="text/html",
    key="download_instant_js_calculator",
)
configured_agent_provider, configured_agent_key = _configured_agent_api_key()
if configured_agent_key:
    st.sidebar.caption(
        f"AI Math Agent API key detected ({configured_agent_provider.title()})."
    )
else:
    with st.sidebar.expander("AI Math Agent API key"):
        st.selectbox(
            "Provider",
            ["Gemini", "OpenAI"],
            key="ai_agent_provider_choice",
        )
        st.session_state["ai_agent_provider"] = (
            "gemini"
            if st.session_state["ai_agent_provider_choice"] == "Gemini"
            else "openai"
        )
        st.text_input(
            "Optional API key",
            type="password",
            key="ai_agent_api_key",
            help="Leave blank to use the local SymPy math agent.",
        )
st.markdown(
    f"""
    <style>
    .stApp, [data-testid="stSidebar"] {{
        background-color: {theme_colors["background"]};
        color: {theme_colors["foreground"]};
    }}
    h1, h2, h3, label {{
        color: {theme_colors["accent"]} !important;
    }}
    .stTextInput input, .stTextArea textarea {{
        background-color: {theme_colors["surface"]};
        color: {theme_colors["foreground"]};
        border-color: {theme_colors["accent"]};
    }}
    div[data-testid="stLatex"] {{
        background-color: {theme_colors["surface"]};
        border-radius: 0.5rem;
        padding: 0.5rem;
    }}
    div[data-testid="stMarkdownContainer"] {{
        color: {theme_colors["foreground"]};
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

initialize_shareable_state()

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

solver_tab, surface_tab, simulators_tab, ai_agent_tab = _tabs_with_query_params(
    [
        "OmniMath Solver",
        "3D Surface Grapher",
        "Physics & Engineering Simulators",
        "AI Math Agent",
    ],
    key="active_tab",
)

if _tab_is_open(solver_tab):
    with solver_tab:
        calculator_tab, notebook_tab, checker_tab, calculus_tab, study_tab = st.tabs(
            [
                "Calculator",
                "Notebook / Scratchpad",
                "Spot the Mistake",
                "Visual Calculus",
                "Study Sheet",
            ]
        )

        with calculator_tab:
            with st.expander("Camera & Image Math Scanner"):
                uploaded_math_image = st.file_uploader(
                    "Upload a PNG or JPG image",
                    type=["png", "jpg", "jpeg"],
                    key="math_image_upload",
                )
                camera_math_image = st.camera_input(
                    "Take a picture of an equation",
                    key="math_camera_input",
                )
                if uploaded_math_image and st.button(
                    "Extract text from uploaded image",
                    key="extract_uploaded_math",
                ):
                    extract_math_text(uploaded_math_image)
                if camera_math_image and st.button(
                    "Extract text from camera image",
                    key="extract_camera_math",
                ):
                    extract_math_text(camera_math_image)

            st.title("OmniMath Calculator")
            user_input = st.text_input(
                "Enter a math expression or query (e.g., derivative of x^3):",
                key="query_input",
            )
            if user_input:
                handle_universal_query(user_input)

        with notebook_tab:
            render_notebook()

        with checker_tab:
            render_homework_checker()

        with calculus_tab:
            render_visual_calculus()

        with study_tab:
            render_study_sheet()

if _tab_is_open(surface_tab):
    with surface_tab:
        render_surface_grapher()

if _tab_is_open(simulators_tab):
    with simulators_tab:
        selected_simulator = st.selectbox(
            "Choose a simulator",
            [
                "Projectile Motion with Air Drag",
                "Damped Harmonic Oscillator",
                "RC / RLC Circuit Transient Response",
            ],
            key="physics_simulator",
        )
        if selected_simulator == "Projectile Motion with Air Drag":
            render_projectile_simulator()
        elif selected_simulator == "Damped Harmonic Oscillator":
            render_oscillator_simulator()
        else:
            render_circuit_simulator()

if _tab_is_open(ai_agent_tab):
    with ai_agent_tab:
        render_ai_math_agent()

sync_shareable_state()
with st.sidebar.expander("Shareable problem link"):
    query_string = urlencode(st.query_params.to_dict(), doseq=True)
    if query_string:
        st.caption("Copy this query string and append it to the app URL:")
        st.code(f"?{query_string}", language="text")
    else:
        st.caption("Enter a problem or adjust a graph/simulator to create a share link.")
