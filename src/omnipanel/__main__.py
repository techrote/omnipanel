"""Support ``python -m omnipanel`` without import-time startup."""

from omnipanel.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
