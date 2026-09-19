import os
import threading
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# Niewielki serwer HTTP, żeby Render nie ubijał usługi
app = Flask('')

@app.route('/')
def home():
    return "Bot działa 24/7!"

def run_http():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Pobieranie danych z ustawień
TOKEN = os.getenv("MTU1MDc5NTk0MjM3NzE2NDgzMA.G_pJuY.7-5Jq9r7ONAbeW4YqL8l0rrUw4r4qjzt4DUg5k")
SUGGESTIONS_CHANNEL_ID = 1550764675224969237

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
            await interaction.response.send_message("Błąd: Nie znaleziono kanału propozycji!", ephemeral=True)
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

        await interaction.response.send_message("Twój pomysł został wysłany!", ephemeral=True)

class BotPropozycji(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Komendy Slash zostały zsynchronizowane!")

    async def on_ready(self):
        print(f"Zalogowano jako {self.user}")

bot = BotPropozycji()

@bot.tree.command(name="propozycja", description="Wyślij nową propozycję")
async def propozycja(interaction: discord.Interaction):
    await interaction.response.send_modal(ModalPropozycji())

if __name__ == "__main__":
    # Uruchomienie serwera www w osobnym wątku
    t = threading.Thread(target=run_http)
    t.start()

    if not TOKEN:
        print("BŁĄD: Brak tokenu DISCORD_TOKEN!")
    else:
        bot.run(TOKEN)
