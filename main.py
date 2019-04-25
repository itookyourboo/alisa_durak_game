from card import *
from flask import Flask, request
import logging
import json
from random import shuffle, choice


HELP_TXT = '''Дурак - это карточная игра. В ней используется колода из 36 карт.
Каждая карта имеет масть (♥, ♣, ♦, ♠) и достоинство (6, 7, 8, 9, 10, В, Д, К, Т).
Карта высшего достоинства может покрыть любую карту низшего достоинства, если они одной масти.
В начале игры выбирается козырь - масть, обладающая особой силой, стоящая над другими.
Козырная карта может покрыть любую карту иной масти.

Мы играем в простого дурака - за один ход можно дать одну или несколько карт одного достоинства.
Ну что, поехали?'''
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
                sessionStorage[user_id]['trump'] = game_deck[-1]  # Не Дональд!
                sessionStorage[user_id]['trump'].set_trump()
                sessionStorage[user_id]['alice_cards'] = game_deck[:6]
                sessionStorage[user_id]['player_cards'] = sort_cards(game_deck[6:12])
                sessionStorage[user_id]['deck'] = game_deck[12:]
                sessionStorage[user_id]['on_table'] = {}   # В первом списке покрываемые, во втором кроющие
                sessionStorage[user_id]['player_gives'] = False
                sessionStorage[user_id]['covering_card'] = None
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
                res['response']['text'] = HELP_TXT
                res['response']['buttons'] = [
                    {
                        'title': 'Играть',
                        'hide': True
                    }
                ]
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
        if req['request']['original_utterance'].lower() == 'не добавлять' and game_info['on_table']:
            cover_cards(res, req)
            return 

        # TODO: добавить except IndexError для строки ниже
        card = Card(req['request']['command'][:-1], game_info['suits'][req['request']['command'][-1]])
        if card in game_info['player_cards']:
            if not game_info['on_table'] or list(game_info['on_table'])[0].equal(card):
                game_info['on_table'][card] = None
                game_info['player_cards'].remove(card)
                equal_cards = find_equals(list(game_info['on_table'])[0], game_info['player_cards'])
                # TODO: не отображать "добавить еще", когда у алисы меньше карт, чем игрок может дать
                if equal_cards and len(game_info['alice_cards']) > len(game_info['on_table']):
                    res['response']['text'] = 'Добавите еще карту?'
                    res['response']['buttons'] = [{'title': str(card), 'hide': True} for card in
                                                  equal_cards + ['Не добавлять']]
                else:
                    cover_cards(res, req)
        else:
            res['response']['text'] = 'Такой карты нет. Попробуйте еще раз.'
            res['response']['buttons'] = [{'title': str(card), 'hide': True} for card in
                                          (sort_cards(game_info['player_cards'])
                                           if not game_info['on_table'] else
                                           find_equals(list(game_info['on_table'])[0],
                                                       game_info['player_cards']) + ['Не добалять'])]

    else:
        if 'взять' in req['request']['nlu']['tokens']:
            game_info['player_cards'] += [i for item in game_info['on_table'].items() for i in item if i is not None]

            if take_new_cards(res, req, [game_info['alice_cards']]):
                return
            give_cards(res, req)
        elif 'сброс' in req['request']['nlu']['tokens']:
            game_info['player_cards'] += [card for card in game_info['on_table'].values() if card is not None]
            res['response']['text'] = ' '.join(map(str, game_info['on_table'])) + '\n' + 'Какую карту будете крыть?'
            res['response']['buttons'] = [{'title': str(card), 'hide': False} for card in
                                          [covering_c for covering_c, c in game_info['on_table'].items() if c is None]] + \
                                         [{'title': str(btn), 'hide': True} for btn in sort_cards(find_bigger(list(game_info['on_table'])[0],
                                                  game_info['player_cards'])) + ['Взять']]
        else:
            card = Card(req['request']['command'][:-1], game_info['suits'][req['request']['command'][-1]])
            if card in game_info['on_table']:
                game_info['covering_card'] = card
                res['response']['text'] = f'Выбрана карта {card}. Чем будете крыть?'
                res['response']['buttons'] = [{'title': str(c), 'hide': True} for c in
                                              sort_cards(find_bigger(card, game_info['player_cards'])) + ['Взять', 'Сброс']]
            elif card in game_info['player_cards']:
                if card.can_beat(game_info['covering_card']):
                    if game_info['on_table'][game_info['covering_card']] is not None:
                        game_info['player_cards'].append(game_info['on_table'][game_info['covering_card']])
                    game_info['on_table'][game_info['covering_card']] = card
                    game_info['player_cards'].remove(card)
                    game_info['covering_card'] = None
                    remain = [covering_c for covering_c, c in game_info['on_table'].items() if c is None]
                    if not remain:

                        res['response']['text'] = 'Бито. Ваш ход.'
                        game_info['player_gives'] = True
                        if take_new_cards(res, req,
                                       [game_info['alice_cards'], game_info['player_cards']]):
                            return
                        res['response']['buttons'] = [{'title': str(c), 'hide': True} for c in
                                                      sort_cards(game_info['player_cards'])]

                    elif len(remain) > 1:
                        res['response']['text'] = 'Какую дальше карту будете крыть?'
                        res['response']['buttons'] = [{'title': str(card), 'hide': False} for card in
                                                      remain] + [{'title': str(btn), 'hide': True} for btn in sort_cards(find_bigger(list(game_info['on_table'])[0],
                                                                                                                                     game_info['player_cards'])) + ['Взять']]
                    else:
                        game_info['covering_card'] = remain[0]
                        res['response']['text'] = f'Осталось покрыть {remain[0]}'
                        res['response']['buttons'] = [{'title': str(c), 'hide': True} for c in
                                                      sort_cards(find_bigger(remain[0], game_info['player_cards'])) + ['Взять']]
                else:
                    res['response']['text'] = f'Эта карта не может покрыть {game_info["covering_card"]}'
                    res['response']['buttons'] = [{'title': str(c), 'hide': True} for c in
                                                  sort_cards(find_bigger(game_info["covering_card"], game_info['player_cards'])) + ['Взять']]
            else:
                res['response']['text'] = 'Такой карты нет'
                if game_info['covering_card'] is None:
                    remain = [covering_c for covering_c, c in game_info['on_table'].items() if
                              c is None]
                    res['response']['buttons'] = [{'title': str(card), 'hide': False} for card in
                                                  remain] + [{'title': str(btn), 'hide': True} for btn in sort_cards(find_bigger(list(game_info['on_table'])[0],
                                                  game_info['player_cards'])) + ['Взять']]
                else:
                    res['response']['buttons'] = [{'title': str(c), 'hide': True} for c in
                                                  sort_cards(find_bigger(game_info['covering_card'], game_info['player_cards']))]


def give_cards(res, req):
    # TODO: не давать игроку больше карт, чем у него есть
    game_info = sessionStorage[req['session']['user_id']]
    min_card = min(game_info['alice_cards'])
    game_info['on_table'] = {key: None for key in find_equals(min_card, game_info['alice_cards'])}
    [game_info['alice_cards'].remove(card) for card in game_info['on_table']]
    res['response']['text'] = res['response'].get('text', '') + ' '.join(map(str, game_info['on_table'])) + '\n'
    if len(game_info['on_table']) > 1:
        res['response']['text'] += 'Какую карту будете крыть?'
        res['response']['buttons'] = [{'title': str(card), 'hide': False} for card in
                                      list(game_info['on_table'])] + [{'title': str(btn), 'hide': True} for btn in sort_cards(find_bigger(list(game_info['on_table'])[0],
                                                  game_info['player_cards'])) + ['Взять']]
    else:
        game_info['covering_card'] = list(game_info['on_table'])[0]
        
        res['response']['buttons'] = [{'title': str(c), 'hide': True} for c in
                                      sort_cards(find_bigger(list(game_info['on_table'])[0],
                                                  game_info['player_cards']))]

    if {'title': 'Взять', 'hide': True} not in res['response']['buttons']:
        res['response']['buttons'] += [{'title': 'Взять', 'hide': True}]
    game_info['player_gives'] = False


def cover_cards(res, req):
    # Функция будет крыть карты игрока и вызывать give_cards или брать карты
    game_info = sessionStorage[req['session']['user_id']]
    for covering_card in game_info['on_table']:
        bigger_cards = [c for c in game_info['alice_cards'] if c.can_beat(covering_card)]
        if bigger_cards:
            card = min(bigger_cards)
            game_info['on_table'][covering_card] = card
            game_info['alice_cards'].remove(card)
        else:
            res['response']['text'] = 'Беру'
            game_info['alice_cards'] += [i for item in game_info['on_table'].items() for i in item
                                          if i is not None]
            if take_new_cards(res, req, [game_info['player_cards']]):
                return
            res['response']['buttons'] = [{'title': str(c), 'hide': True} for c in
                                          sort_cards(game_info['player_cards'])]
            game_info['player_gives'] = True
            return
    res['response']['text'] = 'Покрыла: ' + ' '.join(map(str, game_info['on_table'].values())) + '\n'
    if take_new_cards(res, req, [game_info['player_cards'], game_info['alice_cards']]):
        return
    give_cards(res, req)


def take_new_cards(res, req, takers):
    game_info = sessionStorage[req['session']['user_id']]
    for taker in takers:
        number_of_cards = max(0, 6 - len(taker))
        taker += game_info['deck'][:number_of_cards]
        game_info['deck'] = game_info['deck'][number_of_cards:]
    game_info['on_table'].clear()
    game_info['covering_card'] = None
    return check_win(res, req)


def check_win(res, req):
    game_info = sessionStorage[req['session']['user_id']]
    if game_info['alice_cards'] and game_info['player_cards']:
        return False
    if not (game_info['alice_cards'] or game_info['player_cards']):
        res['response']['text'] = 'Ничья'
    elif not game_info['alice_cards']:
        res['response']['text'] = 'Я победила'
    elif not game_info['player_cards']:
        res['response']['text'] = 'Вы победили'
    res['response']['end_session'] = True
    # TODO: отобразить кнопку "Еще партию!"
    return True


def find_equals(card, cards_arr):
    return [c for c in cards_arr if card.equal(c)]


def find_bigger(card, cards_arr):
    return cards_arr
    # return [c for c in cards_arr if c.can_beat(card)]


def sort_cards(cards_arr):
    return sorted(cards_arr, key=lambda x: (x.is_trump(), x.get_value_index()))


if __name__ == '__main__':
    app.run()
