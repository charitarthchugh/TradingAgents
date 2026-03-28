import os
import questionary
from typing import List, Optional, Tuple, Dict

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from cli.models import AnalystType
from tradingagents.llm_clients.model_catalog import get_model_options

console = Console()


def query_available_models(base_url: str, api_key: Optional[str] = None) -> List[str]:
    """Query available models from an OpenAI-compatible endpoint.

    Args:
        base_url: The base URL of the API endpoint
        api_key: Optional API key for authentication

    Returns:
        List of model IDs available at the endpoint
    """
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{base_url.rstrip('/')}/models", headers=headers)
            response.raise_for_status()
            data = response.json()

            if "data" in data:
                return [model["id"] for model in data["data"]]
            elif "models" in data:
                return [model["id"] for model in data["models"]]
            elif isinstance(data, list):
                return [
                    model.get("id", model.get("name", str(model))) for model in data
                ]
            else:
                console.print(
                    "[yellow]Could not parse model list from endpoint[/yellow]"
                )
                return []
    except httpx.HTTPError as e:
        console.print(f"[yellow]Could not fetch models from endpoint: {e}[/yellow]")
        return []
    except Exception as e:
        console.print(f"[yellow]Error querying models: {e}[/yellow]")
        return []


def select_custom_endpoint() -> Tuple[str, Optional[str], Optional[str]]:
    """Prompt for custom OpenAI-compatible endpoint configuration.

    Returns:
        Tuple of (provider_name, base_url, api_key)
    """
    endpoint_env = os.environ.get("CUSTOM_LLM_ENDPOINT", "")
    api_key_env = os.environ.get("CUSTOM_LLM_API_KEY", "")

    endpoint = questionary.text(
        "Enter your custom OpenAI-compatible endpoint URL:",
        default=endpoint_env,
        validate=lambda x: len(x.strip()) > 0 or "Please enter a valid URL.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not endpoint:
        console.print("\n[red]No endpoint provided. Exiting...[/red]")
        exit(1)

    endpoint = endpoint.strip()

    use_api_key = questionary.confirm(
        "Do you want to set an API key for this endpoint?",
        default=bool(api_key_env),
    ).ask()

    api_key = None
    if use_api_key:
        api_key = questionary.password(
            "Enter API key (press Enter to leave empty):",
            default=api_key_env,
            style=questionary.Style(
                [
                    ("text", "fg:green"),
                    ("highlighted", "noinherit"),
                ]
            ),
        ).ask()
        if api_key == "":
            api_key = None

    return "Custom", endpoint, api_key


def select_model_interactive(models: List[str], model_type: str = "model") -> str:
    """Interactive model selection with search functionality.

    Args:
        models: List of available model IDs
        model_type: Description of model type ("deep-thinking" or "quick-thinking")

    Returns:
        Selected model ID
    """
    if not models:
        console.print(
            "[yellow]No models found at endpoint. Please enter model name manually.[/yellow]"
        )
        return enter_custom_model_name()

    display_models = models[:10]

    choices = [questionary.Choice(model, value=model) for model in display_models]
    choices.append(
        questionary.Choice("Search for a specific model...", value="__search__")
    )
    choices.append(questionary.Choice("Enter custom model name...", value="__custom__"))

    choice = questionary.select(
        f"Select Your {model_type.replace('-', ' ').title()} LLM Model:",
        choices=choices,
        instruction=f"\n- Showing {len(display_models)} of {len(models)} models\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]
        ),
    ).ask()

    if choice == "__search__":
        return search_and_select_model(models, model_type)
    elif choice == "__custom__":
        return enter_custom_model_name()
    return choice


def search_and_select_model(all_models: List[str], model_type: str = "model") -> str:
    """Search for a model by name filter.

    Args:
        all_models: List of all available model IDs
        model_type: Description of model type

    Returns:
        Selected model ID
    """
    search_term = questionary.text(
        "Search models (partial match):",
        validate=lambda x: len(x.strip()) > 0 or "Please enter a search term.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not search_term:
        return enter_custom_model_name()

    search_term = search_term.strip().lower()
    filtered_models = [m for m in all_models if search_term in m.lower()]

    if not filtered_models:
        console.print(f"[yellow]No models match '{search_term}'[/yellow]")
        return enter_custom_model_name()

    choices = [questionary.Choice(model, value=model) for model in filtered_models[:20]]
    choices.append(questionary.Choice("Enter custom model name...", value="__custom__"))

    choice = questionary.select(
        f"Search results for '{search_term}' ({len(filtered_models)} found):",
        choices=choices,
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]
        ),
    ).ask()

    if choice == "__custom__":
        return enter_custom_model_name()
    return choice


def enter_custom_model_name() -> str:
    """Prompt user to enter a custom model name."""
    model = questionary.text(
        "Enter custom model name:",
        validate=lambda x: len(x.strip()) > 0 or "Please enter a model name.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not model:
        console.print("\n[red]No model name provided. Exiting...[/red]")
        exit(1)

    return model.strip()


TICKER_INPUT_EXAMPLES = "Examples: SPY, CNC.TO, 7203.T, 0700.HK"

ANALYST_ORDER = [
    ("Market Analyst", AnalystType.MARKET),
    ("Social Media Analyst", AnalystType.SOCIAL),
    ("News Analyst", AnalystType.NEWS),
    ("Fundamentals Analyst", AnalystType.FUNDAMENTALS),
]


def get_ticker() -> str:
    """Prompt the user to enter a ticker symbol."""
    ticker = questionary.text(
        f"Enter the exact ticker symbol to analyze ({TICKER_INPUT_EXAMPLES}):",
        validate=lambda x: len(x.strip()) > 0 or "Please enter a valid ticker symbol.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not ticker:
        console.print("\n[red]No ticker symbol provided. Exiting...[/red]")
        exit(1)

    return normalize_ticker_symbol(ticker)


def normalize_ticker_symbol(ticker: str) -> str:
    """Normalize ticker input while preserving exchange suffixes."""
    return ticker.strip().upper()


def get_analysis_date() -> str:
    """Prompt the user to enter a date in YYYY-MM-DD format."""
    import re
    from datetime import datetime

    def validate_date(date_str: str) -> bool:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return False
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    date = questionary.text(
        "Enter the analysis date (YYYY-MM-DD):",
        validate=lambda x: (
            validate_date(x.strip())
            or "Please enter a valid date in YYYY-MM-DD format."
        ),
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not date:
        console.print("\n[red]No date provided. Exiting...[/red]")
        exit(1)

    return date.strip()


def select_analysts() -> List[AnalystType]:
    """Select analysts using an interactive checkbox."""
    choices = questionary.checkbox(
        "Select Your [Analysts Team]:",
        choices=[
            questionary.Choice(display, value=value) for display, value in ANALYST_ORDER
        ],
        instruction="\n- Press Space to select/unselect analysts\n- Press 'a' to select/unselect all\n- Press Enter when done",
        validate=lambda x: len(x) > 0 or "You must select at least one analyst.",
        style=questionary.Style(
            [
                ("checkbox-selected", "fg:green"),
                ("selected", "fg:green noinherit"),
                ("highlighted", "noinherit"),
                ("pointer", "noinherit"),
            ]
        ),
    ).ask()

    if not choices:
        console.print("\n[red]No analysts selected. Exiting...[/red]")
        exit(1)

    return choices


def select_research_depth() -> int:
    """Select research depth using an interactive selection."""

    # Define research depth options with their corresponding values
    DEPTH_OPTIONS = [
        ("Shallow - Quick research, few debate and strategy discussion rounds", 1),
        ("Medium - Middle ground, moderate debate rounds and strategy discussion", 3),
        ("Deep - Comprehensive research, in depth debate and strategy discussion", 5),
    ]

    choice = questionary.select(
        "Select Your [Research Depth]:",
        choices=[
            questionary.Choice(display, value=value) for display, value in DEPTH_OPTIONS
        ],
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:yellow noinherit"),
                ("highlighted", "fg:yellow noinherit"),
                ("pointer", "fg:yellow noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        console.print("\n[red]No research depth selected. Exiting...[/red]")
        exit(1)

    return choice


def select_shallow_thinking_agent(
    provider,
    endpoint_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """Select shallow thinking llm engine using an interactive selection."""

    if provider.lower() == "custom" and endpoint_url:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Fetching available models...", total=None)
            models = query_available_models(endpoint_url, api_key)

        if models:
            return select_model_interactive(models, "quick-thinking")
        else:
            console.print(
                "[yellow]Could not fetch models. Please enter manually.[/yellow]"
            )
            return enter_custom_model_name()

    choice = questionary.select(
        "Select Your [Quick-Thinking LLM Engine]:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in get_model_options(provider, "quick")
        ],
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        console.print(
            "\n[red]No shallow thinking llm engine selected. Exiting...[/red]"
        )
        exit(1)

    return choice


def select_deep_thinking_agent(
    provider,
    endpoint_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """Select deep thinking llm engine using an interactive selection."""

    if provider.lower() == "custom" and endpoint_url:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Fetching available models...", total=None)
            models = query_available_models(endpoint_url, api_key)

        if models:
            return select_model_interactive(models, "deep-thinking")
        else:
            console.print(
                "[yellow]Could not fetch models. Please enter manually.[/yellow]"
            )
            return enter_custom_model_name()

    choice = questionary.select(
        "Select Your [Deep-Thinking LLM Engine]:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in get_model_options(provider, "deep")
        ],
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        console.print("\n[red]No deep thinking llm engine selected. Exiting...[/red]")
        exit(1)

    return choice


def select_llm_provider() -> tuple[str, str]:
    """Select the OpenAI api url using interactive selection.

    Returns:
        Tuple of (provider_name, base_url) for standard providers,
        or (provider_name, base_url, api_key) for custom endpoint
    """
    BASE_URLS = [
        ("OpenAI", "https://api.openai.com/v1"),
        ("Google", "https://generativelanguage.googleapis.com/v1"),
        ("Anthropic", "https://api.anthropic.com/"),
        ("xAI", "https://api.x.ai/v1"),
        ("Openrouter", "https://openrouter.ai/api/v1"),
        ("Ollama", "http://localhost:11434/v1"),
        ("Custom OpenAI-Compatible Endpoint", "__custom__"),
    ]

    choice = questionary.select(
        "Select your LLM Provider:",
        choices=[
            questionary.Choice(display, value=(display, value))
            for display, value in BASE_URLS
        ],
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select\n- Set CUSTOM_LLM_ENDPOINT env var for quick access",
        style=questionary.Style(
            [
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        console.print("\n[red]no OpenAI backend selected. Exiting...[/red]")
        exit(1)

    display_name, url = choice

    if url == "__custom__":
        display_name, url, api_key = select_custom_endpoint()
        console.print(f"You selected: {display_name}\tURL: {url}")
        return display_name, url, api_key

    console.print(f"You selected: {display_name}\tURL: {url}")
    return display_name, url


def ask_openai_reasoning_effort() -> str:
    """Ask for OpenAI reasoning effort level."""
    choices = [
        questionary.Choice("Medium (Default)", "medium"),
        questionary.Choice("High (More thorough)", "high"),
        questionary.Choice("Low (Faster)", "low"),
    ]
    return questionary.select(
        "Select Reasoning Effort:",
        choices=choices,
        style=questionary.Style(
            [
                ("selected", "fg:cyan noinherit"),
                ("highlighted", "fg:cyan noinherit"),
                ("pointer", "fg:cyan noinherit"),
            ]
        ),
    ).ask()


def ask_anthropic_effort() -> str | None:
    """Ask for Anthropic effort level.

    Controls token usage and response thoroughness on Claude 4.5+ and 4.6 models.
    """
    return questionary.select(
        "Select Effort Level:",
        choices=[
            questionary.Choice("High (recommended)", "high"),
            questionary.Choice("Medium (balanced)", "medium"),
            questionary.Choice("Low (faster, cheaper)", "low"),
        ],
        style=questionary.Style(
            [
                ("selected", "fg:cyan noinherit"),
                ("highlighted", "fg:cyan noinherit"),
                ("pointer", "fg:cyan noinherit"),
            ]
        ),
    ).ask()


def ask_gemini_thinking_config() -> str | None:
    """Ask for Gemini thinking configuration.

    Returns thinking_level: "high" or "minimal".
    Client maps to appropriate API param based on model series.
    """
    return questionary.select(
        "Select Thinking Mode:",
        choices=[
            questionary.Choice("Enable Thinking (recommended)", "high"),
            questionary.Choice("Minimal/Disable Thinking", "minimal"),
        ],
        style=questionary.Style(
            [
                ("selected", "fg:green noinherit"),
                ("highlighted", "fg:green noinherit"),
                ("pointer", "fg:green noinherit"),
            ]
        ),
    ).ask()


def ask_output_language() -> str:
    """Ask for report output language."""
    choice = questionary.select(
        "Select Output Language:",
        choices=[
            questionary.Choice("English (default)", "English"),
            questionary.Choice("Chinese (中文)", "Chinese"),
            questionary.Choice("Japanese (日本語)", "Japanese"),
            questionary.Choice("Korean (한국어)", "Korean"),
            questionary.Choice("Hindi (हिन्दी)", "Hindi"),
            questionary.Choice("Spanish (Español)", "Spanish"),
            questionary.Choice("Portuguese (Português)", "Portuguese"),
            questionary.Choice("French (Français)", "French"),
            questionary.Choice("German (Deutsch)", "German"),
            questionary.Choice("Arabic (العربية)", "Arabic"),
            questionary.Choice("Russian (Русский)", "Russian"),
            questionary.Choice("Custom language", "custom"),
        ],
        style=questionary.Style([
            ("selected", "fg:yellow noinherit"),
            ("highlighted", "fg:yellow noinherit"),
            ("pointer", "fg:yellow noinherit"),
        ]),
    ).ask()

    if choice == "custom":
        return questionary.text(
            "Enter language name (e.g. Turkish, Vietnamese, Thai, Indonesian):",
            validate=lambda x: len(x.strip()) > 0 or "Please enter a language name.",
        ).ask().strip()

    return choice
