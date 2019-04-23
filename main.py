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
                'hide': True
            },
            {
                'title': 'Помощь',
                'hide': True
            }
        ]
        sessionStorage[user_id] = {
            'game_started': False
            # здесь информация о том, что пользователь начал игру. По умолчанию False
        }
    else:
        # В sessionStorage[user_id]['game_started'] хранится True или False в зависимости от того,
        # начал пользователь игру или нет.
        if not sessionStorage[user_id]['game_started']:
            # игра не начата, значит мы ожидаем ответ на предложение сыграть.
            if 'играть' in req['request']['nlu']['tokens']:
                sessionStorage[user_id]['game_started'] = True
                sessionStorage[user_id]['suits'] = {s: Suit(s) for s in SUITS}

                game_deck = [Card(v, s) for v in VALUES for s in sessionStorage[user_id]['suits'].values()]
                shuffle(game_deck)
                sessionStorage[user_id]['alice_cards'] = game_deck[:6]
                sessionStorage[user_id]['player_cards'] = game_deck[6:12]
                sessionStorage[user_id]['deck'] = game_deck[12:]
                sessionStorage[user_id]['trump'] = game_deck[-1]  # Не Дональд!
                sessionStorage[user_id]['trump'].set_trump()
                sessionStorage[user_id]['on_table'] = [[], []]   # В первом списке покрываемые, во втором кроющие
                sessionStorage[user_id]['player_gives'] = False
                alice_trump, sessionStorage[user_id]['player_gives'] = is_humane_first(
                    sessionStorage[user_id]['alice_cards'], sessionStorage[user_id]['player_cards'])

                res['response']['text'] = f'Козырь: {sessionStorage[user_id]["trump"]}\n' \
                    f'{alice_trump}, ' \
                    f'{"вы ходите" if sessionStorage[user_id]["player_gives"] else "поэтому я хожу первой"}.\n'
                res['response']['buttons'] = [{'title': str(card), 'hide': True} for card in
                                              sessionStorage[user_id]['player_cards']]
                if not sessionStorage[user_id]['player_gives']:
                    give_cards(res, req)
            elif 'помощь' in req['request']['nlu']['tokens']:
                res['response']['text'] = '* Сюда придумать помощь *'
            else:
                res['response']['text'] = 'Не поняла ответа!'
                res['response']['buttons'] = [
                    {
                        'title': 'Играть',
                        'hide': True
                    },
                    {
                        'title': 'Помощь',
                        'hide': True
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
        return f'Мой самый маленький козырь - {alice_min_trumps}', alice_min_trumps > min(player_trumps) if player_trumps else False
    else:
        alice_max_card = max(alice_cards)
        if player_trumps:
            return f'У меня нет козырей', True
        player_max_card = max(player_cards)
        if alice_max_card == player_max_card:
            return f'Похоже, у нас нет козырей, а самые большие карты одинаковые. Я подкинула монетку, ' \
                       f'выпал{choice("а решка", " орел")}', choice([False, True])
        return f'Похоже, у нас нет козырей. Моя самая большая карта - {alice_max_card}', alice_max_card < player_max_card


def play_game(res, req):
    game_info = sessionStorage[req['session']['user_id']]
    if game_info['player_gives']:
        # Тут игрок кидает карты Алисе
        if req['request']['original_utterance'].lower() == 'не добавлять' and game_info['on_table'][0]:
            cover_cards(res, req)
            return 

        # TODO: добавить except IndexError для строки ниже
        card = Card(req['request']['command'][0], game_info['suits'][req['request']['command'][1]])
        if card in game_info['player_cards']:
            if not game_info['on_table'][0] or game_info['on_table'][0][0].equal(card):
                game_info['on_table'][0].append(card)
                game_info['player_cards'].remove(card)
                equal_cards = find_equals(game_info['on_table'][0][0], game_info['player_cards'])
                if equal_cards:
                    res['response']['text'] = 'Добавите еще карту?'
                    res['response']['buttons'] = [{'title': str(card), 'hide': True} for card in
                                                  equal_cards + ['Не добавлять']]
                else:
                    cover_cards(res, req)
        else:
            res['response']['text'] = 'Такой карты нет. Попробуйте еще раз.'
            res['response']['buttons'] = [{'title': str(card), 'hide': True} for card in
                                          (game_info['player_cards']
                                           if not game_info['on_table'][0] else
                                           find_equals(game_info['on_table'][0][0],
                                                       game_info['player_cards']) + ['Не добалять'])]

    else:
        # Тут игрок покрывает карты Алисы
        res['response']['text'] = 'Ветка "игрок кроет"'



def give_cards(res, req):
    game_info = sessionStorage[req['session']['user_id']]
    min_card = min(game_info['alice_cards'])
    game_info['on_table'][0] = find_equals(min_card, game_info['alice_cards'])
    [game_info['alice_cards'].remove(card) for card in game_info['on_table'][0]]
    res['response']['text'] += ' '.join(map(str, game_info['on_table'][0])) + '\n'
    res['response']['buttons'] = [{'title': str(card), 'hide': True} for card in
                                  game_info['player_cards']]
    game_info['player_gives'] = False


def cover_cards(res, req):
    # Функция будет крыть карты игрока и вызывать give_cards или брать карты
    res['response']['text'] = 'Пока не умею крыть.'


def find_equals(card, cards_arr):
    return [c for c in cards_arr if card.equal(c)]


if __name__ == '__main__':
    app.run()
