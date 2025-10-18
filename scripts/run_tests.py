#!/usr/bin/env python
"""
Script utility per eseguire test con varie configurazioni

Uso:
    python scripts/run_tests.py --unit              # Solo unit tests
    python scripts/run_tests.py --integration       # Solo integration tests
    python scripts/run_tests.py --e2e               # Solo E2E tests
    python scripts/run_tests.py --all               # Tutti i test
    python scripts/run_tests.py --coverage          # Con coverage report
    python scripts/run_tests.py --quick             # Test veloci
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> int:
    """Esegue un comando e ritorna il codice di uscita"""
    print(f"\n{'=' * 60}")
    print(f"🧪 {description}")
    print(f"{'=' * 60}\n")

    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Esegui test suite")

    parser.add_argument("--unit", action="store_true", help="Esegui solo unit tests")
    parser.add_argument(
        "--integration", action="store_true", help="Esegui solo integration tests"
    )
    parser.add_argument("--e2e", action="store_true", help="Esegui solo E2E tests")
    parser.add_argument("--all", action="store_true", help="Esegui tutti i test")
    parser.add_argument(
        "--quick", action="store_true", help="Esegui solo test veloci"
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Genera report coverage"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Output verbose"
    )
    parser.add_argument(
        "--failfast", "-x", action="store_true", help="Stop al primo errore"
    )
    parser.add_argument(
        "--parallel", "-n", type=int, help="Esegui test in parallelo"
    )

    args = parser.parse_args()

    # Base command
    cmd = ["uv", "run", "pytest", "tests/"]

    # Verbose
    if args.verbose:
        cmd.append("-vv")
    else:
        cmd.append("-v")

    # Fail fast
    if args.failfast:
        cmd.append("-x")

    # Parallel execution
    if args.parallel:
        cmd.extend(["-n", str(args.parallel)])

    # Test markers
    if args.unit:
        cmd.extend(["-m", "unit"])
    elif args.integration:
        cmd.extend(["-m", "integration"])
    elif args.e2e:
        cmd.extend(["-m", "e2e"])
    elif args.quick:
        cmd.extend(["-m", "unit and not slow"])
    elif args.all:
        pass  # Run tutti i test
    else:
        # Default: solo unit tests
        cmd.extend(["-m", "unit"])

    # Coverage
    if args.coverage:
        cmd.extend(
            [
                "--cov=src/rag_gestionale",
                "--cov-report=term-missing",
                "--cov-report=html",
                "--cov-report=xml",
            ]
    else:
        cmd.append("--no-cov")

    # Esegui test
    returncode = run_command(
        cmd, f"Esecuzione test ({' '.join(cmd[3:])})"  # Skip 'uv run pytest'
    )

    # Se coverage è richiesto, mostra il report
    if args.coverage and returncode == 0:
        print("\n" + "=" * 60)
        print("📊 Report coverage generato in: htmlcov/index.html")
        print("=" * 60)

    return returncode


if __name__ == "__main__":
    sys.exit(main())
