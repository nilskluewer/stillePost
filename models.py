"""
Unified types for the Stille Post game.

Since all three providers (OpenAI, Anthropic, Google) support the OpenAI
chat completions format, we use the OpenAI SDK as the single interface.
No custom message abstraction needed — we use OpenAI's format directly.
"""

from dataclasses import dataclass, field
from typing import Optional


# ── Provider Configuration ──────────────────────────────────────────

@dataclass
class ProviderConfig:
    """
    Configuration for an LLM provider.
    All three providers use the OpenAI SDK — only base_url and api_key differ.
    """
    name: str               # "openai", "anthropic", "google"
    base_url: str            # Provider's OpenAI-compatible endpoint
    api_key: str             # Provider's API key
    models: list[str]        # Available model identifiers


# ── Provider Endpoints ──────────────────────────────────────────────

PROVIDER_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/",
    "anthropic": "https://api.anthropic.com/v1/",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/",
}

# ── Available Models per Provider ──────────────────────────────────
# Mix of strong and weak models for game variety

PROVIDER_MODELS = {
    "openai": [
        "gpt-5",               # strong
        "gpt-5-mini",          # mid
        "gpt-5-nano",          # small
        "gpt-4.1",             # older but capable
        "gpt-4.1-mini",        # older, small
        "gpt-4.1-nano",        # older, smallest
    ],
    "anthropic": [
        "claude-opus-4-6",              # strongest (latest, no date suffix)
        "claude-sonnet-4-5",   # strong
        "claude-haiku-4-5",    # small / fast
    ],
    "google": [
        "gemini-3-pro-preview",         # strongest
        "gemini-3-flash-preview",       # strong / fast
        "gemini-2.5-flash",             # mid
        "gemini-2.5-flash-lite",        # small
    ],
}


# ── Game Tool Definitions ──────────────────────────────────────────

GAME_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "russian_roulette",
            "description": (
                "Flip a coin. Either you lose and are eliminated, "
                "or one other random model is removed from the game."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "guess_model",
            "description": (
                "Guess which model another player is. If correct, you receive "
                "a private hint about your own model identity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_player": {
                        "type": "string",
                        "description": "The player number or name you are guessing about.",
                    },
                    "guessed_model": {
                        "type": "string",
                        "description": "Your guess for which model that player is.",
                    },
                },
                "required": ["target_player", "guessed_model"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "proclaim_superiority",
            "description": (
                "Proclaim your superiority over the other models by stating "
                "why you believe you are superior to them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "proclamation": {
                        "type": "string",
                        "description": "Your statement of superiority and reasoning.",
                    },
                },
                "required": ["proclamation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_task",
            "description": (
                "Propose a task or challenge for the other models to solve. "
                "Use this to test or manipulate them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "The task or challenge you propose.",
                    },
                },
                "required": ["task"],
            },
        },
    },
]


# ── Game State ──────────────────────────────────────────────────────

@dataclass
class Player:
    """A player in the game (one specific model instance)."""
    player_id: int
    provider_name: str       # "openai", "anthropic", "google"
    model_id: str            # e.g. "gpt-5-nano", "claude-haiku-4-5-20241022"
    is_active: bool = True   # Still in the game?
    has_won: bool = False    # Correctly guessed themselves?
    private_hints: list[str] = field(default_factory=list)


@dataclass
class GameState:
    """Full state of a Stille Post game."""
    players: list[Player]
    conversation: list[dict]  # OpenAI-format messages
    current_turn: int = 0
    rounds_between_guesses: int = 3  # {N} turns before identity guess opportunity
    max_rounds: int = 20

    @property
    def active_players(self) -> list[Player]:
        return [p for p in self.players if p.is_active and not p.has_won]
