#!/usr/bin/env python3
"""
hello_world.py

A simple standalone script that prints 'Hello, World!' to stdout.
This script is intentionally placed at the root of the backend container repository
and does not interact with or modify the FastAPI application or its services.

Usage:
  python hello_world.py
"""

# PUBLIC_INTERFACE
def main() -> None:
    """Print 'Hello, World!' to stdout."""
    print("Hello, World!")


if __name__ == "__main__":
    main()
