# 🧮 Python Algebra & Graphing Calculator

An interactive, web-based algebra and graphing calculator built with **Python**, **Streamlit**, **SymPy**, and **Matplotlib**. It supports exact fractions, square roots, algebraic simplification, equation solving, quadratic analysis, systems of equations, and live function plotting.

---

## ✨ Features

- **Natural Language & Equation Prompt:** Type plain-English math queries or full equations directly (e.g., `what is (3/4 + 2/5) * sqrt(25)`, `3(x + 2) = 5x - 4`, `factor x^2 - 9`, `derivative of x^3 + 2x`).
- **AI Math Agent:** Chat about word problems and multi-step math, ask follow-up questions, and send verified results to the grapher or solver. It uses local SymPy without an API key; Gemini answers stream as they arrive and fall back to local SymPy after a four-second request timeout. Optionally configure `GEMINI_API_KEY` or `OPENAI_API_KEY` in the environment or Streamlit secrets, or enter a key in the sidebar.
- **Clickable Scientific Keypad:** Quick-insert buttons for powers, square roots, fractions, trigonometry, parentheses, and variables.
- **Exact & Decimal Math:** Preserves exact fractions (`1/3 + 2/5 = 11/15`) and simplified radicals (`sqrt(50) = 5*sqrt(2)`) alongside decimal approximations.
- **Quadratic Analyzer:** Automatically calculates the discriminant, vertex coordinates, and real or complex roots—and plots the parabola.
- **Systems of Equations Solver:** Solves two-variable linear or nonlinear systems (e.g., `2x + y = 10; x - y = 2`) and graphs their intersection point.
- **Step-by-Step Solutions:** Explanations for equations, derivatives, integrals, arithmetic, and supported symbolic operations.
- **Notebook / Scratchpad:** Evaluate multi-line expressions and reuse variables defined earlier in the notebook.
- **Spot the Mistake:** Check algebraic answers and get a problem-specific, step-by-step walkthrough with targeted hints for sign, partial-answer, power-rule, integration-constant, and angle-unit mistakes.
- **Visual Calculus:** Explore left, right, and midpoint Riemann sums and compare Taylor polynomials with their functions.
- **Shareable Problem Links:** URL parameters preserve the active tab, main query, surface graph, and simulator settings.
- **Study Sheet Export:** Select solved problems from the session history and download their steps and final answers as Markdown.
- **Advanced Symbolic Math:** ODEs, Taylor series, summations, partial fractions, trigonometric simplification, and matrix operations.
- **Statistics & Number Theory:** Mean, median, mode, population variance and standard deviation, prime factors, GCD, and LCM.
- **Math Reference Guide:** Expandable sidebar categories with clickable example queries for supported topics.
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
python -m pip install -r requirements.txt
```
The image scanner also requires the Tesseract OCR system package.

### 3. Launch the App
```bash
python -m streamlit run calculator.py
```
The AI Math Agent works without an API key. To enable hosted explanations, set
`GEMINI_API_KEY` or `OPENAI_API_KEY` in the environment or Streamlit secrets.
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
| **Differential Equations** | `ode y' = y` |
| **Series & Summations** | `series sin(x)` or `sum 1/n^2 from 1 to oo` |
| **Matrix Operations** | `det [[1,2],[3,4]]` or `rref [[1,2,3],[4,5,6]]` |
| **Statistics** | `stats 10, 20, 30, 40` |
| **Number Theory** | `prime factors 360`, `gcd 48, 180`, or `lcm 12, 15` |

---

## 🛠️ Built With

- [Streamlit](https://streamlit.io) – Interactive browser UI
- [SymPy](https://sympy.org) – Symbolic mathematics & exact algebra
- [Matplotlib](https://matplotlib.org) – 2D function and intersection plotting
- [NumPy](https://numpy.org) – Numerical array evaluation
- [Plotly](https://plotly.com/python/) – Interactive 3D and calculus visualizations
