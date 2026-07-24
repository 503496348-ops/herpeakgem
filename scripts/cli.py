#!/usr/bin/env python3
"""HerPeakGem — 他山之石智能教育平台 CLI"""
import argparse, json, sys, os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def cmd_serve(args: list[str]) -> None:
    """Start HerPeakGem web server."""
    try:
        from herpeakgem.runtime.launcher import start
        print(json.dumps({"action": "serve", "port": args.port or 8080, "status": "starting"}, ensure_ascii=False))
        start(home=Path(args.home) if args.home else None)
    except ImportError as e:
        print(json.dumps({"error": str(e), "fix": "pip install -e ."}, ensure_ascii=False))

def cmd_setup(args: list[str]) -> None:
    """Run PocketBase collection bootstrap."""
    try:
        from scripts.pb_setup import main as pb_main
        pb_main()
    except Exception as e:
        print(json.dumps({"error": str(e), "status": "setup_failed"}, ensure_ascii=False))

def cmd_update(args: list[str]) -> None:
    """Check for updates."""
    try:
        from scripts.update import main as update_main
        update_main()
    except Exception as e:
        print(json.dumps({"error": str(e), "status": "update_check_failed"}, ensure_ascii=False))

def cmd_doctor(args: list[str]) -> None:
    """Run health diagnostics."""
    try:
        from scripts.doctor import main as doctor_main
        sys.exit(doctor_main())
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))

def cmd_skills(args: list[str]) -> None:
    """List available skills."""
    skills_dir = PROJECT_ROOT / 'herpeakgem' / 'skills' / 'builtin'
    if skills_dir.exists():
        skills = [d.name for d in skills_dir.iterdir() if d.is_dir()]
        for s in sorted(skills):
            print(f"  {s}")
    else:
        print("  (no built-in skills found)")

def cmd_info(args: list[str]) -> None:
    """Show product info."""
    # Count modules
    pkg_dir = PROJECT_ROOT / 'herpeakgem'
    py_count = len(list(pkg_dir.rglob('*.py'))) if pkg_dir.exists() else 0
    skills_dir = pkg_dir / 'skills' / 'builtin'
    skill_count = len(list(skills_dir.iterdir())) if skills_dir.exists() else 0
    print(json.dumps({
        "product": "HerPeakGem 他山之石",
        "type": "智能教育平台",
        "python_files": py_count,
        "built_in_skills": skill_count,
        "modules": ["agents", "services", "api", "runtime"],
        "status": "ok"
    }, ensure_ascii=False, indent=2))

def main() -> None:
    p = argparse.ArgumentParser(description='HerPeakGem 他山之石智能教育平台')
    sub = p.add_subparsers(dest='command')

    sv = sub.add_parser('serve', help='启动 Web 服务')
    sv.add_argument('--port', type=int, default=8080)
    sv.add_argument('--home', help='运行时工作目录')

    sub.add_parser('setup', help='初始化 PocketBase 集合')
    sub.add_parser('update', help='检查更新')
    sub.add_parser('doctor', help='健康诊断')
    sub.add_parser('skills', help='列出内置技能')
    sub.add_parser('info', help='产品信息')

    args = p.parse_args()
    if args.command == 'serve': cmd_serve(args)
    elif args.command == 'setup': cmd_setup(args)
    elif args.command == 'update': cmd_update(args)
    elif args.command == 'doctor': cmd_doctor(args)
    elif args.command == 'skills': cmd_skills(args)
    elif args.command == 'info': cmd_info(args)
    else: p.print_help()

if __name__ == '__main__':
    main()
