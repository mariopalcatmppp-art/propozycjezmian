import os
import threading
import discord
from discord.ext import commands
from flask import Flask

# Uruchomienie prostego serwera HTTP dla Rendera
app = Flask('')

@app.route('/')
def home():
    return "Bot działa 24/7!"

def run_http():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# KONFIGURACJA:
TOKEN = "MTU1MDc5NTk0MjM3NzE2NDgzMA.GDiRNf.QGooY0pNLW4C4FbuQt76d5OK6r5Ro5A_m6BKes"
SUGGESTIONS_CHANNEL_ID = 1550764675224969237

# Okno formularza po kliknięciu przycisku
class ModalPropozycji(discord.ui.Modal, title="Nowa Propozycja"):
    tytul = discord.ui.TextInput(
        label="Tytuł propozycji",
        placeholder="Wpisz krótki tytuł...",
        max_length=100
    )
    opis = discord.ui.TextInput(
        label="Opis propozycji",
        style=discord.TextStyle.paragraph,
        placeholder="Opisz dokładnie swój pomysł...",
        max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):
        kanal = interaction.client.get_channel(SUGGESTIONS_CHANNEL_ID)
        if not kanal:
            await interaction.response.send_message("Błąd: Nie znaleziono kanału propozycji w konfiguracji!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"💡 Propozycja: {self.tytul.value}",
            description=self.opis.value,
            color=discord.Color.blue()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)

        msg = await kanal.send(embed=embed)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")

        await interaction.response.send_message("Twój pomysł został wysłany na kanał propozycji!", ephemeral=True)

# Przycisk, który otwiera formularz
class WidokPropozycji(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Przycisk działa bezterminowo

    @discord.ui.button(label="💡 Zgłoś propozycję", style=discord.ButtonStyle.primary, custom_id="przycisk_propozycji_v1")
    async def przycisk_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalPropozycji())

class BotPropozycji(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Rejestracja widoku przycisku, żeby działał po restarcie bota
        self.add_view(WidokPropozycji())

    async def on_ready(self):
        print(f"Zalogowano jako {self.user}")

bot = BotPropozycji()

# Komenda tekstowa dla administratora
@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.message.delete()  # Kasuje treść "!setup" dla czystości na kanale
    
    embed = discord.Embed(
        title="💡 System Propozycji",
        description="Kliknij poniższy przycisk, aby otworzyć formularz i przesłać swój pomysł!",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=WidokPropozycji())

if __name__ == "__main__":
    t = threading.Thread(target=run_http, daemon=True)
    t.start()

    if not TOKEN:
        print("BŁĄD: Brak tokenu DISCORD_TOKEN w Environment Variables!")
    else:
        print("Łączenie z Discordem...")
        bot.run(TOKEN)
