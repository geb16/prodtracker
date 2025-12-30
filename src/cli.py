# pathfile src/cli.py
import typer
import uvicorn

# from prodtracker import agent
from prodtracker.api.server import app

# Explain typer CLI
# Typer is a library for building command-line interface (CLI) applications
# with a focus on ease of use, and automatic generation of help and completion options.
#  @cli.command() decorates functions to create CLI commands.
# with the use cli() we can run simple commands from terminal like:
# python src/cli.py start-agent instead of writing complex scripts like python -m prodtracker.agent.

cli = typer.Typer()


@cli.command()
def start_agent():
    print("Agent functionality is currently disabled.")


@cli.command()
def start_api():
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    cli()

# to run the api use the command:
# python src/cli.py start-api
