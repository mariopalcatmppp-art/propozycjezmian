import os
import threading
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# Uruchomienie serwera HTTP dla Rendera
app = Flask('')

@app.route('/')
def home():
    return "Bot działa 24/7!"

def run_http():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# KONFIGURACJA:
TOKEN = os.environ.get("DISCORD_TOKEN")
SUGGESTIONS_CHANNEL_ID = 123456789012345678  # Podmień na ID swojego kanału z propozycjami (sam numer)

# --- 1. MODAL DLA ADMINA (POWÓD ODRZUCENIA PROPOZYCJI) ---
class ModalOdrzucenia(discord.ui.Modal, title="Powód Odrzucenia Propozycji"):
    powod = discord.ui.TextInput(
        label="Powód odrzucenia",
        style=discord.TextStyle.paragraph,
        placeholder="Wpisz powód odrzucenia propozycji...",
        max_length=500,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(name="❌ Status", value=f"Odrzucona przez {interaction.user.mention}", inline=False)
        embed.add_field(name="📝 Powód odrzucenia", value=self.powod.value, inline=False)

        widok = discord.ui.View.from_message(interaction.message)
        for child in widok.children:
            child.disabled = True

        await interaction.message.edit(embed=embed, view=widok)
        await interaction.response.send_message("Propozycja została odrzucona.", ephemeral=True)

# --- 2. PRZYCISKI AKCJI ADMINA (AKCEPTUJ / ODRZUĆ) ---
class WidokDecyzjiAdmina(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🟢 Akceptuj", style=discord.ButtonStyle.success, custom_id="admin_akceptuj")
    async def akceptuj_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Tylko administratorzy mogą akceptować propozycje!", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(name="✅ Status", value=f"Zaakceptowana przez {interaction.user.mention}", inline=False)

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message("Propozycja została zaakceptowana!", ephemeral=True)

    @discord.ui.button(label="🔴 Odrzuć", style=discord.ButtonStyle.danger, custom_id="admin_odrzuc")
    async def odrzuc_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Tylko administratorzy mogą odrzucać propozycje!", ephemeral=True)
            return

        await interaction.response.send_modal(ModalOdrzucenia())

# --- 3. FORMULARZ ZGŁASZANIA PROPOZYCJI ---
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

        msg = await kanal.send(embed=embed, view=WidokDecyzjiAdmina())
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")

        await interaction.response.send_message("Twój pomysł został wysłany!", ephemeral=True)

# --- 4. PRZYCISK PROPOZYCJI ---
class WidokPropozycji(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💡 Zgłoś propozycję", style=discord.ButtonStyle.primary, custom_id="przycisk_propozycji_v2")
    async def przycisk_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalPropozycji())

# --- 5. PRZYCISK PRZEJŚCIA DO MATERIAŁU/LINKU (URL) ---
class WidokLinkuFilmu(discord.ui.View):
    def __init__(self, url: str):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="▶️ Przejdź do materiału", url=url, style=discord.ButtonStyle.link))

# --- 6. GŁÓWNA KLASA BOTA ---
class BotPropozycji(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(WidokPropozycji())
        self.add_view(WidokDecyzjiAdmina())

    async def on_ready(self):
        print(f"Zalogowano jako {self.user}")

bot = BotPropozycji()

# Komenda setupu panelu propozycji
@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.message.delete()
    embed = discord.Embed(
        title="💡 System Propozycji",
        description="Kliknij poniższy przycisk, aby otworzyć formularz i przesłać swój pomysł!",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=WidokPropozycji())

# --- FUNKCJE SOCIAL MEDIA I OGŁOSZEŃ ---

# 1. Komenda !social - linki do YouTube i Kicka
@bot.command(name="social")
async def social(ctx):
    embed = discord.Embed(
        title="🌐 Nasze Media Społecznościowe",
        description="Bądź na bieżąco i zaobserwuj nasze profile!",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="🎬 YouTube", 
        value="[Kliknij tutaj, aby przejść na YouTube](https://youtube.com/@nkt_bez_cenzury?si=seIjd17VJTIwp4VZ)", 
        inline=False
    )
    embed.add_field(
        name="🟢 Kick", 
        value="[Kliknij tutaj, aby przejść na transmisję Kick](https://kick.com/firllii)", 
        inline=False
    )
    embed.set_footer(text="Dziękujemy za każde wsparcie i zostawiony ślad!")
    
    await ctx.send(embed=embed)

# 2. Komenda !ogloszenie <link> - powiadomienie z przyciskiem
@bot.command(name="ogloszenie")
@commands.has_permissions(administrator=True)
async def ogloszenie(ctx, url: str = None):
    await ctx.message.delete()
    
    if not url:
        await ctx.send("❌ Użycie: `!ogloszenie <link_do_filmu_lub_streama>`", delete_after=5)
        return

    embed = discord.Embed(
        title="🚀 NOWY MATERIAŁ / STREAM!",
        description=(
            "Właśnie wpadł nowy materiał! 🔥\n\n"
            "Wpadajcie sprawdzić, zostawcie coś po sobie dla algorytmu i dajcie znać, jak wrażenia!\n"
            "Kliknij poniższy przycisk, aby przejść bezpośrednio do materiału."
        ),
        color=discord.Color.gold()
    )
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    
    embed.set_footer(text=f"Ogłoszenie dodane przez {ctx.author.display_name}")

    await ctx.send(embed=embed, view=WidokLinkuFilmu(url))

if __name__ == "__main__":
    t = threading.Thread(target=run_http, daemon=True)
    t.start()

    if not TOKEN:
        print("BŁĄD: Brak tokenu DISCORD_TOKEN w Environment Variables!")
    else:
        print("Łączenie z Discordem...")
        bot.run(TOKEN)
