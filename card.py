VALUES = ['6', '7', '8', '9', '10', 'В', 'Д', 'К', 'Т']
SUITS = ['♥', '♣', '♦', '♠']


class Card:
    def __init__(self, value, suit):
        self.value = value
        self.suit = suit

    def __gt__(self, other):
        if self.is_trump() and not other.is_trump():
            return True
        elif not self.is_trump() and other.is_trump():
            return False
        return VALUES.index(self.get_value()) > VALUES.index(other.get_value())

    def __lt__(self, other):
        if self.is_trump() and not other.is_trump():
            return False
        elif not self.is_trump() and other.is_trump():
            return True
        return VALUES.index(self.get_value()) < VALUES.index(other.get_value())

    def __eq__(self, other):
        return self.get_value() == other.get_value() and self.get_suit() == other.get_suit()

    def __str__(self):
        return f'{self.value}{self.suit}'

    def __hash__(self):
        return VALUES.index(self.value) * len(SUITS) + SUITS.index(str(self.suit))

    def can_beat(self, other):
        if self.is_trump() and not other.is_trump():
            return True
        elif self.get_suit() == other.get_suit():
            return VALUES.index(self.get_value()) > VALUES.index(other.get_value())
        return False

    def equal(self, other):
        return self.get_value() == other.get_value()

    def get_value(self):
        return self.value

    def get_suit(self):
        return self.suit

    def is_trump(self):
        return self.suit.is_trump()

    def set_trump(self):
        self.suit.set_trump()


class Suit:
    def __init__(self, suit):
        self.suit = suit
        self.trump = False

    def is_trump(self):
        return self.trump

    def set_trump(self):
        self.trump = True

    def __eq__(self, other):
        return self.suit == other.suit

    def __str__(self):
        return self.suit

# while True:
#     v1, s1, v2, s2 = input().split()
#     c1, c2 = Card(v1, s1), Card(v2, s2)
#     print(c1, ('>' if c1 > c2 else ('<' if c1 < c2 else '=')), c2)
