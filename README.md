# 🧮 Python Algebra & Graphing Calculator

An interactive, web-based algebra and graphing calculator built with **Python**, **Streamlit**, **SymPy**, and **Matplotlib**. It supports exact fractions, square roots, algebraic simplification, equation solving, quadratic analysis, systems of equations, and live function plotting.

---

## ✨ Features

- **Natural Language & Equation Prompt:** Type plain-English math queries or full equations directly (e.g., `what is (3/4 + 2/5) * sqrt(25)`, `3(x + 2) = 5x - 4`, `factor x^2 - 9`, `derivative of x^3 + 2x`).
- **Clickable Scientific Keypad:** Quick-insert buttons for powers, square roots, fractions, trigonometry, parentheses, and variables.
- **Exact & Decimal Math:** Preserves exact fractions (`1/3 + 2/5 = 11/15`) and simplified radicals (`sqrt(50) = 5*sqrt(2)`) alongside decimal approximations.
- **Quadratic Analyzer:** Automatically calculates the discriminant, vertex coordinates, and real or complex roots—and plots the parabola.
- **Systems of Equations Solver:** Solves two-variable linear or nonlinear systems (e.g., `2x + y = 10; x - y = 2`) and graphs their intersection point.
- **Interactive Function Grapher:** Plots any function $f(x)$ over a custom $x$-range with gridlines and axes.

---

## 🚀 How to Run

### 1. Clone the Repository
```bash
git clone https://github.com
cd YOUR_REPO_NAME
```

### 2. Install Dependencies
```bash
python -m pip install streamlit sympy matplotlib numpy
```

### 3. Launch the App
```bash
python -m streamlit run calculator.py
```
*(If running in **GitHub Codespaces**, click **Open in Browser** when prompted, or open the **Ports** tab and click the globe icon next to port `8501`.)*

---

## 💡 Example Inputs to Try

| Feature | Example Input |
| :--- | :--- |
| **Exact Fractions & Roots** | `(3/4 + 2/5) * sqrt(16)` |
| **Algebra Expansion** | `(x + 3)^2 - (x - 1)(x + 4)` |
| **Solve Equation** | `3(x + 2) = 5x - 4` |
| **Quadratic Analysis** | `quadratic x^2 - 6x + 8` |
| **System of Equations** | `2x + y = 10; x - y = 2` |
| **Calculus** | `derivative of x^3 + 4x` or `integral of 2x + 1` |
| **Graphing** | `graph sin(x) from -10 to 10` |

---

## 🛠️ Built With

- [Streamlit](https://streamlit.io) – Interactive browser UI
- [SymPy](https://sympy.org) – Symbolic mathematics & exact algebra
- [Matplotlib](https://matplotlib.org) – 2D function and intersection plotting
- [NumPy](https://numpy.org) – Numerical array evaluation
