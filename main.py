from card import *
from flask import Flask, request
import logging
import json
from random import shuffle, choice

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
sessionStorage = {}


@app.route('/post', methods=['POST'])
def main():
    logging.info('Request: %r', request.json)
    response = {
        'session': request.json['session'],
        'version': request.json['version'],
        'response': {
            'end_session': False
        }
    }
    handle_dialog(response, request.json)
    logging.info('Response: %r', response)
    return json.dumps(response)


def handle_dialog(res, req):
    user_id = req['session']['user_id']
    if req['session']['new']:
        res['response']['text'] = 'Привет. Я могу сыграть с тобой в "Дурака". Выбери действие'
        res['response']['buttons'] = [
            {
                'title': 'Играть',
            },
            {
                'title': 'Помощь',
            }
        ]
        sessionStorage[user_id] = {
            'game_started': False
            # здесь информация о том, что пользователь начал игру. По умолчанию False
        }
    else:
        # У нас уже есть имя, и теперь мы ожидаем ответ на предложение сыграть.
        # В sessionStorage[user_id]['game_started'] хранится True или False в зависимости от того,
        # начал пользователь игру или нет.
        if not sessionStorage[user_id]['game_started']:
            # игра не начата, значит мы ожидаем ответ на предложение сыграть.
            if 'играть' in req['request']['nlu']['tokens']:
                sessionStorage[user_id]['game_started'] = True
                game_suits = [Suit(s) for s in SUITS]

                game_deck = [Card(v, s) for v in VALUES for s in game_suits]
                shuffle(game_deck)
                sessionStorage[user_id]['alice_cards'] = game_deck[:6]
                sessionStorage[user_id]['player_cards'] = game_deck[6:12]
                sessionStorage[user_id]['deck'] = game_deck[12:]
                sessionStorage[user_id]['trump'] = game_deck[-1]  # Не Дональд!
                sessionStorage[user_id]['trump'].set_trump()
                alice_trump, sessionStorage[user_id]['is_humane'] = is_humane_first(
                    sessionStorage[user_id]['alice_cards'], sessionStorage[user_id]['player_cards'])
                res['response']['text'] = f'Козырь: {sessionStorage[user_id]["trump"]}\n' \
                    f'Минимальный козырь Алисы: {alice_trump}\n' \
                    f'is_humane: {sessionStorage[user_id]["is_humane"]}'
                res['response']['buttons'] = [{'title': str(card)} for card in sessionStorage[user_id]['player_cards']]
                return
                # play_game(res, req)
            elif 'помощь' in req['request']['nlu']['tokens']:
                res['response']['text'] = '* Сюда придумать помощь *'
            else:
                res['response']['text'] = 'Не поняла ответа!'
                res['response']['buttons'] = [
                    {
                        'title': 'Играть',
                    },
                    {
                        'title': 'Помощь',
                    }
                ]
        else:
            play_game(res, req)


def is_humane_first(alice_cards, player_cards):
    # Возвращает ("минимальный козырь врага", "ходит ли игрок первым, bool")
    alice_trumps = list(filter(lambda card: card.is_trump(), alice_cards))
    player_trumps = list(filter(lambda card: card.is_trump(), player_cards))
    if alice_trumps:
        alice_min_trumps = min(alice_trumps)
        return alice_min_trumps, alice_min_trumps > min(player_trumps) if player_trumps else False
    elif player_trumps:
        return None, True
    else:
        alice_max_card, player_max_card = max(alice_cards), max(player_cards)
        if alice_max_card == player_max_card:
            return alice_max_card, choice([False, True])
        return alice_max_card, alice_max_card < player_max_card


def play_game(res, req):
    user_id = req['session']['user_id']



if __name__ == '__main__':
    app.run()
# shuffle(cards)
#
# p1 = cards[:6]
# p2 = cards[6:12]
# cards = cards[12:]
#
# trump = cards[-1].get_suit()
#
# print('Козырь', suits[trump])
# print('p1', *sorted(p1))
# print('p2', *sorted(p2))
