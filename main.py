from card import *
from flask import Flask, request
import logging
import json
from random import shuffle, choice
from copy import deepcopy
from strings import *

MODE_SIMPLE = 'SIMPLE'
MODE_FLUSH = 'FLUSH'
MODES = {
    MODE_FLUSH: ('подкидной', 'подкидного'),
    MODE_SIMPLE: ('простой', 'простого')
    # 'TRANSFERABLE': ('переводной', 'в переводного'),
    # 'TWO_TRUMPS': ('двойной козырь', 'с двойным козырем', 'два козыря', 'с двумя козырями')
}
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
    req = request.json
    normalize_command(req)
    logging.info('command = ' + req['request']['command'])
    handle_dialog(response, req)
    logging.info('Response: %r', response)
    normalize_tts(response)
    return json.dumps(response)


def handle_dialog(res, req):
    user_id = req['session']['user_id']
    if req['session']['new']:
        answer(res, HELLO, HELLO_TTS)
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
            answer(res, HELP_TXT, HELP_TXT_TTS)
        # выйти из игры
        elif any(word in req['request']['nlu']['tokens'] for word in ['умеешь', 'делать', 'можешь',
                                                                      'что']):
            res['response']['text'] = WHAT_CAN_YOU_DO
        elif any(word in req['request']['nlu']['tokens'] for word in ['выход', 'хватит', 'пока',
                                                                      'свидания', 'стоп', 'нет',
                                                                      'выключи', 'останови']):
            answer(res, BYE, BYE_TTS)
            res['response']['end_session'] = True
        elif not sessionStorage[user_id]['game_started']:
            if not sessionStorage[user_id].get('choose_mode', False):
                # игра не начата, значит мы ожидаем ответ на предложение сыграть.
                if any(word in req['request']['nlu']['tokens'] for word in ['играть', 'давай', 'да',
                                                                            'поехали', 'ладно', 'старт',
                                                                            'ок', 'хорошо', 'запуск',
                                                                            'запускай']):
                    answer(res, CHOOSE_GAMEMODE, CHOOSE_GAMEMODE_TTS)
                    sessionStorage[user_id]['choose_mode'] = True
                else:
                    answer(res, NOT_UNDERSTANDABLE, NOT_UNDERSTANDABLE_TTS)
            elif sessionStorage[user_id]['choose_mode'] and not sessionStorage[user_id].get('mode', False):
                for mode in MODES:
                    if any(word in req['request']['nlu']['tokens'] for word in MODES[mode]):
                        sessionStorage[user_id]['choose_mode'] = False
                        sessionStorage[user_id]['game_started'] = True
                        sessionStorage[user_id]['mode'] = mode

                        distribution(user_id, res, req)
                        return
                res['response']['text'] = NO_SUCH_MODE
                res['response']['tts'] = NO_SUCH_MODE_TTS
                answer(res, NO_SUCH_MODE, NO_SUCH_MODE_TTS)
        else:
            if any(word in req['request']['nlu']['tokens'] for word in ['козырь', 'козырная',
                                                                        'какой', 'какая']):
                res['response']['text'] = f"{TRUMP} - {str(sessionStorage[user_id]['trump'])}."
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
    else:
        if sessionStorage[user_id].get('choose_mode', False):
            res['response']['buttons'] = [
                {
                    'title': MODES[mode][0].capitalize(),
                    'hide': True
                } for mode in MODES
            ]

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
        return f'{THE_SMALLEST_TRUMP} - {alice_min_trumps}', \
               alice_min_trumps > min(player_trumps) if player_trumps else False
    else:
        alice_max_card = max(alice_cards)
        if player_trumps:
            return NO_TRUMP, True
        player_max_card = max(player_cards)
        if alice_max_card == player_max_card:
            return f'{COIN}, выпал{choice("а решка", " орел")}.', choice([False, True])
        return f'{NO_TRUMPS} - {alice_max_card}', alice_max_card < player_max_card


def play_game(res, req):
    game_info = sessionStorage[req['session']['user_id']]
    if game_info['player_gives']:
        # Тут игрок кидает карты Алисе
        if req['request']['original_utterance'].lower() in BITO \
                and game_info['mode'] == MODE_FLUSH:
            cover_cards(res, req)
            return
        if (req['request']['original_utterance'].lower() == 'не добавлять' or 'не' in
            req['request']['original_utterance'].lower()) and game_info['on_table']:
            cover_cards(res, req)
            return
        try:
            # command = req['request']['command']
            command = req['request']['original_utterance']
            card = Card(command[:-1],
                        game_info['suits'][command[-1]])
        except Exception:
            card = None

        if card in game_info['player_cards']:
            flush_condition = not game_info['table_cash']
            if (game_info['mode'] == MODE_SIMPLE and (not game_info['on_table'] or list(game_info['on_table'])[0].equal(card))) or \
                    (game_info['mode'] == MODE_FLUSH and (flush_condition or can_flush(game_info['table_cash'], card))):
                game_info['on_table'][card] = None
                game_info['table_cash'][card] = None
                game_info['player_cards'].remove(card)
                equal_cards = find_equals(list(game_info['on_table'])[0], game_info['player_cards'])
                # добавление нескольких карт
                if equal_cards and len(game_info['alice_cards']) > len(game_info['on_table']):
                    answer(res, WILL_YOU_ADD, WILL_YOU_ADD_TTS)
                    res['response']['buttons'] = [{'title': str(card), 'hide': True} for card in
                                                  sort_cards(equal_cards) + ['Не добавлять']]
                else:
                    cover_cards(res, req)
            else:
                answer(res, CANT_ADD, CANT_ADD_TTS)
        else:
            answer(res, NO_SUCH_CARD_AGAIN, NO_SUCH_CARD_AGAIN_TTS)

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
                res['response']['text'] = CANT_RESET + '\n' + str(game_info['covering_card'])
            else:

                for card in game_info['on_table']:
                    if game_info['on_table'][card] is not None:
                        game_info['player_cards'].append(game_info['on_table'][card])
                        game_info['on_table'][card] = None
                game_info['covering_card'] = None
                static_buttons = [{'title': str(card), 'hide': False}
                                  for card in game_info['on_table']]
                res['response']['text'] = ' '.join(map(str, game_info['on_table'])) + \
                                          '\n' + WHICH_CARD
                res['response']['buttons'] = static_buttons + \
                                             [{'title': str(btn), 'hide': True} for btn in
                                              sort_cards(find_bigger(list(game_info['on_table'])[0],
                                                                     game_info['player_cards']))]
        else:
            try:
                # command = req['request']['command']
                command = req['request']['original_utterance']
                card = Card(command[:-1],
                            game_info['suits'][command[-1]])
            except Exception:
                card = None

            # реализация крытия карт игроком
            if card in game_info['on_table']:
                game_info['covering_card'] = card
                res['response']['text'] = f'{CHOOSED_CARD} {card}. {WHAT_TO_COVER}'
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
                        res['response']['text'] = BITO_0
                        game_info['player_gives'] = True
                        if take_new_cards(res, req,
                                          [game_info['alice_cards'], game_info['player_cards']]):
                            return
                        res['response']['buttons'] = [{'title': str(c), 'hide': True} for c in
                                                      sort_cards(game_info['player_cards'])]

                    elif len(remain) > 1:
                        answer(res, WHICH_CARD_THEN, WHICH_CARD_THEN_TTS)
                        res['response']['buttons'] = [{'title': str(card), 'hide': False}
                                                      for card in remain] + \
                                                     [{'title': str(btn), 'hide': True} for btn in
                                                      sort_cards(find_bigger(list(
                                                          game_info['on_table'])[0],
                                                                             game_info[
                                                                                 'player_cards']))]
                    else:
                        game_info['covering_card'] = remain[0]
                        res['response']['text'] = f'{CARD_LEFT} {remain[0]}.'
                        res['response']['buttons'] = [{'title': str(c), 'hide': True}
                                                      for c in sort_cards(
                                find_bigger(remain[0], game_info['player_cards']))]
                else:
                    res['response']['text'] = f'{CANT_COVER} ' \
                        f'{game_info["covering_card"]}.'
            else:
                if len(game_info['on_table']) > 1 and game_info['covering_card'] is None:
                    answer(res, f'{NO_SUCH_CARD}\n{CHOOSE_DOWN}', f'{NO_SUCH_CARD_TTS}\n{CHOOSE_DOWN_TTS}')
                else:
                    answer(res, NO_SUCH_CARD, NO_SUCH_CARD_TTS)


def give_cards(res, req):
    user_id = req['session']['user_id']
    # ход Алисы под игрока
    game_info = sessionStorage[user_id]
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
    res['response']['text'] = f"{res['response'].get('text', '')}{COVER}: " \
                              f"{' '.join(map(str, game_info['on_table']))}\n"
    if len(game_info['on_table']) > 1:
        res['response']['text'] += CHOOSE_DOWN
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

    if not game_info['mode'] == MODE_FLUSH or not find_flush(game_info['table_cash'], game_info['player_cards']):
        game_info['player_gives'] = False
        game_info['table_cash'].clear()


def cover_cards(res, req):
    # Функция будет крыть карты игрока и вызывать give_cards или брать карты
    user_id = req['session']['user_id']
    game_info = sessionStorage[user_id]
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
                    res['response']['text'] = TAKE
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
            res['response']['text'] = TAKE
            game_info['alice_cards'] += [i for item in game_info['on_table'].items() for i in item
                                         if i is not None]
            if take_new_cards(res, req, [game_info['player_cards']]):
                return
            res['response']['buttons'] = [{'title': str(c), 'hide': True} for c in
                                          sort_cards(game_info['player_cards'])]
            game_info['player_gives'] = True
            return
    res['response']['text'] = ' '.join(map(str, game_info['on_table'].values())) + \
                              '\n'
    flush_give = False
    if game_info['mode'] == MODE_FLUSH:
        flush = find_flush(game_info['on_table'], game_info['player_cards'])
        if flush:
            res['response']['text'] += WILL_YOU_ADD
            res['response']['buttons'] = [{'title': str(c), 'hide': True} for c in
                                          sort_cards(flush)]
            res['response']['buttons'].append({'title': 'Бито', 'hide': True})
        else:
            flush_give = True
        game_info['table_cash'] = deepcopy(game_info['on_table'])

    if take_new_cards(res, req, [game_info['player_cards'], game_info['alice_cards']]):
        return

    if game_info['mode'] == MODE_SIMPLE or flush_give:
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
    res['response']['text'] = res['response'].get('text', '').replace(BITO_0, BITO_1)
    if not (game_info['alice_cards'] or game_info['player_cards']):
        res['response']['text'] += '\n' + choice(RESULT_DRAW)[0]
    elif not game_info['alice_cards']:
        res['response']['text'] += '\n' + choice(RESULT_LOSE)[0]
    elif not game_info['player_cards']:
        res['response']['text'] += '\n' + choice(RESULT_WIN)[0]
    res['response']['text'] += '\n' + PLAY_AGAIN
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


def distribution(user_id, res, req):
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
    sessionStorage[user_id]['table_cash'] = {}
    sessionStorage[user_id]['player_gives'] = False
    sessionStorage[user_id]['covering_card'] = None
    alice_trump, sessionStorage[user_id]['player_gives'] = is_humane_first(
        sessionStorage[user_id]['alice_cards'], sessionStorage[user_id]['player_cards'])

    res['response']['text'] = '{}: {}\n{}, {}.\n'.format(TRUMP,
        sessionStorage[user_id]["trump"], alice_trump,
        (YOUR_MOVE if sessionStorage[user_id]["player_gives"] else
         ALISAS_MOVE))
    res['response']['buttons'] = [{'title': str(card), 'hide': True} for card in
                                  sessionStorage[user_id]['player_cards']]

    if not sessionStorage[user_id]['player_gives']:
        give_cards(res, req)
    add_default_buttons(res, user_id)


def find_equals(card, cards_arr):
    # возвращает массив карт с одинаковым достоинством
    return [c for c in cards_arr if c is not None and card is not None and card.equal(c)]


def find_bigger(card, cards_arr):
    # заглушка, так как эта функция использовалась везде, но потом потеряла актуальность)
    return cards_arr
    # return [c for c in cards_arr if c.can_beat(card)]


def can_flush(on_table, card):
    return find_equals(card, on_table.keys()) or find_equals(card, on_table.values())


def find_flush(on_table, cards_arr):
    result = []
    for covered, covering in on_table.items():
        covered_equal = find_equals(covered, cards_arr)
        covering_equal = find_equals(covering, cards_arr)
        [result.append(i) for i in covered_equal + covering_equal]
    return list(set(result))


def sort_cards(cards_arr):
    # сортировка карт
    return sorted(cards_arr, key=lambda x: (x.is_trump(), x.get_value_index()))


def normalize_tts(res):
    res['response']['tts'] = res['response'].get('text', '').replace('\n', '\n ')
    for source, dest in STRINGS_TO_SPEECH:
        res['response']['tts'] = res['response']['tts'].replace(source, dest)

    for comb in combs:
        if comb not in res['response']['tts']:
            continue
        res['response']['tts'] = res['response']['tts'].replace(comb, combs[comb])


def normalize_command(req):
    req['request']['command'] = ''.join(
        req['request']['command'].lower().replace('.', '').strip().split()).replace('ё', 'е')
    for symbol, words in {**SUITS_TO_REPLACE, **value_names}.items():
        for word in words:
            req['request']['command'] = req['request']['command'].replace(word.replace('ё', 'е'),
                                                                          symbol)
    req['request']['command'] = req['request']['command'].upper()


def answer(res, text, tts=None):
    res['response']['text'] = text
    if tts is not None:
        res['response']['tts'] = tts


if __name__ == '__main__':
    app.run()
