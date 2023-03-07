import discord, os, glob, re, json, types
from typing import Any
from discord.ext import tasks
from dotenv import load_dotenv
from ruamel.yaml import YAML, constructor
from datetime import datetime, timedelta, timezone



def utcnow() -> datetime: return datetime.now(timezone.utc)

def format_timedelta(td: timedelta, smallest_unit="s") -> str:
    match smallest_unit:
        case "s": return re.sub(r"\.\d+", "", str(td))
        case "m": return re.sub(r":\d+\.\d+", "", str(td))
        case "h": return re.sub(r":\d+:\d+\.\d+", "", str(td))
    return str(td)

def string_to_timedelta(string: str) -> timedelta:
    weeks = re.findall(r"(\d+) ?w(?:eeks?)?", string, re.IGNORECASE)
    days = re.findall(r"(\d+) ?d(?:ays?)?", string, re.IGNORECASE)
    hours = re.findall(r"(\d+) ?h(?:ours?)?", string, re.IGNORECASE)
    minutes = re.findall(r"(\d+) ?m(?:in|minutes?)?", string, re.IGNORECASE)
    seconds = re.findall(r"(\d+) ?s(?:ec|econds?)?", string, re.IGNORECASE)

    w = int(weeks[0]) if weeks else 0
    d = int(days[0]) if days else 0
    h = int(hours[0]) if hours else 0
    m = int(minutes[0]) if minutes else 0
    s = int(seconds[0]) if seconds else 0
    
    return timedelta(
        weeks=w,
        days=d,
        hours=h,
        minutes=m,
        seconds=s
    )

# https://discord.com/developers/docs/reference#message-formatting-timestamp-styles
def timestamp(dt: datetime, mode: str = "") -> str:
    if not mode: return f"<t:{int(dt.timestamp())}>"
    return f"<t:{int(dt.timestamp())}:{mode}>"

# ---------- Load Token ---------- #

load_dotenv()
TOKEN = os.getenv("TOKEN")





# ---------- Load YAML ---------- #

yaml_files: list[str] = []

for pattern in ["*.yml", "*.yaml"]:
    yaml_files += glob.glob(pattern)

if not yaml_files:
    raise FileNotFoundError("Could not find any YAML files.")

for path in yaml_files:
    try:
        with open(path) as f:
            yaml = YAML(typ="safe").load(f)
    except constructor.DuplicateKeyError: # Top notch error handling
        raise constructor.DuplicateKeyError("Duplicate keys are not supported.")

    if yaml: break

# I feel like errors have so much more to offer while Im just using them to print a message...
if not yaml: raise SyntaxError("YAML file is empty.")
if not isinstance(yaml, dict): raise TypeError("YAML is not a dictionary.")

print(f"Executing {path}")







# ---------- Assign Intents ---------- #

intents = discord.Intents.default()

if "intents" in yaml:
    if not isinstance(yaml["intents"], list): raise TypeError("Intents must be a list of strings.")

    for intent in yaml["intents"]:
        if not isinstance(intent, str): raise TypeError("Intents must be string values")
        if not hasattr(intents, intent): raise ValueError(f"'{intent}' is not a valid intent.")
        exec(f"intents.{intent} = True")

client = discord.Client(intents=intents)






# ---------- Create Variables ---------- #

yaml_variables: list[str] = []

if "variables" in yaml:
   for var in yaml["variables"]:
       if not isinstance(var, str): raise SyntaxError("Variable names must be string.")
       if not re.fullmatch(r"[A-z_][A-z0-9_ ]*", var): raise SyntaxError(f"'{var}' is not a valid variable name.")
       var_name = var.replace(" ", "_")
       if var_name in yaml_variables: raise NameError(f"Could not define '{var}' since '{var_name}' already exists.")
       yaml_variables.append(var_name)
       exec(f'{var_name} = {repr(yaml["variables"][var])}')






# ---------- Guild With More Stats ---------- #

# Guild has slots which makes it hard to extend, hopefully this works
class Guild(discord.Guild):
    def __init__(self, guild: discord.Guild) -> None:
        if not guild: return
        self.role_count = len(guild.roles)
        self.category_count = len(guild.categories)
        self.forum_count = len(guild.forums)
        self.channel_count = len(guild.channels)
        self.emoji_count = len(guild.emojis)
        self.event_count = len(guild.scheduled_events)
        self.stage_channel_count = len(guild.stage_channels)
        self.stage_instance_count = len(guild.stage_instances)
        self.sticker_count = len(guild.stickers)
        self.text_channel_count = len(guild.text_channels)
        self.thread_count = len(guild.threads)
        self.voice_channel_count = len(guild.voice_channels)

        for key in guild.__slots__:
            setattr(self, key, getattr(guild, key))






# ---------- JSON ---------- #

class SaveHandler:
    path = ""
    data = {
        "messages": {},
        "timers": []
    }

    def __init__(self, path: str) -> None:
        self.path = path
        try:
            with open(path) as f:
                self.data = json.load(f)
        except: self.save()

    def save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=4)
    
    # I cant specify that func should be a Function because pyton has no forward declaration :(
    async def get_message(self, func) -> discord.Message:
        if "messages" not in self.data: return None
        if func.execution_path not in self.data["messages"]: return None
        msg = self.data["messages"][func.execution_path]
        if "channel" not in msg: return None
        if "id" not in msg: return None

        channel = await func.get_channel(msg["channel"])
        if not channel: return None

        try:
            message = await channel.fetch_message(msg["id"])
        except discord.NotFound: return None
        return message

    def save_msg(self, func) -> None:
        if not func: raise Exception("Could not save message.")
        if not hasattr(func, "msg"): raise Exception(f"Could not save message.\nTrace: {func.execution_path}")
        if not func.msg: raise Exception(f"Could not save message.\nTrace: {func.execution_path}")
        if "messages" not in self.data: self.data["messages"] = {}
        self.data["messages"][func.execution_path] = {
            "channel": func.msg.channel.id,
            "id": func.msg.id
        }
        self.save()

    def save_timer(self, func) -> None:
        if not func: raise Exception("Could not save timer.")
        if not hasattr(func, "time"): raise Exception(f"Could not save timer.\nTrace: {func.execution_path}")
        if not hasattr(func, "do"): raise Exception(f"Could not save timer.\nTrace: {func.execution_path}")
        if not func.time: raise Exception(f"Could not save timer.\nTrace: {func.execution_path}")
        if "timers" not in self.data: self.data["timers"] = []

        self.data["timers"].append({
            "func": func.execution_path,
            "channel": func.channel.id if func.channel else None,
            "user": func.user.id if func.user else None,
            "guild": func.guild.id if func.guild else None,
            "time": func.time.isoformat() if func.time else None,
            "do": func.do
        })

        self.save()
    
    def remove_timer_by_path(self, execution_path: str) -> None:
        for x in self.get_timers():
            if x["func"] == execution_path:
                self.data["timers"].remove(x)
                break
        self.save()

    def remove_timers(self, timers: list[dict]) -> None:
        for x in timers:
            self.data["timers"].remove(x)
        self.save()


    def get_timers(self) -> list[dict]:
        return self.data.get("timers", [])










save_data = SaveHandler("data.json")













# ---------- Functions ---------- #
# Functions should probably have their own file but Im too lazy

# Abstract-ish (you can instantiate it but it will convert itself to the correct type)
class Function:
    channel: discord.TextChannel = None
    user: discord.Member | discord.User = None
    guild: discord.Guild = None
    raw_function = {}
    function_name = ""
    execution_path = ""
    additional_variables = {}

    def __init__(self, raw_function: dict = None, channel: discord.TextChannel = None, user: discord.Member | discord.User = None, guild: discord.Guild = None, execution_path: str = "") -> None:
        self.channel = None
        self.user = None
        self.guild = None
        self.raw_function = {}
        self.function_name = ""
        self.execution_path = ""
        self.additional_variables = {}
        
        if not raw_function: return
        if not isinstance(raw_function, dict): raise TypeError(f"Function must be dictionary.\n{raw_function}")
        self.channel = channel
        self.user = user
        if guild: self.guild = Guild(guild)
        elif isinstance(user, discord.Member): self.guild = Guild(user.guild)
        self.raw_function = raw_function
        self.function_name = list(raw_function.keys())[0]
        self.execution_path = execution_path + " -> " + self.function_name
        self.assign_type(self.function_name)

    def assign_type(self, function_name: str) -> bool:
        match function_name.lower().replace(" ", "_"):
            case "add_role" | "add_roles": self.__class__ = FunctionAddRoles
            case "remove_role" | "remove_roles": self.__class__ = FunctionRemoveRoles
            case "set_variable" | "set_variables": self.__class__ = FunctionSetVariable
            case "remove_role" | "remove_roles": self.__class__ = FunctionRemoveRoles
            case "update_roles": self.__class__ = FunctionUpdateRoles
            case "update_message": self.__class__ = FunctionUpdateMessage
            case "send_message": self.__class__ = FunctionSendMessage
            case "response": self.__class__ = FunctionResponseMessage
            case "wait": self.__class__ = FunctionWait
            case _: return False
        return True

    # virtual
    async def find_arguments(self, arguments) -> None: pass

    # virtual
    async def execute(self) -> bool:
        await self.find_arguments(self.raw_function[self.function_name])
        return False

    async def get_user(self, id: int | str) -> discord.Member | discord.User:
        if not id: return None

        if isinstance(id, str):
            var = id.replace(" ", "_")
            if var in yaml_variables:
                return self.get_user(eval(var))
            if id.startswith("@"): id = id[1:]

        if self.guild:
            if isinstance(id, int):
                user = self.guild.get_member(id)
                if not user: user = await self.guild.fetch_member(id)
                return user
            
            if not isinstance(id, str): raise TypeError(f"User must be an integer ID, a username or a variable pointing to one of the former.\nTrace: {self.execution_path}")
            if id.lower() == "user": return self.user

            return self.guild.get_member_named(id)

        else:
            if isinstance(id, int):
                user = client.get_user(id)
                if not user: user = await client.fetch_user(id)
                return user
            
            if not isinstance(id, str): raise TypeError(f"User must be an integer ID, a username or a variable pointing to one of the former.\nTrace: {self.execution_path}")

            for user in client.users:
                if str(user) == id: return user
                if user.name == id: return user
            
            for user in client.get_all_members():
                if str(user) == id: return user
                if user.name == id: return user
                if user.nick == id: return user

    def get_role(self, id: int | str) -> discord.Role:
        if not id: return None

        if isinstance(id, str):
            var = id.replace(" ", "_")
            if var in yaml_variables:
                return self.get_role(eval(var))
            if id.startswith("@"): id = id[1:]
        
        if not self.guild:
            for guild in self.user.mutual_guilds:
                if isinstance(id, int): return guild.get_role(id)
                for role in guild.roles:
                    if role.name == id: return role
            return None
        
        if isinstance(id, int): return self.guild.get_role(id)
        
        for role in self.guild.roles:
            if role.name == id: return role

    async def get_channel(self, id: int | str):
        if not id: return None

        if isinstance(id, int):
            channel = client.get_channel(id)
            if channel: return channel
            channel = await client.fetch_channel(id)
            return channel

        if not isinstance(id, str):
            raise TypeError(f"Channel must be an integer ID, a channel name or a variable pointing to one of the former.\nTrace: {self.execution_path}")

        if id.startswith("#"): id = id[1:]

        for channel in client.get_all_channels():
            if channel.name == id: return channel
            
        return None

    def get_colour(self, id: int | str) -> int:
        if not id: return None
        if isinstance(id, int): return id
        if id in yaml_variables: return self.get_colour(eval(id))
        return None

    
    async def get_server(self, id: int | str) -> Guild:
        if not id: return None

        if isinstance(id, int):
            server = client.get_guild(id)
            if server: return Guild(server)
            server = await client.fetch_guild(id)
            if server: return Guild(server)
            return None

        if not isinstance(id, str): raise TypeError(f"Guild must be an integer ID, a guild name or a variable pointing to one of the former.\nTrace: {self.execution_path}")

        if id in yaml_variables: return await self.get_server(eval(id))

        for server in client.guilds:
            if server.name == id: return Guild(server)
        
        return None

    def evaluate(self, _string: str) -> Any:
        if not _string: return _string

        for _key in self.__dict__:
            exec(f"{_key} = self.{_key}")
        
        for _key in self.additional_variables:
            exec(f"{_key} = self.additional_variables[{repr(_key)}]")

        try:
            return eval(_string)
        except Exception as e: raise type(e)(f"{e}\nTrace: {self.execution_path}\n\n{_string}") from e

    def evaluate_string(self, _string: str) -> str:
        if not _string: return _string

        for _dictionary in [self.__dict__, self.additional_variables]:
            for _key in _dictionary:
                exec(f"{_key} = self.{_key}")
        
        try:
            return eval(f"f{repr(_string)}")
        except Exception as e: raise type(e)(f"{e}\nTrace: {self.execution_path}\n\n{_string}") from e

    async def aexec(self, code: str) -> None:
        # Make an async function with the code and `exec` it
        exec(
            'async def __exec(self):\n' +
            ''.join(f'\n {l}' for l in code.split('\n'))
        )
        await locals()["__exec"](self)


# Abstract
class FunctionRoles(Function):
    target: discord.Member = None
    roles: list[discord.Role] = []
    reason: str = None

    async def find_arguments(self, arguments) -> None:
        self.target = None
        self.roles = []
        self.reason = None

        if not self.guild: return
        
        if not isinstance(arguments, dict):
            arguments = {"roles": arguments}
        
        self.target = await self.get_user(arguments.get("target", None))
        if not self.target:
            if not isinstance(self.user, discord.Member): return
            self.target = self.user

        for key in ["role", "roles"]:
            if key not in arguments: continue

            value = arguments[key]
            # if instance is string evaluate it
            if isinstance(value, str):
                role = self.get_role(value)
                if role:
                    self.roles.append(role)
                    continue
                value = self.evaluate(value)

            if isinstance(value, list):
                for role_id in value:
                    role = self.get_role(role_id)
                    if role: self.roles.append(role)
            else:
                role = self.get_role(value)
                if role: self.roles.append(role)
        
        self.reason = arguments.get("reason", None)


    async def execute(self) -> bool:
        await super().execute()
        if not self.target: return False
        if not self.roles: return False
        return True

class FunctionAddRoles(FunctionRoles):
    async def execute(self) -> bool:
        if not await super().execute(): return False
        await self.target.add_roles(*self.roles, reason=self.reason)
        return True

class FunctionRemoveRoles(FunctionRoles):
    async def execute(self) -> bool:
        if not await super().execute(): return False
        await self.target.remove_roles(*self.roles, reason=self.reason)
        return True

class FunctionUpdateRoles(Function):
    target: discord.Member = None
    add: list[discord.Role] = []
    remove: list[discord.Role] = []
    reason: str = None

    async def find_arguments(self, arguments) -> None:
        self.target = None
        self.add = []
        self.remove = []
        self.reason = None

        await super().find_arguments(arguments)
        
        self.target = await self.get_user(arguments.get("target", None))
        if not self.target:
            if not isinstance(self.user, discord.Member):
                if self.user and self.guild:
                    self.user = self.guild.get_member(self.user.id)
                else: return
            self.target = self.user

        for key in ["add", "remove"]:
            if key not in arguments: continue
            value = arguments[key]
            
            if isinstance(value, str):
                role = self.get_role(value)
                if role:
                    exec(f"self.{key}.append(role)")
                    continue
                value = self.evaluate(value)

            if isinstance(value, list):
                for role_id in value:
                    role = self.get_role(role_id)
                    if role: exec(f"self.{key}.append(role)")
            else:
                role = self.get_role(value)
                if role: exec(f"self.{key}.append(role)")
        
        self.reason = arguments.get("reason", None)


    async def execute(self) -> bool:
        await super().execute()
        if not self.target: return False

        remove_roles = set(self.remove) - set(self.add)
        if remove_roles:
            await self.target.remove_roles(*remove_roles, reason=self.reason)
        if self.add:
            await self.target.add_roles(*self.add, reason=self.reason)
        return True

class FunctionSetVariable(Function):
    variables: list[str] = []
    evaluate_values: bool = False
    arguments: dict = {}

    async def find_arguments(self, arguments) -> None:
        self.variables = []
        self.evaluate_values = False
        self.arguments = arguments

        if not isinstance(arguments, dict):
            raise TypeError(f"'{arguments}' is not a dict.\nTrace: {self.execution_path}")
        
        for var in arguments:
            if var == "evaluate":
                self.evaluate_values = arguments[var]
                continue
            
            if var.replace(" ", "_") not in yaml_variables:
                raise NameError(f"{var} is not defined.\nTrace: {self.execution_path}")
            
            self.variables.append(var)
        
    async def execute(self) -> bool:
        await super().execute()
        if not self.variables: return False

        for var in self.variables:
            var_name = var.replace(" ", "_")
            if self.evaluate_values: await self.aexec(f"global {var_name}; {var_name} = {self.arguments[var]}")
            else: await self.aexec(f"global {var_name}; {var_name} = {repr(self.arguments[var])}")
        
        return True

# Abstract
class FunctionMessage(Function):
    content = ""
    tts: bool = False
    embed: discord.Embed = None
    embeds: list[discord.Embed] = []
    file: discord.File = None
    files: list[discord.File] = []
    delete_after: float = None
    allowed_mentions: discord.AllowedMentions = None
    reference = None
    mention_author: bool = None
    view: discord.ui.View = None
    stickers = None
    suppress_embeds: bool = False
    silent: bool = False

    msg: discord.Message = None

    async def send(self) -> discord.Message:
        if not self.channel: return None

        args = {
            "tts": self.tts,
            "delete_after": self.delete_after,
            "allowed_mentions": self.allowed_mentions,
            "reference": self.reference,
            "mention_author": self.mention_author,
            "stickers": self.stickers,
            "suppress_embeds": self.suppress_embeds,
            "view": self.view,
            "silent": self.silent
        }

        if self.file: args["file"] = self.file
        elif self.files: args["files"] = self.files
        if self.embed: args["embed"] = self.embed
        elif self.embeds: args["embeds"] = self.embeds

        self.msg = await self.channel.send(self.content, **args)

    async def edit(self):
        if not self.msg: return

        files = [self.file] if self.file else self.files
        if not files: files = []

        if self.embed:
            self.msg = await self.msg.edit(
                content=self.content,
                embed=self.embed,
                attachments=files,
                suppress=self.suppress_embeds,
                delete_after=self.delete_after,
                allowed_mentions=self.allowed_mentions,
                view=self.view
            )
        else:
            self.msg = await self.msg.edit(
                content=self.content,
                embeds=self.embeds,
                attachments=files,
                suppress=self.suppress_embeds,
                delete_after=self.delete_after,
                allowed_mentions=self.allowed_mentions,
                view=self.view
            )

    def compare_to(self, msg: discord.Message) -> bool:
        if self.view: return False
        if msg.content != self.content: return False
        if len(msg.embeds) == 1:
            if msg.embeds[0] != self.embed: return False
        elif msg.embeds != self.embeds: return False
        if self.file: return [self.file] == msg.attachments
        return self.files == msg.attachments
        
    async def find_arguments(self, arguments) -> None:
        self.content = ""
        self.tts = False
        self.embed = None
        self.embeds = []
        self.file = None
        self.files = []
        self.delete_after = None
        self.allowed_mentions = None
        self.reference = None
        self.mention_author = None
        self.view = None
        self.stickers = None
        self.suppress_embeds = False
        self.silent = False

        if isinstance(arguments, str):
            self.content = arguments
            return

        if "channel" in arguments:
            self.channel = await self.get_channel(arguments["channel"])
        
        if "content" not in arguments: raise SyntaxError(f"Message does not have any content.\nTrace: {self.execution_path}")
        if isinstance(arguments["content"], str): arguments["content"] = [{"text": arguments["content"]}]
        if not isinstance(arguments["content"], list): raise TypeError(f"Content must be string or a list.\nTrace: {self.execution_path} -> content")

        view = VeiwGenerator(self)
        content_count: dict[str, int] = {}

        for item in arguments["content"]:
            if not item: continue
            if not isinstance(item, dict): raise TypeError(f"Message content must be dictionaries.\nTrace: {self.execution_path} -> content -> ?\n{item}")

            content_name = str(list(item.keys())[0])
            content_type = content_name.lower().replace(" ", "_")
            trace = self.execution_path + " -> content -> " + content_name

            if content_type not in content_count: content_count[content_type] = 1
            else:
                content_count[content_type] += 1
                trace += " " + content_count[content_name]


            match content_type:
                case "text": self.content = self.evaluate_string(item["text"])
                case "embed": self.embeds.append(self.create_embed(item["embed"], trace))
                case "select": view.add_select(item[content_name], trace)
                case _: raise NameError(f"'{content_name}' is not a recognised message content type.\nTrace: {self.execution_path} -> content -> ?")

        if self.embeds and len(self.embeds) == 1: self.embed = self.embeds.pop()
        if self.files and len(self.files) == 1: self.file = self.files.pop()

        if view.is_valid(): self.view = view.view

    def create_embed(self, data, trace: str) -> discord.Embed:
        if not isinstance(data, dict): raise TypeError(f"Embed must be a dictionary.\nTrace: {trace}")
        new_embed = discord.Embed(
            colour=self.get_colour(data.get("colour")),
            title=self.evaluate_string(data.get("title")),
            type=self.evaluate_string(data.get("type", "rich")),
            url=self.evaluate_string(data.get("url")),
            description=self.evaluate_string(data.get("description"))
        )
        
        fields = data.get("fields", [])
        if not isinstance(fields, list): raise TypeError(f"Embed fields must be a list.\nTrace: {trace} -> fields")

        for field in fields:
            new_embed.add_field(
                name=self.evaluate_string(field.get("name")),
                value=self.evaluate_string(field.get("value")),
                inline=field.get("inline", False)
            )
        
        footer = data.get("footer")
        if not footer: return new_embed

        if isinstance(footer, str): footer = {"text": footer}
        new_embed.set_footer(text=self.evaluate_string(footer.get("text")), icon_url=self.evaluate_string(footer.get("icon")))
        return new_embed

class FunctionSendMessage(FunctionMessage):
    async def execute(self) -> bool:
        await super().execute()
        if not self.channel: return False
        await self.send()
        return True

class FunctionUpdateMessage(FunctionMessage):
    async def execute(self) -> bool:
        await super().execute()
        if not self.channel: return False
        self.msg = await save_data.get_message(self)

        if not self.msg:
            await self.send()
            save_data.save_msg(self)
            return True

        if self.compare_to(self.msg): return False
        await self.edit()

        save_data.save_msg(self)
        return True

class FunctionResponseMessage(FunctionMessage):
    ephemeral = True
    response: discord.InteractionResponse = None

    async def find_arguments(self, arguments) -> None:
        self.ephemeral = True
        self.response = None

        await super().find_arguments(arguments)
        self.delete_after = 15
        
        self.response = self.additional_variables.get("response")
        if not isinstance(arguments, dict): return

        self.ephemeral = arguments.get("ephemeral", True)
        self.delete_after = arguments.get("delete_after", self.delete_after)
        self.delete_after = arguments.get("delete after", self.delete_after)

    async def execute(self) -> bool:
        await super().execute()
        if not self.channel: return False
        if not self.response: return False
        if self.response.is_done(): return False

        args = {
            "tts": self.tts,
            "delete_after": self.delete_after,
            "allowed_mentions": self.allowed_mentions,
            "suppress_embeds": self.suppress_embeds,
            "silent": self.silent,
            "ephemeral": self.ephemeral
        }

        if self.file: args["file"] = self.file
        elif self.files: args["files"] = self.files
        if self.embed: args["embed"] = self.embed
        elif self.embeds: args["embeds"] = self.embeds
        if self.view: args["view"] = self.view

        self.msg = await self.response.send_message(self.content, **args)
        return True
    

class FunctionWait(Function):
    time: datetime = None
    do: list[dict] = []

    async def find_arguments(self, arguments) -> None:
        self.time = None
        self.do = []

        await super().find_arguments(arguments)
        
        for required_key in ["time", "do"]:
            if required_key not in arguments:
                raise SyntaxError(f"Wait function requires '{required_key}'.\nTrace: {self.execution_path}")

        do = arguments["do"]
        if isinstance(do, str): do = self.evaluate(do)

        if not isinstance(arguments["do"], list):
            raise TypeError(f"'do' must be a list of functions.\nTrace: {self.execution_path}")
        
        if not do: raise ValueError("'do' cannot be empty")
        self.do = do


        time = arguments["time"]
        if not isinstance(time, str): raise TypeError(f"Time must be a string.\nTrace: {self.execution_path}")
        if time in yaml_variables: time = self.evaluate(time)
        
        td = string_to_timedelta(arguments["time"])
        if td.total_seconds() <= 0: raise ValueError("Time must have more than 0 seconds.")
        self.time = utcnow() + td



    async def execute(self) -> bool:
        await super().execute()
        if not self.time: return False
        if not self.do: return False
        save_data.save_timer(self)
        return True










# ---------- View and Interactions ---------- #


# Storing object in a list so that they dont get deleted from memory
interactions = []



class Interaction:
    code = {}
    execution_path = ""
    item = None

    def __init__(self, item, code: dict, trace: str) -> None:
        self.execution_path = trace
        self.code = code
        self.item = item


    async def interact(self, interaction: discord.Interaction) -> None:
        args = {}
        for obj in [self.item, interaction]:
            for key in dir(obj):
                if key.startswith("_"): continue
                args[key] = getattr(obj, key)
        
        await run_code(
            "on interaction",
            interaction.channel,
            interaction.user,
            interaction.guild,
            self.code,
            self.execution_path,
            args
        )

        if not interaction.response.is_done():
            await interaction.response.send_message("Done.", ephemeral=True)





class VeiwGenerator:
    view: discord.ui.View = None
    trace: str = ""
    channel: discord.TextChannel = None
    user: discord.Member | discord.User = None
    guild: discord.Guild = None


    def __init__(self, func: Function) -> None:
        self.view = discord.ui.View(timeout=None)
        self.trace = func.execution_path
        self.channel = func.channel
        self.guild = func.guild
        self.user = func.user
    
    def is_valid(self) -> bool:
        return len(self.view.children) > 0


    def add_select(self, data: dict | list, trace: str = "") -> None:
        select = discord.ui.Select()
        if not trace: trace = self.trace

        if isinstance(data, list): data = {"options": data}
        if not isinstance(data, dict): raise TypeError("Select must be a list of options or a dictionary.")
        if "options" not in data: raise SyntaxError(f"Select does not have any options.\nTrace: {trace}")
        if not isinstance(data["options"], list): raise TypeError(f"Options must be a list of options.\nTrace: {trace}")

        for index, option in enumerate(data["options"]):
            if isinstance(option, str):
                select.add_option(label=option)
                continue

            if not isinstance(option, dict):
                raise TypeError(f"Select option must be dictionary or string.\nTrace: {trace} -> option {index}")

            args = {}
            for key in ["label", "value", "description", "emoji", "default"]:
                if key in option:
                    args[key] = option[key]

            select.add_option(**args)
        
        for param in ["placeholder", "min values", "max values"]:
            alt_param = param.replace(" ", "_")
            value = None
            if alt_param != param and alt_param in data:
                value = data[alt_param]
            elif param in data:
                value = data[param]
            else: continue

            if alt_param == "max_values": value = min(value, len(data["options"]))
            setattr(select, alt_param, value)
        
        interaction = Interaction(select, data, trace)
        select.callback = interaction.interact
        interactions.append(interaction)

        self.view.add_item(select)














# Not sure if this should be in a class
async def run_code(code_path: str, channel: discord.TextChannel = None, user: discord.Member | discord.User = None, guild: discord.Guild = None, lookup=None, trace="", extra_data:dict={}) -> None:
    if not lookup: lookup = yaml
    
    for code_path_variant in [code_path, code_path.replace(" ", "_")]:
        if code_path_variant not in lookup: continue

        raw_code = lookup[code_path_variant]
        if isinstance(raw_code, dict): raw_code = [raw_code]

        functions: dict[str, int] = {}

        for raw_function in raw_code:
            func = Function(raw_function, channel, user, guild, trace + code_path)
            if func.function_name in functions:
                functions[func.function_name] += 1
                func.execution_path += " " + str(functions[func.function_name])
            else: functions[func.function_name] = 1

            func.additional_variables = extra_data.copy()
            await func.execute()
        break




async def check_timers() -> None:
    executed_timers: list[dict] = []
    
    for timer in save_data.get_timers():
        if datetime.fromisoformat(timer["time"]) <= utcnow():
            executed_timers.append(timer)

            func = Function()
            user = await func.get_user(timer.get("user"))
            server = await func.get_server(timer.get("guild"))
            channel = await func.get_channel(timer.get("channel"))

            await run_code("do", channel, user, server, timer, timer["func"] + " -> ")
    
    save_data.remove_timers(executed_timers)





@client.event
async def on_ready() -> None:
    await run_code("on connected")
    start_loop()

@client.event
async def on_message(message: discord.Message) -> None:
    if message.author == client.user: return
    await run_code("on message", message.channel, message.author, message.channel.guild)

@client.event
async def on_member_join(member: discord.Member) -> None:
    await run_code("on user joined", None, member, member.guild)

@client.event
async def on_member_remove(member: discord.Member) -> None:
    await run_code("on user left", None, member, member.guild)

@tasks.loop(minutes=1)
async def main_loop() -> None:
    if "loop" not in yaml: return
    await run_code("do", lookup=yaml["loop"], trace="loop -> ")
    await check_timers()


def start_loop() -> None:
    if "loop" not in yaml: return

    for key in ["time", "interval", "every", "wait", "delay"]:
        if key not in yaml["loop"]: continue
        td = string_to_timedelta(yaml["loop"][key])
        main_loop.change_interval(seconds=td.total_seconds())
        break

    main_loop.start()


client.run(TOKEN)


