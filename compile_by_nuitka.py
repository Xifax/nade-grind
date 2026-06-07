import os
import platform
import subprocess
import sys

# Include example txt
RESOURCES = [
    ("words.txt", "words.txt"),
]

# Application entry point
ENTRY_POINT = "src/tui.py"

# Output directory for the binaries
OUTPUT_DIR = "dist"


def copy_resources():
    """Copy the resources to the output directory."""
    for src, dst in RESOURCES:
        if os.path.isdir(src):
            subprocess.check_call(["cp", "-r", src, os.path.join(OUTPUT_DIR, dst)])
        else:
            subprocess.check_call(["cp", src, os.path.join(OUTPUT_DIR, dst)])


def build_with_nuitka(env):
    """Build the application using Nuitka."""
    system = platform.system().lower()
    if system not in ["linux", "windows"]:
        raise ValueError(
            "Unsupported platform. This script only supports Linux and Windows."
        )

    # Nuitka command for Linux
    if env == "linux":
        command = [
            "uv",
            "run",
            "nuitka",
            "--standalone",
            "--onefile",
            "--include-package=textual",
            f"--output-dir={OUTPUT_DIR}",
            ENTRY_POINT,
        ]
        subprocess.check_call(command)
    # Nuitka command for Windows
    elif env == "windows":
        # Windows has problems with subprocess, so...
        # Let's construct the command as a string
        command = (
            f"uv run nuitka --standalone --onefile "
            f"--include-package=textual "
            f"--output-dir={OUTPUT_DIR} "
            f"--windows-console-mode=force "
            f"{ENTRY_POINT}"
        )
        os.system(command)


def main(env):
    # Create the output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print(f"Building for {env}")

    print("Building with Nuitka...")
    build_with_nuitka(env)

    copy_resources()

    print(
        f"Build completed successfully! The binary is located in the '{OUTPUT_DIR}' directory."
    )


if __name__ == "__main__":
    # Pass environment (windows, linux) as an argument
    if len(sys.argv) > 1:
        environment = sys.argv[1]
        main(environment)
    else:
        main(None)
