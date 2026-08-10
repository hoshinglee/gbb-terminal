from __future__ import annotations

import json
from dataclasses import asdict

from gbb_terminal.api.dependencies import build_services


def main() -> None:
    services = build_services()
    result = services.company_identity.sync_sec_directory()
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
