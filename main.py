from card import *
from random import shuffle


cards = [Card(v, s) for v in values for s in suits]
shuffle(cards)

p1 = cards[:6]
p2 = cards[6:12]
cards = cards[12:]

trump = cards[-1].get_suit()

print('Козырь', suits[trump])
print('p1', *sorted(p1))
print('p2', *sorted(p2))