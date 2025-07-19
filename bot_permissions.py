import bot_response as br
import discord

def make_permissions_list(perms: discord.Permissions) -> str:
    perms_list = [name for name, value in perms if value]
    return ", ".join(perms_list).replace("_", " ").title()

def make_lacking_perms_response(command_name: str, user_name: str, perms_needed: discord.Permissions) -> br.Response:
    return br.Response(
        is_error = True,
        title="Lacking permissions!",
        txt=f"You (`{user_name}`) lack permissions to use {command_name}.\nRequired permissions are: {make_permissions_list(perms_needed)}",
    )

EDIT_REMINDERS = discord.Permissions(
    manage_messages = True
)
def make_admin():
    admin = discord.Permissions()
    for name, _ in admin:
        setattr(admin, name, True)
    return admin
ADMIN = make_admin()