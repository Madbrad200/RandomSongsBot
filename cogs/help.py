import disnake
from disnake.ext import commands
from typing import Optional, Set
import inspect  # for formatting bot description

# https://gist.github.com/InterStella0/454cc51e05e60e63b81ea2e8490ef140


class HelpDropdown(disnake.ui.Select):
    def __init__(self, help_command: "MyHelpCommand", options: list[disnake.SelectOption]):
        # max_value = can only choose 1 option in the menu
        super().__init__(placeholder="Choose a category...", min_values=1, max_values=1, options=options)
        self._help_command = help_command

    async def callback(self, interaction: disnake.Interaction):
        # values[0] = gets cog name
        embed = (
            await self._help_command.cog_help_embed(self._help_command.context.bot.get_cog(self.values[0]))
            if self.values[0] != self.options[0].value
            else await self._help_command.bot_help_embed(self._help_command.get_bot_mapping())
        )
        await interaction.response.edit_message(embed=embed)


# creating view
class HelpView(disnake.ui.View):
    def __init__(self, help_command: "MyHelpCommand", options: list[disnake.SelectOption], *, timeout: Optional[float] = 300.0):
        super().__init__(timeout=timeout)
        self.add_item(HelpDropdown(help_command, options))
        self._help_command = help_command

    async def on_timeout(self):
        # remove dropdown from message on timeout
        self.clear_items()
        await self._help_command.response.edit(view=self)

    # checks if the person who used the command is the same person clicking through the menu
    async def interaction_check(self, interaction: disnake.Interaction) -> bool:
        return self._help_command.context.author == interaction.user


class MyHelpCommand(commands.MinimalHelpCommand):

    def get_command_signature(self, command):
        # signature inclues arguments/params of the command
        return f"@RandomSongsBot#3234 {command.qualified_name} {command.signature}"

    # colour for embeds
    COLOUR = disnake.Colour.from_rgb(198, 146, 148)  # beige pink

    # generate list of cogs we can select
    async def _cog_select_options(self) -> list[disnake.SelectOption]:
        options: list[disnake.SelectOption] = []
        options.append(disnake.SelectOption(
            label="Home",
            emoji="🏠",
            description="Go back to the main menu.",
        ))

        never_send_cogs = ("BotAdmin", "botlistinfo", "errorhandling", "HelpCommand") 

        for cog, command_set in self.get_bot_mapping().items():
            filtered = await self.filter_commands(command_set, sort=True)

            if not filtered:
                continue
            # check if cog has cog_emoji attribute, or use 📄
            emoji = getattr(cog, "COG_EMOJI", "📄")
            options.append(disnake.SelectOption(
                label=cog.qualified_name if cog else "Help",
                emoji=emoji,
                description=cog.description[1:100] if cog and cog.description else None
            )
            )  # max 100 chars, skip first character because it's the italics asterisk

        new_options = options.copy()
        for item in options:
            if item.label in never_send_cogs:
                new_options.remove(item)
        return new_options

    # create the embed for the help cmd
    # command_set runs if we're getting help for a group of commands
    # default showing bots avatar as true (set_author)
    async def _help_embed(
        self, title: str, description: Optional[str] = None, mapping: Optional[str] = None,
        command_set: Optional[Set[commands.Command]] = None, set_author: bool = False
    ) -> disnake.Embed:

        embed = disnake.Embed(title=title, colour=self.COLOUR)
        # if description exists, enter description. a description is optional, defaults to None
        if description:
            embed.description = description
        if command_set:
            # show help about all commands in the set/group
            filtered = await self.filter_commands(command_set, sort=True)
            for command in filtered:
                # use command.description if the kwarg is set, but check for command.help (command docstring) first
                if command.help is not None:
                    help_mode = command.help
                else:
                    help_mode = command.description
                embed.description += f"\n\n**{self.get_command_signature(command)}**\n{help_mode}\n"
                # embed.add_field(
                #     name=self.get_command_signature(command),
                #     value=command.description or "...",
                #     inline=False
                # )
        elif mapping:
            # add a short description of commands in each cog
            for cog, command_set in mapping.items():
                filtered = await self.filter_commands(command_set, sort=True)
                if not filtered:
                    continue
                name = cog.qualified_name if cog else "Help"  # in-case a command isn't in a cog

                # cogs to never send in help cmd
                never_send_cogs = ("BotAdmin", "botlistinfo", "errorhandling", "HelpCommand") 

                if name not in never_send_cogs:
                    emoji = getattr(cog, "COG_EMOJI", "📄")
                    cog_label = f"{emoji} {name}" if emoji else name
                    # \u2002 is an en-space

                    # cmd_list = "\u2002".join(
                    #     f"`{self.context.clean_prefix}{cmd.name}`" for cmd in filtered
                    # )
                    if name == "Help/Change Prefix":
                        # because we're adding this to the cogs list after, we nee to add the unicode new line before the name of every unlisted command (rather than ignoring the first one)
                        # this allows us to easily append it to the uncategorised list
                        cmd_list = "\u2002".join(f"`{c.name}`" for c in filtered) 
                    else:
                        cmd_list = "\u2002".join(f"`{c.name}`" for c in filtered) 
                    # this is the default for commands not inside a cog (Uncategorised). This is overwritten below if they are in a cog
                    # add cog description, then cmd list, if cog description exists otherwise just list cmds
                    value = (
                        f"{cog.description}\n{cmd_list}"
                        if cog and cog.description
                        else cmd_list
                    )

                    embed.add_field(name=cog_label, value=value, inline=False)

        return embed

    async def bot_help_embed(self, mapping: dict) -> disnake.Embed:
        return await self._help_embed(
            title="Bot Commands Help",
            description=inspect.cleandoc(
                """
                __Introduction__
                Hello! I'm a music discovery bot, created by @Madbrad200#5991. My commands are prefixed by my mention, @AsterieBot#7609 (or use slash commands with `/`). Be sure to type the mention out, rather than copy/pasting it.
                
                For example, to use the `randommusic` command, you'd write `@RandomSongsBot#3234 randommusic`.

                Click through the menu for detailed info about the categories (don't see the menu? It times out after awhile - rerun the command)
                """),
            mapping=mapping,
            set_author=False,
        )
    
    # creates a mapping (dict) of all the cogs, and all the commands in said cog
    async def send_bot_help(self, mapping: dict):
        embed = await self.bot_help_embed(mapping)
        options = await self._cog_select_options()
        self.response = await self.get_destination().send(embed=embed, view=HelpView(self, options))

    # sends help about a specific command
    async def send_command_help(self, command: commands.Command):
        # qualified_name = full name of command

        # use command.description if the kwarg is set, but check for command.help (command docstring) first
        if command.help is not None:
            help_mode = command.help
        else:
            help_mode = command.description

        embed = await self._help_embed(
            title=f"📄 {command.qualified_name}",
            description=f"Usage: **{self.get_command_signature(command)}**\n{help_mode}",
            command_set=command.commands if isinstance(command, commands.Group) else None
        )  # command_set runs if we're getting help for a GROUP of commands, else none
        await self.get_destination().send(embed=embed)

    async def cog_help_embed(self, cog: Optional[commands.Cog]) -> disnake.Embed:
        if cog is None:
            return await self._help_embed(
                title="Unlisted",
                command_set=self.get_bot_mapping()[None]
            )
        return await self._help_embed(
            title=f"📄 {cog.qualified_name}",
            description=cog.description,
            command_set=cog.get_commands()
        )

    # send help about a specific cog
    async def send_cog_help(self, cog: commands.Cog):
        embed = await self.cog_help_embed(cog)
        await self.get_destination().send(embed=embed)

    # Use the same function as command help for group help
    send_group_help = send_command_help


class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command  # preserves the default help command in `_original_help_command` before we override it
        # Setting the cog for the help

        attributes = {
           'aliases': ["helps", "commands", "commandlist", "helplist", "cmdlist", "cmdslist"],
           'cooldown': commands.CooldownMapping.from_cooldown(3, 6, commands.BucketType.user),
           'usage': '<command/category_name>',
           'brief': 'Why, I\'m just a simple help command'
        }

        help_command = MyHelpCommand(command_attrs=attributes)
        help_command.cog = self  # Instance of YourCog class
        bot.help_command = help_command  # assign help command to EmbedHelpCommand, this is the equivilent of placing help_command=help_command in the bot constructor

    # if cog is unloaded, revert to default
    def cog_unload(self):
        self.bot.help_command = self._original_help_command  # revert back to default


def setup(bot):
    bot.add_cog(HelpCommand(bot))
