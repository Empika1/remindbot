import discord

EMBED_COLOR_ERROR = 0xe32214
EMBED_COLOR_WARNING = 0xe3c714
EMBED_COLOR_GOOD = 0x22e314

class Response:
    def __init__(self, title: str, txt: str = '', is_error: bool = False, notes: list[str]|None = None, warnings: list[str]|None = None):
        self.title = title
        self.txt = txt
        self.is_error = is_error
        self.notes = notes if notes is not None else []
        self.warnings = warnings if warnings is not None else []

    def make_embed(self) -> discord.embeds.Embed:
        title = f"Error: {self.title}" if self.is_error else self.title

        notes = "\n".join([f"**Note:** *{note}*" for note in self.notes])
        warnings = "\n".join([f"**Warning: {note}**" for note in self.warnings])

        txt = f"{self.txt}"
        if len(self.notes) > 0:
            txt += f"\n\n{notes}"
        if len(self.warnings) > 0:
            txt += f"\n\n{warnings}"

        color = EMBED_COLOR_ERROR if self.is_error else EMBED_COLOR_WARNING if len(self.warnings) > 0 else EMBED_COLOR_GOOD

        embed=discord.Embed(title=title,
                            description=txt, 
                            color=color)
        return embed