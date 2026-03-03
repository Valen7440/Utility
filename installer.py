# TODO: Credits to [Caylies](https://github.com/Caylies) for the original code!
import base64
import aiohttp
import enum
import os
from packaging.version import parse as parse_version

from ballsdex import __version__

SUPPORTED_VERSION_AT = "2.29.5"

if parse_version(__version__) < parse_version(SUPPORTED_VERSION_AT):
    raise Exception(
        f"Unsupported ballsdex version (Actual Version: {__version__}) "
        f"Version > 2.29.5 is required."
    )

class ModelType(enum.IntEnum):
    TORTOISE = 1
    DJANGO = 2

GITHUB = "Valen7440/Utility/contents/"
PACKAGE_PATH = "ballsdex/packages/utility"
PACKAGE_FILES = [
    "__init__.py", 
    "cog.py",
    "components.py"
]
TORTOISE_MODELS = ["broadcast_models.py"]
DJANGO_APP_FILES = {
    "broadcast_app": [
        "__init__.py", 
        "apps.py", 
        "models.py", 
        "migrations/__init__.py", 
        "migrations/0001_initial.py"
    ],
}

os.makedirs("ballsdex/packages/utility", exist_ok=True)

async def fetch_github_file(session: aiohttp.ClientSession, url: str):
    async with session.get(url) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Failed to fetch {url} ({resp.status})")
        data = await resp.json()
        return data

async def add_package(package: str):
    """
    Adds a package to the config.yml file.

    Parameters
    ----------
    package: str
        The package you want to append to the config.yml file.
    """
    with open("config.yml", "r") as file:
        lines = file.readlines()

    item = f"  - {package}\n"

    if "packages:\n" not in lines or item in lines:
        return

    for i, line in enumerate(lines):
        if line.rstrip().startswith("packages:"):
            lines.insert(i + 1, item)
            break

    with open("config.yml", "w") as file:
        file.writelines(lines)

    await ctx.send("Added package to config file")

async def add_model(model: str, model_type: ModelType):
    """
    Adds a model to the config.yml file.

    Parameters
    ---------
    model: str
        The model you want to append to the config.yml file
    model_type: ModelType
        If model is a Tortoise model or Django App.
    """
    with open("config.yml", "r") as file:
        lines = file.readlines()

    item = f"  - {model}\n"
    key = "extra-tortoise-models:" if model_type == ModelType.TORTOISE else "extra-django-apps:"

    for i, line in enumerate(lines):
        if line.rstrip().startswith(key):
            lines.insert(i + 1, item)
            break

    with open("config.yml", "w") as file:
        file.writelines(lines)

    model_name = model_type.name.lower()
    await ctx.send(f"Added {model_name} {"model" if model_name == "tortoise" else "app"} to config file")

async def install_package_files():
    """
    Installs and updates files from the GitHub page.
    """
    files = PACKAGE_FILES.copy()
    if os.path.isfile(f"{PACKAGE_PATH}/config.toml"):
        files.pop(files.index("config.toml"))
        await ctx.send("-# `config.toml` file already found. Skipping it.")

    progress_message = await ctx.send(
        f"Installing package files: 0% (0/{len(files)})"
    )

    log = []
    async with aiohttp.ClientSession() as session:
        for index, file in enumerate(files):
            data = await fetch_github_file(session, f"https://api.github.com/repos/{GITHUB}/utility/{file}")

            remote_content = base64.b64decode(data["content"]).decode("UTF-8")
            local_file_path = f"{PACKAGE_PATH}/{file}"

            with open(local_file_path, "w") as opened_file:
                opened_file.write(remote_content)

            log.append(f"-# Installed `{file}`")

            percentage = round((index + 1) / len(files) * 100)

            await progress_message.edit(
                content=(
                    f"Installing package files: {percentage}% ({index + 1}/{len(files)})"
                    f"\n{'\n'.join(log)}"
                )
            )

            await asyncio.sleep(1)

async def install_tortoise_models():
    """
    Installs and updates files from the GitHub page.
    """
    progress_message = await ctx.send(
        f"Installing tortoise models: 0% (0/{len(TORTOISE_MODELS)})"
    )

    log = []

    async with aiohttp.ClientSession() as session:
        for index, file in enumerate(TORTOISE_MODELS):
            data = await fetch_github_file(session, f"https://api.github.com/repos/{GITHUB}/{file}")

            remote_content = base64.b64decode(data["content"]).decode("UTF-8")
            local_file_path = f"ballsdex/core/{file}"
            with open(local_file_path, "w") as opened_file:
                opened_file.write(remote_content)

            log.append(f"-# Installed `{file}`")

            percentage = round((index + 1) / len(TORTOISE_MODELS) * 100)

            await progress_message.edit(
                content=(
                    f"Installing tortoise models: {percentage}% ({index + 1}/{len(TORTOISE_MODELS)})"
                    f"\n{'\n'.join(log)}"
                )
            )

            await asyncio.sleep(1)

async def install_django_app_files(app_name: str):
    """
    Installs and updates files from the GitHub page.
    """
    files = DJANGO_APP_FILES.get(app_name, [])
    progress_message = await ctx.send(
        f"Installing {app_name} files: 0% (0/{len(files)})"
    )

    log = []

    async with aiohttp.ClientSession() as session:
        for index, file in enumerate(files):
            data = await fetch_github_file(session, f"https://api.github.com/repos/{GITHUB}/{app_name}/{file}")

            remote_content = base64.b64decode(data["content"]).decode("UTF-8")
            local_file_path = f"admin_panel/{app_name}/{file}"

            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

            with open(local_file_path, "w") as opened_file:
                opened_file.write(remote_content)

            log.append(f"-# Installed `{file}`")

            percentage = round((index + 1) / len(files) * 100)

            await progress_message.edit(
                content=(
                    f"Installing {app_name} files: {percentage}% ({index + 1}/{len(files)})"
                    f"\n{'\n'.join(log)}"
                )
            )

            await asyncio.sleep(1)

await install_tortoise_models()
await install_django_app_files("broadcast_app")
await install_package_files()
await add_package(PACKAGE_PATH.replace("/", "."))
await add_model("ballsdex.core.broadcast_models", ModelType.TORTOISE)
await add_model("broadcast_app", ModelType.DJANGO)

await ctx.send("Reloading commands...")

try:
    await bot.reload_extension(PACKAGE_PATH.replace("/", "."))
except commands.ExtensionNotLoaded:
    await bot.load_extension(PACKAGE_PATH.replace("/", "."))

await bot.tree.sync()

await ctx.send("Finished installing/updating everything!")