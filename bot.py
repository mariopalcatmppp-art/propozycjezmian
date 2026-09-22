import os
import json
import time
import random
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
ADMIN_DISCORD_ID = 1539023712160981013
SUGGESTIONS_CHANNEL_ID = 1550764675224969237
DATA_FILE = "user_data.json"

# --- ZARZĄDZANIE DANYMI UŻYTKOWNIKÓW ---
def load_user_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_user_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

user_db = load_user_data()

def get_user_wallet(user_id: int):
    uid = str(user_id)
    if uid not in user_db:
        user_db[uid] = {
            "coins": 100,  # Bonus na start
            "last_daily": 0
        }
        save_user_data(user_db)
    return user_db[uid]

# --- 1. MINIGRA SAPER (INTERAKTYWNE PRZYCISKI) ---
class SaperGameView(discord.ui.View):
    def __init__(self, user_id: int, bet: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bet = bet
        self.multiplier = 1.0
        self.safe_tiles_found = 0
        # Losujemy 2 miny na 9 pól
        self.mines = set(random.sample(range(9), 2))
        self.revealed = set()

        for i in range(9):
            btn = discord.ui.Button(label="❓", style=discord.ButtonStyle.secondary, custom_id=f"mine_{i}", row=i // 3)
            btn.callback = self.make_callback(i)
            self.add_item(btn)

    def make_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("To nie jest Twoja gra!", ephemeral=True)
                return

            if index in self.revealed:
                await interaction.response.send_message("To pole zostało już odkryte!", ephemeral=True)
                return

            self.revealed.add(index)

            if index in self.mines:
                # Trafiono na minę - przegrana
                for child in self.children:
                    child.disabled = True
                    idx = int(child.custom_id.split("_")[1])
                    if idx in self.mines:
                        child.label = "💥"
                        child.style = discord.ButtonStyle.danger
                
                embed = discord.Embed(
                    title="💥 BOOM! Trafiłeś na minę!",
                    description=f"Przegrałeś swoją stawkę **{self.bet} monet**!",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=self)
                self.stop()
            else:
                # Bezpieczne pole
                self.safe_tiles_found += 1
                self.multiplier += 0.4

                for child in self.children:
                    idx = int(child.custom_id.split("_")[1])
                    if idx == index:
                        child.label = "💎"
                        child.style = discord.ButtonStyle.success
                        child.disabled = True

                winnings = int(self.bet * self.multiplier)

                if self.safe_tiles_found == 7: # Wyczyszczono całą planszę
                    wallet = get_user_wallet(self.user_id)
                    wallet["coins"] += winnings
                    save_user_data(user_db)

                    embed = discord.Embed(
                        title="🏆 NIESAMOWITE! Odkryłeś wszystkie bezpieczne pola!",
                        description=f"Wygrywasz maksymalną nagrodę **{winnings} monet** (Mnożnik x{self.multiplier:.1f})!",
                        color=discord.Color.gold()
                    )
                    for child in self.children:
                        child.disabled = True
                    await interaction.response.edit_message(embed=embed, view=self)
                    self.stop()
                else:
                    embed = discord.Embed(
                        title="💎 Trafiłeś bezpieczne pole!",
                        description=f"Aktualny mnożnik: **x{self.multiplier:.1f}**\nMożliwa wygrana: **{winnings} monet**.\n\nKlikaj dalej lub zrealizuj wygraną poniżej!",
                        color=discord.Color.green()
                    )
                    await interaction.response.edit_message(embed=embed, view=self)

        return callback

# --- 2. MODAL DLA ADMINA (POWÓD ODRZUCENIA PROPOZYCJI) ---
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

# --- 3. PRZYCISKI AKCJI ADMINA ---
class WidokDecyzjiAdmina(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🟢 Akceptuj", style=discord.ButtonStyle.success, custom_id="admin_akceptuj")
    async def akceptuj_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ADMIN_DISCORD_ID:
            await interaction.response.send_message("Tylko wyznaczony administrator może zarządzać propozycjami!", ephemeral=True)
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
        if interaction.user.id != ADMIN_DISCORD_ID:
            await interaction.response.send_message("Tylko wyznaczony administrator może zarządzać propozycjami!", ephemeral=True)
            return

        await interaction.response.send_modal(ModalOdrzucenia())

# --- 4. FORMULARZ ZGŁASZANIA PROPOZYCJI ---
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

        msg = await kanal.send(embed=embed, view=WidokDecyzjiAdmina())
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")

        await interaction.response.send_message("Twój pomysł został pomyślnie wysłany!", ephemeral=True)

# --- 5. PRZYCISK ZGŁASZANIA PROPOZYCJI ---
class WidokPropozycji(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💡 Zgłoś propozycję", style=discord.ButtonStyle.primary, custom_id="przycisk_propozycji_v3")
    async def przycisk_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalPropozycji())

# --- 6. PRZYCISK PRZEJŚCIA DO MATERIAŁU ---
class WidokLinkuFilmu(discord.ui.View):
    def __init__(self, url: str):
        super().__init__(timeout=None)
        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"https://{url}"
        self.add_item(discord.ui.Button(label="▶️ Przejdź do materiału", url=url, style=discord.ButtonStyle.link))

# --- 7. GŁÓWNA KLASA BOTA ---
class BotPropozycji(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(WidokPropozycji())
        self.add_view(WidokDecyzjiAdmina())
        await self.tree.sync()

    async def on_ready(self):
        print(f"Zalogowano jako {self.user}")

bot = BotPropozycji()

# --- KOMENDY SOCIAL & EKONOMIA (DLA WSZYSTKICH) ---

@bot.tree.command(name="social", description="Wyświetla odnośniki do naszych mediów społecznościowych")
async def social_slash(interaction: discord.Interaction):
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
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="dzienna_nagroda", description="Odbierz darmowe monety co 24 godziny!")
async def dzienna_nagroda_slash(interaction: discord.Interaction):
    wallet = get_user_wallet(interaction.user.id)
    now = time.time()
    cooldown = 24 * 3600

    if now - wallet["last_daily"] < cooldown:
        remaining = int((cooldown - (now - wallet["last_daily"])) / 3600)
        await interaction.response.send_message(f"⏳ Odbierałeś już swoją nagrodę! Wróć za około **{remaining} godz.**", ephemeral=True)
        return

    reward = random.randint(100, 250)
    wallet["coins"] += reward
    wallet["last_daily"] = now
    save_user_data(user_db)

    embed = discord.Embed(
        title="🎁 Dzienna Nagroda Odebrana!",
        description=f"Otrzymujesz **{reward} monet**! 🎉\nAktualny stan konta: **{wallet['coins']} monet**.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stan_konta", description="Sprawdza stan portfela monet")
async def stan_konta_slash(interaction: discord.Interaction, uzytkownik: discord.Member = None):
    target = uzytkownik or interaction.user
    wallet = get_user_wallet(target.id)

    embed = discord.Embed(
        title=f"💰 Portfel: {target.display_name}",
        description=f"Liczba monet: **{wallet['coins']} 🪙**",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ruletka", description="Zagraj w ruletkę i spróbuj pomnożyć swoje monety!")
@app_commands.describe(stawka="Ile monet chcesz obstawić?", kolor="Wybierz kolor: czarny, czerwony lub zielony")
@app_commands.choices(kolor=[
    app_commands.Choice(name="🔴 Czerwony (Mnożnik x2)", value="czerwony"),
    app_commands.Choice(name="⚫ Czarny (Mnożnik x2)", value="czarny"),
    app_commands.Choice(name="🟢 Zielony (Mnożnik x14)", value="zielony")
])
async def ruletka_slash(interaction: discord.Interaction, stawka: int, kolor: app_commands.Choice[str]):
    if stawka <= 0:
        await interaction.response.send_message("❌ Stawka musi być większa niż 0!", ephemeral=True)
        return

    wallet = get_user_wallet(interaction.user.id)
    if wallet["coins"] < stawka:
        await interaction.response.send_message(f"❌ Nie masz wystarczająco monet! Posiadasz tylko {wallet['coins']} monet.", ephemeral=True)
        return

    # Pobieramy stawkę
    wallet["coins"] -= stawka

    # Losowanie ruletki (0-36)
    roll = random.randint(0, 36)
    if roll == 0:
        winning_color = "zielony"
    elif roll % 2 == 0:
        winning_color = "czarny"
    else:
        winning_color = "czerwony"

    won = False
    multiplier = 0
    if kolor.value == winning_color:
        won = True
        multiplier = 14 if winning_color == "zielony" else 2

    if won:
        winnings = stawka * multiplier
        wallet["coins"] += winnings
        color_emoji = "🟢" if winning_color == "zielony" else ("🔴" if winning_color == "czerwony" else "⚫")
        embed = discord.Embed(
            title="🎰 RZUT RULETKĄ",
            description=f"Wypadło: {color_emoji} **{winning_color.upper()}** (Liczba {roll})\n\n🎉 **WYGRANA!** Zdobywasz **{winnings} monet**!\nStan konta: **{wallet['coins']} monet**.",
            color=discord.Color.green()
        )
    else:
        color_emoji = "🟢" if winning_color == "zielony" else ("🔴" if winning_color == "czerwony" else "⚫")
        embed = discord.Embed(
            title="🎰 RZUT RULETKĄ",
            description=f"Wypadło: {color_emoji} **{winning_color.upper()}** (Liczba {roll})\n\n❌ **PRZEGRANA!** Tracisz {stawka} monet.\nStan konta: **{wallet['coins']} monet**.",
            color=discord.Color.red()
        )

    save_user_data(user_db)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="saper", description="Zagraj w Sapera i odkrywaj pola z diamentami!")
@app_commands.describe(stawka="Ile monet chcesz postawić?")
async def saper_slash(interaction: discord.Interaction, stawka: int):
    if stawka <= 0:
        await interaction.response.send_message("❌ Stawka musi być większa niż 0!", ephemeral=True)
        return

    wallet = get_user_wallet(interaction.user.id)
    if wallet["coins"] < stawka:
        await interaction.response.send_message(f"❌ Nie masz tylu monet! Posiadasz tylko {wallet['coins']} monet.", ephemeral=True)
        return

    wallet["coins"] -= stawka
    save_user_data(user_db)

    view = SaperGameView(interaction.user.id, stawka)
    embed = discord.Embed(
        title="💣 Saper - Gra Hazardowa",
        description=f"Postawiłeś **{stawka} monet**.\nNa planszy są 2 miny i 7 diamentów 💎.\nKlikaj pola, aby zwiększać swój mnożnik!",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="top_punkty", description="Wyświetla ranking najbogatszych graczy na serwerze")
async def top_punkty_slash(interaction: discord.Interaction):
    sorted_users = sorted(user_db.items(), key=lambda x: x[1].get("coins", 0), reverse=True)[:10]

    embed = discord.Embed(
        title="🏆 Ranking Najbogatszych Graczy",
        color=discord.Color.gold()
    )

    description_text = ""
    for idx, (uid, data) in enumerate(sorted_users, 1):
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else f"Użytkownik ({uid})"
        coins = data.get("coins", 0)
        description_text += f"**{idx}.** {name} — **{coins} 🪙**\n"

    embed.description = description_text or "Brak danych w rankingu."
    await interaction.response.send_message(embed=embed)

# --- KOMENDY ADMINA (TYLKO DLA CIEBIE) ---

@bot.tree.command(name="setup", description="Wysyła panel propozycji na kanał (Tylko dla wyznaczonego admina)")
async def setup_slash(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_DISCORD_ID:
        await interaction.response.send_message("❌ Nie posiadasz uprawnień do użycia tej komendy!", ephemeral=True)
        return

    embed = discord.Embed(
        title="💡 System Propozycji",
        description="Kliknij poniższy przycisk, aby otworzyć formularz i przesłać swój pomysł!",
        color=discord.Color.green()
    )
    await interaction.channel.send(embed=embed, view=WidokPropozycji())
    await interaction.response.send_message("Panel propozycji został pomyślnie wysłany!", ephemeral=True)

@bot.tree.command(name="ogloszenie", description="Wysyła ogłoszenie o nowym materiale/streamie (Tylko dla wyznaczonego admina)")
@app_commands.describe(url="Wklej bezpośredni link do filmu lub streama")
async def ogloszenie_slash(interaction: discord.Interaction, url: str):
    if interaction.user.id != ADMIN_DISCORD_ID:
        await interaction.response.send_message("❌ Nie posiadasz uprawnień do użycia tej komendy!", ephemeral=True)
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
    if interaction.guild and interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    
    embed.set_footer(text=f"Ogłoszenie dodane przez {interaction.user.display_name}")

    await interaction.channel.send(embed=embed, view=WidokLinkuFilmu(url))
    await interaction.response.send_message("Ogłoszenie zostało wysłane na kanał!", ephemeral=True)

if __name__ == "__main__":
    t = threading.Thread(target=run_http, daemon=True)
    t.start()

    if not TOKEN:
        print("BŁĄD: Brak tokenu DISCORD_TOKEN w Environment Variables!")
    else:
        print("Łączenie z Discordem...")
        bot.run(TOKEN)
        
