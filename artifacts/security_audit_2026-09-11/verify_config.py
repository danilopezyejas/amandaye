"""Read-only audit checks. No network, real DB connection, or dotenv loading."""
import ast
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "venv/Lib/site-packages"))

from django.conf import settings

settings.configure(
    SECRET_KEY="synthetic-audit-only-key",
    ALLOWED_HOSTS=["testserver"],
    INSTALLED_APPS=[],
    ROOT_URLCONF=__name__,
)
urlpatterns = []

from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.test import RequestFactory


def source_definitions(relative_path, names):
    path = ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    definitions = [node for node in tree.body if getattr(node, "name", None) in names]
    namespace = {"redirect": redirect}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


url_functions = source_definitions(
    "amandaye_backend/amandaye_backend/urls.py",
    {"fallback_redirect", "custom_404"},
)
middleware = source_definitions(
    "amandaye_backend/amandaye_backend/middleware.py", {"Redirect404Middleware"}
)["Redirect404Middleware"]
factory = RequestFactory()
request = factory.get("/missing-audit-path", HTTP_REFERER="https://attacker.invalid/")
results = {}
for name in ("fallback_redirect", "custom_404"):
    response = url_functions[name](request)
    assert response.status_code == 302 and response["Location"] == "https://attacker.invalid/"
    results[name] = {"status": response.status_code, "external_redirect": True}
response = middleware(lambda req: HttpResponseNotFound())(request)
assert response["Location"] == "https://attacker.invalid/"
results["middleware_external_redirect"] = True

settings_path = ROOT / "amandaye_backend/amandaye_backend/settings.py"
tree = ast.parse(settings_path.read_text(encoding="utf-8-sig"))
assignments = {
    node.targets[0].id: node.value
    for node in tree.body
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
}
secret_node = assignments["SECRET_KEY"]
results["secret_has_hardcoded_fallback"] = (
    isinstance(secret_node, ast.Call)
    and len(secret_node.args) > 1
    and isinstance(secret_node.args[1], ast.Constant)
    and bool(secret_node.args[1].value)
)
results["debug_literal"] = ast.literal_eval(assignments["DEBUG"])
results["allowed_hosts_literal"] = ast.literal_eval(assignments["ALLOWED_HOSTS"])
results["rest_framework_setting_names"] = sorted(ast.literal_eval(assignments["REST_FRAMEWORK"]))

# Inspect only variable names, never print values or use these credentials.
env_text = (ROOT / "amandaye_backend/.env").read_text(encoding="utf-8-sig")
results["project_env_contains_secret_key"] = bool(re.search(r"(?m)^\s*SECRET_KEY\s*=", env_text))

# Report locations/aggregate counts, without outputting individual records.
dump_lines = (ROOT / "docker/mysql/init/amandaye.sql").read_text(encoding="utf-8-sig").splitlines()
results["dump_insert_headers"] = [
    {"line": number, "table": match.group(1)}
    for number, line in enumerate(dump_lines, 1)
    if (match := re.match(r"INSERT INTO `([^`]+)`", line))
]
results["dump_value_line_count"] = sum(bool(re.match(r"^\([0-9]", line)) for line in dump_lines)
print(json.dumps(results, indent=2, ensure_ascii=False))
