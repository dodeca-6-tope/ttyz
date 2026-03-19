"""Flex layout primitives for terminal UI."""

from terminal.measure import display_width


class Flex:
    """Flex layout utilities — arrange content like CSS flexbox."""

    @staticmethod
    def wrap(chunks: list, width: int, sep: str = " ") -> list[str]:
        """Wrap chunks into lines that fit within width, joining with separator.

        Chunks can be str or Text (anything with len() and str()).
        """
        sep_w = display_width(sep)
        lines: list[str] = []
        cur_parts: list[str] = []
        cur_w = 0
        for chunk in chunks:
            chunk_w = display_width(str(chunk))
            new_w = chunk_w if not cur_parts else cur_w + sep_w + chunk_w
            if new_w <= width:
                cur_parts.append(str(chunk))
                cur_w = new_w
            else:
                if cur_parts:
                    lines.append(sep.join(cur_parts))
                cur_parts = [str(chunk)]
                cur_w = chunk_w
        if cur_parts:
            lines.append(sep.join(cur_parts))
        return lines
