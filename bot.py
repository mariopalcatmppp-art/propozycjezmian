import discord
from discord.ext import commands
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import Button, View, Modal, TextInput

# === TUTAJ WPISZ SWOJE DANE ===
TOKEN = "MTU1MDc5NTk0MjM3NzE2NDgzMA.G_pJuY.7-5Jq9r7ONAbeW4YqL8l0rrUw4r4qjzt4DUg5k"
SUGGESTIONS_CHANNEL_ID = 1550764675224969237
class SuggestionModal(Modal, title="Nowa Propozycja Zmiany"):
    title_input = TextInput(
        label="Tytuł propozycji",
        placeholder="np. Dodanie nowego kanału tekstowego",
        max_length=100,
        required=True
    )
    description_input = TextInput(
        label="Opis zmiany / uzasadnienie",
        style=discord.TextStyle.paragraph,
        placeholder="Opisz dokładnie, co chcesz zmienić i dlaczego...",
        max_length=1000,
        required=True
    )

    async def on_submit(self, interaction: Interaction):
        channel = interaction.guild.get_channel(SUGGESTIONS_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Błąd: Nie znaleziono kanału na propozycje.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"💡 {self.title_input.value}",
            description=self.description_input.value,
            color=discord.Color.blue()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Status", value="⏳ Oczekuje na rozpatrzenie", inline=False)
        embed.set_footer(text=f"ID Autora: {interaction.user.id}")

        view = SuggestionVoteView()
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message("Twoja propozycja została wysłana!", ephemeral=True)


class SuggestionVoteView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Za (0)", style=ButtonStyle.green, custom_id="vote_yes")
    async def vote_yes(self, interaction: Interaction, button: Button):
        await interaction.response.send_message("Głos został zarejestrowany!", ephemeral=True)

    @discord.ui.button(label="Przeciw (0)", style=ButtonStyle.red, custom_id="vote_no")
    async def vote_no(self, interaction: Interaction, button: Button):
        await interaction.response.send_message("Głos został zarejestrowany!", ephemeral=True)


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = Bot()

@bot.tree.command(name="propozycja", description="Otwiera formularz dodawania propozycji")
async def suggest(interaction: Interaction):
    await interaction.response.send_modal(SuggestionModal())

if __name__ == "__main__":
    bot.run(TOKEN)