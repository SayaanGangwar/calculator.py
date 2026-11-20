# calculator.py
Calculator in Github that is testing 


import re
import subprocess
import sys


def ensure_dependencies():
    """Automatically installs sympy, matplotlib, and numpy if not installed."""
    required = {
        "sympy": "sympy>=1.12",
        "matplotlib": "matplotlib>=3.8.0",
        "numpy": "numpy>=1.26.0",
    }
    missing = []
    for pkg_import, pkg_spec in required.items():
        try:
            __import__(pkg_import)
        except ImportError:
            missing.append(pkg_spec)

    if missing:
        print(f"Installing missing packages: {', '.join(missing)}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        print("Installation complete!\n")


ensure_dependencies()

import numpy as np
import matplotlib.pyplot as plt
import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

# Setup parser to allow natural math syntax like '2x' and 'x^2'
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
    # Convert standalone integers in division like 1/3 into Rational(1, 3)
    expr_str = re.sub(
        r"(?<![.\w])(\d+)\s*/\s*(\d+)(?![.\w])",
        r"Rational(\1, \2)",
        expr_str,
    )
    return parse_expr(expr_str, local_dict=LOCAL_DICT, transformations=TRANSFORMATIONS)


def evaluate_expression():
    """Handles arithmetic, fractions, powers, roots, and algebraic simplification."""
    raw = input(
        "\nEnter math or algebra expression (e.g., 1/3 + 2/5, sqrt(50), (x+2)^2): "
    )
    try:
        expr = clean_and_parse(raw)
        simplified = sp.simplify(expr)
        expanded = sp.expand(simplified)

        print(f"Exact Result:   {expanded}")
        if not expanded.free_symbols:
            print(f"Decimal Approx: {expanded.evalf(10)}")
    except Exception as e:
        print(f"Invalid expression: {e}")


def solve_equation():
    """Solves linear, quadratic, and higher-order algebraic equations."""
    raw = input("\nEnter equation (e.g., x^2 - 5x + 6 = 0 or 2x + 3 = 11): ")
    try:
        if "=" in raw:
            lhs_str, rhs_str = raw.split("=", 1)
            lhs = clean_and_parse(lhs_str)
            rhs = clean_and_parse(rhs_str)
            equation = sp.Eq(lhs, rhs)
        else:
            equation = sp.Eq(clean_and_parse(raw), 0)

        symbols = sorted(equation.free_symbols, key=lambda s: s.name)
        target_var = symbols[0] if symbols else x
        solutions = sp.solve(equation, target_var)

        if not solutions:
            print("No solutions found.")
        else:
            print(f"\nSolutions for {target_var}:")
            for idx, sol in enumerate(solutions, 1):
                approx = complex(sol.evalf())
                approx_str = (
                    f"{approx.real:.4g}"
                    if approx.imag == 0
                    else f"{approx.real:.4g} + {approx.imag:.4g}i"
                )
                print(f"  {target_var}_{idx} = {sol}  (≈ {approx_str})")
    except Exception as e:
        print(f"Could not solve equation: {e}")


def solve_quadratic_helper():
    """Dedicated quadratic solver showing vertex, discriminant, and roots."""
    print("\nQuadratic Form: ax^2 + bx + c = 0")
    try:
        a = clean_and_parse(input("Enter a: "))
        b = clean_and_parse(input("Enter b: "))
        c = clean_and_parse(input("Enter c: "))

        if a == 0:
            print("'a' cannot be 0 for a quadratic equation.")
            return

        discriminant = sp.simplify(b**2 - 4 * a * c)
        vertex_x = sp.simplify(-b / (2 * a))
        vertex_y = sp.simplify(a * vertex_x**2 + b * vertex_x + c)

        expr = a * x**2 + b * x + c
        roots = sp.solve(expr, x)

        print(f"\nEquation:     {expr} = 0")
        print(f"Discriminant: {discriminant}")
        print(f"Vertex:       ({vertex_x}, {vertex_y})")
        print(f"Roots:        {roots}")

        plot_choice = (
            input("Would you like to graph this quadratic? (y/n): ").strip().lower()
        )
        if plot_choice == "y":
            plot_expression(expr, x_center=float(vertex_x.evalf()))
    except Exception as e:
        print(f"Error in quadratic calculation: {e}")


def plot_expression(expr=None, x_center=0.0):
    """Graphs any function in terms of x."""
    try:
        if expr is None:
            raw = input(
                "\nEnter function of x to graph (e.g., x^2 - 4, sin(x), sqrt(x)): "
            )
            expr = clean_and_parse(raw)

        min_in = input(f"Enter min x (default {x_center - 10}): ").strip()
        max_in = input(f"Enter max x (default {x_center + 10}): ").strip()
        x_min = float(min_in) if min_in else (x_center - 10)
        x_max = float(max_in) if max_in else (x_center + 10)

        f_num = sp.lambdify(x, expr, modules=["numpy"])
        x_vals = np.linspace(x_min, x_max, 500)
        y_vals = f_num(x_vals)

        if np.ndim(y_vals) == 0:
            y_vals = np.full_like(x_vals, y_vals)

        plt.figure(figsize=(8, 5))
        plt.plot(x_vals, y_vals, label=f"y = {expr}", color="#1f77b4", linewidth=2)
        plt.axhline(0, color="black", linewidth=1)
        plt.axvline(0, color="black", linewidth=1)
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.title(f"Graph of y = {expr}")
        plt.xlabel("x")
        plt.ylabel("y")
        plt.legend()
        plt.tight_layout()
        plt.show()
    except Exception as e:
        print(f"Could not plot function: {e}")


def main():
    while True:
        print("\n" + "=" * 44)
        print("   PYTHON ALGEBRA & GRAPHING CALCULATOR")
        print("=" * 44)
        print("1. Calculate / Simplify (Arithmetic, Fractions, Roots, Algebra)")
        print("2. Solve Equation (Linear, Quadratic, Polynomial)")
        print("3. Quadratic Analyzer (Roots, Vertex, Discriminant + Graph)")
        print("4. Graph a Function f(x)")
        print("5. Exit")

        choice = input("\nSelect an option (1-5): ").strip()

        if choice == "1":
            evaluate_expression()
        elif choice == "2":
            solve_equation()
        elif choice == "3":
            solve_quadratic_helper()
        elif choice == "4":
            plot_expression()
        elif choice == "5":
            print("Goodbye!")
            break
        else:
            print("Please enter a valid number between 1 and 5.")


if __name__ == "__main__":
    main()