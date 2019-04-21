values = ['6', '7', '8', '9', '10', 'В', 'Д', 'К', 'Т']
suits = {               # масти
    'hearts': '♥',      # черви
    'clubs': '♣',       # трефы / крести
    'diamonds': '♦',    # бубны
    'spades': '♠'       # пики
}
trump = 'clubs'         # козырь Mr. Trump


class Card:
    def __init__(self, value, suit):
        self.value = value
        self.suit = suit

    def __gt__(self, other):
        if self.is_trump() and not other.is_trump():
            return True
        elif not self.is_trump() and other.is_trump():
            return False
        if self.suit == other.suit:
            return values.index(self.value) > values.index(other.value)
        if self.suit != other.suit != trump:
            return values.index(self.value) > values.index(other.value)
        return False

    def __eq__(self, other):
        return self.suit != other.suit != trump and self.value == other.value

    def __ge__(self, other):
        return self.__gt__(other) or self.__eq__(other)

    def __str__(self):
        return f'{self.value}{suits[self.suit]}'

    def get_value(self):
        return self.value

    def get_suit(self):
        return self.suit

    def is_trump(self):
        return self.suit == trump


# while True:
#     v1, s1, v2, s2 = input().split()
#     c1, c2 = Card(v1, s1), Card(v2, s2)
#     print(c1, ('>' if c1 > c2 else ('<' if c1 < c2 else '=')), c2)