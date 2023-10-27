import datetime
import discord
from discord.ext import commands
import cv2
import numpy as np
from discord.commands import ApplicationContext, Option
import sqlite3
from scipy import spatial
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", case_insensitive=True, intents=intents, help_command=None)


@bot.event
async def on_ready(): #when bot goes online
    print("logged as {0.user}".format(bot))

conn = sqlite3.connect("starscape_pro.db")


def get_systems(img):
    non_altered = img.copy()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ret, thresh = cv2.threshold(img, 127, 255, cv2.THRESH_TOZERO)

    hsv = cv2.cvtColor(thresh, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    thresh1 = cv2.threshold(s, 40, 255, cv2.THRESH_BINARY)[1]

    kernel = np.ones((3, 3), np.uint8)
    opening = cv2.morphologyEx(thresh1, cv2.MORPH_OPEN, kernel)

    contours, hierarchy = cv2.findContours(opening, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(img, contours, -1, (0, 255, 0), 3)

    lower_bound = np.array([0, 0, 190])
    upper_bound = np.array([10, 10, 220])
    mask = cv2.inRange(hsv, lower_bound, upper_bound)
    segmented_img = cv2.bitwise_and(gray, gray, mask=mask)
    kernel = np.ones((2, 2), np.uint8)
    erosion = cv2.erode(segmented_img, kernel, iterations=1)
    kernel = np.ones((9, 9), np.uint8)
    dilation = cv2.dilate(erosion, kernel, iterations=2)

    cont, hierarchy = cv2.findContours(dilation, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    try:
        (x, y), radius = cv2.minEnclosingCircle(cont[0])
    except IndexError:
        error = "Failed to set some or all other systems. Please input rest manually"
    main = (int(x), int(y))
    img = cv2.circle(img, main, 2, (0, 0, 255), 2)

    others = []
    for colors in contours:
        (x, y), radius = cv2.minEnclosingCircle(colors)
        center = (int(x), int(y))
        others.append(center)

    tree = spatial.KDTree(others)
    query = tree.query([main])
    main = others.pop(query[1][0])

    look_up = {"[255 230 200]": "A",
               "[ 60  80 255]": "M",
               "[255 200 100]": "B",
               "[120 240 255]": "G",
               "[210 245 255]": "F",
               "[ 80 165 255]": "K"}

    x, y = main
    error = ""
    try:
        main = look_up[str(non_altered[y][x])]
    except KeyError:
        main = ""
        error = "Failed to set some or all other systems. Please input rest manually"

    second = []

    for col in others:
        x, y = col
        try:
            second.append(look_up[str(non_altered[y][x])])
        except KeyError:
            error = "Failed to set some or all other systems. Please input rest manually"
    return main, second, error


image_types = ["png", "jpeg", "gif", "jpg"]

def color_only_solve(main, colors, connected=0):
    if connected == 0:
        possible = conn.execute("SELECT id, connected_i, spectral, name, security FROM systems WHERE security='Wild' and spectral=?", [main]).fetchall()
    else:
        possible = conn.execute("SELECT id, connected_i, spectral, name, security FROM systems WHERE security='Wild' and spectral=? and connection_count=?", [main, connected]).fetchall()
    possible_s = []
    for system in possible:
        connected = conn.execute(f"SELECT id, connected_i, spectral FROM systems WHERE id IN ({system[1]})").fetchall()
        con = set()
        col = []
        level2 = [system[0]]
        for color in connected:
            if color[2] not in colors:
                break
            else:
                level2.append(color[0])
        for i in connected:
            col.append(i[2])
            for x in list(map(int, i[1].split(","))):
                if x not in level2:
                    con.add(str(x))

        connnected_2 = conn.execute(f"SELECT id, connected_i, spectral FROM systems WHERE id IN ({','.join(con)})").fetchall()
        for color in connnected_2:
            if color[2] not in colors:
                break
            else:
                col.append(color[2])
        if sorted(col) == sorted(colors):
            possible_s.append(system[3])
    return possible_s

class connected_choose(discord.ui.Button):
    def __init__(self, label:str, row:int, custom:str):
        super().__init__(
            label=label,
            style=discord.enums.ButtonStyle.grey,
            row=row,
            custom_id=custom
        )

    async def callback(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        temp=embed.fields[0].value
        name = embed.fields[0].name
        embed.remove_field(0)
        s = temp[:37] + self.label + temp[37 + 1:]
        embed.add_field(name=name, value=s,inline=False)
        await interaction.response.edit_message(embed=embed)


class target_choose(discord.ui.Button):
    def __init__(self, emoji ,row:int):
        super().__init__(
            emoji=emoji,
            style=discord.enums.ButtonStyle.grey,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        temp=embed.fields[0].value.split("\n")
        name = embed.fields[0].name
        embed.remove_field(0)
        s = temp[1].split(":")[0]
        new_string = s + ": " + str(self.emoji)
        temp[1] = new_string
        embed.add_field(name=name, value="\n".join(temp),inline=False)
        await interaction.response.edit_message(embed=embed)

class other_choose(discord.ui.Button):
    def __init__(self, emoji ,row:int):
        super().__init__(
            emoji=emoji,
            style=discord.enums.ButtonStyle.grey,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        temp=embed.fields[0].value.split("\n")
        name = embed.fields[0].name
        embed.remove_field(0)
        splitted = temp[2].split("):")
        old = splitted[0]
        colors = splitted[1]
        new_string = old + "): " + colors + " " + str(self.emoji)
        temp[2] = new_string
        embed.add_field(name=name, value="\n".join(temp),inline=False)
        await interaction.response.edit_message(embed=embed)

class other_remove(discord.ui.Button):
    def __init__(self, emoji ,row:int):
        super().__init__(
            emoji=emoji,
            style=discord.enums.ButtonStyle.red,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        temp=embed.fields[0].value.split("\n")
        name = embed.fields[0].name
        embed.remove_field(0)
        splitted = temp[2].split("):")
        old = splitted[0]
        colors = list(filter(None, splitted[1].split(" ")))
        if len(colors) == 0:
            return None
        elif len(colors) == 1:
            temp[2] = old + "): "
            embed.add_field(name=name, value="\n".join(temp),inline=False)
            await interaction.response.edit_message(embed=embed)
        else:
            colors.pop()
        temp[2] = old + "): " +" ".join(colors)
        embed.add_field(name=name, value="\n".join(temp),inline=False)
        await interaction.response.edit_message(embed=embed)



class main_view(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx
    pressed = False
    blue = "<:B_:949716430901903380>"
    light_blue = "<:A_:949716430545367050>"
    skin = "<:F_:949716431031894167>"
    yellow = "<:G_:949716431627493416>"
    orange = "<:K_:949716420416110612>"
    red = "<:M_:949716373397987428>"
    remove = "<:x_:949741601666777159>"

    @discord.ui.button(label="Connected", style=discord.enums.ButtonStyle.primary)
    async def connected_button_callback(self, button, interaction: discord.Interaction):
            if self.pressed:
                await self.remove_useless(interaction)
            button.style = discord.enums.ButtonStyle.green
            self.add_item(connected_choose("0", 2, "0"))
            self.add_item(connected_choose("1", 2, "1"))
            self.add_item(connected_choose("2", 2, "2"))

            self.add_item(connected_choose("3", 3, "3"))
            self.add_item(connected_choose("4", 3, "4"))
            self.add_item(connected_choose("5", 3, "5"))

            self.add_item(connected_choose("6", 4, "6"))
            self.add_item(connected_choose("7", 4, "7"))
            self.add_item(connected_choose("8", 4, "8"))
            self.pressed = True
            await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Target color", style=discord.enums.ButtonStyle.primary)
    async def target_button_callback(self, button, interaction):
        if self.pressed:
            await self.remove_useless(interaction)
        button.style = discord.enums.ButtonStyle.green
        self.add_item(target_choose(self.blue, 2))
        self.add_item(target_choose(self.light_blue, 2))
        self.add_item(target_choose(self.skin, 2))
        self.add_item(target_choose(self.yellow, 3))
        self.add_item(target_choose(self.orange, 3))
        self.add_item(target_choose(self.red, 3))
        self.pressed = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Other colors", style=discord.enums.ButtonStyle.primary)
    async def other_button_callback(self, button, interaction):
        if self.pressed:
            await self.remove_useless(interaction)
        button.style = discord.enums.ButtonStyle.green
        self.add_item(other_choose(self.blue, 2))
        self.add_item(other_choose(self.light_blue, 2))
        self.add_item(other_choose(self.skin, 2))
        self.add_item(other_choose(self.yellow, 3))
        self.add_item(other_choose(self.orange, 3))
        self.add_item(other_choose(self.red, 3))
        self.add_item(other_remove(self.remove, 2))
        self.pressed = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Solve", style=discord.enums.ButtonStyle.red)
    async def solve_button_callback(self, button, interaction: discord.Interaction):
        try:
            embed = interaction.message.embeds[0]
            temp=embed.fields[0].value
            connected = temp[37]
            parts = temp.split("\n")
            target = parts[1].split("):")[1][3]
            splitted = parts[2].split("):")
            colors = list(filter(None, splitted[1].split(" ")))
            other = []
            for x in colors:
                other.append(x[2])
        except IndexError as e:
            return await interaction.response.send_message(f"Argument missing", ephemeral=True)
        await interaction.response.send_message(f"Working on it", ephemeral=True)

        res = color_only_solve(target, other, int(connected))
        if not len(res):
            await interaction.followup.send("Failed to locate your beacon.", ephemeral=True)
        else:
            await interaction.message.edit(view=self)
            await interaction.followup.send(", ".join(res) + " (This message will get deleted after a while. You have been warned)", ephemeral=True)





    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("You can't do that. Please run your own command /solve_beacon", ephemeral=True)
            return False
        return True

    async def remove_useless(self, interaction: discord.Interaction):
        self.pressed = False
        to_del2 = []
        to_col = ["Target color", "Other colors", "Connected"]
        for x in self.children:
            if x.row is not None:
                to_del2.append(x)
            if x.label in to_col:
                x.style = discord.enums.ButtonStyle.primary
        for y in to_del2:
            self.remove_item(y)
        await interaction.message.edit(view=self)

look_up = {"B": "<:B_:949716430901903380>",
           "A": "<:A_:949716430545367050>",
           "F": "<:F_:949716431031894167>",
           "G": "<:G_:949716431627493416>",
           "K": "<:K_:949716420416110612>",
           "M": "<:M_:949716373397987428>",
           "": ""
           }


@bot.slash_command(description="Command for solving beacon.")
async def solve_beacon(ctx,
                       connected: Option(int, "Enter the amount of systems target location is connected to.", default = 0, min_value=0, max_value=9),
                       attachment: Option(discord.Attachment, "Beacon image (Computer vision will attempt to read data from image for you)", required=False, default="")):
    await ctx.defer()
    target = ""
    other = ""
    if attachment != "":
        img = np.asarray(bytearray(await attachment.read()), 'uint8')
        img = cv2.imdecode(img, cv2.IMREAD_COLOR)
        try:
            main, second, error = get_systems(img)
            target = look_up[main]
            for x in second:
                other += look_up[x] + " "
            if error != "":
                await ctx.followup.send(error, ephemeral=True)
        except Exception as e:
            await ctx.followup.send("Computer vision failed fully. Please use manual input!", ephemeral=True)

    view = main_view(ctx)
    embed = discord.Embed(title="Beacon Solver", description="Make sure external emojis is allowed. Source code can be found [here](https://github.com/iraaz4321/starscape_beacon_solver)", colour=0xfbeb04, timestamp=datetime.datetime.utcnow())
    embed.add_field(name=f"Beacon data",
                    value=f"Target system connected count (opt): {connected}\nTarget system color (req): {target}\nRest of colors (req): {other}", inline=False)
    embed.set_footer(text="")
    await ctx.respond(embed=embed, view=view)


bot.run(os.getenv("token"))