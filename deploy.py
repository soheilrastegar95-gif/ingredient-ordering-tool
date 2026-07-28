"""
deploy.py — runs git add, commit, and push in one go.

Usage:
    python deploy.py "Your commit message here"

If you don't pass a message, it uses a default one.
Run this from inside your project folder (where your .git folder is).
"""
import subprocess
import sys


def run(cmd):
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(result.returncode)


def push():
    print("$ git push")
    result = subprocess.run(["git", "push"], capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        # Likely the very first push — no upstream branch set yet
        print(result.stderr)
        print("Retrying with upstream set (first push)...")
        run(["git", "push", "-u", "origin", "main"])
    else:
        print(result.stderr)


def main():
    message = sys.argv[1] if len(sys.argv) > 1 else "Update app"

    run(["git", "add", "."])

    print("$ git commit -m ...")
    result = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        print("(This is fine if it just says 'nothing to commit' — continuing to push.)")

    push()

    print("\n✅ Pushed successfully. Streamlit Cloud should redeploy in about a minute.")


if __name__ == "__main__":
    main()
