"""Demo app for the terminal package."""

from terminal import Terminal, TextInput

with Terminal() as term:
    ti = TextInput()

    while True:
        lines = [
            "Terminal Demo",
            "",
            f"value: {ti.display()}",
            "",
            f"raw ({len(ti.value)} chars): {ti.value[:80]}{'...' if len(ti.value) > 80 else ''}",
            f"cursor: {ti.cursor}",
            f"pastes: {ti._pastes}",
            "",
            "[enter] done  [esc] quit",
        ]
        term.render(lines)

        key = term.readkey()
        if key is None:
            continue
        if key == "esc":
            break
        if key == "enter":
            break
        ti.handle_key(key)

print(f"\nFinal value: {ti.value}")
