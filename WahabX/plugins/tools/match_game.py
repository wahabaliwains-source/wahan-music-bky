# Interactive Tic-Tac-Toe challenge game for group chats.
import asyncio
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


_PENDING: dict[tuple[int, int], tuple[int, int]] = {}
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
    rows.append([
        InlineKeyboardButton(
            "🏳️ X SURRENDER",
            callback_data=f"tttquit|{game.chat_id}|{game.message_id}|X",
        ),
        InlineKeyboardButton(
            "🏳️ O SURRENDER",
            callback_data=f"tttquit|{game.chat_id}|{game.message_id}|O",
        ),
    ])
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


def _clear(key):
    _PENDING.pop(key, None)
    _GAMES.pop(key, None)
    _LOCKS.pop(key, None)


@app.on_message(filters.text & filters.regex(r"^/(?:match|xmatch)(?:@[A-Za-z0-9_]+)?(?:\\s+.*)?$"), group=5)
async def create_match(client, message: Message):
    if not message.from_user or not message.chat:
        return
    if str(message.chat.type) not in ("group", "supergroup"):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply_text(
            "🎮 MATCH\n\n"
            "Jisko match challenge karna hai, uske message par reply karke /match ya /xmatch bhejo."
        )

    challenger = message.from_user
    opponent = message.reply_to_message.from_user

    if opponent.id == challenger.id:
        return await message.reply_text("😂 Khud ko match? Kisi aur ke message par reply karo.")

    try:
        me = await app.get_me()
        if opponent.id == me.id:
            return await message.reply_text("😎 Mujhe match mein nahi bula sakte.")
    except Exception:
        pass

    for old_key, players in list(_PENDING.items()):
        if old_key[0] == message.chat.id and (
            players[0] in (challenger.id, opponent.id)
            or players[1] in (challenger.id, opponent.id)
        ):
            _PENDING.pop(old_key, None)

    sent = await message.reply_text(
        "⚔️ MATCH CHALLENGE\n\n"
        f"❌ X — {challenger.mention}\n"
        f"⭕ O — {opponent.mention}\n\n"
        f"{opponent.mention}, tumhe match challenge mila hai!\n"
        "Neeche ACCEPT ya DECLINE dabao.",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ ACCEPT",
                    callback_data=f"tttaccept|{message.chat.id}|PENDING",
                ),
                InlineKeyboardButton(
                    "❌ DECLINE",
                    callback_data=f"tttdecline|{message.chat.id}|PENDING",
                ),
            ]
        ]),
    )

    key = (message.chat.id, sent.id)
    await sent.edit_reply_markup(
        InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ ACCEPT",
                    callback_data=f"tttaccept|{message.chat.id}|{sent.id}",
                ),
                InlineKeyboardButton(
                    "❌ DECLINE",
                    callback_data=f"tttdecline|{message.chat.id}|{sent.id}",
                ),
            ]
        ])
    )
    _PENDING[key] = (challenger.id, opponent.id)


@app.on_callback_query(filters.regex(r"^ttt(?:accept|decline)\|"))
async def match_response(client, query):
    data = query.data.split("|")
    if len(data) != 3:
        return await query.answer("Invalid match.", show_alert=True)

    action, chat_id, message_id = data
    if not message_id.isdigit():
        return await query.answer("Match invalid hai.", show_alert=True)

    key = (int(chat_id), int(message_id))
    pending = _PENDING.get(key)
    if not pending:
        return await query.answer("Ye match expire ho gaya.", show_alert=True)

    challenger_id, opponent_id = pending
    if query.from_user.id != opponent_id:
        return await query.answer(
            "Ye button sirf challenged player use kar sakta hai.",
            show_alert=True,
        )

    if action == "tttdecline":
        _clear(key)
        return await query.edit_message_text(
            "❌ MATCH DECLINED\n\nDono dobara /match se challenge kar sakte ho."
        )

    try:
        challenger = await app.get_users(challenger_id)
        opponent = await app.get_users(opponent_id)
    except Exception:
        return await query.answer("Players nahi mil rahe.", show_alert=True)

    game = Game(
        chat_id=key[0],
        message_id=key[1],
        x_id=challenger_id,
        o_id=opponent_id,
        x_name=_label(challenger),
        o_name=_label(opponent),
    )
    _PENDING.pop(key, None)
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
        return await query.answer("Invalid move.", show_alert=True)

    _, chat_id, message_id, cell = data
    key = (int(chat_id), int(message_id))
    game = _GAMES.get(key)
    if not game:
        return await query.answer("Match khatam ho gaya.", show_alert=True)

    try:
        cell = int(cell)
    except ValueError:
        return await query.answer("Invalid box.", show_alert=True)

    if not 0 <= cell <= 8:
        return await query.answer("Invalid box.", show_alert=True)

    player_id = game.x_id if game.turn == "X" else game.o_id
    if query.from_user.id != player_id:
        return await query.answer("Abhi tumhari turn nahi hai 😌", show_alert=True)

    lock = _LOCKS.get(key)
    if lock is None:
        return await query.answer("Match khatam ho gaya.", show_alert=True)

    async with lock:
        if game.board[cell]:
            return await query.answer("Ye box already filled hai.", show_alert=True)

        game.board[cell] = game.turn
        result = _winner(game.board)

        if result == "DRAW":
            text = (
                "🤝 MATCH DRAW!\n\n"
                f"❌ {game.x_name}\n"
                f"⭕ {game.o_name}\n\n"
                "Koi winner nahi — rematch karo 😎"
            )
            await query.edit_message_text(text)
            _clear(key)
            return await query.answer("Draw!")

        if result in ("X", "O"):
            winner_name = game.x_name if result == "X" else game.o_name
            loser_name = game.o_name if result == "X" else game.x_name
            text = (
                "🏆 MATCH FINISHED!\n\n"
                f"❌ {game.x_name}\n"
                f"⭕ {game.o_name}\n\n"
                f"👑 WINNER: {winner_name}\n"
                f"💀 Loser: {loser_name}\n\n"
                f"🎉 {result} ne match jeet liya!"
            )
            await query.edit_message_text(text)
            _clear(key)
            return await query.answer("Winner! 🏆")

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
        return await query.answer("Invalid.", show_alert=True)

    _, chat_id, message_id, symbol = data
    key = (int(chat_id), int(message_id))
    game = _GAMES.get(key)
    if not game:
        return await query.answer("Match khatam ho gaya.", show_alert=True)

    player_id = game.x_id if symbol == "X" else game.o_id
    if query.from_user.id != player_id:
        return await query.answer("Ye surrender button tumhara nahi hai.", show_alert=True)

    winner_symbol = "O" if symbol == "X" else "X"
    winner_name = game.o_name if winner_symbol == "O" else game.x_name
    loser_name = game.x_name if symbol == "X" else game.o_name

    await query.edit_message_text(
        "🏆 MATCH FINISHED!\n\n"
        f"👑 WINNER: {winner_name} ({winner_symbol})\n"
        f"🏳️ Surrender: {loser_name} ({symbol})\n\n"
        "Rematch ke liye /match use karo."
    )
    _clear(key)
    await query.answer("Surrender recorded.")


__MODULE__ = "Mᴀᴛᴄʜ Gᴀᴍᴇ"
__HELP__ = """
**Mᴀᴛᴄʜ Gᴀᴍᴇ:**
• Kisi member ke message par reply karke /match
• Challenged player ko ACCEPT / DECLINE buttons milenge
• Accept ke baad X vs O Tic-Tac-Toe start hoga
• Apni turn par board ka box tap karo
• 3 in a row = winner
• Surrender option bhi available
"""
