"""Check report structure, references, code syntax and proposed permission policy."""
import ast
import re
import sys
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "venv/Lib/site-packages"))
report = Path(__file__).with_name("INFORME.md").read_text(encoding="utf-8")
findings = re.split(r"(?m)^\*\*H\d{2}\. ", report)[1:]
assert len(findings) == 13
for index, finding in enumerate(findings, 1):
    for section in ("**1. Vulnerabilidad", "**2. Ubicación", "**3. Riesgo", "**4. Código"):
        assert section in finding, (index, section)

snippets = re.findall(r"```python\n(.*?)\n```", report, re.S)
for index, snippet in enumerate(snippets, 1):
    ast.parse(snippet, filename=f"report_python_snippet_{index}")

links = re.findall(r"\]\((C:/[^)]+)\)", report)
for link in links:
    line_match = re.search(r":(\d+)$", link)
    target = Path(link[:line_match.start()] if line_match else link)
    assert target.is_file(), target
    if line_match:
        assert 0 < int(line_match.group(1)) <= len(target.read_bytes().splitlines()), link

# Only the standalone permission class is executed; no app or DB is loaded.
namespace = {}
exec(compile(snippets[0], "proposed_club_permissions", "exec"), namespace)
permission = namespace["ClubPermissions"]()
meta = SimpleNamespace(app_label="usuarios", model_name="socios")
queryset = SimpleNamespace(model=SimpleNamespace(_meta=meta))

def allowed(action, grants=(), authenticated=True, active=True, report_view=False):
    user = SimpleNamespace(
        is_authenticated=authenticated, is_active=active,
        has_perm=lambda value: value in grants,
    )
    request = SimpleNamespace(user=user, method="GET" if action in ("list", "retrieve", None) else "POST")
    view = SimpleNamespace(action=action, queryset=queryset)
    if report_view:
        view.required_permission = "cobranzas.puede_ver_resumen_cobranzas"
    return permission.has_permission(request, view)

assert not allowed("list", authenticated=False)
assert not allowed("list")
assert allowed("list", {"usuarios.view_socios"})
assert not allowed("aprobar", {"usuarios.change_socios"})
assert allowed("aprobar", {"usuarios.puede_aprobar_socio"})
assert not allowed("aprobar", {"usuarios.puede_aprobar_socio"}, active=False)
assert not allowed("destroy", {"usuarios.view_socios"})
assert not allowed("unknown_action", {"usuarios.change_socios"})
assert not allowed(None, {"usuarios.view_socios"}, report_view=True)
assert allowed(None, {"cobranzas.puede_ver_resumen_cobranzas"}, report_view=True)

print(f"PASS: 13 findings contain the four requested sections; {len(snippets)} Python snippets parse")
print(f"PASS: {len(links)} local file/line references exist")
print("PASS: 10 proposed permission-policy scenarios; no SQL, app imports, or persistent changes")
