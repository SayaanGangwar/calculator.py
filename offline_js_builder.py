"""Build a self-contained, browser-native OmniMath calculator page."""


def offline_js_calculator_html() -> str:
    """Return a single-file OmniMath app with no remote assets or libraries."""
    return r"""<!doctype html>
    function cleanMathInput(raw) {
  let s = raw.trim();
  s = s.replace(/^(what is|calculate|solve|simplify|evaluate|find|explain why|why is|how do you solve)\s+/i, '');
  s = s.replace(/\?+$/g, '').trim();
  // Convert 'x' or '×' between numbers into '*' (so 5.6 x 6.6897 multiplies instead of treating x as a variable)
  s = s.replace(/(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)/gi, '$1 * $2');
  s = s.replace(/×/g, '*').replace(/÷/g, '/');
  return s;
}

function evalSafeJS(expr) {
  let jsExpr = expr
    .replace(/\^/g, '**')
    .replace(/\bsin\(/g, 'Math.sin(')
    .replace(/\bcos\(/g, 'Math.cos(')
    .replace(/\btan\(/g, 'Math.tan(')
    .replace(/\bsqrt\(/g, 'Math.sqrt(')
    .replace(/\blog\(/g, 'Math.log10(')
    .replace(/\bln\(/g, 'Math.log(')
    .replace(/\bpi\b/gi, 'Math.PI')
    .replace(/\be\b/g, 'Math.E');
  if (/[^0-9+\-*/().\sMathsincoqrtlgPIE*]/.test(jsExpr)) throw new Error("Unsupported syntax");
  return Function('"use strict"; return (' + jsExpr + ')')();
}

function generateHumanSteps(rawInput) {
  const cleaned = cleanMathInput(rawInput);

  // 1. Two-number multiplication (with decimal place breakdown)
  const multMatch = cleaned.match(/^(-?\d+(?:\.\d+)?)\s*\*\s*(-?\d+(?:\.\d+)?)$/);
  if (multMatch) {
    const aStr = multMatch[1], bStr = multMatch[2];
    const a = parseFloat(aStr), b = parseFloat(bStr);
    const decA = (aStr.split('.')[1] || '').length;
    const decB = (bStr.split('.')[1] || '').length;
    const totalDec = decA + decB;
    const intA = Math.round(a * Math.pow(10, decA));
    const intB = Math.round(b * Math.pow(10, decB));
    const intProd = intA * intB;
    const ans = Number((a * b).toPrecision(12));

    if (totalDec > 0) {
      return {
        steps: [
          `1. Count decimal places: ${aStr} has ${decA} decimal place(s) and ${bStr} has ${decB} decimal place(s) (${totalDec} total).`,
          `2. Multiply without decimals: ${intA} × ${intB} = ${intProd.toLocaleString()}.`,
          `3. Move the decimal point ${totalDec} place(s) from the right → ${ans}.`
        ],
        answer: ans
      };
    }
    return {
      steps: [`1. Multiply ${aStr} by ${bStr} directly to get ${ans}.`],
      answer: ans
    };
  }

  // 2. Linear equations: ax + b = c
  if (cleaned.includes('=')) {
    const parts = cleaned.split('=');
    if (parts.length === 2 && !isNaN(parseFloat(parts[1]))) {
      const lhs = parts[0].replace(/\s+/g, '');
      const rhs = parseFloat(parts[1].trim());
      const lin = lhs.match(/^([+-]?\d*\.?\d*)x([+-]\d+\.?\d*)?$/i);
      if (lin) {
        const a = (lin[1] === '' || lin[1] === '+') ? 1 : (lin[1] === '-' ? -1 : parseFloat(lin[1]));
        const b = lin[2] ? parseFloat(lin[2]) : 0;
        let steps = [];
        let newRhs = rhs;
        if (b !== 0) {
          newRhs = Number((rhs - b).toPrecision(12));
          const opText = b > 0 ? `Subtract ${b} from` : `Add ${Math.abs(b)} to`;
          steps.push(`1. ${opText} both sides: ${a}x = ${rhs} - (${b}) = ${newRhs}.`);
        }
        const xVal = Number((newRhs / a).toPrecision(12));
        steps.push(`${steps.length + 1}. Divide both sides by ${a}: x = ${newRhs} / ${a} = ${xVal}.`);
        return { steps, answer: `x = ${xVal}` };
      }
    }
  }

  // 3. Multi-step PEMDAS arithmetic (Parentheses -> Exponents -> Mult/Div -> Add/Sub)
  let steps = [];
  let current = cleaned.replace(/\s+/g, '');
  let stepNum = 1;

  while (/\(([^()]+)\)/.test(current)) {
    current = current.replace(/\(([^()]+)\)/, (m, inner) => {
      const val = Number(evalSafeJS(inner).toPrecision(12));
      steps.push(`${stepNum++}. Parentheses: (${inner}) = ${val}.`);
      return val;
    });
  }
  while (/(-?\d+(?:\.\d+)?)\^(-?\d+(?:\.\d+)?)/.test(current)) {
    current = current.replace(/(-?\d+(?:\.\d+)?)\^(-?\d+(?:\.\d+)?)/, (m, base, exp) => {
      const val = Number(Math.pow(parseFloat(base), parseFloat(exp)).toPrecision(12));
      steps.push(`${stepNum++}. Exponent: ${base}^${exp} = ${val}.`);
      return val;
    });
  }
  while (/(-?\d+(?:\.\d+)?)([*/])(-?\d+(?:\.\d+)?)/.test(current)) {
    current = current.replace(/(-?\d+(?:\.\d+)?)([*/])(-?\d+(?:\.\d+)?)/, (m, l, op, r) => {
      const val = Number((op === '*' ? parseFloat(l) * parseFloat(r) : parseFloat(l) / parseFloat(r)).toPrecision(12));
      steps.push(`${stepNum++}. ${op === '*' ? 'Multiply' : 'Divide'}: ${l} ${op} ${r} = ${val}.`);
      return val;
    });
  }
  while (/(-?\d+(?:\.\d+)?)([+-])(\d+(?:\.\d+)?)/.test(current)) {
    current = current.replace(/(-?\d+(?:\.\d+)?)([+-])(\d+(?:\.\d+)?)/, (m, l, op, r) => {
      const val = Number((op === '+' ? parseFloat(l) + parseFloat(r) : parseFloat(l) - parseFloat(r)).toPrecision(12));
      steps.push(`${stepNum++}. ${op === '+' ? 'Add' : 'Subtract'}: ${l} ${op} ${r} = ${val}.`);
      return val;
    });
  }

  const finalAns = Number(evalSafeJS(cleaned).toPrecision(12));
  if (steps.length === 0) {
    steps.push(`1. Evaluate ${cleaned} directly = ${finalAns}.`);
  }
  return { steps, answer: finalAns };
}

    const explained = generateHumanSteps(userQuestion);
const replyText = explained.steps.join('\n') + `\nAnswer: ${explained.answer}`;
    const explained = generateHumanSteps(userQuestion);
const replyText = explained.steps.join('\n') + `\nAnswer: ${explained.answer}`;
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="A self-contained offline mathematics and engineering calculator.">
<title>OmniMath Instant Offline Calculator</title>
<style>
:root{color-scheme:dark;--bg:#071a2c;--fg:#d9f0ff;--surface:#12304a;--accent:#62c6f2;--muted:#91adc0;--border:#31556e;--good:#38c98b;--warn:#ffc857;--bad:#ff6b76;font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg)}button,input,textarea,select{font:inherit;color:inherit}button{border:1px solid var(--border);background:var(--surface);padding:.55rem .8rem;border-radius:.55rem;cursor:pointer}button:hover,button.active{border-color:var(--accent);color:var(--accent)}input,textarea,select{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:.5rem;padding:.65rem}textarea{min-height:110px;resize:vertical}label{display:block;color:var(--muted);font-size:.9rem;margin:.5rem 0 .25rem}h1,h2,h3{color:var(--accent);line-height:1.2}h1{font-size:1.45rem;margin:.15rem 0 1rem}h2{font-size:1.25rem}h3{font-size:1.05rem}.layout{display:grid;grid-template-columns:280px minmax(0,1fr);min-height:100vh}.sidebar{padding:1rem;background:var(--surface);border-right:1px solid var(--border);overflow:auto}.main{padding:1.2rem;max-width:1450px;width:100%;margin:auto}.brand{font-weight:750;font-size:1.3rem;color:var(--accent)}.small{font-size:.86rem;color:var(--muted)}.stack{display:grid;gap:.55rem}.theme-select{margin-bottom:1rem}.download{width:100%;margin:.3rem 0}.category{border-top:1px solid var(--border);padding:.6rem 0}.category summary{cursor:pointer;color:var(--accent);font-weight:650}.preset-list{display:grid;gap:.35rem;margin-top:.55rem}.preset-list button{font-size:.85rem;text-align:left}.top-tabs,.sub-tabs{display:flex;gap:.45rem;flex-wrap:wrap;margin:.1rem 0 1rem}.top-tabs button{font-weight:650}.panel,.card{background:var(--surface);border:1px solid var(--border);border-radius:.75rem;padding:1rem;margin:.75rem 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.75rem}.row{display:flex;align-items:center;gap:.6rem}.row>*{flex:1}.range-row{display:grid;grid-template-columns:1fr auto;gap:.6rem;align-items:center}.range-row input{padding:0;accent-color:var(--accent)}.out{white-space:pre-wrap;overflow-wrap:anywhere;border-left:3px solid var(--accent);padding:.65rem .8rem;background:var(--bg);border-radius:.3rem;margin:.7rem 0}.steps{padding-left:1.5rem}.good{color:var(--good)}.warn{color:var(--warn)}.bad{color:var(--bad)}.hidden{display:none!important}.canvas-wrap{position:relative;width:100%;height:390px;background:var(--bg);border:1px solid var(--border);border-radius:.6rem;overflow:hidden}.canvas-wrap canvas{width:100%;height:100%;display:block;touch-action:none}.canvas-tools{display:flex;gap:.4rem;flex-wrap:wrap;margin:.5rem 0}.metric{padding:.65rem;border:1px solid var(--border);border-radius:.5rem}.metric strong{display:block;color:var(--accent);font-size:1.1rem}.subtle{font-size:.8rem;color:var(--muted)}.answer-row{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}.sim-control{margin-bottom:.55rem}.sim-control input[type=range]{accent-color:var(--accent)}.messages{max-height:360px;overflow:auto}.message{border-bottom:1px solid var(--border);padding:.5rem 0}.message.user{color:var(--accent)}.linklike{border:0;background:transparent;color:var(--accent);padding:.2rem;text-align:left}@media(max-width:850px){.layout{grid-template-columns:1fr}.sidebar{border-right:0;border-bottom:1px solid var(--border)}.main{padding:.75rem}.answer-row{grid-template-columns:1fr}.canvas-wrap{height:320px}}
</style>
</head>
<body>
<div class="layout">
<aside class="sidebar">
  <div class="brand">OmniMath</div><div class="small">Instant offline calculator</div>
  <label for="theme">Color theme</label><select class="theme-select" id="theme"></select>
  <button class="download" id="downloadFull">Download Full OmniMath App (.html)</button>
  <p class="small">The full Stlite download is online-dependent. This JavaScript edition runs without a network connection.</p>
  <div class="category"><strong>Math Reference Guide</strong></div>
  <div id="presets"></div>
  <details class="category"><summary>AI Math Agent API key (optional)</summary>
    <p class="small">If used, your prompt and key are sent directly from this browser to Google Gemini. Offline local solving works without a key.</p>
    <label for="apiKey">Gemini API key</label><input id="apiKey" type="password" autocomplete="off" placeholder="Optional; not saved">
  </details>
  <button class="download" id="studyDownload">Download Study Sheet (.md)</button>
</aside>
<main class="main">
  <h1>OmniMath Calculator</h1>
  <nav class="top-tabs" id="mainTabs"></nav>
  <section id="solverPage">
    <nav class="sub-tabs" id="solverTabs"></nav>
    <section id="calculatorPane" class="pane">
      <div class="card">
        <h2>Calculator &amp; Solver</h2>
        <label for="query">Enter an expression or query</label>
        <div class="row"><input id="query" placeholder="e.g. derivative of x^3 + 2x" autocomplete="off"><button id="solve">Solve</button></div>
        <div id="solverResult" aria-live="polite"></div>
      </div>
      <details class="card"><summary>Camera &amp; Image Math Scanner</summary>
        <label for="imageInput">Upload or take a picture of an equation</label><input id="imageInput" type="file" accept="image/png,image/jpeg" capture="environment">
        <button id="extractImage">Extract text when native browser OCR is available</button>
        <p id="imageStatus" class="small">Image selection is available offline. This lightweight self-contained build does not bundle an OCR model; type or paste the recognized equation into the solver.</p>
        <img id="imagePreview" alt="Selected math image preview" class="hidden" style="max-width:100%;max-height:240px">
      </details>
    </section>
    <section id="notebookPane" class="pane hidden card">
      <h2>Notebook / Scratchpad</h2><p class="small">Assignments are available to later lines (for example x = 7, y = 3, (x*y)^2).</p>
      <textarea id="notebookInput">v0 = 25
t = 3.5
d = v0*t - 0.5*9.8*t^2</textarea><button id="runNotebook">Evaluate notebook</button><div id="notebookResult"></div>
    </section>
    <section id="checkerPane" class="pane hidden card">
      <h2>Spot the Mistake</h2><div class="answer-row"><div><label for="homeworkProblem">Original expression/problem</label><input id="homeworkProblem" placeholder="e.g. integrate x^2"></div><div><label for="homeworkAttempt">Your attempt/answer</label><input id="homeworkAttempt" placeholder="e.g. x^3/3"></div></div>
      <button id="checkHomework">Check my work</button><div id="homeworkResult"></div>
    </section>
    <section id="calculusPane" class="pane hidden">
      <nav class="sub-tabs"><button class="active" data-calc="riemann">Riemann Sums</button><button data-calc="taylor">Taylor Series</button></nav>
      <div id="riemannPane" class="card">
        <h2>Riemann Sum Visualizer</h2><label>Function f(x)</label><input id="riemannExpr" value="x^2">
        <div class="grid"><div><label>Lower bound a</label><input id="riemannA" value="0" type="number" step="any"></div><div><label>Upper bound b</label><input id="riemannB" value="3" type="number" step="any"></div>
        <div><label>Rectangle sample point</label><select id="riemannMethod"><option>Left</option><option>Right</option><option>Midpoint</option></select></div><div><label>Rectangles n <output id="riemannNOut">12</output></label><input id="riemannN" type="range" min="2" max="100" value="12"></div></div>
        <div class="canvas-wrap"><canvas id="riemannCanvas"></canvas></div><div id="riemannMetrics"></div>
      </div>
      <div id="taylorPane" class="card hidden"><h2>Taylor Series Approximator</h2>
        <div class="grid"><div><label>Function f(x)</label><input id="taylorExpr" value="sin(x)"></div><div><label>Center a</label><input id="taylorCenter" type="number" value="0" step="any"></div>
        <div><label>Polynomial degree <output id="taylorDegreeOut">4</output></label><input id="taylorDegree" type="range" min="0" max="12" value="4"></div><div><label>Plot half-width <output id="taylorSpanOut">5</output></label><input id="taylorSpan" type="range" min="1" max="10" value="5" step=".5"></div></div>
        <div class="canvas-wrap"><canvas id="taylorCanvas"></canvas></div><div id="taylorResult" class="out"></div>
      </div>
    </section>
    <section id="studyPane" class="pane hidden card"><h2>LaTeX / Markdown Study Sheet</h2><div id="historyList" class="small">Solved problems will appear here for selection and export.</div></section>
  </section>
  <section id="surfacePage" class="hidden card">
    <h2>3D Surface Grapher</h2><p class="small">Drag to rotate. Scroll to zoom. Presets: paraboloid, saddle, ripple, and sine plane.</p>
    <div class="canvas-tools" id="surfacePresets"></div>
    <div class="row"><input id="surfaceExpr" value="sin(sqrt(x^2+y^2))" aria-label="Surface z=f(x,y)"><button id="surfacePlot">Plot surface</button></div>
    <div class="grid"><div><label>x range ± <output id="surfaceXOut">5</output></label><input id="surfaceXRange" type="range" min="1" max="10" value="5" step=".5"></div><div><label>y range ± <output id="surfaceYOut">5</output></label><input id="surfaceYRange" type="range" min="1" max="10" value="5" step=".5"></div>
    <div><label>Colorscale</label><select id="surfaceScale"><option>Viridis</option><option>Plasma</option><option>Inferno</option><option>Cividis</option></select></div></div>
    <div class="canvas-wrap"><canvas id="surfaceCanvas"></canvas></div><div id="surfaceResult" class="out"></div>
  </section>
  <section id="simPage" class="hidden card">
    <h2>Physics &amp; Engineering Simulators</h2><label for="simulator">Choose a simulator</label>
    <select id="simulator"><option>Projectile Motion with Air Drag</option><option>Damped Harmonic Oscillator</option><option>RC / RLC Circuit Transient Response</option></select>
    <div id="simControls"></div><div class="canvas-wrap"><canvas id="simCanvas"></canvas></div><div id="simMetrics" class="grid"></div>
  </section>
  <section id="agentPage" class="hidden card">
    <h2>AI Math Agent</h2><p class="small">Offline local solving handles arithmetic, equations, systems, and common word problems. For Gemini, add an API key in the sidebar while online.</p>
    <div id="chatHistory" class="messages"></div><div class="row"><input id="agentPrompt" placeholder="Ask a math question or follow up..."><button id="askAgent">Ask</button></div>
    <div id="agentStatus" class="small"></div><button id="clearChat">Clear conversation</button>
  </section>
</main>
</div>
<script>
"use strict";
const themes={
 "Midnight Dark":{bg:"#10131d",fg:"#e8ecf5",surface:"#1b2232",accent:"#91a7ff",border:"#384258"},
 "Clean Light":{bg:"#f7f8fb",fg:"#202536",surface:"#ffffff",accent:"#3157a4",border:"#cbd2e1"},
 "Matrix Green":{bg:"#06120b",fg:"#c7f9cc",surface:"#102318",accent:"#50fa7b",border:"#315b3c"},
 "Ocean Blue":{bg:"#071a2c",fg:"#d9f0ff",surface:"#12304a",accent:"#62c6f2",border:"#31556e"}};
const reference={
 "Arithmetic & Units":[["Arithmetic","(5 + 6) * 5"],["Unit conversion","convert 100 km to miles"]],
 "Algebra & Equations":[["Solve an equation","3(x + 2) = 5x - 4"],["Systems of equations","x + y = 10, x - y = 2"],["Factor","factor x^2 - 9"],["Expand","expand (x + 2)^2"]],
 "Calculus":[["Derivative","derivative of x^3 + 2x"],["Integral","integrate x^2"],["Limit","limit sin(x)/x as x -> 0"],["ODE","ode y' = y"]],
 "Series & Sums":[["Taylor series","series sin(x)"],["Summation","sum 1/n^2 from 1 to oo"]],
 "Expression Tools":[["Partial fractions","apart (x^2 + 1)/(x*(x + 1))"],["Trig simplification","trigsimp sin(x)^2 + cos(x)^2"],["Graph","graph sin(x) from -10 to 10"]],
 "Matrices, Statistics & Number Theory":[["Determinant","det [[1,2],[3,4]]"],["Inverse","inv [[1,2],[3,4]]"],["Eigenvalues and vectors","eigen [[1,2],[3,4]]"],["RREF","rref [[1,2,3],[4,5,6]]"],["Statistics","stats 10, 20, 30, 40"],["Prime factors","prime factors 360"],["GCD","gcd 48, 180"],["LCM","lcm 12, 15"]]
};
const $=id=>document.getElementById(id);
function themeInit(){const s=$("theme");Object.keys(themes).forEach(n=>s.add(new Option(n,n)));s.value="Ocean Blue";s.onchange=()=>{const t=themes[s.value];for(const [k,v] of Object.entries({bg:t.bg,fg:t.fg,surface:t.surface,accent:t.accent,border:t.border}))document.documentElement.style.setProperty("--"+k,v);drawAll()}}
function presetInit(){const root=$("presets");for(const [group,items] of Object.entries(reference)){const d=document.createElement("details");d.className="category";const summary=document.createElement("summary");summary.textContent=group;d.append(summary);const list=document.createElement("div");list.className="preset-list";items.forEach(([label,q])=>{const b=document.createElement("button");b.textContent=label;b.onclick=()=>{$("query").value=q;showMain("OmniMath Solver");showSolver("Calculator");$("query").focus()};list.append(b)});d.append(list);root.append(d)}}
const mainNames=["OmniMath Solver","3D Surface Grapher","Physics & Engineering Simulators","AI Math Agent"];
function tabsInit(){const root=$("mainTabs");mainNames.forEach((n,i)=>{const b=document.createElement("button");b.textContent=n;b.onclick=()=>showMain(n);if(!i)b.classList.add("active");root.append(b)});const sub=$("solverTabs");["Calculator","Notebook / Scratchpad","Spot the Mistake","Visual Calculus","Study Sheet"].forEach((n,i)=>{const b=document.createElement("button");b.textContent=n;b.onclick=()=>showSolver(n);if(!i)b.classList.add("active");sub.append(b)});document.querySelectorAll("[data-calc]").forEach(b=>b.onclick=()=>{document.querySelectorAll("[data-calc]").forEach(x=>x.classList.toggle("active",x===b));$("riemannPane").classList.toggle("hidden",b.dataset.calc!=="riemann");$("taylorPane").classList.toggle("hidden",b.dataset.calc!=="taylor")})}
function showMain(name){$("solverPage").classList.toggle("hidden",name!==mainNames[0]);$("surfacePage").classList.toggle("hidden",name!==mainNames[1]);$("simPage").classList.toggle("hidden",name!==mainNames[2]);$("agentPage").classList.toggle("hidden",name!==mainNames[3]);[...$("mainTabs").children].forEach(b=>b.classList.toggle("active",b.textContent===name));if(name===mainNames[1])drawSurface();if(name===mainNames[2])drawSimulator()}
function showSolver(name){const keys=["Calculator","Notebook / Scratchpad","Spot the Mistake","Visual Calculus","Study Sheet"],ids=["calculatorPane","notebookPane","checkerPane","calculusPane","studyPane"];ids.forEach((id,i)=>$(id).classList.toggle("hidden",keys[i]!==name));[...$("solverTabs").children].forEach(b=>b.classList.toggle("active",b.textContent===name));if(name==="Visual Calculus")drawAll();if(name==="Study Sheet")renderHistory()}

// A deliberately small recursive-descent parser keeps evaluation local and avoids eval().
function tokenize(src){src=src.replaceAll("×","*").replaceAll("÷","/").replaceAll("^","**").replace(/\bpi\b/gi,"pi").replace(/\binfinity\b|\binf\b/gi,"Infinity");const out=[];let i=0;while(i<src.length){if(/\s/.test(src[i])){i++;continue}const m=src.slice(i).match(/^(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?|^[A-Za-z_]\w*|^\*\*|^[+\-*/%^(),=]/i);if(!m)throw Error("Unsupported character: "+src[i]);out.push(m[0]);i+=m[0].length}return out}
const funcs=new Set(["sqrt","cbrt","abs","sin","cos","tan","asin","acos","atan","sinh","cosh","tanh","log","ln","exp","factorial"]);
function parse(src){const ts=tokenize(src);let p=0;const peek=()=>ts[p],take=()=>ts[p++];function atom(){const t=take();if(t===undefined)throw Error("Expected a value");if(t==="("){const n=expr(0);if(take()!==")")throw Error("Missing )");return n}if(t==="+"||t==="-")return{t:"un",op:t,a:expr(25)};if(/^(?:\d|\.)/.test(t))return{t:"num",v:Number(t)};if(t==="Infinity")return{t:"num",v:Infinity};if(/^[A-Za-z_]/.test(t)){const name=t.toLowerCase();if(funcs.has(name)&&peek()==="("){take();const args=[];if(peek()!==")"){args.push(expr(0));while(peek()===","){take();args.push(expr(0))}}if(take()!==")")throw Error("Missing ) after "+t);return{t:"fn",n:name,a:args}}if(name==="pi")return{t:"num",v:Math.PI};if(name==="e")return{t:"num",v:Math.E};if(name==="i")throw Error("Complex arithmetic is not supported in this offline build");return{t:"var",n:t}}throw Error("Unexpected token: "+t)}
const prec={"=":1,"+":10,"-":10,"*":20,"/":20,"%":20,"**":30};function expr(min){let left=atom();while(p<ts.length){let op=peek(),implicit=false;if(op==="("||/^(?:\d|\.)/.test(op)||/^[A-Za-z_]/.test(op)){if(op==="("&&left.t==="var"&&funcs.has(left.n.toLowerCase()))break;op="*";implicit=true}const bp=prec[op];if(bp===undefined||bp<min)break;if(!implicit)take();const right=expr(bp+(op==="**"?0:1));left={t:"op",op,a:left,b:right}}return left}const tree=expr(0);if(p<ts.length)throw Error("Unexpected token: "+peek());return tree}
function ev(n,vars={}){if(n.t==="num")return n.v;if(n.t==="var"){if(Object.hasOwn(vars,n.n))return vars[n.n];throw Error("Unknown variable: "+n.n)}if(n.t==="un")return n.op==="-"?-ev(n.a,vars):ev(n.a,vars);if(n.t==="op"){const a=ev(n.a,vars),b=ev(n.b,vars);if(n.op==="+")return a+b;if(n.op==="-")return a-b;if(n.op==="*")return a*b;if(n.op==="/")return a/b;if(n.op==="%")return a%b;if(n.op==="**")return a**b}const x=ev(n.a[0],vars),f=n.n;const funcsEval={sqrt:Math.sqrt,cbrt:Math.cbrt,abs:Math.abs,sin:Math.sin,cos:Math.cos,tan:Math.tan,asin:Math.asin,acos:Math.acos,atan:Math.atan,sinh:Math.sinh,cosh:Math.cosh,tanh:Math.tanh,log:Math.log10,ln:Math.log,exp:Math.exp,factorial:v=>{if(!Number.isInteger(v)||v<0||v>170)throw Error("factorial requires an integer from 0 to 170");let r=1;for(let i=2;i<=v;i++)r*=i;return r}};if(f==="log"&&n.a.length>1)return Math.log(ev(n.a[0],vars))/Math.log(ev(n.a[1],vars));return funcsEval[f](x)}
function str(n,parent=0){if(n.t==="num")return Number.isFinite(n.v)?String(Number(n.v.toPrecision(10))):String(n.v);if(n.t==="var")return n.n;if(n.t==="un")return n.op+str(n.a,25);if(n.t==="fn")return n.n+"("+n.a.map(x=>str(x)).join(", ")+")";const q={"=":1,"+":10,"-":10,"*":20,"/":20,"**":30}[n.op];let text=n.op==="**"?str(n.a,q)+"^"+str(n.b,q):str(n.a,q)+" "+n.op+" "+str(n.b,q+1);return q<parent?"("+text+")":text}
function simp(n){if(n.t==="un"){const a=simp(n.a);if(a.t==="num")return{t:"num",v:n.op==="-"?-a.v:a.v};return{...n,a}}if(n.t==="fn"){const a=n.a.map(simp);if(a.every(x=>x.t==="num")){try{return{t:"num",v:ev({t:"fn",n:n.n,a}, {})}}catch{}}return{...n,a}}if(n.t==="op"){const a=simp(n.a),b=simp(n.b);if(a.t==="num"&&b.t==="num"){try{return{t:"num",v:ev({t:"op",op:n.op,a,b})}}catch{}}if(n.op==="+"&&b.t==="num"&&b.v===0)return a;if(n.op==="+"&&a.t==="num"&&a.v===0)return b;if(n.op==="-"&&b.t==="num"&&b.v===0)return a;if(n.op==="*"&&((a.t==="num"&&a.v===0)||(b.t==="num"&&b.v===0)))return{t:"num",v:0};if(n.op==="*"&&a.t==="num"&&a.v===1)return b;if(n.op==="*"&&b.t==="num"&&b.v===1)return a;if(n.op==="**"&&b.t==="num"&&b.v===1)return a;if(n.op==="**"&&b.t==="num"&&b.v===0)return{t:"num",v:1};return{...n,a,b}}return n}
function deriv(n,v="x"){if(n.t==="num")return{t:"num",v:0};if(n.t==="var")return{t:"num",v:n.n===v?1:0};if(n.t==="un")return{t:"un",op:n.op,a:deriv(n.a,v)};if(n.t==="op"){const a=n.a,b=n.b,dA=deriv(a,v),dB=deriv(b,v);if(n.op==="+")return{...n,a:dA,b:dB};if(n.op==="-")return{...n,a:dA,b:dB};if(n.op==="*")return{t:"op",op:"+",a:{t:"op",op:"*",a:dA,b},b:{t:"op",op:"*",a,b:dB}};if(n.op==="/")return{t:"op",op:"/",a:{t:"op",op:"-",a:{t:"op",op:"*",a:dA,b},b:{t:"op",op:"*",a,b:dB}},b:{t:"op",op:"**",a:b,b:{t:"num",v:2}}};if(n.op==="**"&&b.t==="num")return{t:"op",op:"*",a:{t:"op",op:"*",a:b,b:{t:"op",op:"**",a,b:{t:"num",v:b.v-1}}},b:dA};if(n.op==="**")return{t:"op",op:"*",a:n,b:{t:"op",op:"+",a:{t:"op",op:"*",a:dB,b:{t:"fn",n:"ln",a:[a]}},b:{t:"op",op:"*",a:b,b:{t:"op",op:"/",a:dA,b:a}}}}}if(n.t==="fn"){const a=n.a[0],d=deriv(a,v),wrap=(f,arg=d)=>({t:"op",op:"*",a:{t:"fn",n:f,a:[a]},b:arg});if(n.n==="sin")return wrap("cos");if(n.n==="cos")return{t:"un",op:"-",a:wrap("sin")};if(n.n==="tan")return{t:"op",op:"/",a:d,b:{t:"op",op:"**",a:{t:"fn",n:"cos",a:[a]},b:{t:"num",v:2}}};if(n.n==="exp")return wrap("exp");if(n.n==="ln"||n.n==="log")return{t:"op",op:"/",a:d,b:a};if(n.n==="sqrt")return{t:"op",op:"/",a:d,b:{t:"op",op:"*",a:{t:"num",v:2},b:{t:"fn",n:"sqrt",a:[a]}}};if(n.n==="abs")return{t:"op",op:"*",a:{t:"op",op:"/",a:a,b:{t:"fn",n:"abs",a:[a]}},b:d}}return{t:"num",v:0}}
function integrate(n,v="x"){if(n.t==="num")return{t:"op",op:"*",a:n,b:{t:"var",n:v}};if(n.t==="var"){if(n.n!==v)return{t:"op",op:"*",a:n,b:{t:"var",n:v}};return{t:"op",op:"/",a:{t:"op",op:"**",a:n,b:{t:"num",v:2}},b:{t:"num",v:2}}}if(n.t==="un")return{...n,a:integrate(n.a,v)};if(n.t==="op"&&(n.op==="+"||n.op==="-"))return{...n,a:integrate(n.a,v),b:integrate(n.b,v)};if(n.t==="op"&&n.op==="*"&&n.a.t==="num")return{...n,a:n.a,b:integrate(n.b,v)};if(n.t==="op"&&n.op==="**"&&n.a.t==="var"&&n.a.n===v&&n.b.t==="num"){if(n.b.v===-1)return{t:"fn",n:"ln",a:[{t:"fn",n:"abs",a:[n.a]}]};return{t:"op",op:"/",a:{t:"op",op:"**",a:n.a,b:{t:"num",v:n.b.v+1}},b:{t:"num",v:n.b.v+1}}}if(n.t==="fn"&&n.a[0].t==="var"&&n.a[0].n===v){if(n.n==="sin")return{t:"un",op:"-",a:{t:"fn",n:"cos",a:[n.a[0]]}};if(n.n==="cos")return{t:"fn",n:"sin",a:[n.a[0]]};if(n.n==="exp")return n}throw Error("Offline symbolic integration supports powers, sums, constants, sin, cos, and exp.")}
function mathSteps(query){const clean=query.trim().replace(/^(what is|calculate|compute|evaluate|simplify)\s+/i,"").replace(/\?$/,"");let m,expr,steps=[],answer;
 if((m=clean.match(/^(?:derivative|differentiate|d\/dx)(?:\s+of)?\s+(.+)$/i))){expr=parse(m[1]);const d=simp(deriv(expr));answer=str(d);steps=["Apply the derivative rule term by term (including the chain rule where needed).",`d/dx (${str(expr)}) = ${answer}`];return{answer,steps,graph:answer}}
 if((m=clean.match(/^(?:integrate|integral|antiderivative)(?:\s+of)?\s+(.+)$/i))){expr=parse(m[1]);const r=simp(integrate(expr));answer=str(r)+" + C";steps=["Integrate each term using the power rule or a standard antiderivative.",`∫ (${str(expr)}) dx = ${answer}`];return{answer,steps}}
 if((m=clean.match(/^limit\s+(.+?)\s+(?:as\s+)?x\s*(?:->|→|to)\s*(.+)$/i))){expr=parse(m[1]);const pt=ev(parse(m[2].replace(/infinity|inf/gi,"1e12")));let val=ev(expr,{x:pt});if(!Number.isFinite(val)){const eps=Math.max(1e-8,Math.abs(pt)*1e-8),left=ev(expr,{x:pt-eps}),right=ev(expr,{x:pt+eps});val=Number.isFinite(left)&&Number.isFinite(right)?(left+right)/2:Number.isFinite(left)?left:right}answer=String(Number(val.toPrecision(10)));return{answer,steps:[`Substitute x = ${m[2]} into the expression where defined; use nearby values if direct substitution is indeterminate.`,`Limit = ${answer}`]}}
 if((m=clean.match(/^(factor|expand)(?:\s+of)?\s+(.+)$/i))){expr=parse(m[2]);const p=polynomial(expr,"x");if(m[1].toLowerCase()==="factor"&&p&&p.length===3){const rr=roots(p);if(rr.length===2){const factor=r=>r<0?`(x + ${-r})`:`(x - ${r})`;answer=`${factor(rr[0])} * ${factor(rr[1])}`;return{answer,steps:["Factor the quadratic using its roots.",`${str(expr)} = ${answer}`]}}}if(m[1].toLowerCase()==="expand"&&p){answer=polyString(p,"x");return{answer,steps:["Distribute products and combine like powers.",`${str(expr)} = ${answer}`]}}answer=str(simp(expr));return{answer,steps:[`${m[1]} the expression.`,`${str(expr)} = ${answer}`]}}
 if((m=clean.match(/^trigsimp\s+(.+)$/i))&&/sin\(x\)\s*(?:\^|\*\*)\s*2/.test(m[1])&&/cos\(x\)\s*(?:\^|\*\*)\s*2/.test(m[1]))return{answer:"1",steps:["Use sin(x)^2 + cos(x)^2 = 1.","Result: 1"]};
 if((m=clean.match(/^apart\s+(.+)$/i))){const rational=parse(m[1]);if(rational.t==="op"&&rational.op==="/"&&rational.b){const numerator=polynomial(rational.a,"x"),denominator=polynomial(rational.b,"x");if(numerator&&denominator&&denominator.length===3&&numerator.length<=3){const rr=roots(denominator);if(rr.length===2&&Math.abs(rr[0]-rr[1])>1e-10){const quotient=(numerator[2]||0)/(denominator[2]||1),remainder=numerator.map((v,i)=>v-quotient*(denominator[i]||0)),residue=r=>remainder.reduce((s,v,i)=>s+v*r**i,0)/(denominator[1]+2*denominator[2]*r),terms=rr.map(r=>({r,a:residue(r)})),fmtTerm=({r,a})=>`${a<0?" - ":" + "}${Math.abs(a)}/${r===0?"x":`(x ${r<0?"+ "+-r:"- "+r})`}`;answer=(quotient?String(quotient):"")+terms.map(fmtTerm).join("");if(answer.startsWith(" + "))answer=answer.slice(3);if(answer.startsWith(" - "))answer="-"+answer.slice(3);return{answer,steps:["Divide the numerator by the denominator if needed, then resolve the remainder over its distinct linear factors.",`${str(rational)} = ${answer}`]}}}}throw Error("Partial fractions supports rational expressions with two distinct linear denominator factors.")};
 expr=parse(clean);const simplified=simp(expr);answer=str(simplified);try{const val=ev(simplified);steps=["Apply parentheses, powers, multiplication/division, then addition/subtraction.",`${answer} = ${Number.isFinite(val)?Number(val.toPrecision(12)):val}`];answer=Number.isFinite(val)?String(Number(val.toPrecision(12))):String(val)}catch{steps=["Expression parsed and simplified.",`Result: ${answer}`]}
 return{answer,steps,graph:typeof simplified==="object"?str(simplified):null}
}
function polynomial(n,v){if(n.t==="num")return[n.v];if(n.t==="var")return n.n===v?[0,1]:null;if(n.t==="un"){const a=polynomial(n.a,v);return a&&a.map(x=>-x)}if(n.t==="op"){const a=polynomial(n.a,v),b=polynomial(n.b,v);if(n.op==="+"||n.op==="-"){if(!a||!b)return null;const r=Array(Math.max(a.length,b.length)).fill(0);for(let i=0;i<r.length;i++)r[i]=(a[i]||0)+(n.op==="+"?1:-1)*(b[i]||0);return r}if(n.op==="*"){if(!a||!b||a.length+b.length>4)return null;const r=Array(a.length+b.length-1).fill(0);a.forEach((x,i)=>b.forEach((y,j)=>r[i+j]+=x*y));return r}if(n.op==="/"&&b&&b.length===1)return a&&a.map(x=>x/b[0]);if(n.op==="**"&&b&&b.length===1&&Number.isInteger(b[0])&&b[0]>=0&&b[0]<=2)return polynomialPower(a,b[0])}return null}
function polynomialPower(a,p){if(!a)return null;let r=[1];for(let k=0;k<p;k++){const next=Array(r.length+a.length-1).fill(0);r.forEach((x,i)=>a.forEach((y,j)=>next[i+j]+=x*y));r=next}return r}
function polyString(p,v){const terms=[];for(let i=p.length-1;i>=0;i--){const c=p[i]||0;if(Math.abs(c)<1e-12)continue;const magnitude=Math.abs(c),body=i===0?String(magnitude):`${magnitude===1?"":magnitude+"*"}${v}${i===1?"":"^"+i}`;terms.push((terms.length?(c<0?" - ":" + "):(c<0?"-":""))+body)}return terms.join("")||"0"}
function roots(poly){while(poly.length>1&&Math.abs(poly.at(-1))<1e-12)poly.pop();if(poly.length===1)return[];if(poly.length===2)return[-poly[0]/poly[1]];if(poly.length===3){const[a,b,c]=poly,disc=b*b-4*c*a;if(disc<0)return[];if(disc===0)return[-b/(2*c)];return[(-b+Math.sqrt(disc))/(2*c),(-b-Math.sqrt(disc))/(2*c)]}throw Error("Only linear and quadratic equations can be solved in this offline build.")}
function linearForm(node,vars){const zero=Object.fromEntries(vars.map(v=>[v,0])),base=ev(node,zero),coeff=vars.map(v=>ev(node,{...zero,[v]:1})-base);if(Math.abs(ev(node,Object.fromEntries(vars.map(v=>[v,1])))-base-coeff.reduce((a,b)=>a+b,0))>1e-8)throw Error("System equations must be linear.");return[...coeff,-base]}
function solveSystem(text){const eqs=splitComma(text).filter(Boolean);if(eqs.length<2||!eqs.every(e=>e.includes("=")))throw Error("Enter a system such as x+y=10, x-y=2.");const vars=[...new Set(eqs.join(" ").match(/[A-Za-z_]\w*/g)||[])].filter(x=>!funcs.has(x.toLowerCase())&&!["pi","e"].includes(x.toLowerCase()));if(vars.length!==2)throw Error("The offline system solver supports two variables.");const rows=eqs.slice(0,2).map(e=>{const[l,r]=e.split("=");return linearForm(parse(l+"-("+r+")"),vars)});const det=rows[0][0]*rows[1][1]-rows[1][0]*rows[0][1];if(Math.abs(det)<1e-12)throw Error("System has no unique solution.");const a=(rows[0][2]*rows[1][1]-rows[1][2]*rows[0][1])/det,b=(rows[0][0]*rows[1][2]-rows[1][0]*rows[0][2])/det;return{answer:`${vars[0]} = ${a}, ${vars[1]} = ${b}`,steps:[`Start with ${eqs.slice(0,2).join(" and ")}.`,`Solve by elimination/substitution: ${vars[0]} = ${a}.`,`Substitute back: ${vars[1]} = ${b}.`]}}
function splitComma(s){let depth=0,start=0,out=[];for(let i=0;i<s.length;i++){if("([{".includes(s[i]))depth++;if(")]}".includes(s[i]))depth--;if(s[i]===","&&depth===0){out.push(s.slice(start,i).trim());start=i+1}}out.push(s.slice(start).trim());return out}
function solveQuery(raw){let q=raw.trim().replace(/\?$/,""),m;const strip=q.replace(/^(what is|calculate|compute|solve|evaluate|find|simplify)\s+/i,"");
 if((m=strip.match(/^(?:convert\s+)?([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*([a-z/]+)\s+(?:to|in|into)\s+([a-z/]+)$/i)))return convert(m[1],m[2],m[3]);
 if(q.includes("=")&&splitComma(q).filter(x=>x.includes("=")).length>1)return solveSystem(q.replace(/\bgraph\b/ig,""));
 if((m=strip.match(/^(?:det|inv|eigen|rref)\s+(.+)$/i)))return matrixOp(strip.match(/^\w+/)[0].toLowerCase(),m[1]);
 if((m=strip.match(/^stats\s+(.+)$/i)))return stats(m[1]);
 if((m=strip.match(/^prime\s+factors?\s+(.+)$/i)))return primeFactors(m[1]);
 if((m=strip.match(/^(gcd|lcm)\s+(.+)$/i)))return gcdLcm(m[1],m[2]);
 if((m=strip.match(/^sum\s+(.+?)\s+from\s+(.+?)\s+to\s+(.+)$/i))){let f=parse(m[1]),a=ev(parse(m[2])),b=m[3].match(/oo|inf/i)?100000:Number(ev(parse(m[3]))),v=(m[1].match(/\bn\b/)||["n"])[0],total=0;for(let i=a;i<=Math.min(b,100000);i++)total+=ev(f,{[v]:i});return{answer:String(total),steps:[`Sum ${m[1]} from ${a} to ${m[3]}.`,`Finite sum approximation/result: ${total}.`]}}
 if((m=strip.match(/^series\s+(.+?)(?:\s+around\s+([-+\d.]+))?(?:\s+to\s+order\s+(\d+))?$/i)))return taylor(m[1],Number(m[2]||0),Number(m[3]||6)-1);
 if((m=strip.match(/^ode\s+(.+)$/i)))return{answer:m[1].includes("y' = y")||m[1].includes("y'=y")?"y(x) = C1*exp(x)":"ODE is recognized, but the offline symbolic ODE solver only handles y' = k*y.",steps:["Interpret y' as dy/dx.",m[1].includes("y' = y")||m[1].includes("y'=y")?"Separate variables: dy/y = dx; integrate to obtain y = C1·e^x.":"Supported offline pattern: y' = k*y."]};
 if((m=strip.match(/^(?:graph|plot)\s+(.+?)(?:\s+from\s+([-+\d.]+)\s+to\s+([-+\d.]+))?$/i))){const exp=m[1].replace(/^y\s*=\s*/i,"");showMain("OmniMath Solver");showSolver("Calculator");$("query").value="";draw2D(exp,Number(m[2]||-10),Number(m[3]||10));return{answer:"Opened the interactive 2D grapher below.",steps:[`Plot y = ${exp} from ${m[2]||-10} to ${m[3]||10}.`]}}
 if(strip.includes("=")){const parts=splitComma(strip);if(parts.length>1)return solveSystem(strip);const[l,r]=strip.split("="),vars=[...new Set((l+" "+r).match(/[A-Za-z_]\w*/g)||[])].filter(x=>!funcs.has(x.toLowerCase())&&!["pi","e"].includes(x.toLowerCase()));const v=vars[0]||"x",p=polynomial(parse(l+"-("+r+")"),v);if(!p)throw Error("Only linear/quadratic equations can be solved offline.");const rr=roots(p);return{answer:`${v} = ${rr.join(" or ")||"no real solutions"}`,steps:[`Move all terms to one side: ${str(simp(parse(l+"-("+r+")")))} = 0.`,`Apply the ${p.length===3?"quadratic formula":"linear isolation"} to obtain ${v} = ${rr.join(" or ")||"no real solutions"}.`]}}
 return mathSteps(strip)}
function convert(num,from,to){const f=from.toLowerCase(),t=to.toLowerCase(),groups={length:{m:1,meter:1,meters:1,km:1000,kilometer:1000,kilometers:1000,cm:.01,centimeter:.01,centimeters:.01,mm:.001,millimeter:.001,millimeters:.001,mi:1609.344,mile:1609.344,miles:1609.344,yd:.9144,yard:.9144,yards:.9144,ft:.3048,foot:.3048,feet:.3048,in:.0254,inch:.0254,inches:.0254},mass:{kg:1,kilogram:1,kilograms:1,g:.001,gram:.001,grams:.001,mg:1e-6,milligram:1e-6,milligrams:1e-6,lb:.45359237,lbs:.45359237,pound:.45359237,pounds:.45359237,oz:.0283495231,ounce:.0283495231,ounces:.0283495231},time:{s:1,sec:1,second:1,seconds:1,min:60,minute:60,minutes:60,hr:3600,hour:3600,hours:3600,day:86400,days:86400},speed:{"m/s":1,"km/h":1/3.6,kph:1/3.6,mph:.44704},angle:{rad:1,radian:1,radians:1,deg:Math.PI/180,degree:Math.PI/180,degrees:Math.PI/180}};const temp={c:"c",celsius:"c",f:"f",fahrenheit:"f",k:"k",kelvin:"k"};if(temp[f]&&temp[t]){let c=temp[f]==="c"?+num:temp[f]==="f"?(+num-32)*5/9:+num-273.15;let v=temp[t]==="c"?c:temp[t]==="f"?c*9/5+32:c+273.15;return{answer:`${num} ${from} = ${v} ${to}`,steps:["Convert through the Celsius temperature scale.",`${num} ${from} = ${v} ${to}.`]}}for(const g of Object.values(groups))if(f in g&&t in g)return{answer:`${num} ${from} = ${Number((num*g[f]/g[t]).toPrecision(8))} ${to}`,steps:[`Convert through the common ${from} / ${to} base unit.`,`Result: ${Number((num*g[f]/g[t]).toPrecision(8))} ${to}.`]};throw Error("Those units are incompatible or not recognized.")}
function matrixOp(op,text){let m;try{m=JSON.parse(text.replace(/\s/g,""))}catch{throw Error("Use JSON-like rows, for example [[1,2],[3,4]].")}if(!Array.isArray(m)||!m.length||m.some(r=>!Array.isArray(r)||r.length!==m[0].length))throw Error("Matrix rows must have equal lengths.");const A=m.map(r=>r.map(Number)),n=A.length;if(op==="det"){if(n!==A[0].length)throw Error("Determinant requires a square matrix.");let d=1,B=A.map(r=>r.slice());for(let i=0;i<n;i++){let p=i;for(let j=i+1;j<n;j++)if(Math.abs(B[j][i])>Math.abs(B[p][i]))p=j;if(!B[p][i])return{answer:"0",steps:["The matrix is singular; determinant = 0."]};if(p!==i){[B[p],B[i]]=[B[i],B[p]];d=-d}d*=B[i][i];for(let j=i+1;j<n;j++){let q=B[j][i]/B[i][i];for(let k=i+1;k<n;k++)B[j][k]-=q*B[i][k]}}return{answer:String(d),steps:[`Apply Gaussian elimination to the ${n}×${n} matrix.`,`Determinant = ${d}.`]}}if(op==="rref"||op==="inv"){let B=A.map((r,i)=>r.concat(op==="inv"?Array.from({length:n},(_,j)=>+(i===j)):[]));if(op==="inv"&&n!==A[0].length)throw Error("Inverse requires a square matrix.");let row=0;for(let col=0;col<A[0].length&&row<B.length;col++){let p=row;for(let j=row+1;j<B.length;j++)if(Math.abs(B[j][col])>Math.abs(B[p][col]))p=j;if(Math.abs(B[p][col])<1e-12)continue;[B[p],B[row]]=[B[row],B[p]];let q=B[row][col];B[row]=B[row].map(x=>x/q);for(let j=0;j<B.length;j++)if(j!==row){q=B[j][col];B[j]=B[j].map((x,k)=>x-q*B[row][k])}row++}return{answer:JSON.stringify(op==="inv"?B.map(r=>r.slice(n)):B),steps:["Use Gauss-Jordan row reduction.",`${op.toUpperCase()} = ${JSON.stringify(op==="inv"?B.map(r=>r.slice(n)):B)}.`]}}if(op==="eigen"&&n===2&&A[0].length===2){let tr=A[0][0]+A[1][1],d=A[0][0]*A[1][1]-A[0][1]*A[1][0],disc=tr*tr-4*d;if(disc<0)throw Error("Complex eigenvalues are not supported.");let vals=[(tr+Math.sqrt(disc))/2,(tr-Math.sqrt(disc))/2];return{answer:`Eigenvalues: ${vals.join(", ")} (2×2 matrix)`,steps:["Solve det(A − λI) = 0.",`Eigenvalues: ${vals.join(", ")}.`]}}throw Error("Eigenvalues are available for 2×2 matrices in this offline build.")}
function stats(text){const a=text.split(",").map(Number);if(a.some(x=>!Number.isFinite(x)))throw Error("Enter comma-separated numbers.");const s=[...a].sort((x,y)=>x-y),mean=a.reduce((x,y)=>x+y,0)/a.length,med=s.length%2?s[(s.length-1)/2]:(s[s.length/2-1]+s[s.length/2])/2,v=a.reduce((q,x)=>q+(x-mean)**2,0)/a.length,counts=new Map();a.forEach(x=>counts.set(x,(counts.get(x)||0)+1));const max=Math.max(...counts.values()),mode=max===1?"No mode":[...counts].filter(x=>x[1]===max).map(x=>x[0]).join(", ");return{answer:`Mean: ${mean}\nMedian: ${med}\nMode: ${mode}\nPopulation variance: ${v}\nPopulation standard deviation: ${Math.sqrt(v)}`,steps:["Sort values to find the median; calculate the arithmetic mean.",`Mean ${mean}; median ${med}; population variance ${v}; standard deviation ${Math.sqrt(v)}.`]}}
function primeFactors(text){let n=Math.trunc(Number(ev(parse(text))));if(!Number.isFinite(n)||n===0)throw Error("Enter a nonzero integer.");const original=n;let f=[];for(let p=2;p*p<=Math.abs(n);p++)while(n%p===0){f.push(p);n/=p}if(Math.abs(n)>1)f.push(n);return{answer:`${original} = ${f.join(" × ")||"1"}`,steps:["Repeatedly divide by the smallest prime factor.",`Prime factorization: ${f.join(" × ")||"1"}.`]}}
function gcdLcm(op,text){const ns=text.split(",").map(x=>Math.trunc(Number(ev(parse(x)))));if(ns.some(x=>!Number.isFinite(x)))throw Error("Enter integers.");function g(a,b){return b?g(b,a%b):Math.abs(a)}const r=ns.reduce((a,b)=>op==="gcd"?g(a,b):Math.abs(a*b)/g(a,b));return{answer:String(r),steps:[`Apply ${op.toUpperCase()} to ${ns.join(", ")}.`,`Result: ${r}.`]}}

let history=[];
try{const saved=JSON.parse(localStorage.getItem("omnimath-history")||"[]");if(Array.isArray(saved))history=saved}catch(e){$("agentStatus").textContent="Browser storage is unavailable; history will last for this page session."}
function saveHistory(){try{localStorage.setItem("omnimath-history",JSON.stringify(history))}catch(e){$("agentStatus").textContent="History is available for this page session, but browser storage could not save it: "+e.message}}
function runSolver(){const q=$("query").value;if(!q.trim())return;try{const r=solveQuery(q);$("solverResult").innerHTML="";const ans=document.createElement("div");ans.className="out";ans.textContent=r.answer;$("solverResult").append(ans);const ol=document.createElement("ol");ol.className="steps";(r.steps||[]).forEach(s=>{const li=document.createElement("li");li.textContent=s;ol.append(li)});$("solverResult").append(ol);history.unshift({query:q,answer:r.answer,steps:r.steps||[]});history=history.slice(0,80);saveHistory();renderHistory()}catch(e){$("solverResult").innerHTML="";const d=document.createElement("div");d.className="out bad";d.textContent=e.message;$("solverResult").append(d)}}
$("solve").onclick=runSolver;$("query").addEventListener("keydown",e=>{if(e.key==="Enter")runSolver()});
function runNotebook(){const vars={},lines=$("notebookInput").value.split(/\r?\n/),out=[];lines.forEach((line,i)=>{line=line.trim();if(!line||line.startsWith("#"))return;try{const m=line.match(/^([A-Za-z_]\w*)\s*=\s*(.+)$/);if(m){const tree=parse(m[2]),value=ev(tree,vars);vars[m[1]]=value;out.push(`${i+1}. ${m[1]} = ${str(simp(tree))} = ${value}`)}else out.push(`${i+1}. ${line} = ${ev(parse(line),vars)}`)}catch(e){out.push(`${i+1}. ${line} — ${e.message}`)}});$("notebookResult").textContent=out.join("\n")}
$("runNotebook").onclick=runNotebook;runNotebook();
function checkHomework(){const p=$("homeworkProblem").value,a=$("homeworkAttempt").value;if(!p||!a){$("homeworkResult").textContent="Enter both the original problem and your answer.";return}try{const expected=solveQuery(p).answer,submittedParts=splitComma(a),expectedAssignments=[...expected.matchAll(/([A-Za-z_]\w*)\s*=\s*(-?(?:\d+(?:\.\d*)?|\.\d+))/g)],attemptAssignments={};for(const part of submittedParts){const m=part.match(/^\s*([A-Za-z_]\w*)\s*=\s*(.+)$/);if(m)attemptAssignments[m[1]]=ev(parse(m[2]))}let correct=false;if(expectedAssignments.length){correct=expectedAssignments.length===Object.keys(attemptAssignments).length&&expectedAssignments.every(([,name,value])=>Math.abs(attemptAssignments[name]-Number(value))<1e-8)}else{try{const expectedExpr=parse(expected.replace(/\s*\+\s*C$/,"")),attemptExpr=parse(a.includes("=")?a.split("=").at(-1):a);let exact=true;for(const x of [-2,-1,.3,1,2]){let evExpected,evAttempt;try{evExpected=ev(expectedExpr,{x});evAttempt=ev(attemptExpr,{x})}catch{exact=false;break}if(!Number.isFinite(evExpected)||Math.abs(evExpected-evAttempt)>1e-6){exact=false;break}}correct=exact;if(!correct&&/^(?:integrate|integral|antiderivative)\b/i.test(p.trim())){const integrand=parse(p.trim().replace(/^(?:integrate|integral|antiderivative)(?:\s+of)?\s*/i,"")),derived=deriv(attemptExpr);correct=[-2,-1,.3,1,2].every(x=>Math.abs(ev(derived,{x})-ev(integrand,{x}))<1e-6)}}catch{}}const diagnostic=correct?"Your answer is equivalent to the expected result.":"Your answer differs from the canonical result. Re-check signs, coefficients, and operation order.",steps=[`Original: ${p}`,`Expected result: ${expected}`,`Submitted answer: ${a}`,diagnostic];$("homeworkResult").innerHTML="";const d=document.createElement("div");d.className="out "+(correct?"good":"warn");d.textContent=diagnostic+"\nExpected: "+expected+"\nParsed attempt: "+a;$("homeworkResult").append(d);const ol=document.createElement("ol");steps.forEach(s=>{const li=document.createElement("li");li.textContent=s;ol.append(li)});$("homeworkResult").append(ol)}catch(e){$("homeworkResult").textContent="Could not parse: "+e.message}}
$("checkHomework").onclick=checkHomework;
function renderHistory(){const el=$("historyList");el.textContent="";if(!history.length){el.textContent="Solved problems will appear here for selection and export.";return}history.forEach((r,i)=>{const l=document.createElement("label"),c=document.createElement("input");c.type="checkbox";c.dataset.index=i;c.style.width="auto";l.append(c,document.createTextNode(` ${i+1}. ${r.query} → ${r.answer}`));el.append(l,document.createElement("br"))})}
function download(name,data,type){const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([data],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function studyText(){const chosen=[...$("historyList").querySelectorAll("input:checked")].map(x=>history[+x.dataset.index]);const rows=chosen.length?chosen:history;return"# OmniMath Study Sheet\n\n"+rows.map((r,i)=>`## ${i+1}. ${r.query}\n\n**Answer:** ${r.answer}\n\n### Steps\n${r.steps.map((s,j)=>`${j+1}. ${s}`).join("\n")||"No steps available."}`).join("\n\n")}
$("studyDownload").onclick=()=>download("omnimath-study-sheet.md",studyText(),"text/markdown");$("downloadFull").onclick=()=>alert("The Stlite full-app export remains available from the Streamlit sidebar. This downloaded file is the standalone JavaScript edition.");

let graphState={expr:"x^2",xmin:-10,xmax:10,scale:1,offset:0};
function canvasSetup(c){const r=c.getBoundingClientRect(),d=window.devicePixelRatio||1;c.width=Math.max(1,r.width*d);c.height=Math.max(1,r.height*d);const ctx=c.getContext("2d");ctx.scale(d,d);return{ctx,w:r.width,h:r.height}}
function drawAxes(ctx,w,h,x0,x1,y0,y1){const fg=getComputedStyle(document.documentElement).getPropertyValue("--muted");ctx.strokeStyle=fg;ctx.lineWidth=1;ctx.beginPath();for(let x=Math.ceil(x0);x<=x1;x++){let px=(x-x0)/(x1-x0)*w;ctx.globalAlpha=x===0?.8:.18;ctx.moveTo(px,0);ctx.lineTo(px,h)}for(let y=Math.ceil(y0);y<=y1;y++){let py=(y1-y)/(y1-y0)*h;ctx.globalAlpha=y===0?.8:.18;ctx.moveTo(0,py);ctx.lineTo(w,py)}ctx.stroke();ctx.globalAlpha=1}
function sample(expr,x){return ev(parse(expr),{x})}
function draw2D(expr=graphState.expr,xmin=graphState.xmin,xmax=graphState.xmax){graphState={...graphState,expr,xmin,xmax};const wrap=$("calculatorPane"),old=document.getElementById("graphCard");if(old)old.remove();const card=document.createElement("div");card.id="graphCard";card.className="card";card.innerHTML='<h3>Interactive 2D Grapher</h3><div class="small">Drag to pan · scroll to zoom</div><div class="canvas-wrap"><canvas id="graphCanvas"></canvas></div>';wrap.append(card);const c=$("graphCanvas");function draw(){const{ctx,w,h}=canvasSetup(c),x0=graphState.xmin+graphState.offset,x1=graphState.xmax+graphState.offset,ySpan=(x1-x0)*h/w/2;drawAxes(ctx,w,h,x0,x1,-ySpan,ySpan);ctx.strokeStyle=getComputedStyle(document.documentElement).getPropertyValue("--accent");ctx.lineWidth=2;ctx.beginPath();let started=false;for(let i=0;i<=w;i++){const x=x0+(x1-x0)*i/w;let y;try{y=sample(expr,x)}catch{y=NaN}const py=h/2-y/ySpan*h/2;if(!Number.isFinite(y)||Math.abs(py)>h*4){started=false;continue}if(!started){ctx.moveTo(i,py);started=true}else ctx.lineTo(i,py)}ctx.stroke()}let drag=null;c.onpointerdown=e=>{drag=[e.clientX,graphState.offset];c.setPointerCapture(e.pointerId)};c.onpointermove=e=>{if(drag){graphState.offset=drag[1]-(e.clientX-drag[0])/(c.clientWidth||1)*(graphState.xmax-graphState.xmin);draw()}};c.onpointerup=()=>drag=null;c.onwheel=e=>{e.preventDefault();const center=graphState.offset+(graphState.xmin+graphState.xmax)/2,f=e.deltaY>0?1.12:.89,span=(graphState.xmax-graphState.xmin)*f;graphState.xmin=-span/2;graphState.xmax=span/2;graphState.offset=center-(graphState.xmin+graphState.xmax)/2;draw()};draw()}
function drawCanvasPlot(canvas,series,domain){const{ctx,w,h}=canvasSetup(canvas);let values=[];for(const s of series)for(let i=0;i<=250;i++){let x=domain[0]+(domain[1]-domain[0])*i/250;try{values.push(s.fn(x))}catch{}}let ymin=Math.min(0,...values.filter(Number.isFinite)),ymax=Math.max(0,...values.filter(Number.isFinite));if(ymax-ymin<1e-8){ymin-=1;ymax+=1}const pad=(ymax-ymin)*.1;ymin-=pad;ymax+=pad;const px=x=>(x-domain[0])/(domain[1]-domain[0])*w,py=y=>h-(y-ymin)/(ymax-ymin)*h;drawAxes(ctx,w,h,Math.floor(domain[0]),Math.ceil(domain[1]),Math.floor(ymin),Math.ceil(ymax));const colors=[getComputedStyle(document.documentElement).getPropertyValue("--accent"),"#ff9f43","#50fa7b"];series.forEach((s,j)=>{ctx.beginPath();ctx.strokeStyle=colors[j%colors.length];ctx.lineWidth=2;let first=true;for(let i=0;i<=250;i++){let x=domain[0]+(domain[1]-domain[0])*i/250,y;try{y=s.fn(x)}catch{y=NaN}if(!Number.isFinite(y)){first=true;continue}if(first){ctx.moveTo(px(x),py(y));first=false}else ctx.lineTo(px(x),py(y))}ctx.stroke()})}
function taylor(expr,center,degree){let tree=parse(expr),terms=[],sum={t:"num",v:0},der=tree;for(let k=0;k<=degree;k++){let coeff=ev(der,{x:center})/fact(k);let term={t:"op",op:"*",a:{t:"num",v:coeff},b:{t:"op",op:"**",a:{t:"op",op:"-",a:{t:"var",n:"x"},b:{t:"num",v:center}},b:{t:"num",v:k}}};terms.push(term);sum={t:"op",op:"+",a:sum,b:term};der=deriv(der)}return{tree,poly:simp(sum),text:terms.map(str).join(" + ")}}
function fact(n){let a=1;for(let i=2;i<=n;i++)a*=i;return a}
function drawRiemann(){const c=$("riemannCanvas");if(!c)return;try{const f=parse($("riemannExpr").value),a=+$("riemannA").value,b=+$("riemannB").value,n=+$("riemannN").value,method=$("riemannMethod").value;if(!(b>a))throw Error("Upper bound must exceed lower bound.");const dx=(b-a)/n,rect=[],sum=0;let total=0;for(let i=0;i<n;i++){let x=a+i*dx+(method==="Left"?0:method==="Right"?dx:dx/2),y=ev(f,{x});rect.push([a+i*dx,y]);total+=y*dx}const samples=Array.from({length:251},(_,i)=>a+(b-a)*i/250);drawCanvasPlot(c,[{fn:x=>ev(f,{x})}], [a,b]);const {ctx,w,h}=canvasSetup(c),ys=samples.map(x=>{try{return ev(f,{x})}catch{return NaN}}),lo=Math.min(0,...ys.filter(Number.isFinite)),hi=Math.max(1e-9,...ys.filter(Number.isFinite)),pad=(hi-lo)*.1;let ymin=lo-pad,ymax=hi+pad;const py=y=>h-(y-ymin)/(ymax-ymin)*h;ctx.fillStyle=getComputedStyle(document.documentElement).getPropertyValue("--accent")+"55";ctx.strokeStyle=getComputedStyle(document.documentElement).getPropertyValue("--accent");rect.forEach(([x,y])=>{const x0=(x-a)/(b-a)*w,x1=(x+dx-a)/(b-a)*w,y0=py(0),y1=py(y);ctx.fillRect(x0,Math.min(y0,y1),x1-x0,y0-y1);ctx.strokeRect(x0,Math.min(y0,y1),x1-x0,y0-y1)});$("riemannMetrics").innerHTML="";const m=document.createElement("div");m.className="metric";m.innerHTML=`<strong>${total.toPrecision(8)}</strong>${method} Riemann sum (n=${n})`;$("riemannMetrics").append(m)}catch(e){$("riemannMetrics").textContent=e.message}}
function drawTaylor(){const c=$("taylorCanvas");if(!c)return;try{const exp=$("taylorExpr").value,center=+$("taylorCenter").value,d=+$("taylorDegree").value,span=+$("taylorSpan").value,t=taylor(exp,center,d),f=parse(exp);drawCanvasPlot(c,[{fn:x=>ev(f,{x})},{fn:x=>ev(t.poly,{x})}],[center-span,center+span]);$("taylorResult").textContent=`T${d}(x) = ${str(t.poly)}`}catch(e){$("taylorResult").textContent="Could not build Taylor approximation: "+e.message}}
$("riemannN").oninput=()=>{$("riemannNOut").value=$("riemannN").value;drawRiemann()};["riemannExpr","riemannA","riemannB","riemannMethod"].forEach(id=>$(id).oninput=drawRiemann);
["taylorExpr","taylorCenter","taylorDegree","taylorSpan"].forEach(id=>$(id).oninput=()=>{$("taylorDegreeOut").value=$("taylorDegree").value;$("taylorSpanOut").value=$("taylorSpan").value;drawTaylor()});

let surfaceState={rotX:-.7,rotZ:.7,zoom:1,drag:null};
function surfaceValue(x,y){return ev(parse($("surfaceExpr").value),{x,y})}
function drawSurface(){const c=$("surfaceCanvas");if(!c||$("surfacePage").classList.contains("hidden"))return;const{ctx,w,h}=canvasSetup(c),xRange=+$("surfaceXRange").value,yRange=+$("surfaceYRange").value,maxRange=Math.max(xRange,yRange),res=24,points=[],zvals=[];try{for(let i=0;i<=res;i++){points[i]=[];for(let j=0;j<=res;j++){const x=(i/res*2-1)*xRange,y=(j/res*2-1)*yRange,z=surfaceValue(x,y);points[i][j]={x,y,z};if(Number.isFinite(z))zvals.push(z)}}}catch(e){$("surfaceResult").textContent="Could not evaluate surface: "+e.message;return}const zscale=Math.max(1,...zvals.map(Math.abs)),scale=Math.min(w,h)*.42/maxRange*surfaceState.zoom,minZ=Math.min(...zvals),maxZ=Math.max(...zvals),palettes={Viridis:["#440154","#31688e","#35b779","#fde725"],Plasma:["#0d0887","#9c179e","#ed7953","#f0f921"],Inferno:["#000004","#57106e","#bc3754","#fcffa4"],Cividis:["#00204c","#575d6d","#a59c74","#fee838"]},palette=palettes[$("surfaceScale").value]||palettes.Viridis;function colorAt(z){const t=maxZ===minZ?0.5:(z-minZ)/(maxZ-minZ),segment=t*3,index=Math.min(2,Math.floor(segment)),f=segment-index,parseHex=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16)),a=parseHex(palette[index]),b=parseHex(palette[index+1]);return"rgb("+a.map((v,i)=>Math.round(v+(b[i]-v)*f)).join(",")+")"}function project(p){const x=p.x,y=p.y,z=p.z/zscale*maxRange,cz=Math.cos(surfaceState.rotZ),sz=Math.sin(surfaceState.rotZ),cx=Math.cos(surfaceState.rotX),sx=Math.sin(surfaceState.rotX),u=x*cz-y*sz,v=(x*sz+y*cz)*cx-z*sx,q=(x*sz+y*cz)*sx+z*cx;return[w/2+u*scale,h/2+v*scale-q*scale*.3]}ctx.lineWidth=.8;ctx.globalAlpha=.78;for(let i=0;i<=res;i++){for(let axis=0;axis<2;axis++){ctx.beginPath();let active=false,totalZ=0,count=0;for(let j=0;j<=res;j++){const p=axis===0?points[i][j]:points[j][i];if(!Number.isFinite(p.z)){active=false;continue}const [px,py]=project(p);if(!active){ctx.moveTo(px,py);active=true;totalZ=p.z;count=1}else{ctx.lineTo(px,py);totalZ+=p.z;count++}}ctx.strokeStyle=colorAt(totalZ/count);ctx.stroke()}}ctx.globalAlpha=1;$("surfaceResult").textContent=`z = ${$("surfaceExpr").value} · drag to rotate · scroll to zoom`}
const sc=$("surfaceCanvas");sc.onpointerdown=e=>{surfaceState.drag=[e.clientX,e.clientY];sc.setPointerCapture(e.pointerId)};sc.onpointermove=e=>{if(surfaceState.drag){surfaceState.rotZ+=(e.clientX-surfaceState.drag[0])*.01;surfaceState.rotX+=(e.clientY-surfaceState.drag[1])*.01;surfaceState.drag=[e.clientX,e.clientY];drawSurface()}};sc.onpointerup=()=>surfaceState.drag=null;sc.onwheel=e=>{e.preventDefault();surfaceState.zoom*=e.deltaY>0?.92:1.08;drawSurface()};
$("surfacePlot").onclick=drawSurface;["surfaceXRange","surfaceYRange","surfaceScale"].forEach((id,i)=>$(id).oninput=()=>{if(i<2)$(i?"surfaceYOut":"surfaceXOut").value=$(id).value;drawSurface()});[["Paraboloid","x^2 + y^2"],["Saddle","x^2 - y^2"],["Ripple","sin(sqrt(x^2 + y^2))"],["Sine plane","sin(x) * cos(y)"]].forEach(([label,expression])=>{const b=document.createElement("button");b.textContent=label;b.onclick=()=>{$("surfaceExpr").value=expression;drawSurface()};$("surfacePresets").append(b)});

const simDefaults={"Projectile Motion with Air Drag":[["Launch velocity (m/s)",50,1,100,1],["Launch angle (degrees)",45,0,90,1],["Gravity (m/s²)",9.8,1,20,.1],["Normalized quadratic drag coefficient (1/m)",.02,0,.2,.005]],"Damped Harmonic Oscillator":[["Mass, m (kg)",1,.1,10,.1],["Spring constant, k (N/m)",20,.1,50,.1],["Damping coefficient, c (N·s/m)",2,0,20,.1]],"RC / RLC Circuit Transient Response":[["Resistance, R (Ω)",100,1,1000,1],["Inductance, L (H; set to 0 for an RC circuit)",.1,0,5,.01],["Capacitance, C (F)",.001,.0001,.01,.0001],["Input voltage (V)",12,1,240,1]]};
function simControls(){const name=$("simulator").value,root=$("simControls");root.innerHTML="";simDefaults[name].forEach(([label,val,min,max,step],i)=>{const d=document.createElement("div");d.className="sim-control";const id="sim"+i,l=document.createElement("label"),r=document.createElement("input");l.htmlFor=id;l.textContent=label+" ";r.id=id;r.type="range";r.min=min;r.max=max;r.step=step;r.value=val;r.oninput=()=>{l.textContent=label+" ("+Number(r.value).toPrecision(4)+")";drawSimulator()};l.textContent=label+" ("+Number(val).toPrecision(4)+")";d.append(l,r);root.append(d)});drawSimulator()}
function simVals(){return[...$("simControls").querySelectorAll("input")].map(x=>+x.value)}
let simAnimation=0;
function plotSeries(canvas,series,title){if(simAnimation)cancelAnimationFrame(simAnimation);let vals=[];series.forEach(s=>vals.push(...s.data.map(p=>p[1]).filter(Number.isFinite)));let ymin=Math.min(0,...vals),ymax=Math.max(0,...vals);if(ymax-ymin<1e-8){ymin-=1;ymax+=1}const pad=(ymax-ymin)*.12;ymin-=pad;ymax+=pad;const xmax=Math.max(...series.flatMap(s=>s.data.map(p=>p[0]))),started=performance.now();function paint(progress){const{ctx,w,h}=canvasSetup(canvas),px=x=>x/xmax*w,py=y=>h-(y-ymin)/(ymax-ymin)*h;drawAxes(ctx,w,h,0,Math.ceil(xmax),Math.floor(ymin),Math.ceil(ymax));series.forEach((s,i)=>{ctx.beginPath();ctx.strokeStyle=[getComputedStyle(document.documentElement).getPropertyValue("--accent"),"#ff9f43","#50fa7b"][i%3];ctx.lineWidth=2;s.data.forEach(([x,y],j)=>j?ctx.lineTo(px(x),py(y)):ctx.moveTo(px(x),py(y)));ctx.stroke()});ctx.fillStyle=getComputedStyle(document.documentElement).getPropertyValue("--fg");ctx.fillText(title,8,18);const data=series[0].data,index=Math.min(data.length-1,Math.floor(progress*(data.length-1))),point=data[index];if(point){ctx.beginPath();ctx.fillStyle=getComputedStyle(document.documentElement).getPropertyValue("--accent");ctx.arc(px(point[0]),py(point[1]),5,0,Math.PI*2);ctx.fill()}}function tick(now){if($("simPage").classList.contains("hidden")){simAnimation=0;return}paint(((now-started)%4500)/4500);simAnimation=requestAnimationFrame(tick)}paint(0);simAnimation=requestAnimationFrame(tick)}
function projectilePath(speed,angle,g,drag){const rad=angle*Math.PI/180,dt=.02,state=[0,0,speed*Math.cos(rad),speed*Math.sin(rad)],path=[[0,0]];let flight=0,maxY=0;const deriv=s=>{const velocity=Math.hypot(s[2],s[3]);return[s[2],s[3],-drag*velocity*s[2],-g-drag*velocity*s[3]]},step=(s,k,f)=>s.map((v,i)=>v+f*k[i]);for(let i=1;i<=10000;i++){const k1=deriv(state),k2=deriv(step(state,k1,dt/2)),k3=deriv(step(state,k2,dt/2)),k4=deriv(step(state,k3,dt)),next=state.map((v,j)=>v+dt*(k1[j]+2*k2[j]+2*k3[j]+k4[j])/6);if(next[1]<=0){const fraction=state[1]/(state[1]-next[1]);for(let j=0;j<4;j++)state[j]+=fraction*(next[j]-state[j]);state[1]=0;flight=(i-1+fraction)*dt;path.push([state[0],state[1]]);break}for(let j=0;j<4;j++)state[j]=next[j];flight=i*dt;maxY=Math.max(maxY,state[1]);path.push([state[0],state[1]])}return{path,flight,maxY,range:state[0]}}
function drawSimulator(){if($("simPage").classList.contains("hidden"))return;const name=$("simulator").value,v=simVals(),c=$("simCanvas"),metrics=$("simMetrics");metrics.innerHTML="";let series=[],notes=[];const add=(label,value)=>{const d=document.createElement("div");d.className="metric";d.innerHTML=`<span>${label}</span><strong>${value}</strong>`;metrics.append(d)};
 if(name.startsWith("Projectile")){const [speed,deg,g,drag]=v,ang=deg*Math.PI/180,tmax=2*speed*Math.sin(ang)/g,N=300,ideal=[],trajectory=projectilePath(speed,deg,g,drag);for(let i=0;i<=N;i++){const t=tmax*i/N;ideal.push([speed*Math.cos(ang)*t,speed*Math.sin(ang)*t-.5*g*t*t])}series=[{data:ideal},{data:trajectory.path}];add("Ideal max height",`${(speed**2*Math.sin(ang)**2/(2*g)).toFixed(2)} m`);add("Ideal range",`${(speed**2*Math.sin(2*ang)/g).toFixed(2)} m`);add("Ideal flight time",`${tmax.toFixed(2)} s`);add("Drag max height",`${trajectory.maxY.toFixed(2)} m`);add("Drag range",`${trajectory.range.toFixed(2)} m`);add("Drag flight time",`${trajectory.flight.toFixed(2)} s`);plotSeries(c,series,"Projectile trajectory: ideal / drag")}
 else if(name.startsWith("Damped")){const[m,k,d]=v,disc=d*d-4*m*k,dataX=[],dataV=[];for(let i=0;i<=500;i++){const t=i/50;let x,vel;if(disc< -1e-10){const r=-d/(2*m),w=Math.sqrt(4*m*k-d*d)/(2*m),B=-r/w,e=Math.exp(r*t);x=e*(Math.cos(w*t)+B*Math.sin(w*t));vel=-e*(r*r+w*w)/w*Math.sin(w*t)}else if(disc>1e-10){const q=Math.sqrt(disc),r1=(-d+q)/(2*m),r2=(-d-q)/(2*m),c1=-r2/(r1-r2),c2=r1/(r1-r2);x=c1*Math.exp(r1*t)+c2*Math.exp(r2*t);vel=r1*c1*Math.exp(r1*t)+r2*c2*Math.exp(r2*t)}else{const r=-d/(2*m),e=Math.exp(r*t);x=(1-r*t)*e;vel=-r*r*t*e}dataX.push([t,x]);dataV.push([t,vel])}series=[{data:dataX},{data:dataV}];add("Damping type",disc<0?"underdamped":disc>0?"overdamped":"critically damped");add("Mass",`${m} kg`);add("Spring constant",`${k} N/m`);add("Initial displacement","1 m");plotSeries(c,series,"Spring-mass-damper: x(t) / v(t)")}
 else{const[R,L,C,V]=v,duration=Math.max(5*R*C,10*Math.PI*Math.sqrt(L*C),.1),voltage=[],current=[];let type="RC response";for(let i=0;i<=500;i++){const t=duration*i/500;let vc,cur;if(L===0){vc=V*(1-Math.exp(-t/(R*C)));cur=V/R*Math.exp(-t/(R*C))}else{const w02=1/(L*C),alpha=R/(2*L),D=alpha*alpha-w02;if(D< -1e-12*w02){const w=Math.sqrt(-D),e=Math.exp(-alpha*t);vc=V*(1-e*(Math.cos(w*t)+alpha/w*Math.sin(w*t)));cur=V/(L*w)*e*Math.sin(w*t);type="underdamped RLC response"}else if(D>1e-12*w02){const root=Math.sqrt(D),r1=-alpha+root,r2=-alpha-root,c1=r2/(r1-r2),c2=-r1/(r1-r2),e1=Math.exp(r1*t),e2=Math.exp(r2*t);vc=V*(1+c1*e1+c2*e2);cur=V*C*(c1*r1*e1+c2*r2*e2);type="overdamped RLC response"}else{const e=Math.exp(-alpha*t);vc=V*(1-(1+alpha*t)*e);cur=V*C*alpha*alpha*t*e;type="critically damped RLC response"}}voltage.push([t,vc]);current.push([t,cur])}series=[{data:voltage},{data:current}];add("Response",type);add("Input voltage",`${V} V`);add("Resistance",`${R} Ω`);add("Capacitance",`${C} F`);plotSeries(c,series,"Circuit step response: capacitor voltage / current")}}
$("simulator").onchange=simControls;simControls();

function drawAll(){drawRiemann();drawTaylor();drawSurface();drawSimulator();if($("graphCanvas"))draw2D(graphState.expr,graphState.xmin,graphState.xmax)}
window.addEventListener("resize",()=>drawAll());
document.querySelectorAll(".category details").forEach(()=>{});
$("imageInput").onchange=e=>{const f=e.target.files[0];if(!f)return;const u=URL.createObjectURL(f);$("imagePreview").src=u;$("imagePreview").classList.remove("hidden");$("imageStatus").textContent="Image preview ready. Native browser OCR will be used if supported; otherwise enter the equation manually."};
$("extractImage").onclick=async()=>{if(!("TextDetector" in window)){ $("imageStatus").textContent="This browser does not provide offline TextDetector OCR. The selected image remains available for visual reference; type the equation into the solver.";return}const image=$("imagePreview");if(!image.src){$("imageStatus").textContent="Select an image first.";return}try{const detector=new TextDetector(),blocks=await detector.detect(image),text=blocks.map(b=>b.rawValue).join(" ");if(!text)throw Error("No text was detected.");$("query").value=text;$("imageStatus").textContent="Extracted text. Review it in the solver input.";showMain("OmniMath Solver");showSolver("Calculator")}catch(e){$("imageStatus").textContent="OCR could not process this image: "+e.message}};
function offlineAgent(text){let p=text.trim(),m;if((m=p.match(/area\s+of\s+(?:a\s+)?circle\s+(?:with\s+)?radius\s+([\d.]+)/i))){const r=+m[1],a=Math.PI*r*r;return{answer:`1. Use A = πr².\n2. Substitute r = ${r}: A = π × ${r}².\n3. Area = ${a}.`,query:`area of circle radius ${r}`}}const wordMatch=p.match(/^\s*if\s+(.+?)\s+then\s+(?:what\s+is|find|calculate|compute)\s+(.+?)[?.!]*$/i);if(wordMatch){const equationText=wordMatch[1].replace(/\bequals\b/gi,"=").replace(/\bis\b/gi,"=").replace(/\bplus\b/gi,"+").replace(/\bminus\b/gi,"-").replace(/\btimes\b/gi,"*").replace(/\bxy\b/gi,"x*y"),equations=equationText.split(/\s*,\s*|\s+\band\b\s+/i).filter(x=>x.includes("=")),solved=solveSystem(equations.join(", ")),values={};for(const [,name,value] of solved.answer.matchAll(/([A-Za-z_]\w*)\s*=\s*(-?(?:\d+(?:\.\d*)?|\.\d+))/g))values[name]=Number(value);const requested=wordMatch[2].replace(/\bxy\b/gi,"x*y").replace(/\bto the power of\b/gi,"^");const result=ev(parse(requested),values);return{answer:`1. Translate the conditions into equations: ${equations.join("; ")}.\n2. Solve the system: ${solved.answer}.\n3. Substitute into ${requested}: ${result}.\nAnswer: ${result}`,query:p}}if((m=p.match(/(?:twice|double)\s+(?:a|the|some)\s+number.*?(?:is|equals)\s+(\d+)/i))){const x=+m[1]/2;return{answer:`1. Let the unknown number be x.\n2. Twice the number means 2x = ${m[1]}.\n3. Divide by 2: x = ${x}.`,query:p}}const normalized=p.replace(/\bwhat is\b/i,"").replace(/\bplus\b/gi,"+").replace(/\bminus\b/gi,"-").replace(/\btimes\b/gi,"*").replace(/\bequals\b/gi,"=").replace(/\bsquared\b/gi,"^2");const result=solveQuery(normalized);return{answer:result.steps.map((s,i)=>`${i+1}. ${s}`).join("\n")+"\nAnswer: "+result.answer,query:p}}
function addChat(role,text){const d=document.createElement("div");d.className="message "+role;d.textContent=(role==="user"?"You: ":"OmniMath: ")+text;$("chatHistory").append(d);$("chatHistory").scrollTop=$("chatHistory").scrollHeight}
async function askAgent(){const prompt=$("agentPrompt").value.trim();if(!prompt)return;$("agentPrompt").value="";addChat("user",prompt);const key=$("apiKey").value.trim();try{let ans;if(key){$("agentStatus").textContent="Contacting Gemini; this sends the prompt and key to Google.";const res=await fetch("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key="+encodeURIComponent(key),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({contents:[{parts:[{text:"Solve the user's math question with numbered steps. Be concise. "+prompt}]}]})});if(!res.ok)throw Error("Gemini request failed (HTTP "+res.status+").");const data=await res.json();ans=data.candidates?.[0]?.content?.parts?.map(x=>x.text).join("")||"No response text returned.";$("agentStatus").textContent="Answered with Gemini."}else{const local=offlineAgent(prompt);ans=local.answer;$("agentStatus").textContent="Answered with the local offline solver."}addChat("assistant",ans);history.unshift({query:prompt,answer:ans,steps:[]});history=history.slice(0,80);saveHistory();renderHistory()}catch(e){$("agentStatus").textContent="Online request failed: "+e.message+" Local fallback:";try{addChat("assistant",offlineAgent(prompt).answer)}catch(localError){addChat("assistant","I couldn't solve that locally: "+localError.message)}}}
$("askAgent").onclick=askAgent;$("agentPrompt").addEventListener("keydown",e=>{if(e.key==="Enter")askAgent()});$("clearChat").onclick=()=>{$("chatHistory").innerHTML="";$("agentStatus").textContent=""};
themeInit();presetInit();tabsInit();renderHistory();drawAll();
</script>
</body>
</html>"""
