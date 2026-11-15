import re


_OUTLINE_PLACEHOLDER = re.compile(r"^\s*\[Write this section\]\s*$", re.IGNORECASE)


def unresolved_script_sections(body: str) -> list[str]:
    """Return outline headings that still contain the Studio scaffold marker."""
    current_section = "Script"
    unresolved: list[str] = []
    for line in body.splitlines():
        heading = re.match(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            current_section = heading.group(1).strip()
        elif _OUTLINE_PLACEHOLDER.fullmatch(line):
            unresolved.append(current_section)
    return list(dict.fromkeys(unresolved))
