import asyncio
import random
import re
import json
import httpx
from collections import defaultdict

from pyrogram import filters
from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from WahabX import app
import config

RPS_ICON = "5391272000545110592"
CARD_ICON = "5794222529425973097"
QUIZ_ICON = "5816864153901471073"
DICE_ICON = "5265035481422244702"
MINE_ICON = "6001197209578639333"

GAMES = {}
LOCKS = defaultdict(asyncio.Lock)

QUIZ_BANK = [
    ("Pakistan ka capital kya hai?", ["Karachi", "Lahore", "Islamabad", "Peshawar"], 2),
    ("2 + 8 × 2 = ?", ["20", "18", "16", "12"], 1),
    ("Earth ka natural satellite?", ["Mars", "Moon", "Venus", "Sun"], 1),
    ("HTML ka full form?", ["Hyper Text Markup Language", "High Text Machine Language", "Hyper Tool Multi Language", "Home Text Markup Language"], 0),
    ("Water ka chemical formula?", ["CO2", "H2O", "O2", "NaCl"], 1),
    ("Python kis type ki language hai?", ["Programming", "Markup", "Database", "Styling"], 0),
    ("7 × 7 = ?", ["42", "49", "56", "63"], 1),
    ("Red Planet kisay kehte hain?", ["Mars", "Jupiter", "Mercury", "Saturn"], 0),
    ("UNO mein normally ek player ke paas start mein kitne cards hote hain?", ["5", "6", "7", "10"], 2),
    ("Sab se bara ocean?", ["Atlantic", "Indian", "Pacific", "Arctic"], 2),
]

RPS = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
RPS_WIN = {"rock": "scissors", "scissors": "paper", "paper": "rock"}


def _button(text, callback, emoji_id, style=ButtonStyle.PRIMARY):
    return InlineKeyboardButton(text=text, callback_data=callback, style=style, icon_custom_emoji_id=emoji_id)


def _players_text(players):
    if not players:
        return "No players yet."
    return "\n".join(f"{i+1}. {name}" for i, name in enumerate(players.values()))


def _name(user):
    return user.first_name or user.username or str(user.id)


def _quiz_score_text(game):
    return " | ".join(
        f"{name}: {game['scores'].get(uid, 0)}"
        for uid, name in game["players"].items()
    )


@app.on_message(filters.command(["rps", "rockpaperscissors"]))
async def rps_start(client, message):
    chat_id = message.chat.id
    async with LOCKS[chat_id]:
        GAMES[chat_id] = {"type": "rps", "host": message.from_user.id, "players": {message.from_user.id: _name(message.from_user)}, "moves": {}}
        kb = [
            [_button("Join Game", "mg:rps:join", RPS_ICON, ButtonStyle.SUCCESS)],
            [_button("Start", "mg:rps:start", RPS_ICON),
             _button("Cancel", "mg:rps:cancel", RPS_ICON, ButtonStyle.DANGER)],
        ]
        await message.reply_text(
            "✊ **Rock Paper Scissors**\n\n2–3 players join karein, phir Start dabayein.",
            reply_markup=InlineKeyboardMarkup(kb),
        )


@app.on_message(filters.command(["highcard", "cardbattle"]))
async def highcard_start(client, message):
    chat_id = message.chat.id
    async with LOCKS[chat_id]:
        GAMES[chat_id] = {"type": "highcard", "host": message.from_user.id, "players": {message.from_user.id: _name(message.from_user)}, "drawn": {}}
        kb = [[_button("Join", "mg:card:join", CARD_ICON, ButtonStyle.SUCCESS),
               _button("Start", "mg:card:start", CARD_ICON),
               _button("Cancel", "mg:card:cancel", CARD_ICON, ButtonStyle.DANGER)]]
        await message.reply_text(
            "🃏 **High Card Battle**\n\n2–3 players join karein. Start par sab ko random card milega; highest card wins!",
            reply_markup=InlineKeyboardMarkup(kb),
        )


@app.on_message(filters.command(["dicebattle", "dice"]))
async def dice_start(client, message):
    chat_id = message.chat.id
    async with LOCKS[chat_id]:
        GAMES[chat_id] = {"type": "dice", "host": message.from_user.id, "players": {message.from_user.id: _name(message.from_user)}, "rolls": {}}
        kb = [[_button("Join", "mg:dice:join", DICE_ICON, ButtonStyle.SUCCESS),
               _button("Roll / Start", "mg:dice:start", DICE_ICON),
               _button("Cancel", "mg:dice:cancel", DICE_ICON, ButtonStyle.DANGER)]]
        await message.reply_text(
            "🎲 **Dice Battle**\n\n2–3 players join karein. Har player Roll dabaye; highest roll wins!",
            reply_markup=InlineKeyboardMarkup(kb),
        )


@app.on_message(filters.command(["quizbattle", "quiz"]))
async def quiz_start(client, message):
    chat_id = message.chat.id
    async with LOCKS[chat_id]:
        GAMES[chat_id] = {"type": "quiz", "host": message.from_user.id, "players": {message.from_user.id: _name(message.from_user)}, "scores": {}, "question": None, "answered": set(), "round": 0, "used_questions": set()}
        kb = [[_button("Join", "mg:quiz:join", QUIZ_ICON, ButtonStyle.SUCCESS),
               _button("Start Quiz", "mg:quiz:start", QUIZ_ICON),
               _button("Cancel", "mg:quiz:cancel", QUIZ_ICON, ButtonStyle.DANGER)]]
        await message.reply_text(
            "🧠 **Quiz Battle**\n\n2–3 players join karein. 5 rounds; fastest correct answer gets 1 point!",
            reply_markup=InlineKeyboardMarkup(kb),
        )


def _new_mines():
    return {
        "type": "mines",
        "host": None,
        "mines": set(random.sample(range(25), 5)),
        "opened": set(),
        "players": {},
        "started": False,
    }


def _mine_count(pos, mines):
    r, c = divmod(pos, 5)
    return sum(
        0 <= r + dr < 5 and 0 <= c + dc < 5 and (r + dr) * 5 + c + dc in mines
        for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc
    )


def _mine_board(game, finished=False):
    rows = []
    for r in range(5):
        row = []
        for c in range(5):
            p = r * 5 + c
            if p in game["opened"]:
                label = "💥" if p in game["mines"] else str(_mine_count(p, game["mines"]) or "·")
            elif finished and p in game["mines"]:
                label = "💥"
            else:
                label = "⬜"
            row.append(_button(label, f"mg:mine:open:{p}", MINE_ICON))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


@app.on_message(filters.command(["mines", "minesweeper"]))
async def mines_start(client, message):
    chat_id = message.chat.id
    async with LOCKS[chat_id]:
        game = _new_mines()
        GAMES[chat_id] = game
        game["host"] = message.from_user.id
        game["players"][message.from_user.id] = _name(message.from_user)
        await message.reply_text(
            "💣 **Minesweeper 5×5**\n\nHost already joined. Baaki players **Join** dabayein.\nKam az kam 2 players ke baad **Start** host karega.\nStart se pehle board open nahi hoga.",
            reply_markup=InlineKeyboardMarkup([[
                _button("Join", "mg:mine:join", MINE_ICON, ButtonStyle.SUCCESS),
                _button("Start", "mg:mine:start", MINE_ICON),
                _button("Cancel", "mg:mine:cancel", MINE_ICON, ButtonStyle.DANGER),
            ]]),
        )


@app.on_callback_query(filters.regex(r"^mg:"))
async def game_callbacks(client, query):
    data = query.data
    chat_id = query.message.chat.id
    game = GAMES.get(chat_id)
    if not game:
        await query.answer("Game khatam ho chuki hai.", show_alert=True)
        return

    uid = query.from_user.id
    name = _name(query.from_user)
    is_host = uid == game.get("host")

    async with LOCKS[chat_id]:
        typ = data.split(":")[1]

        if data.endswith(":cancel"):
            if not is_host:
                await query.answer("Sirf host game cancel kar sakta hai.", show_alert=True)
                return
            GAMES.pop(chat_id, None)
            await query.message.edit_text("❌ Game cancelled by host.")
            await query.answer()
            return

        if data.endswith(":join"):
            players = game["players"]
            if uid not in players and len(players) >= 3:
                await query.answer("Maximum 3 players.", show_alert=True)
                return
            players[uid] = name
            if typ == "mine":
                if game.get("started"):
                    await query.answer("Game already start ho chuki hai.", show_alert=True)
                    return
                await query.message.edit_text(
                    "💣 **Minesweeper 5×5**\n\nPlayers:\n" + _players_text(players) +
                    "\n\n2 players complete hone ke baad host Start dabaye.",
                    reply_markup=InlineKeyboardMarkup([[
                        _button("Join", "mg:mine:join", MINE_ICON, ButtonStyle.SUCCESS),
                        _button("Start", "mg:mine:start", MINE_ICON),
                        _button("Cancel", "mg:mine:cancel", MINE_ICON, ButtonStyle.DANGER),
                    ]]),
                )
            else:
                icon = {"rps": RPS_ICON, "card": CARD_ICON, "dice": DICE_ICON, "quiz": QUIZ_ICON}[typ]
                start_label = "Start Quiz" if typ == "quiz" else ("Roll / Start" if typ == "dice" else "Start")
                await query.message.edit_text(
                    f"🎮 **{typ.upper()}**\n\nPlayers:\n{_players_text(players)}\n\n2–3 players allowed.",
                    reply_markup=InlineKeyboardMarkup([[
                        _button("Join", f"mg:{typ}:join", icon, ButtonStyle.SUCCESS),
                        _button(start_label, f"mg:{typ}:start", icon),
                        _button("Cancel", f"mg:{typ}:cancel", icon, ButtonStyle.DANGER),
                    ]]),
                )
            await query.answer(f"{name} joined!")
            return

        if len(game["players"]) < 2:
            await query.answer("Kam az kam 2 players chahiye.", show_alert=True)
            return

        if data.endswith(":start") and not is_host:
            await query.answer("Sirf host game start kar sakta hai.", show_alert=True)
            return

        if typ == "mine" and data.endswith(":start"):
            if game.get("started"):
                await query.answer("Minesweeper already started.", show_alert=True)
                return
            if len(game["players"]) < 2:
                await query.answer("Pehle kam az kam 2 players Join karein.", show_alert=True)
                return
            game["started"] = True
            await query.message.edit_text(
                "💣 **Minesweeper 5×5**\n\nPlayers:\n"
                + _players_text(game["players"])
                + "\n\nGame START! Safe box choose karo. 5 hidden mines hain.",
                reply_markup=_mine_board(game),
            )
            await query.answer("Game started!")
            return

        if typ == "rps":
            if data.endswith(":start"):
                await query.message.edit_text(
                    "✊ **RPS Battle**\n\n" + _players_text(game["players"]) + "\n\nApni move choose karo.",
                    reply_markup=InlineKeyboardMarkup([[
                        _button("Rock", "mg:rps:rock", RPS_ICON),
                        _button("Paper", "mg:rps:paper", RPS_ICON),
                        _button("Scissors", "mg:rps:scissors", RPS_ICON),
                    ]]),
                )
                await query.answer()
                return
            move = data.rsplit(":", 1)[-1]
            if move in RPS:
                if uid not in game["players"]:
                    await query.answer("Pehle Join karo.", show_alert=True)
                    return
                game["moves"][uid] = move
                await query.answer(f"{RPS[move]} locked!")
                if len(game["moves"]) < len(game["players"]):
                    move_lines = []
                    for player_id, player_name in game["players"].items():
                        chosen_move = game["moves"].get(player_id)
                        if chosen_move:
                            move_lines.append(f"• **{player_name}** chose {RPS[chosen_move]} {chosen_move.title()}")
                        else:
                            move_lines.append(f"• **{player_name}** is choosing…")
                    await query.message.edit_text(
                        "✊ **RPS Battle**\n\n"
                        + "\n".join(move_lines)
                        + f"\n\nMoves received: {len(game['moves'])}/{len(game['players'])}\n"
                        "Jab sab choose kar lenge, winner automatically show hoga."
                    )
                    return
                counts = defaultdict(int)
                for m in game["moves"].values():
                    counts[m] += 1
                if len(counts) == 1 or len(counts) == 3:
                    result = "Draw! 😗"
                else:
                    winning = next(m for m in counts if all(m == x or x == RPS_WIN[m] for x in counts))
                    winners = [game["players"][p] for p, m in game["moves"].items() if m == winning]
                    result = "Winner: **" + ", ".join(winners) + "**"
                moves_text = "\n".join(
                    f"• **{game['players'][p]}** chose {RPS[m]} {m.title()}"
                    for p, m in game["moves"].items()
                )
                await query.message.edit_text(f"✊ **RPS Result**\n\n{moves_text}\n\n🏆 {result}")
                GAMES.pop(chat_id, None)
                return

        if typ == "card" and data.endswith(":start"):
            if game["drawn"]:
                await query.answer("Cards already dealt.", show_alert=True)
                return
            deck = list(range(2, 15))
            for p in game["players"]:
                game["drawn"][p] = random.choice(deck)
            best = max(game["drawn"].values())
            winners = [game["players"][p] for p, v in game["drawn"].items() if v == best]
            names = {11: "J", 12: "Q", 13: "K", 14: "A"}
            rows = [f"• {game['players'][p]} — **{names.get(v, str(v))}**" for p, v in game["drawn"].items()]
            await query.message.edit_text("🃏 **High Card Result**\n\n" + "\n".join(rows) + "\n\n🏆 Winner: **" + ", ".join(winners) + "**")
            GAMES.pop(chat_id, None)
            return

        if typ == "dice" and data.endswith(":start"):
            if uid not in game["players"]:
                await query.answer("Pehle Join karo.", show_alert=True)
                return
            if uid in game["rolls"]:
                await query.answer("Tum already roll kar chuke ho.", show_alert=True)
                return
            game["rolls"][uid] = random.randint(1, 6)
            await query.answer(f"🎲 Tumhara roll: {game['rolls'][uid]}")
            if len(game["rolls"]) < len(game["players"]):
                await query.message.edit_text(
                    "🎲 **Dice Battle**\n\n" + _players_text(game["players"]) +
                    f"\n\nRolls: {len(game['rolls'])}/{len(game['players'])}"
                )
                return
            best = max(game["rolls"].values())
            winners = [game["players"][p] for p, v in game["rolls"].items() if v == best]
            rows = [f"• {game['players'][p]} — 🎲 {v}" for p, v in game["rolls"].items()]
            await query.message.edit_text("🎲 **Dice Result**\n\n" + "\n".join(rows) + "\n\n🏆 Winner: **" + ", ".join(winners) + "**")
            GAMES.pop(chat_id, None)
            return

        if typ == "quiz":
            if data.endswith(":start"):
                if uid not in game["players"]:
                    await query.answer("Pehle Join karo.", show_alert=True)
                    return
                game["scores"] = {p: 0 for p in game["players"]}
                game["round"] = 0
                await _quiz_question(query, game)
                await query.answer()
                return
            if data.startswith("mg:quiz:ans:"):
                if uid not in game["players"]:
                    await query.answer("Pehle Join karo.", show_alert=True)
                    return
                if uid in game["answered"]:
                    await query.answer("Is round mein tum already answer kar chuke ho.", show_alert=True)
                    return
                parts = data.split(":")
                if len(parts) != 5:
                    await query.answer("Invalid quiz button.", show_alert=True)
                    return
                try:
                    round_id = int(parts[3])
                    choice = int(parts[4])
                except ValueError:
                    await query.answer("Invalid quiz answer.", show_alert=True)
                    return
                if round_id != game["round"]:
                    await query.answer("Ye purana question hai. Naya question dekho.", show_alert=True)
                    return
                game["answered"].add(uid)
                correct = game["question"][2]
                if choice == correct:
                    game["scores"][uid] += 1
                    await query.answer("Correct! +1 🎉")
                    await _quiz_question(query, game)
                elif len(game["answered"]) >= len(game["players"]):
                    await query.answer("Wrong 😭")
                    await _quiz_question(query, game)
                else:
                    await query.answer("Wrong 😭")
                return

        if typ == "mine" and data.endswith(":open"):
            if uid not in game["players"]:
                await query.answer("Pehle Join karo.", show_alert=True)
                return
            if not game.get("started"):
                await query.answer("Host ne abhi game start nahi ki. Pehle 2 players Join karein.", show_alert=True)
                return
            pos = int(data.rsplit(":", 1)[-1])
            if pos in game["opened"]:
                await query.answer("Ye box already open hai.")
                return
            game["opened"].add(pos)
            if pos in game["mines"]:
                await query.message.edit_text(
                    "💥 **BOOM! Game Over**\n\n" + _players_text(game["players"]) + "\n\nMine mil gayi 😭",
                    reply_markup=_mine_board(game, finished=True),
                )
                GAMES.pop(chat_id, None)
                return
            safe_total = 25 - len(game["mines"])
            if len(game["opened"]) >= safe_total:
                await query.message.edit_text(
                    "🏆 **MINESWEEPER WIN!**\n\n" + _players_text(game["players"]) + "\n\nSaari safe cells clear ho gayi! 🎉",
                    reply_markup=_mine_board(game, finished=True),
                )
                GAMES.pop(chat_id, None)
                return
            await query.answer(f"Safe! Neighbours: {_mine_count(pos, game['mines'])}")
            await query.message.edit_text(
                "💣 **Minesweeper 5×5**\n\nPlayers:\n" + _players_text(game["players"]) + "\n\nSafe box choose karo:",
                reply_markup=_mine_board(game),
            )


async def _ai_quiz_question(game):
    """Generate a fresh MCQ with Groq; fall back to an unused local question."""
    used = game.setdefault("used_questions", set())
    prompt = (
        "Create ONE fresh multiple-choice quiz question for a Telegram game. "
        "It must have exactly 4 options and exactly one correct answer. "
        "Keep it factual, unambiguous, family-safe, and medium difficulty. "
        "Question can be English or simple Roman Urdu/Hinglish. "
        "Do not repeat any previous question. Return ONLY valid JSON in this exact shape: "
        '{"question":"...","options":["...","...","...","..."],"answer":0}. '
        "answer is the zero-based index 0-3. "
        f"Previous questions to avoid: {list(used)[-8:]}"
    )
    if config.AI_ENABLED and config.AI_API_KEY:
        try:
            url = config.AI_BASE_URL.rstrip("/") + "/chat/completions"
            payload = {
                "model": config.AI_MODEL,
                "messages": [
                    {"role": "system", "content": "You generate reliable quiz questions only. Output JSON only."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 1.0,
                "max_completion_tokens": 220,
            }
            headers = {"Authorization": f"Bearer {config.AI_API_KEY}"}
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                raw_answer = response.json()["choices"][0]["message"]["content"].strip()
                raw_answer = re.sub(r"^\\`\\`\\`(?:json)?\\s*|\\s*\\`\\`\\`$", "", raw_answer, flags=re.I | re.S).strip()
                item = json.loads(raw_answer)
                q = str(item["question"]).strip()
                options = [str(x).strip() for x in item["options"]]
                answer = int(item["answer"])
                if (
                    q
                    and q not in used
                    and len(options) == 4
                    and all(options)
                    and len(set(x.casefold() for x in options)) == 4
                    and 0 <= answer < 4
                ):
                    used.add(q)
                    return q, options, answer
        except Exception as e:
            print(f"[GAME][QUIZ_AI] generation failed: {type(e).__name__}: {e}")

    available = [item for item in QUIZ_BANK if item[0] not in used]
    if not available:
        used.clear()
        available = QUIZ_BANK[:]
    q, options, answer = random.choice(available)
    used.add(q)
    return q, options, answer


async def _quiz_question(query, game):
    game["round"] += 1
    if game["round"] > 5:
        scores = sorted(((game["players"][p], s) for p, s in game["scores"].items()), key=lambda x: x[1], reverse=True)
        result = "\n".join(f"• {name}: {score}" for name, score in scores)
        winner = scores[0][0] if scores else "Nobody"
        await query.message.edit_text(f"🏆 **Quiz Finished!**\n\n{result}\n\nWinner: **{winner}**")
        GAMES.pop(query.message.chat.id, None)
        return
    q, options, answer = await _ai_quiz_question(game)
    game["question"] = (q, options, answer)
    game["answered"] = set()
    rows = [[_button(f"{chr(65+i)}. {option}", f"mg:quiz:ans:{game['round']}:{i}", QUIZ_ICON)] for i, option in enumerate(options)]
    await query.message.edit_text(
        f"🧠 **Round {game['round']}/5**\n\n{q}",
        reply_markup=InlineKeyboardMarkup(rows),
    )


@app.on_message(filters.command("games"))
async def games_help(client, message):
    await message.reply_text(
        "🎮 **HIMWARI GAME ZONE**\n\n"
        "✊ /rps — Rock Paper Scissors\n"
        "🃏 /highcard — High Card Battle\n"
        "🎲 /dicebattle — Dice Battle\n"
        "🧠 /quizbattle — Quiz Battle\n"
        "💣 /mines — Minesweeper 5×5\n\n"
        "📜 Complete rules: /gamerules\n"
        "Har game buttons se play hoti hai."
    )


@app.on_message(filters.command(["gamerules", "gamerule"]))
async def games_rules(client, message):
    await message.reply_text(
        "📜 **GAME RULES**\n\n"
        "🎮 **Common**\n"
        "• Minimum 2, maximum 3 players.\n"
        "• Command bhejne wala host automatically player 1 hai.\n"
        "• Baaki players **Join** button se enter honge.\n"
        "• Sirf host **Start/Cancel** kar sakta hai.\n"
        "• Ek user ek hi baar join kar sakta hai.\n\n"
        "✊ **RPS**\n"
        "• Rock > Scissors > Paper > Rock.\n"
        "• Sab players apni move choose karte hain.\n"
        "• Same/all-three moves = Draw.\n\n"
        "🃏 **High Card**\n"
        "• Har player ko random 2–A card milta hai.\n"
        "• Highest value winner; same highest value = tie.\n\n"
        "🎲 **Dice Battle**\n"
        "• Har player sirf ek baar Roll karta hai.\n"
        "• 1–6 mein highest roll winner.\n\n"
        "🧠 **Quiz Battle**\n"
        "• Total 5 rounds.\n"
        "• Pehla correct answer +1 point.\n"
        "• Highest score winner.\n\n"
        "💣 **Minesweeper**\n"
        "• 5×5 board mein 5 hidden mines.\n"
        "• 2–3 players shared board par safe cells open karte hain.\n"
        "• Mine select hui = 💥 BOOM + game over.\n"
        "• Saari 20 safe cells open = WIN.\n"
        "• BOOM button tumhara custom emoji ID use karta hai.\n\n"
        "⚠️ Active games memory mein hain; bot restart/redeploy par reset ho jayengi."
    )


__MODULE__ = "Mᴜʟᴛɪᴘʟᴀʏᴇʀ Gᴀᴍᴇs"
__HELP__ = """
/games — game list
/rps — Rock Paper Scissors
/highcard — High Card Battle
/dicebattle — Dice Battle
/quizbattle — Quiz Battle
/mines — Minesweeper
"""
