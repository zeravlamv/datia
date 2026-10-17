import ast
import multiprocessing as mp
import time
from decimal import Decimal
from typing import Dict, Any

ALLOWED_BUILTINS = {
    'len': len,
    'range': range,
    'sum': sum,
    'min': min,
    'max': max,
    'sorted': sorted,
}

ALLOWED_GLOBALS = {
    'Decimal': Decimal,
}

FORBIDDEN_NAMES = {
    '__builtins__', '__globals__', '__getattribute__', '__subclasses__'
}

FORBIDDEN_NODES = (
    ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.With, ast.Try, ast.Lambda
)

def validate_code(code: str) -> None:
    t = ast.parse(code)
    for n in ast.walk(t):
        if isinstance(n, FORBIDDEN_NODES):
            raise ValueError("Nodo no permitido")
        if isinstance(n, ast.Attribute):
            if getattr(n.attr, 'startswith', lambda x: False)('__'):
                raise ValueError("Acceso prohibido")
        if isinstance(n, ast.Name):
            if n.id in FORBIDDEN_NAMES:
                raise ValueError("Nombre prohibido")

def _runner(code: str, input_data: Dict[str, Any], pipe):
    try:
        validate_code(code)
        env = {'__builtins__': ALLOWED_BUILTINS}
        env.update(ALLOWED_GLOBALS)
        loc = {'input_data': input_data, 'output_data': {}}
        exec(code, env, loc)
        res = loc.get('output_data') or loc.get('result') or {}
        pipe.send({'ok': True, 'data': res})
    except Exception as e:
        pipe.send({'ok': False, 'error': str(e)})

def run_snippet(code: str, inputs: Dict[str, Any], timeout_ms: int = 3000) -> Dict[str, Any]:
    recv, send = mp.Pipe(False)
    p = mp.Process(target=_runner, args=(code, inputs, send))
    p.start()
    start = time.time()
    while True:
        if recv.poll(0.05):
            msg = recv.recv()
            p.terminate()
            if msg.get('ok'):
                return msg['data']
            raise RuntimeError(msg.get('error') or 'Error ejecución')
        if (time.time() - start) * 1000 > timeout_ms:
            p.terminate()
            raise TimeoutError("Timeout ejecución")

def build_code(spec: Dict[str, Any]) -> str:
    c = spec.get('compute')
    args = spec.get('args') or {}
    inp = spec.get('input')
    out = spec.get('output') or 'result'
    if c == 'moving_average':
        w = int(args.get('window', 3))
        series_key = str(inp)
        return (
            "def moving_average(series, w):\n"
            "    s=[Decimal(str(x or 0)) for x in series]\n"
            "    r=[]\n"
            "    for i in range(len(s)):\n"
            "        if i+1<w:\n"
            "            r.append(None)\n"
            "        else:\n"
            "            seg=s[i+1-w:i+1]\n"
            "            r.append(sum(seg)/Decimal(w))\n"
            "    return r\n"
            f"output_data['{out}']=moving_average(input_data.get('{series_key}', []), {w})\n"
        )
    if c == 'ratio':
        a = str(args.get('a'))
        b = str(args.get('b'))
        return (
            "def ratio(a,b):\n"
            "    res=[]\n"
            "    la=len(a); lb=len(b); m=min(la,lb)\n"
            "    for i in range(m):\n"
            "        av=Decimal(str(a[i] or 0))\n"
            "        bv=Decimal(str(b[i] or 0))\n"
            "        res.append((av/bv) if bv!=0 else None)\n"
            "    return res\n"
            f"output_data['{out}']=ratio(input_data.get('{a}', []), input_data.get('{b}', []))\n"
        )
    if c == 'normalize':
        k = str(inp)
        return (
            "def normalize(series):\n"
            "    s=[Decimal(str(x or 0)) for x in series]\n"
            "    if not s:\n"
            "        return []\n"
            "    mn=min(s); mx=max(s)\n"
            "    if mx==mn:\n"
            "        return [Decimal('0') for _ in s]\n"
            "    return [(x-mn)/(mx-mn) for x in s]\n"
            f"output_data['{out}']=normalize(input_data.get('{k}', []))\n"
        )
    raise ValueError("Compute no soportado")
