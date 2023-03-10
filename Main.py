import discord, os, glob, re, json, logging
from typing import Any
from discord.ext import tasks
from dotenv import load_dotenv
from ruamel.yaml import YAML, constructor
from datetime import datetime, timedelta, timezone
import emoji as emojilib


logging.basicConfig(filename="bot.log", encoding="utf-8", format="%(asctime)s - %(levelname)s: %(message)s", level=logging.DEBUG)
logging.info("Startup")


def utcnow() -> datetime:
    logging.debug("Retreived UTC time")
    return datetime.now(timezone.utc)

def format_timedelta(td: timedelta, smallest_unit="s") -> str:
    result = str(td)
    match smallest_unit:
        case "s": result = re.sub(r"\.\d+", "", str(td))
        case "m": result = re.sub(r":\d+\.\d+", "", str(td))
        case "h": result = re.sub(r":\d+:\d+\.\d+", "", str(td))
    logging.debug("Converted timedelta to string with '%s' as the smallest unit: %s", smallest_unit, result)
    return result


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
    
    result = timedelta(
        weeks=w,
        days=d,
        hours=h,
        minutes=m,
        seconds=s
    )

    logging.debug("Converted string to timedelta: '%s' -> %s", string, result)
    return result

# https://discord.com/developers/docs/reference#message-formatting-timestamp-styles
def timestamp(dt: datetime, mode: str = "") -> str:
    result: str = ""
    if not mode: result = f"<t:{int(dt.timestamp())}>"
    else: result = f"<t:{int(dt.timestamp())}:{mode}>"
    logging.debug("Converted datetime to timestamp: %s -> %s", dt, result)
    return result

# ---------- Load Token ---------- #

load_dotenv()
TOKEN = os.getenv("TOKEN")





# ---------- Load YAML ---------- #

yaml_files: list[str] = []

for pattern in ["*.yml", "*.yaml"]:
    yaml_files += glob.glob(pattern)

if yaml_files:
    logging.info("Found the following YAML files: %s", yaml_files)
else:
    logging.critical("Could not find any YAML files")
    raise FileNotFoundError("Could not find any YAML files.")

for path in yaml_files:
    logging.info("Trying to load: %s", path)
    try:
        with open(path, encoding="utf8") as f:
            yaml = YAML(typ="safe").load(f)
    except constructor.DuplicateKeyError: # Top notch error handling
        logging.critical("YAML contains duplicate keys")
        raise constructor.DuplicateKeyError("Duplicate keys are not supported.")
    except Exception as e:
        logging.critical(e)
        raise e
    
    if yaml:
        logging.info("Loaded: %s", path)
        break

# I feel like errors have so much more to offer while Im just using them to print a message...
if not yaml:
    logging.critical("YAML is empty")
    raise SyntaxError("YAML file is empty.")
if not isinstance(yaml, dict):
    logging.critical("YAML is not a dictionary")
    raise TypeError("YAML is not a dictionary.")

print(f"Executing {path}")
logging.info("Executing: %s", path)






# ---------- Assign Intents ---------- #

intents = discord.Intents.default()

if "intents" in yaml:
    logging.info("Setting intents")
    if not isinstance(yaml["intents"], list):
        logging.critical("Intents are of type '%s' and not 'list'", type(yaml["intents"]))
        raise TypeError("Intents must be a list of strings.")

    for intent in yaml["intents"]:
        logging.info("Enabling intent: %s", intent)
        if not isinstance(intent, str):
            logging.critical("Intent is not string")
            raise TypeError("Intents must be string values")
        if not hasattr(intents, intent):
            logging.critical("Intent is invalid")
            raise ValueError(f"'{intent}' is not a valid intent.")
        exec(f"intents.{intent} = True")
    logging.info("Finished setting intents")
else: logging.info("YAML does not contain intents")

client = discord.Client(intents=intents)






# ---------- Create Variables ---------- #

yaml_variables: list[str] = []

if "variables" in yaml:
    logging.info("Assigning variables")
    for var in yaml["variables"]:
        logging.info("Assiging: %s", var)
        if not isinstance(var, str):
            logging.critical("Variable is not a string")
            raise SyntaxError("Variable names must be string.")
        if not re.fullmatch(r"[A-z_][A-z0-9_]*", var):
            logging.critical("Invalid variable name")
            raise SyntaxError(f"'{var}' is not a valid variable name. It can only contain letters, numbers and underscores. It cannot start with a number.")
        
        yaml_variables.append(var)
        logging.info("Value: %s", repr(yaml["variables"][var]))
        exec(f'{var} = {repr(yaml["variables"][var])}')
else: logging.info("YAML does not contain variables")





# ---------- Guild With More Stats ---------- #

# Guild has slots which makes it hard to extend, hopefully this works
class Guild(discord.Guild):
    def __init__(self, guild: discord.Guild) -> None:
        logging.debug("Converting discord.Guild to Guild: %s", guild)
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
        logging.info("Initialising the SaveHandler")
        self.path = path
        logging.info("Trying to load: %s", path)
        try:
            with open(path) as f:
                self.data = json.load(f)
        except Exception as e:
            logging.warn("Loading failed: %s", e)
            self.save()

    def save(self) -> None:
        logging.info("Saving: %s", self.path)
        logging.debug("Data: %s", self.data)
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=4)
        logging.debug("Saved")
    
    # I cant specify that func should be a Function because pyton has no forward declaration :(
    async def get_message(self, func) -> discord.Message:
        logging.info("Retreiving message: %s", func.execution_path if func else "None")
        if not func:
            logging.error("Invalid function")
            return None
        if "messages" not in self.data:
            logging.warn("Does not contain any messages")
            return None
        if func.execution_path not in self.data["messages"]: 
            logging.warn("Does not contain message: %s", func.execution_path)
            return None
        msg = self.data["messages"][func.execution_path]
        logging.debug("Found message: %s", msg)
        if "channel" not in msg:
            logging.error("Message does not contain a channel")
            return None
        if "id" not in msg:
            logging.error("Message does not contain an ID")
            return None

        channel = await func.get_channel(msg["channel"])
        if not channel:
            logging.error("Could not find channel: %s", msg["channel"])
            return None

        try:
            message = await channel.fetch_message(msg["id"])
        except discord.NotFound:
            logging.error("Could not find message: %s", msg["id"])
            return None
        except Exception as e: logging.error(e)
        return message

    def save_msg(self, func) -> None:
        logging.info("Saving message: %s", func.execution_path if func else "None")
        if not func:
            logging.error("Invalid function")
            return
        if not hasattr(func, "msg"):
            logging.error("Function does not have message")
            return
        if not func.msg:
            logging.error("Invalid message")
            return            
        if "messages" not in self.data:
            logging.debug("Created a dictionary for messages in data")
            self.data["messages"] = {}
        self.data["messages"][func.execution_path] = {
            "channel": func.msg.channel.id,
            "id": func.msg.id
        }
        self.save()

    def save_timer(self, func) -> None:
        logging.info("Saving timer: %s", func.execution_path if func else "None")
        if not func:
            logging.error("Invalid function")
            return
        if not hasattr(func, "time"):
            logging.error("Function does not have time")
            return
        if not hasattr(func, "do"):
            logging.error("Timer does not have functions")
            return
        if not func.time:
            logging.error("Invalid time")
            return
        if "timers" not in self.data:
            logging.debug("Created a list for timers in data")
            self.data["timers"] = []

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
        logging.log("Removing timer: %s", execution_path)
        found = False
        for x in self.get_timers():
            if x["func"] == execution_path:
                found = True
                self.data["timers"].remove(x)
                logging.info("Removed timer")
                break
        if found: self.save()
        else: logging.warn("Could not find timer")

    def remove_timers(self, timers: list[dict]) -> None:
        logging.log("Removing timers: %s", [x.get("func") for x in timers])
        for x in timers:
            self.data["timers"].remove(x)
        self.save()


    def get_timers(self) -> list[dict]:
        value = self.data.get("timers", [])
        logging.debug("Retreiving timers: %s", value)
        return value









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
        logging.info("Initialising function: %s", execution_path)
        logging.debug("Raw function: %s", raw_function)
        logging.debug("Channel: %s", channel)
        logging.debug("User: %s", user)
        logging.debug("Guild: %s", guild)
        self.channel = None
        self.user = None
        self.guild = None
        self.raw_function = {}
        self.function_name = ""
        self.execution_path = ""
        self.additional_variables = {}
        
        if not raw_function:
            logging.error("Invalid Function")
            return
        if not isinstance(raw_function, dict):
            logging.error("Function is of type '%s' and 'dict'", type(raw_function))
            return
        self.channel = channel
        self.user = user
        if guild: self.guild = Guild(guild)
        elif isinstance(user, discord.Member):
            self.guild = Guild(user.guild)
            logging.debug("Assigned guild through user: %s", user.guild)
        self.raw_function = raw_function
        self.function_name = list(raw_function.keys())[0]
        self.execution_path = execution_path + " -> " + self.function_name
        self.assign_type(self.function_name)

    def assign_type(self, function_name: str) -> bool:
        logging.debug("Assigning function type: %s", function_name)
        match function_name.lower().replace(" ", "_"):
            case "add_role" | "add_roles": self.__class__ = FunctionAddRoles
            case "remove_role" | "remove_roles": self.__class__ = FunctionRemoveRoles
            case "set_variable" | "set_variables": self.__class__ = FunctionSetVariable
            case "update_roles": self.__class__ = FunctionUpdateRoles
            case "update_message": self.__class__ = FunctionUpdateMessage
            case "send_message": self.__class__ = FunctionSendMessage
            case "response": self.__class__ = FunctionResponseMessage
            case "wait": self.__class__ = FunctionWait
            case "condition": self.__class__ = FunctionCondition
            case _:
                logging.error("Invalid function: %s", function_name)
                return False
        logging.debug("Assigned type: %s", self.__class__)
        return True

    # virtual
    async def find_arguments(self, arguments) -> None:
        logging.debug("Assigning arguments: %s", arguments)

    # virtual
    async def execute(self) -> bool:
        logging.info("Executing: %s", self.execution_path)
        await self.find_arguments(self.raw_function[self.function_name])
        return False

    async def get_user(self, id: int | str) -> discord.Member | discord.User:
        logging.info("Rerieving user: %s", id)
        if not id:
            logging.warn("No ID")
            return None

        if isinstance(id, str):
            var = id.replace(" ", "_")
            if var in yaml_variables:
                logging.debug("Resolving variable")
                return await self.get_user(eval(var))
            if id.startswith("@"): id = id[1:]

        if self.guild:
            logging.debug("Checking guild members")
            if isinstance(id, int):
                user = self.guild.get_member(id)
                if not user: user = await self.guild.fetch_member(id)
                return user
            
            elif not isinstance(id, str):
                logging.error("User is not int or string")
                return None
            
            if id.lower() == "user":
                logging.debug("Returning self.user")
                return self.user

            return self.guild.get_member_named(id)

        else:
            if isinstance(id, int):
                user = client.get_user(id)
                if not user: user = await client.fetch_user(id)
                return user
            
            elif not isinstance(id, str):
                logging.error("User is not int or string")
                return

            for user in client.users:
                if str(user) == id: return user
                if user.name == id: return user
            
            for user in client.get_all_members():
                if str(user) == id: return user
                if user.name == id: return user
                if user.nick == id: return user

    def get_role(self, id: int | str) -> discord.Role:
        logging.info("Rerieving role: %s", id)
        if not id:
            logging.warn("No ID")
            return None

        if isinstance(id, str):
            var = id.replace(" ", "_")
            if var in yaml_variables:
                logging.debug("Resolving variable")
                return self.get_role(eval(var))
            if id.startswith("@"): id = id[1:]
        
        if not self.guild:
            logging.warn("Does not have guild")
            if self.user:
                logging.debug("Checking mutual guilds")
                for guild in self.user.mutual_guilds:
                    if isinstance(id, int):
                        role = guild.get_role(id)
                        if role:
                            logging.debug("Found role")
                            return role
                    for role in guild.roles:
                        if role.name == id:
                            logging.debug("Found role")
                            return role
                
                logging.warn("Could not find role")
                return None
            else:
                logging.warn("Does not have guild or user")
                return None
            

        if isinstance(id, int):
            role = self.guild.get_role(id)
            if role: logging.debug("Found role")
            else: logging.warn("Could not find role")
            return role

        for role in self.guild.roles:
            if role.name == id:
                logging.debug("Found role")
                return role

        logging.warn("Could not find role")
        return None

    async def get_channel(self, id: int | str):
        logging.info("Rerieving channel: %s", id)
        if not id:
            logging.warn("No ID")
            return None

        if isinstance(id, int):
            channel = client.get_channel(id)
            if channel: return channel
            channel = await client.fetch_channel(id)
            return channel

        if not isinstance(id, str):
            logging.error("Channel is not int or string")
            return None

        var = id.replace(" ", "_")
        if var in yaml_variables:
            logging.debug("Resolving variable")
            return await self.get_channel(eval(var))

        if id.startswith("#"): id = id[1:]

        for channel in client.get_all_channels():
            if channel.name == id: return channel
        
        logging.warn("Could not find channel")
        return None

    def get_colour(self, id: int | str) -> int:
        logging.info("Rerieving colour: %s", id)
        if not id:
            logging.warn("No ID")
            return None
        if isinstance(id, int):
            logging.debug("Colour is int, returning as is")
            return id
        if id in yaml_variables:
            logging.debug("Resolving variable")
            return self.get_colour(eval(id))
        
        logging.warn("Could not find colour")
        return None

    def get_emoji(self, id: int | str) -> discord.Emoji | str:
        logging.info("Rerieving emoji: %s", id)
        if not id:
            logging.warn("No ID")
            return None
        emoji = None

        if isinstance(id, str):
            if emojilib.is_emoji(id):
                logging.debug("Emoji is native, returning as is")
                return id
            name = re.match(r":(.+):", id)
            if name: id = name.group(1)

        guilds = [self.guild]
        guilds += client.guilds

        for guild in guilds:
            if not guild: continue
            if isinstance(id, int):
                emoji = discord.utils.get(guild.emojis, id=id)
            elif isinstance(id, str):        
                emoji = discord.utils.get(guild.emojis, name=id)
            else: break
            if emoji: return emoji

        logging.warn("Could not find emoji")
        return None


    async def get_server(self, id: int | str) -> Guild:
        logging.info("Rerieving server: %s", id)
        if not id:
            logging.warn("No ID")
            return None

        if isinstance(id, int):
            server = client.get_guild(id)
            if server: return Guild(server)
            server = await client.fetch_guild(id)
            if server: return Guild(server)
            logging.warn("Could not find server")
            return None

        if not isinstance(id, str):
            logging.warn("Server is not int or string")
            return None
        
        if id in yaml_variables:
            logging.debug("Resolving variable")
            return await self.get_server(eval(id))

        for server in client.guilds:
            if server.name == id: return Guild(server)
        
        logging.warn("Could not find server")
        return None

    def evaluate(self, _string: str, **kwargs) -> Any:
        logging.info("Evaluating: %s", _string)
        if not _string:
            logging.warn("Nothing to evaluate")
            return _string

        for _key in self.additional_variables:
            exec(f"{_key} = self.additional_variables[{repr(_key)}]")

        for _key in self.__dict__:
            if _key == "additional_variables": continue
            exec(f"{_key} = self.{_key}")
        
        for _key in kwargs:
            exec(f"{_key} = {repr(kwargs[_key])}")

        try:
            result = eval(_string)
            logging.info("Evaluated: %s", result)
            return result
        except Exception as e:
            logging.error(e)
            return None

    def evaluate_string(self, _string: str) -> str:
        logging.info("Evaluating as string: %s", _string)
        if not _string:
            logging.warn("Nothing to evaluate")
            return _string

        for _dictionary in [self.__dict__, self.additional_variables]:
            for _key in _dictionary:
                exec(f"{_key} = self.{_key}")
        
        try:
            result = eval(f"f{repr(_string)}")
            logging.info("Evaluated: %s", result)
            return result
        except Exception as e:
            logging.error(e)
            return ""

    def evaluate_condition(self, condition: dict) -> dict:
        logging.info("Evaluating condition: %s", condition.get("if"))
        if self.evaluate(condition.get("if")):
            logging.info("True")
            logging.debug("Data: %s", condition.get("do"))
            return condition.get("do", {"?":{}})
        logging.info("False")
        logging.debug("Data: %s", condition.get("else"))
        return condition.get("else", {"?":{}})

    async def aexec(self, code: str) -> None:
        logging.info("Async execution: %s", code)
        try:
            # Make an async function with the code and `exec` it
            exec(
                'async def __exec(self):\n' +
                ''.join(f'\n {l}' for l in code.split('\n'))
            )
            await locals()["__exec"](self)
        except Exception as e:
            logging.error(e)


    async def refresh(self) -> None:
        logging.info("Refresing function: %s", self.execution_path)
        if self.guild:
            logging.debug("Refresing guild: %s", self.guild)
            self.guild = await self.get_server(self.guild.id)
        if self.channel:
            logging.debug("Refresing channel: %s", self.channel)
            self.channel = await self.get_channel(self.channel.id)
        if self.user:
            logging.debug("Refresing user: %s", self.user)
            self.user = await self.get_user(self.user.id)


class FunctionCondition(Function):
    async def execute(self) -> bool:
        await super().execute()
        code = self.evaluate_condition(self.raw_function[self.function_name])
        await run_code("do", self.channel, self.user, self.guild, {"do": code}, self.execution_path + " -> ", self.additional_variables)
        


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
                try:
                    value = int(value)
                except:
                    role = self.get_role(value)
                    if role:
                        self.roles.append(role)
                        continue
                    value = self.evaluate(value)

            if isinstance(value, list):
                for role_id in value:
                    try:
                        role_id = int(role_id)
                    except: pass
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
                try:
                    value = int(value)
                except:
                    role = self.get_role(value)
                    if role:
                        exec(f"self.{key}.append(role)")
                        continue
                    value = self.evaluate(value)

            if isinstance(value, list):
                for role_id in value:
                    try:
                        role_id = int(role_id)
                    except: pass
                    role = self.get_role(role_id)
                    if role: exec(f"self.{key}.append(role)")
            else:
                role = self.get_role(value)
                if role: exec(f"self.{key}.append(role)")
        
        self.reason = arguments.get("reason", None)

    async def execute(self) -> bool:
        await super().execute()
        if not self.target: return False

        remove_roles: set[discord.Role] = set(self.remove) - set(self.add)
        remove_roles.intersection_update(self.target.roles)
        add_roles: set[discord.Role] = set(self.add) - set(self.target.roles)

        if remove_roles:
            await self.target.remove_roles(*remove_roles, reason=self.reason)
        if add_roles:
            await self.target.add_roles(*add_roles, reason=self.reason)
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
    has_condition: bool = False

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
    
    def get_edit_args(self) -> dict:
        args = {}
        if self.file: args["attachments"] = self.file
        elif self.files: args["attachments"] = self.files

        for key in ["content", "embed", "embeds", "view", "delete_after", "allowed_mentions"]:
            if key == "embeds" and "embed" in args: continue
            value = getattr(self, key)
            if value: args[key] = value

        return args

    async def edit(self):
        if not self.msg: return
        self.msg = await self.msg.edit(**self.get_edit_args())

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
        self.has_condition = False

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
            if item and isinstance(item, dict) and "condition" in item:
                item = self.evaluate_condition(item["condition"])
                self.has_condition = True
            
            if not item: continue
            if not isinstance(item, dict): raise TypeError(f"Message content must be dictionaries.\nTrace: {self.execution_path} -> content -> ?\n{item}")

            content_name = str(list(item.keys())[0])
            content_type = content_name.lower().replace(" ", "_")
            trace = self.execution_path + " -> content -> " + content_name

            if content_type not in content_count: content_count[content_type] = 1
            else:
                content_count[content_type] += 1
                trace += " " + str(content_count[content_name])


            match content_type:
                case "text": self.content = self.evaluate_string(item["text"])
                case "embed": self.embeds.append(self.create_embed(item["embed"], trace))
                case "select": view.add_select(item[content_name], trace)
                case "button": view.add_button(item[content_name], trace)
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
        
        if "thumbnail" in data:
            new_embed.set_thumbnail(url=data["thumbnail"])

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
    followup: discord.Webhook = None

    async def find_arguments(self, arguments) -> None:
        self.ephemeral = True
        self.response = None
        self.followup = None

        await super().find_arguments(arguments)
        self.delete_after = 15
        
        self.response = self.additional_variables.get("response")
        self.followup = self.additional_variables.get("followup")
        if not isinstance(arguments, dict): return

        self.ephemeral = arguments.get("ephemeral", True)
        self.delete_after = arguments.get("delete_after", self.delete_after)
        self.delete_after = arguments.get("delete after", self.delete_after)

    async def execute(self) -> bool:
        await super().execute()
        if not self.channel: return False
        
        use_response = self.response and not self.response.is_done()
        if not use_response and not self.followup: return False

        args = {
            "tts": self.tts,
            "allowed_mentions": self.allowed_mentions,
            "suppress_embeds": self.suppress_embeds,
            "silent": self.silent,
            "ephemeral": self.ephemeral
        }

        if use_response: args["delete_after"] = self.delete_after
        if self.file: args["file"] = self.file
        elif self.files: args["files"] = self.files
        if self.embed: args["embed"] = self.embed
        elif self.embeds: args["embeds"] = self.embeds
        if self.view: args["view"] = self.view

        if use_response: self.msg = await self.response.send_message(self.content, **args)
        else: self.msg = await self.followup.send(self.content, **args)
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
    func = None

    def __init__(self, item, code: dict, trace: str, func = None) -> None:
        logging.info("Listening to interaction: %s", trace)
        self.execution_path = trace
        self.code = code
        self.item = item
        self.func = func


    async def interact(self, interaction: discord.Interaction) -> None:
        logging.info("Interaction: %s", self.execution_path)
        logging.debug("User: %s", interaction.user)
        
        functions = self.code.get("on interaction", [])
        if not functions: functions = self.code.get("on_interaction", [])
        if not isinstance(functions, list):
            logging.error("On interaction is of type '%s' and not 'list'", type(functions))
            return

        if self.func: await self.func.refresh()

        defer = False
        for func in functions:
            for key in func:
                if key == "defer":
                    defer = True
                    break
            if defer: break
        
        if defer:
            logging.info("Response is deferred")
            await interaction.response.defer()
        
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


        if interaction.response.is_done():
            logging.debug("Interaction was responded to")
            return


        if interaction.is_expired():
            logging.error("Interaction expired")
            return
        
        if isinstance(self.func, FunctionMessage) and self.func.has_condition:
            logging.info("Responding to interaction by editing the message")
            await self.func.find_arguments(self.func.raw_function[self.func.function_name])
            await interaction.response.edit_message(**self.func.get_edit_args())
        else:
            logging.info("Interaction was not responded to, sending default response")
            await interaction.response.send_message("Done.", ephemeral=True)






class VeiwGenerator:
    view: discord.ui.View = None
    func: Function = None


    def __init__(self, func: Function) -> None:
        self.view = discord.ui.View(timeout=None)
        self.func = func
    
    def is_valid(self) -> bool:
        return len(self.view.children) > 0


    def add_select(self, data: dict | list, trace: str = "") -> None:
        select = discord.ui.Select()
        if not trace: trace = self.func.execution_path
        logging.info("Adding select: %s", trace)

        if isinstance(data, list): data = {"options": data}
        if not isinstance(data, dict):
            logging.error("Select is not a list of options or a dictionary")
            return
        if "options" not in data:
            logging.error("Select does not have options")
            return
        if not isinstance(data["options"], list):
            logging.error("Options is of type '%s' and not 'list'", type(data["options"]))
            return

        for index, option in enumerate(data["options"]):
            if isinstance(option, str):
                logging.debug("Adding option: %s", option)
                select.add_option(label=option)
                continue

            if not isinstance(option, dict):
                logging.error("Option is not string or dict: %s", option)
                continue

            args = {}
            for key in ["label", "value", "description", "emoji", "default"]:
                if key not in option: continue
                logging.debug("Adding '%s' to option", key)
                value = option[key]
                if key == "default" and isinstance(value, str):
                    value = self.func.evaluate(value, **args)
                args[key] = value

            if "emoji" in args:
                logging.debug("Resolving emoji")
                args["emoji"] = self.func.get_emoji(args["emoji"])
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
            logging.debug("Setting '%s': %s", alt_param, value)
            setattr(select, alt_param, value)
        
        interaction = Interaction(select, data, trace, self.func)
        select.callback = interaction.interact
        interactions.append(interaction)

        self.view.add_item(select)


    def add_button(self, data: dict, trace: str = "") -> None:
        button = discord.ui.Button()
        if not trace: trace = self.func.execution_path
        logging.info("Adding button: %s", trace)

        if not isinstance(data, dict):
            logging.error("Button is not a dictionary")
            return
        if "label" not in data:
            logging.error("Button does not have a label")
            return

        for param in ["disabled", "label", "row", "url", "custom id"]:
            alt_param = param.replace(" ", "_")
            value = None
            if alt_param in data:
                value = data[alt_param]
            elif param in data:
                value = data[param]
            else: continue

            logging.debug("Setting '%s': %s", alt_param, value)
            setattr(button, alt_param, value)

        if "style" in data:
            logging.debug("Retrieving style: %s", data["style"])
            try:
                exec(f"button.style = discord.ButtonStyle.{data['style']}")
            except Exception as e:
                logging.error(e)
        
        interaction = Interaction(button, data, trace, self.func)
        button.callback = interaction.interact
        interactions.append(interaction)

        self.view.add_item(button)













# Not sure if this should be in a class
async def run_code(code_path: str, channel: discord.TextChannel = None, user: discord.Member | discord.User = None, guild: discord.Guild = None, lookup=None, trace="", extra_data:dict={}) -> None:
    if not lookup: lookup = yaml
    
    for code_path_variant in [code_path, code_path.replace(" ", "_")]:
        if code_path_variant not in lookup: continue

        raw_code = lookup[code_path_variant]
        if isinstance(raw_code, dict): raw_code = [raw_code]
        if not raw_code: return

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
    logging.info("Checking timers")
    executed_timers: list[dict] = []
    for timer in save_data.get_timers():
        if datetime.fromisoformat(timer["time"]) <= utcnow():
            logging.info("Found expired timer: %s", timer["func"])
            logging.debug("Data: %s", timer)
            executed_timers.append(timer)

            func = Function()
            user = await func.get_user(timer.get("user"))
            server = await func.get_server(timer.get("guild"))
            channel = await func.get_channel(timer.get("channel"))

            await run_code("do", channel, user, server, timer, timer["func"] + " -> ")
    
    save_data.remove_timers(executed_timers)





@client.event
async def on_ready() -> None:
    if "on connected" not in yaml and "on_connected" not in yaml: return
    logging.info("Ready")
    await run_code("on connected")
    start_loop()

@client.event
async def on_message(message: discord.Message) -> None:
    if "on message" not in yaml and "on_message" not in yaml: return
    if message.author == client.user: return
    logging.info("Message received from: %s", message.author)
    logging.debug("Message content is not logged for privacy reasons")
    await run_code("on message", message.channel, message.author, message.channel.guild)

@client.event
async def on_member_join(member: discord.Member) -> None:
    if "on user joined" not in yaml and "on_user_joined" not in yaml: return
    logging.info("User joined '%s': %s", member.guild.name, member)
    await run_code("on user joined", None, member, member.guild)

@client.event
async def on_member_remove(member: discord.Member) -> None:
    if "on user left" not in yaml and "on_user_left" not in yaml: return
    logging.info("User removed from '%s': %s", member.guild.name, member)
    await run_code("on user left", None, member, member.guild)

@tasks.loop(minutes=1)
async def main_loop() -> None:
    if "loop" not in yaml: return
    logging.info("Executing loop functions")
    await run_code("do", lookup=yaml["loop"], trace="loop -> ")
    await check_timers()


def start_loop() -> None:
    if "loop" not in yaml: return

    for key in ["time", "interval", "every", "wait", "delay"]:
        if key not in yaml["loop"]: continue
        logging.info("Found '%s' for loop", key)
        td = string_to_timedelta(yaml["loop"][key])
        main_loop.change_interval(seconds=td.total_seconds())
        logging.info("Changed loop interval seconds: %s", td.total_seconds())
        break

    logging.info("Starting loop")
    main_loop.start()





@client.event
async def on_connect(): logging.log("Connected")

@client.event
async def on_disconnect(): logging.log("Disonnected")

@client.event
async def on_resumed(): logging.log("Resumed")


logging.info("Starting client")
client.run(TOKEN)


