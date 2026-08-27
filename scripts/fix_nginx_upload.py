"""Fix nginx client_max_body_size for /etc/nginx/sites-available/sayarti.

Adds client_max_body_size 50M to the HTTPS (443) server block and removes
any duplicate from the HTTP (80) redirect block. Safe to run repeatedly.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

NGINX_CONF = Path("/etc/nginx/sites-available/sayarti")
BACKUP = NGINX_CONF.with_suffix(".sayarti.bak")
SIZE_LINE = "    client_max_body_size 50M;"


def main() -> int:
    if not NGINX_CONF.exists():
        print(f"[!] Config not found: {NGINX_CONF}")
        return 1

    shutil.copy2(NGINX_CONF, BACKUP)
    text = NGINX_CONF.read_text(encoding="utf-8")

    # 1. Remove every existing client_max_body_size line (anywhere).
    text = re.sub(r"^\s*client_max_body_size\s+[^;]+;\s*$", "", text, flags=re.MULTILINE)

    # 2. Normalise blank lines produced by the removal.
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    # 3. Find the first HTTPS server block (listen 443) and insert the size line
    #    right after its opening {.
    lines = text.splitlines(True)
    out: list[str] = []
    inserted = False
    in_https = False
    for line in lines:
        out.append(line)
        if not inserted:
            stripped = line.strip()
            if stripped.startswith("server {"):
                in_https = False
            if stripped.startswith("listen 443"):
                in_https = True
            # Insert immediately after the opening brace of the 443 block is found.
            # We track: the first "listen 443 ssl" line is inside the 443 block,
            # so we insert after that line to stay inside the block.
            if in_https and stripped.startswith("listen 443"):
                out.append(SIZE_LINE + "\n")
                inserted = True

    NGINX_CONF.write_text("".join(out), encoding="utf-8")
    print("[+] client_max_body_size 50M added to HTTPS block")

    # 4. Validate and reload nginx.
    result = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
    print(result.stdout.strip())
    print(result.stderr.strip())
    if result.returncode != 0:
        print("[!] nginx test failed, restoring backup")
        shutil.copy2(BACKUP, NGINX_CONF)
        return 1

    subprocess.run(["systemctl", "restart", "nginx"], check=True)
    print("[+] nginx restarted successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())