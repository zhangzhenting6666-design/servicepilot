"""Build an explicit final-project handoff; never copy credentials or raw sessions."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

PRODUCT = Path(__file__).resolve().parents[1]
WORKSPACE = PRODUCT.parent
sys.path.insert(0, str(PRODUCT))
from servicepilot.source_catalog import PUBLIC_FILES, load_snapshot

EXTENSIONS = {'.py', '.md', '.txt', '.json', '.toml', '.cmd', '.ps1', '.cjs',
              '.css', '.html', '.svg', '.png', '.jpg', '.jpeg'}
EXCLUDED_PARTS = {'__pycache__', '.venv', 'node_modules', '.git', 'tmp', 'temp'}
REVIEW_EXCLUDES = {'页面检查记录.json', '2026-10-11-汇总来源.json', '完整运行框架-手机预览.png'}
SAFE_REVIEWS = (
    'orders/c02-review-2026-10-13.json', 'orders/d01-batch1-review-2026-10-13.json',
    'orders/d01-batch2-review-2026-10-13.json', 'orders/e01-capability-review-2026-10-14.json',
    'web/e01-web-review-2026-10-14.json', 'evaluation/evaluation-review-2026-10-14.json',
    'evaluation/development-round1-quality-review.json',
    'evaluation/holdout-round1-interruption-review.json',
    'delivery/delivery-review-2026-10-14.json', 'delivery/delivery-offline-check-2026-10-14.json',
    'workbench/live-review.json', 'workbench/cloud/final-review.json',
    'code-guide/review-2026-10-16.json', 'code-guide/final-offline.json',
    'code-guide/final-responsive.json', 'code-guide/release-sync.json',
    'final-delivery/validation.json',
    'final-delivery/offline-tests.txt',
)
UI_EVIDENCE = ('code-guide', 'header-b', 'panel-refinement', 'presentation-copy', 'presentation-refresh')
SAFE_UI_JSON = {'browser.json', 'offline.json', 'offline-final.json', 'final-offline.json',
                'final-responsive.json', 'responsive.json', 'release.json', 'release-sync.json',
                'scope-check.json', 'screenshot-sizes.json', 'browser-review.json'}


def allowed(path):
    return (path.suffix.lower() in EXTENSIONS and not EXCLUDED_PARTS.intersection(path.parts)
            and not re.search(r'(?i)secret|credential|\.env(?:\.|$)|\.pem$|\.key$', path.name))


def main():
    snapshot = load_snapshot()
    for name in PUBLIC_FILES:
        assert (PRODUCT / name).read_text(encoding='utf-8') == snapshot['files'][name]['text'], name
    destination = PRODUCT / 'artifacts/deployment' / ('handoff-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    source = destination / 'source'
    source.mkdir(parents=True, exist_ok=False)
    paths = set()
    for directory in ('servicepilot', 'data', 'docs', 'tests', 'scripts', 'evaluations', 'assets', 'reviews'):
        for path in (PRODUCT / directory).rglob('*'):
            if (path.is_file() and allowed(path) and path.name not in REVIEW_EXCLUDES
                    and not path.name.endswith('预览.png')):
                paths.add(path)
    paths.update(path for path in PRODUCT.iterdir() if path.is_file() and allowed(path))
    paths.add(PRODUCT / '.streamlit/config.toml')
    for name in SAFE_REVIEWS:
        path = PRODUCT / 'artifacts' / name
        if path.exists():
            paths.add(path)
    for directory in UI_EVIDENCE:
        for path in (PRODUCT / 'artifacts' / directory).glob('*'):
            if path.is_file() and (path.suffix in {'.jpg', '.png'} or path.name in SAFE_UI_JSON):
                paths.add(path)
    for name in ('delivery/screenshots', 'web/screenshots', 'workbench/cloud'):
        for path in (PRODUCT / 'artifacts' / name).glob('*'):
            if path.suffix.lower() in {'.jpg', '.png'} and not re.search(r'(?i)owner|startup|terminal|auth', path.name):
                paths.add(path)
    for path in sorted(paths):
        target = source / 'ServicePilot' / path.relative_to(PRODUCT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    for name in ('LICENSE', 'examples/__init__.py', 'examples/auto_mode.py', 'examples/customer_service/main.py'):
        path = WORKSPACE / 'openai-agents-python-main' / name
        target = source / 'openai-agents-python-main' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    for path, name in ((PRODUCT / 'REPOSITORY_README.md', 'README.md'),
                       (PRODUCT / 'requirements.txt', 'requirements.txt'),
                       (PRODUCT / '.streamlit/config.toml', '.streamlit/config.toml'),
                       (WORKSPACE / '开始这里.md', '开始这里.md'),
                       (WORKSPACE / '.gitattributes', '.gitattributes'),
                       (WORKSPACE / 'openai-agents-python-main/LICENSE', 'THIRD_PARTY_LICENSE')):
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    (source / '.gitignore').write_text(
        '**/.venv/\n**/__pycache__/\n*.py[cod]\n**/node_modules/\n.env*\n**/.env*\n'
        '**/*secret*\n**/*credential*\n*.pem\n*.key\n*.log\n**/*.tmp\n'
        'ServicePilot/artifacts/deployment/\nServicePilot/artifacts/**/web-session-*.json\n'
        'ServicePilot/artifacts/**/eval-run-*.json\nServicePilot/artifacts/**/order-run-*.json\n'
        '**/*.review-control.json\n', encoding='utf-8')
    issues = []
    patterns = [r'\bsk-[A-Za-z0-9_-]{20,}', r'\bgh[pousr]_[A-Za-z0-9]{24,}',
                r'github_pat_[A-Za-z0-9_]{30,}', r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                r'''(?i)(?:api_key|DEEPSEEK_API_KEY|authorization|password)\s*[=:]\s*["'][A-Za-z0-9_./+-]{20,}["']''']
    for path in source.rglob('*'):
        if path.is_file() and path.suffix.lower() not in {'.png', '.jpg', '.jpeg'}:
            text = path.read_text(encoding='utf-8-sig', errors='replace')
            for number, line in enumerate(text.splitlines(), 1):
                if any(re.search(pattern, line) for pattern in patterns):
                    issues.append({'path': str(path.relative_to(source)), 'line': number})
    if issues:
        print(json.dumps({'secret_scan': 'blocked', 'locations_only': issues}, ensure_ascii=True))
        raise SystemExit(1)
    manifest = {'kind': 'complete_project_handoff_without_credentials_or_raw_sessions',
                'workspace_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=WORKSPACE, text=True).strip(),
                'public_snapshot_id': snapshot['snapshot_id'],
                'files': {str(path.relative_to(source)).replace('\\', '/'):
                          hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted(source.rglob('*')) if path.is_file()},
                'secret_scan': 'passed', 'model_api_requested': False,
                'manifest_note': 'Hashes cover all exported content except this self-describing manifest.',
                'excluded': ['keys and authentication', 'venv and caches', 'raw model/session logs',
                             'personal temporary files', 'full third-party SDK download', 'Git internals']}
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'
    (destination / 'manifest.json').write_text(manifest_text, encoding='utf-8')
    public_manifest = source / 'ServicePilot/artifacts/final-delivery/package-manifest.json'
    public_manifest.parent.mkdir(parents=True, exist_ok=True)
    public_manifest.write_text(manifest_text, encoding='utf-8')
    print(json.dumps({'source': str(source), 'manifest': str(destination / 'manifest.json'),
                      'file_count': len(manifest['files']) + 1, 'secret_scan': 'passed', 'uploaded': False}, ensure_ascii=True))


if __name__ == '__main__':
    main()
