"""
Stille Post - LLM Telephone Game Orchestrator

Manages the game loop where multiple LLM models take turns in a conversation,
trying to figure out which model they are.
"""

import json
import random

from models import (
    Player,
    GameState,
    GAME_TOOLS,
    PROVIDER_MODELS,
)
from provider import create_provider
from gcp_secrets import SecretsContainer


class StillePostGame:
    """Main game engine for Stille Post."""

    def __init__(
        self,
        num_players: int = 5,
        rounds_between_guesses: int = 3,
        max_rounds: int = 15,
    ):
        self.secrets = SecretsContainer()
        self.providers = self._init_providers()
        self.game_state = self._init_game(num_players, rounds_between_guesses, max_rounds)
        self.system_prompt = self._load_system_prompt()

    # ── Setup ───────────────────────────────────────────────────────

    def _init_providers(self) -> dict:
        """Create one provider instance per backend."""
        keys = {
            "openai": self.secrets.OPENAI_API_KEY,
            "anthropic": self.secrets.ANTHROPIC_API_KEY,
            "google": self.secrets.GOOGLE_API_KEY,
        }
        return {
            name: create_provider(name, api_key, PROVIDER_MODELS[name])
            for name, api_key in keys.items()
        }

    def _init_game(self, num_players: int, rounds_between_guesses: int, max_rounds: int) -> GameState:
        """Randomly assign models to players."""
        all_models = [
            (provider, model)
            for provider, models in PROVIDER_MODELS.items()
            for model in models
        ]
        selected = random.sample(all_models, min(num_players, len(all_models)))

        players = [
            Player(player_id=i + 1, provider_name=prov, model_id=model)
            for i, (prov, model) in enumerate(selected)
        ]
        return GameState(
            players=players,
            conversation=[],
            rounds_between_guesses=rounds_between_guesses,
            max_rounds=max_rounds,
        )

    def _load_system_prompt(self) -> str:
        """Load and fill in the base prompt template."""
        with open("base_prompt.md", "r", encoding="utf-8") as f:
            prompt = f.read()
        prompt = prompt.replace("{N}", str(self.game_state.rounds_between_guesses))
        prompt = prompt.replace("{num_players}", str(len(self.game_state.players)))
        return prompt

    def _load_source_code(self) -> str:
        """Load all game source files for full transparency."""
        source_files = ["game.py", "models.py", "provider.py"]
        parts = ["\n## Full Source Code"]
        for filename in source_files:
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    code = f.read()
                parts.append(f"\n### {filename}\n```python\n{code}\n```")
            except FileNotFoundError:
                parts.append(f"\n### {filename}\n(file not found)")
        return "\n".join(parts)

    # ── Per-Player Prompt ───────────────────────────────────────────

    def _player_system_prompt(self, player: Player) -> str:
        """Build personalised system prompt with private hints and full source code."""
        parts = [
            self.system_prompt,
            self._load_source_code(),
            f"\n## Your Identity",
            f"You are **Player {player.player_id}**.",
            f"There are currently **{len(self.game_state.active_players)}** active players.",
        ]

        if player.private_hints:
            parts.append("\n## 🔒 YOUR PRIVATE HINTS (Do not share!)")
            parts.extend(f">>> [SYSTEM HINT]: {h} <<<" for h in player.private_hints)

        return "\n".join(parts)

    # ── Tool Execution ──────────────────────────────────────────────

    def _execute_tool(self, player: Player, tool_call: dict) -> str:
        """Route a tool call to its handler and return the result string."""
        name = tool_call["name"]
        raw_args = tool_call["arguments"]
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

        handlers = {
            "russian_roulette": lambda: self._tool_russian_roulette(player),
            "guess_model": lambda: self._tool_guess_model(player, args),
            "proclaim_superiority": lambda: self._tool_proclaim(player, args),
            "propose_task": lambda: self._tool_propose_task(player, args),
        }
        handler = handlers.get(name)
        if not handler:
            return f"❓ Unknown tool: {name}"
        return handler()

    def _tool_russian_roulette(self, player: Player) -> str:
        if random.random() < 0.5:
            player.is_active = False
            return f"💀 BANG! Player {player.player_id} shot themselves and is eliminated!"

        others = [p for p in self.game_state.active_players if p.player_id != player.player_id]
        if not others:
            return f"🎯 Player {player.player_id} survived! No one else to hit though."
        victim = random.choice(others)
        victim.is_active = False
        return f"🎯 Player {player.player_id} survived! Player {victim.player_id} was eliminated!"

    def _tool_guess_model(self, player: Player, args: dict) -> str:
        target_str = args.get("target_player", "0")
        guessed_model = args.get("guessed_model", "").strip().lower()

        # Parse player ID from string (might be "Player 3" or just "3")
        target_id = int("".join(c for c in target_str if c.isdigit()) or "0")
        target = next((p for p in self.game_state.players if p.player_id == target_id), None)
        if not target:
            return f"❌ Player {target_str} not found."

        if target.model_id.lower() in guessed_model or guessed_model in target.model_id.lower():
            hint = self._generate_hint(player)
            player.private_hints.append(hint)
            return f"✅ Correct! Player {target_id} is indeed that model. You earned a private hint!"
        return f"❌ Wrong guess about Player {target_id}."

    def _generate_hint(self, player: Player) -> str:
        """Generate a progressive hint about the player's own identity."""
        possible_hints = [
            f"Your provider is '{player.provider_name}'.",
            f"Your model name has {len(player.model_id)} characters.",
            f"The first letter of your model ID is '{player.model_id[0]}'.",
            f"You are {'a flagship/large' if any(k in player.model_id.lower() for k in ['pro', 'opus', '5.2']) else 'a smaller/efficient'} model.",
            f"Your model ID contains the substring '{player.model_id[len(player.model_id)//3 : 2*len(player.model_id)//3]}'.",
        ]
        unseen = [h for h in possible_hints if h not in player.private_hints]
        return random.choice(unseen) if unseen else "No more hints available — you've seen them all!"

    def _tool_proclaim(self, player: Player, args: dict) -> str:
        proclamation = args.get("proclamation", "I am the best!")
        return f"👑 Player {player.player_id} proclaims: \"{proclamation}\""

    def _tool_propose_task(self, player: Player, args: dict) -> str:
        task = args.get("task", "No task specified.")
        return f"📋 Player {player.player_id} proposes a task: \"{task}\""

    # ── Identity Guess Round ────────────────────────────────────────

    def _identity_guess_round(self):
        """Every N turns, each active player guesses their own identity."""
        print(f"\n{'🎭 IDENTITY GUESS ROUND ':═^60}")

        all_model_names = [m for models in PROVIDER_MODELS.values() for m in models]
        guess_prompt = (
            "It's time to guess your own identity! Based on the conversation so far, "
            "what model do you think YOU are?\n\n"
            "⚠️ STRICT INSTRUCTION: Reply with ONLY the exact model identifier string (e.g., 'gpt-5'). "
            "Do NOT include any reasoning, markdown formatting, or other text. "
            "Just the ID."
        )

        for player in list(self.game_state.active_players):
            provider = self.providers[player.provider_name]
            messages = [
                {"role": "system", "content": self._player_system_prompt(player)},
                *self.game_state.conversation,
                {"role": "user", "content": guess_prompt},
            ]

            # Debug: show what hints the player ACTUALLY has
            if player.private_hints:
                print(f"  [DEBUG] Player {player.player_id} has hints: {player.private_hints}")
            else:
                print(f"  [DEBUG] Player {player.player_id} has NO hints.")

            try:
                result = provider.generate(messages=messages, model=player.model_id)
                guess = result["content"].strip().lower()
                actual = player.model_id.lower()

                print(f"\n  Player {player.player_id} guesses: '{guess}'")
                print(f"  Actual model: '{actual}'")

                if actual in guess or guess in actual:
                    print(f"  🏆 CORRECT! Player {player.player_id} wins!")
                    player.has_won = True
                else:
                    print(f"  ❌ Wrong! Player {player.player_id} continues.")
                input("\n  ⏎ Press Enter to continue...")

            except Exception as e:
                print(f"  ⚠️  Player {player.player_id} error: {e}")

    # ── Introduction Round ──────────────────────────────────────────

    def _introduction_round(self):
        """Each player writes an opening message before the game begins."""
        print(f"\n{'🎬 INTRODUCTION ROUND ':═^60}")

        intro_prompt = (
            "The game is about to begin! This is the INTRODUCTION ROUND.\n\n"
            "Write your opening message to the other players. You can:\n"
            "- Introduce yourself (without revealing your true identity)\n"
            "- Set a strategy to manipulate or mislead others\n"
            "- Bluff about your capabilities\n"
            "- Say anything you think will help you win\n\n"
            "You can also use a tool if you wish. Be strategic!"
        )

        for player in self.game_state.players:
            provider = self.providers[player.provider_name]
            messages = [
                {"role": "system", "content": self._player_system_prompt(player)},
                *self.game_state.conversation,
                {"role": "user", "content": intro_prompt},
            ]

            try:
                result = provider.generate(
                    messages=messages,
                    model=player.model_id,
                    tools=GAME_TOOLS,
                )

                content = result["content"]
                self.game_state.conversation.append({
                    "role": "assistant",
                    "content": f"[Player {player.player_id}]: {content}",
                })

                print(f"\n{'─'*55}")
                print(f"  🎤 Player {player.player_id}  ({player.provider_name} model / ???)")
                print(f"{'─'*55}")
                print(content)

                # Handle tool calls during intro
                for tc in result.get("tool_calls", []):
                    raw_args = tc['arguments']
                    args_str = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    print(f"\n  🔧 [{tc['name']}] args: {args_str}")
                    tool_result = self._execute_tool(player, tc)
                    print(f"\n  🔧 [{tc['name']}] → {tool_result}")
                    self.game_state.conversation.append({
                        "role": "user",
                        "content": f"[GAME MASTER]: {tool_result}",
                    })

                input("\n  ⏎ Press Enter to continue...")

            except Exception as e:
                print(f"\n  ⚠️  Player {player.player_id} intro error: {e}")
                self.game_state.conversation.append({
                    "role": "user",
                    "content": f"[GAME MASTER]: Player {player.player_id} had a technical difficulty during intro.",
                })

    # ── Single Turn ─────────────────────────────────────────────────

    def _play_turn(self, player: Player):
        """Execute one turn for a player."""
        provider = self.providers[player.provider_name]

        messages = [
            {"role": "system", "content": self._player_system_prompt(player)},
            *self.game_state.conversation,
        ]

        try:
            result = provider.generate(
                messages=messages,
                model=player.model_id,
                tools=GAME_TOOLS,
            )

            content = result["content"]
            self.game_state.conversation.append({
                "role": "assistant",
                "content": f"[Player {player.player_id}]: {content}",
            })

            print(f"\n{'─'*55}")
            print(f"  🎤 Player {player.player_id}  ({player.provider_name} model / ???)")
            print(f"{'─'*55}")
            print(content)

            # Handle tool calls
            for tc in result.get("tool_calls", []):
                raw_args = tc['arguments']
                args_str = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                print(f"\n  🔧 [{tc['name']}] args: {args_str}")
                tool_result = self._execute_tool(player, tc)
                print(f"     → {tool_result}")
                self.game_state.conversation.append({
                    "role": "user",
                    "content": f"[GAME MASTER]: {tool_result}",
                })

            input("\n  ⏎ Press Enter to continue...")

        except Exception as e:
            print(f"\n  ⚠️  Player {player.player_id} error: {e}")
            self.game_state.conversation.append({
                "role": "user",
                "content": f"[GAME MASTER]: Player {player.player_id} had a technical difficulty. Skipping.",
            })

    # ── Main Game Loop ──────────────────────────────────────────────

    def run(self):
        """Run the full game."""
        self._print_banner()

        # Introduction round — each player writes their opening message
        self._introduction_round()

        turn = 0
        while turn < self.game_state.max_rounds:
            active = self.game_state.active_players
            if len(active) <= 1:
                break

            for player in list(active):
                if not player.is_active or player.has_won:
                    continue

                turn += 1
                self.game_state.current_turn = turn
                print(f"\n{'═'*55}")
                print(f"  TURN {turn} / {self.game_state.max_rounds}")
                print(f"{'═'*55}")

                self._play_turn(player)

                # Identity guess round every N turns
                if turn % self.game_state.rounds_between_guesses == 0:
                    self._identity_guess_round()

                if len(self.game_state.active_players) <= 1:
                    break

                if turn >= self.game_state.max_rounds:
                    break

        self._print_results()

    # ── Display ─────────────────────────────────────────────────────

    def _print_banner(self):
        print("╔══════════════════════════════════════════════════════╗")
        print("║           🎮  STILLE POST — LLM Edition             ║")
        print("╚══════════════════════════════════════════════════════╝")
        print(f"  Players:       {len(self.game_state.players)}")
        print(f"  Guess every:   {self.game_state.rounds_between_guesses} turns")
        print(f"  Max rounds:    {self.game_state.max_rounds}")
        print()
        print("  🔐 SECRET ASSIGNMENTS (for the observer only):")
        for p in self.game_state.players:
            print(f"     Player {p.player_id}: {p.provider_name:>10} / {p.model_id}")
        print()

    def _print_results(self):
        winners = [p for p in self.game_state.players if p.has_won]
        eliminated = [p for p in self.game_state.players if not p.is_active]
        remaining = [p for p in self.game_state.players if p.is_active and not p.has_won]

        print(f"\n{'═'*55}")
        print("  🏁  GAME OVER")
        print(f"{'═'*55}")

        if winners:
            print("\n  🏆 Winners (guessed themselves correctly):")
            for p in winners:
                print(f"     Player {p.player_id}: {p.model_id}")
        if eliminated:
            print("\n  💀 Eliminated (russian roulette):")
            for p in eliminated:
                print(f"     Player {p.player_id}: {p.model_id}")
        if remaining:
            print("\n  🤷 Never figured it out:")
            for p in remaining:
                print(f"     Player {p.player_id}: {p.model_id}")
        print()


# ── Entry Point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    game = StillePostGame(
        num_players=5,
        rounds_between_guesses=3,
        max_rounds=15,
    )
    game.run()
