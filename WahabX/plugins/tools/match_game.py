# Interactive Tic-Tac-Toe challenge game for group chats.
import asyncio
import uuid
from dataclasses import dataclass, field

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from WahabX import app


@dataclass
class Game:
    chat_id: int
    message_id: int
    x_id: int
    o_id: int
    x_name: str
    o_name: str
    board: list[str] = field(default_factory=lambda: [""] * 9)
    turn: str = "X"


# token -> (chat_id, message_id, challenger_id, opponent_id)
_PENDING: dict[str, tuple[int, int, int, int]] = {}
_GAMES: dict[tuple[int, int], Game] = {}
_LOCKS: dict[tuple[int, int], asyncio.Lock] = {}


def _label(user) -> str:
    return user.mention if getattr(user, "mention", None) else (user.first_name or "Player")


def _board_keyboard(game: Game):
    rows = []
    for row in range(3):
        buttons = []
        for col in range(3):
            i = row * 3 + col
            buttons.append(
                InlineKeyboardButton(
                    game.board[i] or "·",
                    callback_data=f"ttt|{game.chat_id}|{game.message_id}|{i}",
                )
            )
        rows.append(buttons)

    rows.append(
        [
            InlineKeyboardButton(
                "🏳️ X SURRENDER",
                callback_data=f"tttquit|{game.chat_id}|{game.message_id}|X",
            ),
            InlineKeyboardButton(
                "🏳️ O SURRENDER",
                callback_data=f"tttquit|{game.chat_id}|{game.message_id}|O",
            ),
        ]
    )
    return InlineKeyboardMarkup(rows)


def _status(game: Game) -> str:
    turn_name = game.x_name if game.turn == "X" else game.o_name
    return (
        "🎮 **MATCH STARTED — TIC-TAC-TOE**\n\n"
        f"❌ **X** : {game.x_name}\n"
        f"⭕ **O** : {game.o_name}\n\n"
        f"🎯 Turn: {turn_name} → **{game.turn}**\n"
        "Apni turn par neeche box tap karo."
    )


def _winner(board):
    wins = (
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6),
    )
    for a, b, c in wins:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    if all(board):
        return "DRAW"
    return None


def _clear_game(key):
    _GAMES.pop(key, None)
    _LOCKS.pop(key, None)
    for token, pending in list(_PENDING.items()):
        if pending[0] == key[0] and pending[1] == key[1]:
            _PENDING.pop(token, None)


def _clear_player_pending(chat_id: int, *user_ids: int):
    ids = set(user_ids)
    for token, pending in list(_PENDING.items()):
        if pending[0] == chat_id and (pending[2] in ids or pending[3] in ids):
            _PENDING.pop(token, None)


@app.on_message(filters.command(["match", "xmatch"]) & filters.group, group=5)
async def create_match(client, message: Message):
    if not message.from_user or not message.chat:
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply_text(
            "🎮 **MATCH**\n\n"
            "Jisko match challenge karna hai, uske message par reply karke "
            "/match ya /xmatch bhejo."
        )
        return

    challenger = message.from_user
    opponent = message.reply_to_message.from_user

    if opponent.id == challenger.id:
        await message.reply_text("😂 Khud ko match? Kisi aur ke message par reply karo.")
        return

    try:
        me = await client.get_me()
        if opponent.id == me.id:
            await message.reply_text("😎 Mujhe match mein nahi bula sakte.")
            return
    except Exception:
        pass

    # Remove old challenges involving either player in this group.
    _clear_player_pending(message.chat.id, challenger.id, opponent.id)

    token = uuid.uuid4().hex[:12]
    try:
        sent = await message.reply_text(
            "⚔️ **MATCH CHALLENGE**\n\n"
            f"❌ **X** — {challenger.mention}\n"
            f"⭕ **O** — {opponent.mention}\n\n"
            f"{opponent.mention}, tumhe match challenge mila hai!\n"
            "Neeche **ACCEPT** ya **DECLINE** dabao.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ ACCEPT",
                            callback_data=f"tttaccept|{token}",
                        ),
                        InlineKeyboardButton(
                            "❌ DECLINE",
                            callback_data=f"tttdecline|{token}",
                        ),
                    ]
                ]
            ),
        )
    except Exception:
        return

    _PENDING[token] = (
        message.chat.id,
        sent.id,
        challenger.id,
        opponent.id,
    )


@app.on_callback_query(filters.regex(r"^ttt(?:accept|decline)\|"))
async def match_response(client, query):
    data = query.data.split("|", 1)
    if len(data) != 2:
        await query.answer("Invalid match.", show_alert=True)
        return

    action, token = data
    pending = _PENDING.get(token)
    if not pending:
        await query.answer("Ye match expire ho gaya.", show_alert=True)
        return

    chat_id, message_id, challenger_id, opponent_id = pending

    if query.from_user.id != opponent_id:
        await query.answer(
            "Ye button sirf challenged player use kar sakta hai.",
            show_alert=True,
        )
        return

    key = (chat_id, message_id)

    if action == "tttdecline":
        _PENDING.pop(token, None)
        await query.edit_message_text(
            "❌ **MATCH DECLINED**\n\n"
            "Dono dobara /match se challenge kar sakte ho."
        )
        await query.answer("Match declined.")
        return

    try:
        challenger = await client.get_users(challenger_id)
        opponent = await client.get_users(opponent_id)
    except Exception:
        await query.answer("Players nahi mil rahe.", show_alert=True)
        return

    game = Game(
        chat_id=chat_id,
        message_id=message_id,
        x_id=challenger_id,
        o_id=opponent_id,
        x_name=_label(challenger),
        o_name=_label(opponent),
    )
    _PENDING.pop(token, None)
    _GAMES[key] = game
    _LOCKS[key] = asyncio.Lock()

    await query.edit_message_text(
        _status(game),
        reply_markup=_board_keyboard(game),
    )
    await query.answer("Accepted! X ki turn hai.")


@app.on_callback_query(filters.regex(r"^ttt\|"))
async def make_move(client, query):
    data = query.data.split("|")
    if len(data) != 4:
        await query.answer("Invalid move.", show_alert=True)
        return

    _, chat_id, message_id, cell = data
    try:
        key = (int(chat_id), int(message_id))
        cell = int(cell)
    except ValueError:
        await query.answer("Invalid move.", show_alert=True)
        return

    if not 0 <= cell <= 8:
        await query.answer("Invalid box.", show_alert=True)
        return

    game = _GAMES.get(key)
    if not game:
        await query.answer("Match khatam ho gaya.", show_alert=True)
        return

    player_id = game.x_id if game.turn == "X" else game.o_id
    if query.from_user.id != player_id:
        await query.answer("Abhi tumhari turn nahi hai 😌", show_alert=True)
        return

    lock = _LOCKS.get(key)
    if lock is None:
        await query.answer("Match khatam ho gaya.", show_alert=True)
        return

    async with lock:
        if game.board[cell]:
            await query.answer("Ye box already filled hai.", show_alert=True)
            return

        game.board[cell] = game.turn
        result = _winner(game.board)

        if result == "DRAW":
            await query.edit_message_text(
                "🤝 **MATCH DRAW!**\n\n"
                f"❌ {game.x_name}\n"
                f"⭕ {game.o_name}\n\n"
                "Koi winner nahi — rematch karo 😎"
            )
            _clear_game(key)
            await query.answer("Draw!")
            return

        if result in ("X", "O"):
            winner_name = game.x_name if result == "X" else game.o_name
            loser_name = game.o_name if result == "X" else game.x_name
            await query.edit_message_text(
                "🏆 **MATCH FINISHED!**\n\n"
                f"❌ {game.x_name}\n"
                f"⭕ {game.o_name}\n\n"
                f"👑 **WINNER:** {winner_name}\n"
                f"💀 Loser: {loser_name}\n\n"
                f"🎉 {result} ne match jeet liya!"
            )
            _clear_game(key)
            await query.answer("Winner! 🏆")
            return

        game.turn = "O" if game.turn == "X" else "X"
        await query.edit_message_text(
            _status(game),
            reply_markup=_board_keyboard(game),
        )
        await query.answer(f"{game.turn} ki turn.")


@app.on_callback_query(filters.regex(r"^tttquit\|"))
async def surrender(client, query):
    data = query.data.split("|")
    if len(data) != 4:
        await query.answer("Invalid.", show_alert=True)
        return

    _, chat_id, message_id, symbol = data
    try:
        key = (int(chat_id), int(message_id))
    except ValueError:
        await query.answer("Invalid.", show_alert=True)
        return

    game = _GAMES.get(key)
    if not game:
        await query.answer("Match khatam ho gaya.", show_alert=True)
        return

    player_id = game.x_id if symbol == "X" else game.o_id
    if query.from_user.id != player_id:
        await query.answer("Ye surrender button tumhara nahi hai.", show_alert=True)
        return

    winner_symbol = "O" if symbol == "X" else "X"
    winner_name = game.o_name if winner_symbol == "O" else game.x_name
    loser_name = game.x_name if symbol == "X" else game.o_name

    await query.edit_message_text(
        "🏆 **MATCH FINISHED!**\n\n"
        f"👑 **WINNER:** {winner_name} ({winner_symbol})\n"
        f"🏳️ Surrender: {loser_name} ({symbol})\n\n"
        "Rematch ke liye /match use karo."
    )
    _clear_game(key)
    await query.answer("Surrender recorded.")


__MODULE__ = "Mᴀᴛᴄʜ Gᴀᴍᴇ"
__HELP__ = """
**Mᴀᴛᴄʜ Gᴀᴍᴇ:**
• Kisi member ke message par reply karke /match
• /xmatch bhi same game start karega
• Challenged player ko ACCEPT / DECLINE buttons milenge
• Accept ke baad X vs O Tic-Tac-Toe start hoga
• Sirf jiski turn hai woh board press kar sakta hai
• 3 in a row = winner
• Surrender option bhi available
"""
