from http.client import RemoteDisconnected
from typing import List

import click
from click import Choice
from plexapi.exceptions import Unauthorized
from plexapi.myplex import MyPlexAccount, MyPlexResource
from plexapi.server import PlexServer
from urllib3.exceptions import ConnectTimeoutError

from plex_trakt_sync.config import CONFIG

PROMPT_PLEX_PASSWORD = click.style("Please enter your Plex password", fg="yellow")
PROMPT_PLEX_USERNAME = click.style("Please enter your Plex username", fg="yellow")
PROMPT_PLEX_RELOGIN = click.style("You already logged in to Plex, do you want to log in again?", fg="yellow")
PROMPT_MANAGED_USER = click.style("Do you want to use managed user instead of main account?", fg="yellow")


def myplex_login(username, password):
    while True:
        username = click.prompt(PROMPT_PLEX_USERNAME, type=str, default=username)
        password = click.prompt(PROMPT_PLEX_PASSWORD, type=str, default=password, hide_input=True, show_default=False)
        try:
            return MyPlexAccount(username, password)
        except Unauthorized as e:
            click.secho(f"Logging failed: {e} Try again.", fg="red")


def choose_managed_user(account: MyPlexAccount):
    users = [u.title for u in account.users() if u.friend]
    if not users:
        return None

    click.secho("Managed user(s) found:", fg="green")
    users = sorted(users)
    for user in users:
        click.echo(f"- {user}")

    if not click.confirm(PROMPT_MANAGED_USER):
        return None

    # choice = prompt_choice(users)
    user = click.prompt(
        click.style("Please select:", fg="yellow"),
        type=Choice(users),
        show_default=True,
    )

    # Sanity check, even the user can't input invalid user
    user_account = account.user(user)
    if user_account:
        return user

    return None


def prompt_server(servers: List[MyPlexResource]):
    def fmt_server(s):
        return f"- {s.name}: [Last seen: {s.lastSeenAt}, {s.product}/{s.productVersion} on {s.device}: {s.platform}/{s.platformVersion}]"

    owned_servers = [s for s in servers if s.owned]
    unowned_servers = [s for s in servers if not s.owned]

    server_names = []
    if owned_servers:
        click.secho(f"{len(owned_servers)} owned servers found:", fg="green")
        for s in owned_servers:
            click.echo(fmt_server(s))
            server_names.append(s.name)
    if unowned_servers:
        click.secho(f"{len(owned_servers)} unowned servers found:", fg="green")
        for s in unowned_servers:
            click.echo(fmt_server(s))
            server_names.append(s.name)

    return click.prompt(
        click.style("Select default server:", fg="yellow"),
        type=Choice(server_names),
        show_default=True,
    )


def pick_server(account: MyPlexAccount):
    servers = account.resources()
    if not servers:
        return None

    if len(servers) == 1:
        return servers[0]

    server_name = prompt_server(servers)

    # Sanity check, even the user can't choose invalid resource
    server = account.resource(server_name)
    if server:
        return server

    return None


def choose_server(account: MyPlexAccount):
    while True:
        try:
            server = pick_server(account)
            # Connect to obtain baseUrl
            click.secho(f"Attempting to connect to {server.name}. This may take time and emit some errors.", fg="yellow")
            plex = server.connect()
            # Validate connection again, the way we connect
            plex = PlexServer(token=server.accessToken, baseurl=plex._baseurl)
            return [server, plex]
        except (ConnectTimeoutError, RemoteDisconnected, Exception) as e:
            click.secho(f"{e}, Try another server, {type(e)}")


@click.command()
@click.option("--username", help="Plex login", default=CONFIG["PLEX_USERNAME"])
@click.option("--password", help="Plex password")
def plex_login(username, password):
    """
    Log in to Plex Account
    """

    if CONFIG["PLEX_TOKEN"]:
        if not click.confirm(PROMPT_PLEX_RELOGIN, default=True):
            return

    account = myplex_login(username, password)
    click.secho("Login to MyPlex success!", fg="green")

    [server, plex] = choose_server(account)
    click.secho(f"Connection to {plex.friendlyName} established successfully!", fg="green")

    token = server.accessToken
    user = username
    if server.owned:
        managed_user = choose_managed_user(account)
        if managed_user:
            user = managed_user
            token = account.user(managed_user).get_token(plex.machineIdentifier)

    print(f"User={user}, token={token}, {plex._baseurl}")
