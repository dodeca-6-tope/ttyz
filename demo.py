"""Demo app for the terminal package."""

from terminal import Terminal, Paste, TextInput, Text, Picker, View

FRUITS = [
    {"name": "Apple", "value": "apple"},
    {"name": "Banana", "value": "banana"},
    {"name": "Cherry", "value": "cherry"},
    {"name": "Dragonfruit", "value": "dragonfruit"},
    {"name": "Elderberry", "value": "elderberry"},
    {"name": "Fig", "value": "fig"},
    {"name": "Grape", "value": "grape"},
    {"name": "Honeydew", "value": "honeydew"},
]


def render_picker(picker: Picker) -> list[str]:
    v: View = picker.view()
    header = Text(f"\033[1mPick a fruit\033[0m")
    lines = [
        str(header),
        "",
        f"> {v.query}",
        f"  {v.filtered}/{v.total}",
        "",
    ]
    for item in v.items:
        prefix = "> " if item.cursor else "  "
        lines.append(f"{prefix}{item.name}")
    lines.append("")
    lines.append("[enter] select  [esc] quit")
    return lines


def render_input(ti: TextInput, fruit: str) -> list[str]:
    header = Text(f"\033[1mDescribe your {fruit}\033[0m")
    lines = [
        str(header),
        "",
        f"> {ti.display()}",
        "",
        f"  {len(ti.value)} chars",
        "",
        "[enter] done  [esc] quit",
    ]
    return lines


with Terminal() as term:
    picker = Picker(FRUITS)
    ti = TextInput()
    fruit = None

    while True:
        if fruit is None:
            term.render(render_picker(picker))
        else:
            term.render(render_input(ti, fruit))

        key = term.readkey()
        if key is None:
            continue
        if key == "esc":
            break

        if fruit is None:
            event = picker.handle_key(key)
            if event == "select":
                fruit = picker.value
        else:
            if key == "enter":
                break
            ti.handle_key(key)

if fruit:
    print(f"\nYou picked: {fruit}")
    print(f"Description: {ti.value}")
