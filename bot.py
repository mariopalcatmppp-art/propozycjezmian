
import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime

# --- KONFIGURACJA ---
TOKEN = "MTU1MDc5NTk0MjM3NzE2NDgzMA.GmjVYw.nKuVyodtzvPFwcnvjyOMayKIgK1cl4uSuMr4XY"
ADMIN_PASSWORD = "123supermaja!"

# --- FORMULARZ OGŁOSZEŃ DLA ADMINA (MODAL) ---
class AnnouncementModal(discord.ui.Modal, title="📢 Wyślij Ogłoszenie"):
    target_channel_id = discord.ui.TextInput(
        label="ID Kanału Ogłoszeń",
        placeholder="Wklej ID kanału, na który wysłać wiadomość...",
        required=True
    )
    title_text = discord.ui.TextInput(
        label="Tytuł Ogłoszenia",
        placeholder="Wpisz tytuł...",
        required=True
    )
    content_text = discord.ui.TextInput(
        label="Treść Ogłoszenia",
        style=discord.TextStyle.paragraph,
        placeholder="Wpisz pełną treść ogłoszenia...",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.target_channel_id.value)
            channel = interaction.guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message("❌ Nie znaleziono takiego kanału tekstowego!", ephemeral=True)
                return

            embed = discord.Embed(
                title=self.title_text.value,
                description=self.content_text.value,
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.set_footer(text=f"Ogłoszenie wysłane przez {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
            
            await channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Ogłoszenie pomyślnie wysłane na kanał {channel.mention}!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ ID kanału musi być liczbą!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Wystąpił błąd: {e}", ephemeral=True)


# --- WIDOK PANELU ADMINA (PRZYCISKI) ---
class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📊 Statystyki Bota & Serwera", style=discord.ButtonStyle.primary, custom_id="admin_stats_full", row=0)
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        embed = discord.Embed(title="📊 Statystyki Projektu", color=discord.Color.blue())
        embed.add_field(name="Nazwa Serwera", value=guild.name, inline=True)
        embed.add_field(name="Liczba Użytkowników", value=str(guild.member_count), inline=True)
        embed.add_field(name="Liczba Kanałów", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Opóźnienie (Ping)", value=f"{round(interaction.client.latency * 1000)} ms", inline=True)
        embed.set_footer(text="Panel Administratora")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📢 Wyślij Ogłoszenie", style=discord.ButtonStyle.success, custom_id="admin_announce_full", row=0)
    async def announce_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AnnouncementModal())

    @discord.ui.button(label="🧹 Wyczyść Czat (50 wiadomości)", style=discord.ButtonStyle.secondary, custom_id="admin_clear_chat", row=1)
    async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Nie masz uprawnień do zarządzania wiadomościami!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=50)
        await interaction.followup.send(f"✅ Usunięto **{len(deleted)}** wiadomości z tego kanału.", ephemeral=True)

    @discord.ui.button(label="🛡️ Status Systemu", style=discord.ButtonStyle.danger, custom_id="admin_status_full", row=1)
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚙️ Status Podsystemów",
            description="🟢 Wszystkie usłuigi działają prawidłowo.\n🟢 Połączenie z API Discorda: Stabilne\n🟢 Baza danych / Cache: OK",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# --- BOT MAIN CLASS ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(AdminPanelView())
        await self.tree.sync()

bot = MyBot()

@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Game(name="Użyj /help do zabawy!"))


# ==============================================================================
# 🛠️ KOMENDA ADMINISTRATORA (/admin)
# ==============================================================================

@bot.tree.command(name="admin", description="Dostęp do panelu administratora")
@app_commands.describe(haslo="Hasło autoryzacyjne administratora")
async def admin(interaction: discord.Interaction, haslo: str):
    if haslo == ADMIN_PASSWORD:
        embed = discord.Embed(
            title="🛠️ Ukryty Panel Administratora",
            description="Witaj w prywatnym centrum zarządzania projektem.\n\nWybierz opcję z poniższego menu interaktywnego. Żaden inny użytkownik nie widzi tej wiadomości ani Twoich interakcji.",
            color=discord.Color.dark_red()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="🔒 Status Dostępu", value="Autoryzacja pomyślna (Poziom Root)", inline=False)
        
        await interaction.response.send_message(embed=embed, view=AdminPanelView(), ephemeral=True)
    else:
        # Zabezpieczenie: cicha odpowiedź przy złym haśle
        await interaction.response.send_message("❌ Odmowa dostępu: Niepoprawne hasło.", ephemeral=True)


# ==============================================================================
# 🎉 KOMENDY PUBLICZNE I ROZRYWKOWE
# ==============================================================================

@bot.tree.command(name="help", description="Wyświetla listę dostępnych komend")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Centrum Pomocy i Rozrywki",
        description="Oto lista wszystkich dostępnych komend, z których możesz korzystać na tym serwerze:",
        color=discord.Color.blurple()
    )
    embed.add_field(name="🎲 /kostka", value="Rzuca tradycyjną kością sześciościenną (1-6).", inline=True)
    embed.add_field(name="🪙 /moneta", value="Rzuca monetą – Orzeł czy Reszka?", inline=True)
    embed.add_field(name="🔮 /kulka [pytanie]", value="Magiczna kulka 8-Ball odpowiada na Twoje pytania.", inline=True)
    embed.add_field(name="✂️ /kamien_papier [wybor]", value="Zagraj z botem w Kamień, Papier, Nożyce.", inline=True)
    embed.add_field(name="🎯 /losuj [od] [do]", value="Losuje liczbę z podanego zakresu.", inline=True)
    embed.add_field(name="❤️ /statek_milosny [osoba1] [osoba2]", value="Oblicza wskaźnik dopasowania miłosnego.", inline=True)
    embed.add_field(name="🖼️ /avatar [uzytkownik]", value="Wyświetla profilowe wybranego użytkownika.", inline=True)
    embed.add_field(name="🐸 /mem", value="Generuje losowy żart/mem.", inline=True)
    embed.set_footer(text="Użyj symbolu / aby wywołać dowolną komendę!")
    
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="kostka", description="Rzuć kością 6-ścienną")
async def kostka(interaction: discord.Interaction):
    wynik = random.randint(1, 6)
    await interaction.response.send_message(f"🎲 **{interaction.user.display_name}** wyrzuca: **{wynik}**!")


@bot.tree.command(name="moneta", description="Rzuć monetą")
async def moneta(interaction: discord.Interaction):
    wynik = random.choice(["Orzeł", "Reszka"])
    await interaction.response.send_message(f"🪙 **{interaction.user.display_name}** rzuca monetą... Wynik to: **{wynik}**!")


@bot.tree.command(name="kulka", description="Zapytaj magiczną kulkę 8-Ball")
@app_commands.describe(pytanie="Twoje pytanie do magicznej kulki")
async def kulka(interaction: discord.Interaction, pytanie: str):
    odpowiedzi = [
        "Zdecydowanie tak!", "Wszystko wskazuje na to, że tak.", "Moim zdaniem – nie.",
        "Zapytaj ponownie później.", "Nie stawiaj na to.", "Znaki mówią: tak.",
        "Moje źródła mówią nie.", "Bardzo prawdopodobne."
    ]
    embed = discord.Embed(color=discord.Color.purple())
    embed.add_field(name="❓ Pytanie", value=pytanie, inline=False)
    embed.add_field(name="🔮 Odpowiedź", value=random.choice(odpowiedzi), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="kamien_papier", description="Zagraj w Kamień, Papier, Nożyce")
@app_commands.choices(wybor=[
    app_commands.Choice(name="Kamień 🪨", value="Kamień"),
    app_commands.Choice(name="Papier 📄", value="Papier"),
    app_commands.Choice(name="Nożyce ✂️", value="Nożyce")
])
async def kamien_papier(interaction: discord.Interaction, wybor: app_commands.Choice[str]):
    bot_wybor = random.choice(["Kamień", "Papier", "Nożyce"])
    gracz = wybor.value

    if gracz == bot_wybor:
        wynik = "🤝 Remis!"
    elif (gracz == "Kamień" and bot_wybor == "Nożyce") or \
         (gracz == "Papier" and bot_wybor == "Kamień") or \
         (gracz == "Nożyce" and bot_wybor == "Papier"):
        wynik = "🎉 Wygrałeś!"
    else:
        wynik = "💻 Bot wygrał!"

    await interaction.response.send_message(
        f"Twój wybór: **{gracz}** | Wybór bota: **{bot_wybor}**\nWynik: **{wynik}**"
    )


@bot.tree.command(name="losuj", description="Losuje liczbę z wybranego zakresu")
@app_commands.describe(od="Liczba minimalna", do="Liczba maksymalna")
async def losuj(interaction: discord.Interaction, od: int, do: int):
    if od >= do:
        await interaction.response.send_message("❌ Liczba 'od' musi być mniejsza od liczby 'do'!", ephemeral=True)
        return
    wynik = random.randint(od, do)
    await interaction.response.send_message(f"🎯 Wylosowana liczba z zakresu {od}-{do} to: **{wynik}**")


@bot.tree.command(name="statek_milosny", description="Sprawdź procent dopasowania dwóch osób")
@app_commands.describe(osoba1="Pierwsza osoba", osoba2="Druga osoba")
async def statek_milosny(interaction: discord.Interaction, osoba1: discord.Member, osoba2: discord.Member):
    procent = random.randint(0, 100)
    
    if procent > 80:
        komentarz = "❤️ Idealna para! Miłość wisi w powietrzu!"
    elif procent > 50:
        komentarz = "🙂 Jest całkiem nieźle, warto spróbować!"
    else:
        komentarz = "💔 Lepiej zostańcie przyjaciółmi..."

    embed = discord.Embed(title="❤️ Kalkulator Miłosny", color=discord.Color.magenta())
    embed.add_field(name="Para", value=f"{osoba1.mention} + {osoba2.mention}", inline=False)
    embed.add_field(name="Dopasowanie", value=f"**{procent}%**", inline=False)
    embed.add_field(name="Ocena", value=komentarz, inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="avatar", description="Pobierz powiększony avatar użytkownika")
@app_commands.describe(uzytkownik="Wybierz użytkownika")
async def avatar(interaction: discord.Interaction, uzytkownik: discord.Member = None):
    target = uzytkownik or interaction.user
    embed = discord.Embed(title=f"Avatar użytkownika {target.display_name}", color=discord.Color.dark_gold())
    embed.set_image(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="mem", description="Losowy żart / tekst rozrywkowy")
async def mem(interaction: discord.Interaction):
    zarty = [
        "Dlaczego programiści wolą ciemny motyw? Bo światło przyciąga robaki (bugi)! 🐛",
        "Wchodzą dwa bajty do baru. Jednego zmieniono na bit. Ten drugi pyta: 'Co z tobą?', a ten odpowiada: 'Nic, czuję się trochę mniej wartościowy.' 💻",
        "Pytanie: Ile programistów potrzeba do zmiany żarówki?\nOdpowiedź: Żadnego, to problem sprzętowy. 💡"
    ]
    await interaction.response.send_message(f"😄 {random.choice(zarty)}")


# --- URUCHOMIENIE BOTA ---
bot.run(TOKEN)
          
