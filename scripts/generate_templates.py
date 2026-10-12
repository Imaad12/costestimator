"""Regenerate templates/*.xlsx and templates/*.docx.  Usage: python scripts/generate_templates.py"""
import subprocess
import sys

sys.exit(subprocess.call([sys.executable, "-m", "app.cli", "templates"]))
