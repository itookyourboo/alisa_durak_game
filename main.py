from card import *
from flask import Flask, request
import logging
import json
from random import shuffle, choice
from copy import deepcopy

HELP_TXT = '''Дурак - это карточная игра. В ней используется колода из 36 карт.
Каждая карта имеет масть (♥, ♣, ♦, ♠) и достоинство (6, 7, 8, 9, 10, В, Д, К, Т).
Карта высшего достоинства может покрыть любую карту низшего достоинства, если они одной масти.
В начале игры выбирается козырь - масть, обладающая особой силой, стоящая над другими.
Козырная карта может покрыть любую карту иной масти.

Мы играем в простого дурака - за один ход можно дать одну или несколько карт одного достоинства.
Ну что, поехали?'''

WHAT_CAN_YOU_DO = 'Я могу сыграть с тобой в "Дурака". Мой интеллект позволяет мне делать ' \
                  'логичные ходы - крыть и давать карты.'
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
        res['response']['text'] = 'Привет! Давай сыграем в "Дурака". ' \
                                  'Для управления используй кнопки. Выбери действие'
        res['response']['buttons'] = [
            {
                'title': 'Играть',
                'hide': True
            },
            {
                'title': 'Выход',
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
        if any(word in req['request']['nlu']['tokens'] for word in ['помощь', 'правила', 'помоги']):
            res['response']['text'] = HELP_TXT
        # выйти из игры
        elif any(word in req['request']['nlu']['tokens'] for word in ['умеешь', 'делать', 'можешь',
                                                                      'что']):
            res['response']['text'] = WHAT_CAN_YOU_DO
        elif any(word in req['request']['nlu']['tokens'] for word in ['выход', 'хватит', 'пока',
                                                                      'свидания', 'стоп', 'нет',
                                                                      'выключи', 'останови']):
            res['response']['text'] = 'Надеюсь, было весело. Пока.'
            res['response']['end_session'] = True
        elif not sessionStorage[user_id]['game_started']:
            # игра не начата, значит мы ожидаем ответ на предложение сыграть.
            if any(word in req['request']['nlu']['tokens'] for word in ['играть', 'давай', 'да',
                                                                        'поехали', 'ладно', 'старт',
                                                                        'ок', 'хорошо', 'запуск',
                                                                        'запускай']):
                # раздача карт

                sessionStorage[user_id]['game_started'] = True
                sessionStorage[user_id]['suits'] = {s: Suit(s) for s in SUITS}

                game_deck = [Card(v, s) for v in VALUES
                             for s in sessionStorage[user_id]['suits'].values()]
                shuffle(game_deck)
                sessionStorage[user_id]['trump'] = game_deck[-1]  # Не Дональд!
                sessionStorage[user_id]['trump'].set_trump()
                sessionStorage[user_id]['alice_cards'] = game_deck[:6]
                sessionStorage[user_id]['player_cards'] = sort_cards(game_deck[6:12])
                sessionStorage[user_id]['deck'] = game_deck[12:]
                sessionStorage[user_id]['on_table'] = {}
                sessionStorage[user_id]['player_gives'] = False
                sessionStorage[user_id]['covering_card'] = None
                alice_trump, sessionStorage[user_id]['player_gives'] = is_humane_first(
                    sessionStorage[user_id]['alice_cards'], sessionStorage[user_id]['player_cards'])

                res['response']['text'] = 'Козырь: {}\n{}, {}.\n'.format(
                    sessionStorage[user_id]["trump"], alice_trump,
                    ("вы ходите" if sessionStorage[user_id]["player_gives"] else
                     "поэтому я хожу первой"))
                res['response']['buttons'] = [{'title': str(card), 'hide': True} for card in
                                              sessionStorage[user_id]['player_cards']]
                if not sessionStorage[user_id]['player_gives']:
                    give_cards(res, req)

            # показать игроку сообщение с помощью
            else:
                res['response']['text'] = 'Не поняла ответа!'
        else:
            if any(word in req['request']['nlu']['tokens'] for word in ['козырь', 'козырная',
                                                                        'какой', 'какая']):
                res['response']['text'] = 'Козырем является ' + str(
                    sessionStorage[user_id]['trump'])
            else:
                play_game(res, req)

    add_default_buttons(res, user_id)


def add_default_buttons(res, user_id):
    if 'buttons' in res['response']:
        sessionStorage[user_id]['last_buttons'] = deepcopy(res['response']['buttons'])
    else:
        res['response']['buttons'] = deepcopy(sessionStorage[user_id]['last_buttons'])
    if sessionStorage[user_id]['game_started']:
        if {'title': 'Козырь', 'hide': True} not in res['response']['buttons']:
            res['response']['buttons'].append({'title': 'Козырь', 'hide': True})
        if not sessionStorage[user_id]['player_gives']:
            if len(sessionStorage[user_id]['on_table']) > 1:
                res['response']['buttons'].append({'title': 'Сброс', 'hide': True})
            res['response']['buttons'].append({'title': 'Взять', 'hide': True})

    for button in ['Помощь', 'Что ты умеешь?']:
        button_dict = {'title': button, 'hide': True}
        if button_dict not in res['response']['buttons']:
            res['response']['buttons'].append(button_dict)


def is_humane_first(alice_cards, player_cards):
    # Возвращает ("минимальный козырь врага", "ходит ли игрок первым, bool")
    alice_trumps = list(filter(lambda card: card.is_trump(), alice_cards))
    player_trumps = list(filter(lambda card: card.is_trump(), player_cards))
    if alice_trumps:
        alice_min_trumps = min(alice_trumps)
        return f'Мой самый маленький козырь - {alice_min_trumps}', \
               alice_min_trumps > min(player_trumps) if player_trumps else False
    else:
        alice_max_card = max(alice_cards)
        if player_trumps:
            return f'У меня нет козырей', True
        player_max_card = max(player_cards)
        if alice_max_card == player_max_card:
            return f'Похоже, у нас нет козырей, а самые большие карты одинаковые. Я подкинула ' \
                       f'монетку, выпал{choice("а решка", " орел")}', choice([False, True])
        return f'Похоже, у нас нет козырей. Моя самая большая карта - {alice_max_card}', \
               alice_max_card < player_max_card


def play_game(res, req):
    game_info = sessionStorage[req['session']['user_id']]
    if game_info['player_gives']:
        # Тут игрок кидает карты Алисе
        if (req['request']['original_utterance'].lower() == 'не добавлять' or 'не' in
            req['request']['original_utterance'].lower()) and game_info['on_table']:
            cover_cards(res, req)
            return
        try:
            card = Card(req['request']['command'][:-1],
                        game_info['suits'][req['request']['command'][-1]])
        except Exception:
            card = None
        if card in game_info['player_cards']:
            if not game_info['on_table'] or list(game_info['on_table'])[0].equal(card):
                game_info['on_table'][card] = None
                game_info['player_cards'].remove(card)
                equal_cards = find_equals(list(game_info['on_table'])[0], game_info['player_cards'])
                # добавление нескольких карт
                if equal_cards and len(game_info['alice_cards']) > len(game_info['on_table']):
                    res['response']['text'] = 'Добавите еще карту?'
                    res['response']['buttons'] = [{'title': str(card), 'hide': True} for card in
                                                  sort_cards(equal_cards) + ['Не добавлять']]
                else:
                    cover_cards(res, req)
        else:
            res['response']['text'] = 'Такой карты нет. Попробуйте еще раз.'

    else:
        # взятие карт игроком
        if any(word in req['request']['nlu']['tokens'] for word in ['взять', 'взял', 'взяла', 'нет',
                                                                    'беру', 'нечем', 'забрать',
                                                                    'забрал', 'забрала']):
            game_info['player_cards'] += [i for item in game_info['on_table'].items() for i in item
                                          if i is not None]

            if take_new_cards(res, req, [game_info['alice_cards']]):
                return
            give_cards(res, req)
        # сброс карт
        elif any(word in req['request']['nlu']['tokens'] for word in ['сброс', 'снять', 'вернуть',
                                                                      'сбрось', 'верни', 'отменить',
                                                                      'сними', 'отмена', 'назад']):
            if len(game_info['on_table']) < 2:
                res['response']['text'] = 'Нельзя выполнить сброс\n' + \
                                          str(game_info['covering_card'])
            else:

                for card in game_info['on_table']:
                    if game_info['on_table'][card] is not None:
                        game_info['player_cards'].append(game_info['on_table'][card])
                        game_info['on_table'][card] = None
                game_info['covering_card'] = None
                static_buttons = [{'title': str(card), 'hide': False}
                                  for card in game_info['on_table']]
                res['response']['text'] = ' '.join(map(str, game_info['on_table'])) + \
                                          '\nКакую карту будете крыть?'
                res['response']['buttons'] = static_buttons + \
                                             [{'title': str(btn), 'hide': True} for btn in
                                              sort_cards(find_bigger(list(game_info['on_table'])[0],
                                                                     game_info['player_cards']))]
        else:
            try:
                card = Card(req['request']['command'][:-1],
                            game_info['suits'][req['request']['command'][-1]])
            except Exception:
                card = None

            # реализация крытия карт игроком

            if card in game_info['on_table']:
                game_info['covering_card'] = card
                res['response']['text'] = f'Выбрана карта {card}. Чем будете крыть?'
                res['response']['buttons'] = [{'title': str(c), 'hide': True} for c in
                                              sort_cards(find_bigger(card,
                                                                     game_info['player_cards']))]
            elif card in game_info['player_cards'] and game_info['covering_card'] is not None:
                if card.can_beat(game_info['covering_card']):
                    if game_info['on_table'][game_info['covering_card']] is not None:
                        game_info['player_cards'].append(game_info['on_table']
                                                         [game_info['covering_card']])
                    game_info['on_table'][game_info['covering_card']] = card
                    game_info['player_cards'].remove(card)
                    game_info['covering_card'] = None
                    remain = [covering_c for covering_c, c in game_info['on_table'].items()
                              if c is None]
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
                        res['response']['buttons'] = [{'title': str(card), 'hide': False}
                                                      for card in remain] + \
                                                     [{'title': str(btn), 'hide': True} for btn in
                                                      sort_cards(find_bigger(list(
                                                          game_info['on_table'])[0],
                                                                             game_info[
                                                                                 'player_cards']))]
                    else:
                        game_info['covering_card'] = remain[0]
                        res['response']['text'] = f'Осталось покрыть {remain[0]}'
                        res['response']['buttons'] = [{'title': str(c), 'hide': True}
                                                      for c in sort_cards(
                                find_bigger(remain[0], game_info['player_cards']))]
                else:
                    res['response']['text'] = f'Эта карта не может покрыть ' \
                        f'{game_info["covering_card"]}'
            else:
                res['response']['text'] = 'Такой карты нет'


def give_cards(res, req):
    # ход Алисы под игрока
    game_info = sessionStorage[req['session']['user_id']]
    min_card = min(game_info['alice_cards'])
    equals = find_equals(min_card, game_info['alice_cards'])
    deck_len = len(game_info['deck'])
    p_len = len(game_info['player_cards'])
    # тактика игры меняется в зависимости от продолжительности игры и стоимости минимальной карты
    if len(equals) == 1:
        game_info['on_table'] = {equals[0]: None}
    elif deck_len > 6 and min_card.get_cost() <= 0:
        game_info['on_table'] = {key: None for key in equals if not key.is_trump() or
                                 choice([True, False]) and not key.is_trump()}
    elif deck_len <= 6 and min_card.get_cost() <= 0:
        game_info['on_table'] = {key: None for key in sort_cards(equals)[:min(p_len, len(equals))]}
    elif deck_len > 6 and min_card.get_cost() > 0:
        game_info['on_table'] = {key: None for key in equals if not key.is_trump()}
    else:
        cards = list(filter(lambda x: not x.is_trump() or
                                      choice([True, False]) and not x.is_trump(), equals))
        game_info['on_table'] = {key: None for key in sort_cards(cards)[:min(p_len, len(cards))]}

    [game_info['alice_cards'].remove(card) for card in game_info['on_table']]
    res['response']['text'] = res['response'].get('text', '') + ' '.join(
        map(str, game_info['on_table'])) + '\n'
    if len(game_info['on_table']) > 1:
        res['response']['text'] += 'Какую карту будете крыть?'
        res['response']['buttons'] = [{'title': str(card), 'hide': False}
                                      for card in list(game_info['on_table'])] + \
                                     [{'title': str(btn), 'hide': True} for btn in sort_cards(
                                         find_bigger(list(game_info['on_table'])[0],
                                                     game_info['player_cards']))]
    else:
        game_info['covering_card'] = list(game_info['on_table'])[0]

        res['response']['buttons'] = [{'title': str(c), 'hide': True} for c in
                                      sort_cards(find_bigger(list(game_info['on_table'])[0],
                                                             game_info['player_cards']))]

    # res['response']['buttons'] += [{'title': 'Взять', 'hide': True}]
    game_info['player_gives'] = False


def cover_cards(res, req):
    # Функция будет крыть карты игрока и вызывать give_cards или брать карты
    game_info = sessionStorage[req['session']['user_id']]
    for covering_card in game_info['on_table']:
        bigger_cards = [c for c in game_info['alice_cards'] if c.can_beat(covering_card)]
        if bigger_cards:
            min_big = min(bigger_cards)
            # Тактика игры меняется в зависимости от продолжительности игры
            if len(game_info['deck']) > 6:
                # если есть несколько вариантов покрыть, то дельта стоимостей должна быть <= 120
                if len(bigger_cards) > 1 and min_big.get_cost() <= covering_card.get_cost() + 120:
                    card = min_big
                    game_info['on_table'][covering_card] = card
                    game_info['alice_cards'].remove(card)
                # если один - <= 100
                elif len(bigger_cards) == 1 and min_big.get_cost() <= covering_card.get_cost() \
                        + 100:
                    card = min_big
                    game_info['on_table'][covering_card] = card
                    game_info['alice_cards'].remove(card)
                # иначе берём
                else:
                    res['response']['text'] = 'Беру'
                    game_info['alice_cards'] += [i for item in game_info['on_table'].items()
                                                 for i in item if i is not None]
                    if take_new_cards(res, req, [game_info['player_cards']]):
                        return
                    res['response']['buttons'] = [{'title': str(c), 'hide': True} for c in
                                                  sort_cards(game_info['player_cards'])]
                    game_info['player_gives'] = True
                    return
            # если конец игры, отбиваемся любыми средствами
            else:
                card = min_big
                game_info['on_table'][covering_card] = card
                game_info['alice_cards'].remove(card)
        # если нечем отбиваться, берём карты
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
    res['response']['text'] = 'Покрыла: ' + ' '.join(map(str, game_info['on_table'].values())) + \
                              '\n'
    if take_new_cards(res, req, [game_info['player_cards'], game_info['alice_cards']]):
        return
    give_cards(res, req)


def take_new_cards(res, req, takers):
    # взять карты из колоды
    game_info = sessionStorage[req['session']['user_id']]
    for taker in takers:
        number_of_cards = max(0, 6 - len(taker))
        taker += game_info['deck'][:number_of_cards]
        game_info['deck'] = game_info['deck'][number_of_cards:]
    game_info['on_table'].clear()
    game_info['covering_card'] = None
    return check_win(res, req)


def check_win(res, req):
    # проверка на конец игры. Определение победителя
    game_info = sessionStorage[req['session']['user_id']]
    if game_info['alice_cards'] and game_info['player_cards']:
        return False
    res['response']['text'] = res['response'].get('text', '').replace('Бито. Ваш ход.', 'Бито.')
    if not (game_info['alice_cards'] or game_info['player_cards']):
        res['response']['text'] += '\nНичья!'
    elif not game_info['alice_cards']:
        res['response']['text'] += '\nЯ победила!'
    elif not game_info['player_cards']:
        res['response']['text'] += '\nВы победили!'
    res['response']['text'] += '\nСыграем еще раз?'
    res['response']['buttons'] = [
        {
            'title': 'Играть',
            'hide': True
        },
        {
            'title': 'Выход',
            'hide': True
        }
    ]
    game_info['game_started'] = False
    return True


def find_equals(card, cards_arr):
    # возвращает массив карт с одинаковым достоинством
    return [c for c in cards_arr if card.equal(c)]


def find_bigger(card, cards_arr):
    # заглушка, так как эта функция использовалась везде, но потом потеряла актуальность)
    return cards_arr
    # return [c for c in cards_arr if c.can_beat(card)]


def sort_cards(cards_arr):
    # сортировка карт
    return sorted(cards_arr, key=lambda x: (x.is_trump(), x.get_value_index()))


def normalize_tts(res):
    res['response']['tts'] = res['response']['text']
    for comb in combs:
        if comb not in res['response']['tts']:
            continue
        res['response']['tts'] = res['response']['tts'].replace(comb, combs[comb])


if __name__ == '__main__':
    app.run()
